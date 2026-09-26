"""WebSocket Connection and Broadcast Manager for Real-time PSX Market & Alerts."""

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Set
from fastapi import WebSocket, WebSocketDisconnect

log = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages WebSocket connections, symbol subscriptions, and real-time event broadcasting."""

    def __init__(self):
        # All active client connections
        self.active_connections: Set[WebSocket] = set()
        # Symbol -> set of WebSockets subscribed
        self.symbol_subscriptions: Dict[str, Set[WebSocket]] = {}
        # User ID -> set of WebSockets for personal alerts/portfolio
        self.user_connections: Dict[str, Set[WebSocket]] = {}
        # WebSocket -> user_id (if authenticated)
        self.socket_user_map: Dict[WebSocket, str] = {}
        # Lock for thread-safe state mutations
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket, user_id: str | None = None) -> None:
        """Accept connection and register in pools."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
            if user_id:
                self.socket_user_map[websocket] = user_id
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(websocket)
        log.info("WebSocket client connected. Total active: %d", len(self.active_connections))

    async def disconnect(self, websocket: WebSocket) -> None:
        """Unregister connection and clean up all subscriptions."""
        async with self._lock:
            self.active_connections.discard(websocket)
            # Remove from symbol subscriptions
            for sym, subscribers in list(self.symbol_subscriptions.items()):
                subscribers.discard(websocket)
                if not subscribers:
                    self.symbol_subscriptions.pop(sym, None)
            # Remove from user connections
            user_id = self.socket_user_map.pop(websocket, None)
            if user_id and user_id in self.user_connections:
                self.user_connections[user_id].discard(websocket)
                if not self.user_connections[user_id]:
                    self.user_connections.pop(user_id, None)
        log.info("WebSocket client disconnected. Total active: %d", len(self.active_connections))

    async def subscribe_symbols(self, websocket: WebSocket, symbols: list[str]) -> list[str]:
        """Subscribe a websocket to quote updates for a list of PSX symbols."""
        subscribed = []
        async with self._lock:
            for s in symbols:
                sym = s.strip().upper()
                if not sym:
                    continue
                if sym not in self.symbol_subscriptions:
                    self.symbol_subscriptions[sym] = set()
                self.symbol_subscriptions[sym].add(websocket)
                subscribed.append(sym)
        return subscribed

    async def unsubscribe_symbols(self, websocket: WebSocket, symbols: list[str]) -> list[str]:
        """Unsubscribe a websocket from quote updates for a list of PSX symbols."""
        unsubscribed = []
        async with self._lock:
            for s in symbols:
                sym = s.strip().upper()
                if sym in self.symbol_subscriptions:
                    self.symbol_subscriptions[sym].discard(websocket)
                    if not self.symbol_subscriptions[sym]:
                        self.symbol_subscriptions.pop(sym, None)
                    unsubscribed.append(sym)
        return unsubscribed

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
            if "*" in self.symbol_subscriptions or "ALL" in self.symbol_subscriptions:
                recipients.update(self.symbol_subscriptions.get("*", set()))
                recipients.update(self.symbol_subscriptions.get("ALL", set()))

        if not recipients:
            return 0

        sent_count = 0
        dead_sockets = []
        for ws in recipients:
            success = await self.send_json_safe(ws, payload)
            if success:
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

        if not recipients:
            return 0

        sent_count = 0
        dead_sockets = []
        for ws in recipients:
            success = await self.send_json_safe(ws, payload)
            if success:
                sent_count += 1
            else:
                dead_sockets.append(ws)

        for ws in dead_sockets:
            await self.disconnect(ws)
        return sent_count

    async def broadcast_all(self, payload: dict) -> int:
        """Broadcast a message to every connected client."""
        async with self._lock:
            recipients = list(self.active_connections)

        sent_count = 0
        dead_sockets = []
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
        }


# Global singleton instance
ws_manager = WebSocketConnectionManager()
