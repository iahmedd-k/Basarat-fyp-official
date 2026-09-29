"""WebSocket Connection and Broadcast Manager for Real-time PSX Market & Alerts."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional, Set

from fastapi import WebSocket

log = logging.getLogger(__name__)

PROTOCOL_VERSION = "1.0"
MAX_SUBSCRIBE_SYMBOLS = 200


class WebSocketConnectionManager:
    """Manages WebSocket connections, symbol subscriptions, and real-time event broadcasting."""

    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self.symbol_subscriptions: Dict[str, Set[WebSocket]] = {}
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        self.socket_user_map: Dict[WebSocket, str] = {}
        self.socket_subscriptions: Dict[WebSocket, Set[str]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str | None = None) -> None:
        """Accept connection and register in pools."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
            self.socket_subscriptions.setdefault(websocket, set())
            if user_id:
                self.socket_user_map[websocket] = user_id
                self.user_connections.setdefault(user_id, set()).add(websocket)
        log.info("WebSocket client connected. Total active: %d", len(self.active_connections))

    async def bind_user(self, websocket: WebSocket, user_id: str) -> None:
        """Attach/replace authenticated user without re-accepting the socket."""
        async with self._lock:
            old_user = self.socket_user_map.get(websocket)
            if old_user and old_user in self.user_connections:
                self.user_connections[old_user].discard(websocket)
                if not self.user_connections[old_user]:
                    self.user_connections.pop(old_user, None)
            self.socket_user_map[websocket] = user_id
            self.user_connections.setdefault(user_id, set()).add(websocket)
            self.active_connections.add(websocket)
            self.socket_subscriptions.setdefault(websocket, set())

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister connection and clean up all subscriptions."""
        async with self._lock:
            self.active_connections.discard(websocket)
            for sym, subscribers in list(self.symbol_subscriptions.items()):
                subscribers.discard(websocket)
                if not subscribers:
                    self.symbol_subscriptions.pop(sym, None)
            self.socket_subscriptions.pop(websocket, None)
            user_id = self.socket_user_map.pop(websocket, None)
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    self.user_connections.pop(user_id, None)
        log.info("WebSocket client disconnected. Total active: %d", len(self.active_connections))

    @staticmethod
    def _normalize_symbols(symbols: list[str] | str | None) -> list[str]:
        if symbols is None:
            return []
        if isinstance(symbols, str):
            symbols = [symbols]
        out: list[str] = []
        seen: set[str] = set()
        for raw in symbols:
            sym = str(raw or "").strip().upper()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            out.append(sym)
            if len(out) >= MAX_SUBSCRIBE_SYMBOLS:
                break
        return out

    async def subscribe_symbols(self, websocket: WebSocket, symbols: list[str] | str) -> list[str]:
        """Subscribe a websocket to quote updates for a list of PSX symbols."""
        normalized = self._normalize_symbols(symbols)
        subscribed = []
        async with self._lock:
            self.socket_subscriptions.setdefault(websocket, set())
            for sym in normalized:
                self.symbol_subscriptions.setdefault(sym, set()).add(websocket)
                self.socket_subscriptions[websocket].add(sym)
                subscribed.append(sym)
        return subscribed

    async def unsubscribe_symbols(self, websocket: WebSocket, symbols: list[str] | str) -> list[str]:
        """Unsubscribe a websocket from quote updates for a list of PSX symbols."""
        normalized = self._normalize_symbols(symbols)
        unsubscribed = []
        async with self._lock:
            for sym in normalized:
                if sym in self.symbol_subscriptions:
                    self.symbol_subscriptions[sym].discard(websocket)
                    if not self.symbol_subscriptions[sym]:
                        self.symbol_subscriptions.pop(sym, None)
                if websocket in self.socket_subscriptions:
                    self.socket_subscriptions[websocket].discard(sym)
                unsubscribed.append(sym)
        return unsubscribed

    async def get_subscriptions(self, websocket: WebSocket) -> list[str]:
        async with self._lock:
            return sorted(self.socket_subscriptions.get(websocket, set()))

    async def send_json_safe(self, websocket: WebSocket, payload: dict) -> bool:
        """Send JSON to a websocket safely without crashing on broken pipe."""
        try:
            await websocket.send_text(json.dumps(payload, default=str))
            return True
        except Exception:
            return False

    async def broadcast_market_quote(self, symbol: str, quote_data: dict) -> int:
        """Broadcast live price tick to all subscribers of this symbol and market-wide subscribers."""
        sym = symbol.strip().upper()
        payload = {
            "event": "quote_update",
            "symbol": sym,
            "data": quote_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        recipients: Set[WebSocket] = set()
        async with self._lock:
            if sym in self.symbol_subscriptions:
                recipients.update(self.symbol_subscriptions[sym])
            recipients.update(self.symbol_subscriptions.get("*", set()))
            recipients.update(self.symbol_subscriptions.get("ALL", set()))

        return await self._send_to_recipients(recipients, payload)

    async def broadcast_board_update(
        self,
        quotes: list[dict],
        *,
        as_of: str | None = None,
        is_stale: bool = False,
        source: str = "session_refresh",
    ) -> int:
        """Fan out a scraped board snapshot to each client, filtered by their subscriptions."""
        quote_map: Dict[str, dict] = {}
        for row in quotes:
            if not isinstance(row, dict):
                continue
            sym = str(row.get("symbol") or "").strip().upper()
            if sym:
                quote_map[sym] = row

        if not quote_map:
            return 0

        async with self._lock:
            targets = list(self.active_connections)

        sent_count = 0
        dead_sockets: list[WebSocket] = []
        ts = datetime.now(timezone.utc).isoformat()

        for ws in targets:
            async with self._lock:
                subscribed = set(self.socket_subscriptions.get(ws, set()))

            if not subscribed:
                continue

            if "*" in subscribed or "ALL" in subscribed:
                data = quote_map
            else:
                data = {sym: quote_map[sym] for sym in subscribed if sym in quote_map}

            if not data:
                continue

            payload = {
                "event": "board_update",
                "as_of": as_of,
                "is_stale": is_stale,
                "source": source,
                "count": len(data),
                "data": data,
                "timestamp": ts,
                "protocol_version": PROTOCOL_VERSION,
            }
            ok = await self.send_json_safe(ws, payload)
            if ok:
                sent_count += 1
            else:
                dead_sockets.append(ws)

        for ws in dead_sockets:
            await self.disconnect(ws)
        return sent_count

    async def send_user_alert(self, user_id: str, alert_data: dict) -> int:
        """Send a real-time price trigger or portfolio alert to a specific authenticated user."""
        payload = {
            "event": "alert_triggered",
            "user_id": user_id,
            "alert": alert_data,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        recipients: Set[WebSocket] = set()
        async with self._lock:
            if user_id in self.user_connections:
                recipients.update(self.user_connections[user_id])

        return await self._send_to_recipients(recipients, payload)

    async def broadcast_all(self, payload: dict) -> int:
        """Broadcast a message to every connected client."""
        async with self._lock:
            recipients = list(self.active_connections)
        return await self._send_to_recipients(set(recipients), payload)

    async def _send_to_recipients(self, recipients: Set[WebSocket], payload: dict) -> int:
        if not recipients:
            return 0
        sent_count = 0
        dead_sockets: list[WebSocket] = []
        for ws in recipients:
            success = await self.send_json_safe(ws, payload)
            if success:
                sent_count += 1
            else:
                dead_sockets.append(ws)
        for ws in dead_sockets:
            await self.disconnect(ws)
        return sent_count

    def get_stats(self) -> dict:
        """Return operational metrics for WebSocket health monitor."""
        return {
            "total_connections": len(self.active_connections),
            "subscribed_symbols_count": len(self.symbol_subscriptions),
            "authenticated_users_count": len(self.user_connections),
            "subscribed_symbols": list(self.symbol_subscriptions.keys())[:20],
            "protocol_version": PROTOCOL_VERSION,
        }


ws_manager = WebSocketConnectionManager()
