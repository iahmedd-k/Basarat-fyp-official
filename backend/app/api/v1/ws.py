"""WebSocket endpoints for live PSX stock feeds, market streams, and personal alerts."""

import json
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field

from app.core.security import decode_token
from app.services.websocket_manager import ws_manager
from app.services.market_service import MarketService

log = logging.getLogger(__name__)

router = APIRouter()


class BroadcastQuoteRequest(BaseModel):
    symbol: str = Field(..., description="PSX Stock Ticker Symbol, e.g. 'SYS', 'LUCK'")
    price: float = Field(..., description="Latest traded price in PKR")
    change: float = Field(default=0.0, description="Price change in PKR")
    change_pct: float = Field(default=0.0, description="Percentage price change")
    volume: int = Field(default=0, description="Day trading volume")
    high: Optional[float] = None
    low: Optional[float] = None


class WSStatsResponse(BaseModel):
    total_connections: int
    subscribed_symbols_count: int
    authenticated_users_count: int
    subscribed_symbols: list[str]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


@router.get(
    "/ws/stats",
    response_model=WSStatsResponse,
    summary="Get real-time WebSocket connection and subscription metrics",
)
async def get_websocket_stats():
    """Returns active WebSocket client connections, unique symbol subscriptions, and active users."""
    stats = ws_manager.get_stats()
    return WSStatsResponse(**stats)


@router.post(
    "/ws/broadcast",
    summary="Publish quote update to subscribed WebSocket clients (Internal/Ingestion)",
)
async def broadcast_quote(data: BroadcastQuoteRequest):
    """Broadcasts a real-time price tick for a symbol to all subscribed frontend clients."""
    payload = data.model_dump()
    delivered = await ws_manager.broadcast_market_quote(data.symbol, payload)
    return {
        "status": "success",
        "symbol": data.symbol.upper(),
        "clients_reached": delivered,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@router.websocket("/ws/market")
async def websocket_market_endpoint(websocket: WebSocket):
    """
    Public / Authenticated Live Market Data WebSocket.

    Supported Client Commands (JSON):
    1. {"action": "subscribe", "symbols": ["SYS", "LUCK", "KSE100"]}
    2. {"action": "unsubscribe", "symbols": ["LUCK"]}
    3. {"action": "get_snapshot", "symbols": ["SYS"]}
    4. {"action": "ping"} -> returns {"event": "pong", "timestamp": "..."}
    """
    await ws_manager.connect(websocket)
    # Send initial welcome handshake
    await ws_manager.send_json_safe(
        websocket,
        {
            "event": "connected",
            "message": "Connected to Basarat Live PSX WebSocket Stream",
            "supported_actions": ["subscribe", "unsubscribe", "get_snapshot", "ping"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
    )

    try:
        while True:
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                await ws_manager.send_json_safe(
                    websocket,
                    {"event": "error", "message": "Invalid JSON message format"},
                )
                continue

            action = str(msg.get("action", "")).lower()

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
                if isinstance(symbols, str):
                    symbols = [symbols]
                subscribed = await ws_manager.subscribe_symbols(websocket, symbols)
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "subscribed",
                        "symbols": subscribed,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            elif action == "unsubscribe":
                symbols = msg.get("symbols", [])
                if isinstance(symbols, str):
                    symbols = [symbols]
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
                snapshots = {}
                try:
                    all_quotes = await MarketService().get_market_data(read_only=True)
                    quote_map = {q.get('symbol', '').upper(): q for q in all_quotes if q.get('symbol')}
                    for s in symbols:
                        sym = s.strip().upper()
                        if sym in quote_map:
                            snapshots[sym] = quote_map[sym]
                except Exception:
                    pass
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "snapshot",
                        "data": snapshots,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    },
                )

            else:
                await ws_manager.send_json_safe(
                    websocket,
                    {
                        "event": "error",
                        "message": f"Unknown action '{action}'. Use subscribe, unsubscribe, get_snapshot, or ping.",
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
    token: Optional[str] = Query(None),
):
    """
    Authenticated User Alerts & Notifications WebSocket.

    Pass JWT token via Query parameter (?token=...) or initial auth message:
    {"action": "authenticate", "token": "..."}
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
            raw_data = await websocket.receive_text()
            try:
                msg = json.loads(raw_data)
            except Exception:
                await ws_manager.send_json_safe(
                    websocket,
                    {"event": "error", "message": "Invalid JSON format"},
                )
                continue

            action = str(msg.get("action", "")).lower()

            if action == "ping":
                await ws_manager.send_json_safe(
                    websocket,
                    {"event": "pong", "timestamp": datetime.now(timezone.utc).isoformat()},
                )

            elif action == "authenticate":
                auth_token = msg.get("token")
                payload = decode_token(auth_token) if auth_token else None
                if payload and payload.get("type") == "access" and payload.get("sub"):
                    new_user_id = payload["sub"]
                    # Re-register with authenticated user ID
                    await ws_manager.disconnect(websocket)
                    await ws_manager.connect(websocket, user_id=new_user_id)
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
                            "message": "Authentication failed: Invalid or expired JWT token.",
                        },
                    )

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)
    except Exception as exc:
        log.warning("WebSocket alert error: %s", exc)
        await ws_manager.disconnect(websocket)
