"""WebSocket endpoints for live PSX stock feeds, market streams, and personal alerts.

Primary transport for Android/web during market hours. If WebSocket fails, clients
MUST fall back to REST GET /api/v1/market/quotes (cache-only; safe to poll).

Discovery contract for mobile: GET /api/v1/market/live (documented in Swagger).
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Query, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.core.security import decode_token
from app.services.market_service import MarketService
from app.services.websocket_manager import PROTOCOL_VERSION, ws_manager

log = logging.getLogger(__name__)

router = APIRouter()

WS_IDLE_TIMEOUT_SECONDS = 120
MAX_MESSAGE_BYTES = 16_384


class BroadcastQuoteRequest(BaseModel):
    symbol: str = Field(..., description="PSX ticker, e.g. SYS")
    price: float = Field(..., description="Latest traded price in PKR")
    change: float = Field(default=0.0)
    change_pct: float = Field(default=0.0)
    volume: int = Field(default=0)
    high: Optional[float] = None
    low: Optional[float] = None


class WSStatsResponse(BaseModel):
    total_connections: int
    subscribed_symbols_count: int
    authenticated_users_count: int
    subscribed_symbols: list[str]
    protocol_version: str = PROTOCOL_VERSION
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WSProtocolDocsResponse(BaseModel):
    """Swagger-visible contract so Android can wire WS + REST fallback without guesswork."""

    protocol_version: str
    primary_transport: str = "websocket"
    fallback_transport: str = "rest_polling"
    websocket_path: str
    websocket_url_template: str = Field(
        description="Replace {host} with API host. Use wss:// in production."
    )
    alerts_websocket_path: str
    rest_fallback_path: str
    rest_discovery_path: str = "/api/v1/market/live"
    recommended_rest_poll_seconds: int
    session_refresh_seconds: int
    client_actions: list[str]
    server_events: list[str]
    subscribe_example: dict
    snapshot_example: dict
    notes: list[str]


def _ws_base_paths(request: Request | None = None) -> dict:
    settings = get_settings()
    prefix = settings.API_V1_PREFIX.rstrip("/")
    host = ""
    scheme = "wss"
    if request is not None:
        host = request.headers.get("host") or request.url.netloc
        scheme = "wss" if request.url.scheme == "https" else "ws"
    return {
        "prefix": prefix,
        "market_path": f"{prefix}/ws/market",
        "alerts_path": f"{prefix}/ws/alerts",
        "host": host,
        "scheme": scheme,
    }


@router.get(
    "/ws/protocol",
    response_model=WSProtocolDocsResponse,
    summary="WebSocket + REST fallback protocol (Android / Swagger)",
    response_description="Authoritative client integration contract for live market data",
)
async def get_websocket_protocol(request: Request):
    """
    Use this endpoint from Swagger to wire the Android live feed.

    **Flow**
    1. Prefer WebSocket `GET` upgrade to `/api/v1/ws/market`
    2. On failure/disconnect → poll `GET /api/v1/market/quotes` every `recommended_rest_poll_seconds`
    3. Reconnect WebSocket with exponential backoff in the background
    """
    settings = get_settings()
    paths = _ws_base_paths(request)
    return WSProtocolDocsResponse(
        protocol_version=PROTOCOL_VERSION,
        websocket_path=paths["market_path"],
        websocket_url_template=f"{{scheme}}://{{host}}{paths['market_path']}",
        alerts_websocket_path=paths["alerts_path"],
        rest_fallback_path=f"{paths['prefix']}/market/quotes",
        recommended_rest_poll_seconds=settings.MARKET_REST_POLL_SECONDS,
        session_refresh_seconds=settings.MARKET_SESSION_REFRESH_SECONDS,
        client_actions=[
            "subscribe",
            "unsubscribe",
            "get_snapshot",
            "get_subscriptions",
            "ping",
        ],
        server_events=[
            "connected",
            "subscribed",
            "unsubscribed",
            "snapshot",
            "board_update",
            "quote_update",
            "pong",
            "error",
            "authenticated",
            "unauthenticated",
            "alert_triggered",
        ],
        subscribe_example={"action": "subscribe", "symbols": ["SYS", "LUCK", "OGDC"]},
        snapshot_example={"action": "get_snapshot", "symbols": ["SYS", "LUCK"]},
        notes=[
            "Subscribe to ALL or * to receive the full board on each session refresh.",
            "board_update payloads are filtered to your subscriptions (scalable).",
            "REST /market/quotes is cache-only and safe to poll; it never scrapes PSX.",
            "Celery refreshes the shared Redis snapshot during PSX open hours.",
            "Pass JWT as ?token= for /ws/alerts, or send action=authenticate.",
        ],
    )


@router.get(
    "/ws/stats",
    response_model=WSStatsResponse,
    summary="Get real-time WebSocket connection and subscription metrics",
)
async def get_websocket_stats():
    stats = ws_manager.get_stats()
    return WSStatsResponse(**stats)


@router.post(
    "/ws/broadcast",
    summary="Publish a single quote tick to WS subscribers (debug/internal)",
    include_in_schema=True,
)
async def broadcast_quote(data: BroadcastQuoteRequest):
    """
    Manual/debug tick publisher. Production session updates use Redis pub/sub from Celery
    (`board_update`), not this endpoint.
    """
    payload = data.model_dump()
    delivered = await ws_manager.broadcast_market_quote(data.symbol, payload)
    return {
        "status": "success",
        "symbol": data.symbol.upper(),
        "clients_reached": delivered,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _build_connected_payload(request_headers_host: str | None = None) -> dict:
    settings = get_settings()
    freshness = MarketService.quote_freshness()
    market_state = {"status": "unknown"}
    try:
        from app.services.news_pipeline.market_schedule import market_status

        market_state = await market_status()
    except Exception as exc:
        log.debug("market_status unavailable for WS handshake: %s", exc)

    prefix = settings.API_V1_PREFIX.rstrip("/")
    return {
        "event": "connected",
        "message": "Connected to Basarat Live PSX WebSocket Stream",
        "protocol_version": PROTOCOL_VERSION,
        "supported_actions": [
            "subscribe",
            "unsubscribe",
            "get_snapshot",
            "get_subscriptions",
            "ping",
        ],
        "server_events": [
            "board_update",
            "quote_update",
            "snapshot",
            "pong",
            "error",
        ],
        "rest_fallback": {
            "path": f"{prefix}/market/quotes",
            "poll_seconds": settings.MARKET_REST_POLL_SECONDS,
            "discovery_path": f"{prefix}/market/live",
        },
        "session_refresh_seconds": settings.MARKET_SESSION_REFRESH_SECONDS,
        "market_status": market_state.get("status"),
        "as_of": freshness.get("as_of"),
        "is_stale": freshness.get("is_stale", True),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


async def _quotes_for_symbols(symbols: list[str]) -> dict:
    snapshots: dict = {}
    try:
        all_quotes = await MarketService().get_market_data(read_only=True)
        quote_map = {
            str(q.get("symbol", "")).upper(): q
            for q in all_quotes
            if q.get("symbol")
        }
        want_all = any(s in {"*", "ALL"} for s in symbols)
        if want_all or not symbols:
            return quote_map if want_all else {}
        for sym in symbols:
            if sym in quote_map:
                snapshots[sym] = quote_map[sym]
    except Exception as exc:
        log.warning("WS snapshot fetch failed: %s", exc)
    return snapshots


@router.websocket("/ws/market")
async def websocket_market_endpoint(websocket: WebSocket):
    """
    Live market WebSocket (primary transport).

    Client → Server actions (JSON text frames):
    - `{"action":"subscribe","symbols":["SYS","LUCK"]}` — also accepts `"ALL"` / `"*"`
    - `{"action":"unsubscribe","symbols":["LUCK"]}`
    - `{"action":"get_snapshot","symbols":["SYS"]}`
    - `{"action":"get_subscriptions"}`
    - `{"action":"ping"}`

    Server → Client events:
    - `connected`, `subscribed`, `unsubscribed`, `snapshot`, `board_update`,
      `quote_update`, `pong`, `error`

    If this socket fails, poll REST `/api/v1/market/quotes` (see `/api/v1/ws/protocol`).
    """
    await ws_manager.connect(websocket)
    await ws_manager.send_json_safe(websocket, await _build_connected_payload())

    try:
        while True:
            try:
                raw_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=WS_IDLE_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                # Soft keepalive: ask client to ping; do not disconnect immediately.
                ok = await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "ping",
                        "message": "idle_keepalive",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                if not ok:
                    break
                continue

            if raw_data is None:
                continue
            if len(raw_data.encode("utf-8", errors="ignore")) > MAX_MESSAGE_BYTES:
                await ws_manager.send_json_safe(
                    websocket,
                    {"event": "error", "code": "message_too_large", "message": "Max message size is 16KB"},
                )
                continue

            try:
                msg = json.loads(raw_data)
            except Exception:
                await ws_manager.send_json_safe(
                    websocket,
                    {"event": "error", "code": "invalid_json", "message": "Invalid JSON message format"},
                )
                continue

            if not isinstance(msg, dict):
                await ws_manager.send_json_safe(
                    websocket,
                    {"event": "error", "code": "invalid_payload", "message": "JSON object required"},
                )
                continue

            action = str(msg.get("action", "")).lower().strip()

            if action == "ping":
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            elif action == "subscribe":
                symbols = msg.get("symbols", [])
                subscribed = await ws_manager.subscribe_symbols(websocket, symbols)
                send_snapshot = bool(msg.get("snapshot", True))
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "subscribed",
                        "symbols": subscribed,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                if send_snapshot and subscribed:
                    data = await _quotes_for_symbols(subscribed)
                    freshness = MarketService.quote_freshness()
                    await ws_manager.send_json_safe(
                        websocket,
                        {
                            "event": "snapshot",
                            "data": data,
                            "count": len(data),
                            "as_of": freshness.get("as_of"),
                            "is_stale": freshness.get("is_stale", True),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )

            elif action == "unsubscribe":
                symbols = msg.get("symbols", [])
                unsubscribed = await ws_manager.unsubscribe_symbols(websocket, symbols)
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "unsubscribed",
                        "symbols": unsubscribed,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            elif action == "get_snapshot":
                symbols = msg.get("symbols", [])
                if isinstance(symbols, str):
                    symbols = [symbols]
                normalized = [
                    str(s).strip().upper() for s in (symbols or []) if str(s).strip()
                ]
                if not normalized:
                    normalized = await ws_manager.get_subscriptions(websocket)
                data = await _quotes_for_symbols(normalized)
                freshness = MarketService.quote_freshness()
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "snapshot",
                        "data": data,
                        "count": len(data),
                        "as_of": freshness.get("as_of"),
                        "is_stale": freshness.get("is_stale", True),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            elif action == "get_subscriptions":
                current = await ws_manager.get_subscriptions(websocket)
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "subscriptions",
                        "symbols": current,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            elif not action:
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "error",
                        "code": "missing_action",
                        "message": "Field 'action' is required",
                    },
                )
            else:
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "error",
                        "code": "unknown_action",
                        "message": (
                            f"Unknown action '{action}'. "
                            "Use subscribe, unsubscribe, get_snapshot, get_subscriptions, or ping."
                        ),
                    },
                )

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        log.warning("WebSocket market error: %s", exc)
        await ws_manager.disconnect(websocket)


@router.websocket("/ws/alerts")
async def websocket_alerts_endpoint(
    websocket: WebSocket,
    token: Optional[str] = Query(None, description="JWT access token"),
):
    """
    Authenticated alerts WebSocket.

    Auth: `?token=<JWT>` on connect, or later
    `{"action":"authenticate","token":"<JWT>"}`.
    """
    user_id = None
    if token:
        payload = decode_token(token)
        if payload and payload.get("type") == "access":
            user_id = payload.get("sub")

    await ws_manager.connect(websocket, user_id=user_id)

    if user_id:
        await ws_manager.send_json_safe(
            websocket,
            {
                "event": "authenticated",
                "user_id": user_id,
                "message": "Real-time alert notifications active.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )
    else:
        await ws_manager.send_json_safe(
            websocket,
            {
                "event": "unauthenticated",
                "message": "Send {'action': 'authenticate', 'token': '...'} to receive personalized alerts.",
                "timestamp": datetime.now(timezone.utc).isoformat(),
            },
        )

    try:
        while True:
            try:
                raw_data = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=WS_IDLE_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                ok = await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "ping",
                        "message": "idle_keepalive",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )
                if not ok:
                    break
                continue

            try:
                msg = json.loads(raw_data)
            except Exception:
                await ws_manager.send_json_safe(
                    websocket,
                    {"event": "error", "code": "invalid_json", "message": "Invalid JSON format"},
                )
                continue

            if not isinstance(msg, dict):
                continue

            action = str(msg.get("action", "")).lower().strip()

            if action == "ping":
                await ws_manager.send_json_safe(
                    websocket,
                    {"event": "pong", "timestamp": datetime.now(timezone.utc).isoformat()},
                )

            elif action == "authenticate":
                auth_token = msg.get("token")
                payload = decode_token(auth_token) if auth_token else None
                if payload and payload.get("type") == "access" and payload.get("sub"):
                    new_user_id = str(payload["sub"])
                    await ws_manager.bind_user(websocket, new_user_id)
                    await ws_manager.send_json_safe(
                        websocket,
                        {
                            "event": "authenticated",
                            "user_id": new_user_id,
                            "message": "Successfully authenticated for alert triggers.",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                else:
                    await ws_manager.send_json_safe(
                        websocket,
                        {
                            "event": "error",
                            "code": "auth_failed",
                            "message": "Authentication failed: Invalid or expired JWT token.",
                        },
                    )
            else:
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "error",
                        "code": "unknown_action",
                        "message": "Supported actions: ping, authenticate",
                    },
                )

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        log.warning("WebSocket alert error: %s", exc)
        await ws_manager.disconnect(websocket)
