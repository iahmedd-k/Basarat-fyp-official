"""Comprehensive Test Suite for Real-time WebSockets and Streaming."""

import pytest
from starlette.testclient import TestClient

from app.main import app
from app.services.websocket_manager import ws_manager
from app.core.security import create_access_token


@pytest.fixture(autouse=True)
async def reset_ws_manager():
    """Ensure clean manager state before each test."""
    ws_manager.active_connections.clear()
    ws_manager.symbol_subscriptions.clear()
    ws_manager.user_connections.clear()
    ws_manager.socket_user_map.clear()
    if hasattr(ws_manager, "socket_subscriptions"):
        ws_manager.socket_subscriptions.clear()
    yield


def test_websocket_stats_rest_endpoint():
    """Verify GET /api/v1/ws/stats returns healthy metrics."""
    with TestClient(app) as client:
        res = client.get("/api/v1/ws/stats")
        assert res.status_code == 200
        data = res.json()
        assert "total_connections" in data
        assert "subscribed_symbols_count" in data
        assert "authenticated_users_count" in data
        assert isinstance(data["subscribed_symbols"], list)


def test_websocket_market_handshake_and_ping():
    """Verify connecting to /ws/market sends welcome handshake and responds to ping."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/market") as ws:
            welcome = ws.receive_json()
            assert welcome["event"] == "connected"
            assert "supported_actions" in welcome

            ws.send_json({"action": "ping"})
            pong = ws.receive_json()
            assert pong["event"] == "pong"
            assert "timestamp" in pong


def test_websocket_market_subscribe_and_unsubscribe():
    """Verify subscription to PSX symbols and unsubscription."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/market") as ws:
            _ = ws.receive_json()  # welcome

            ws.send_json({"action": "subscribe", "symbols": ["SYS", "LUCK"]})
            sub_res = ws.receive_json()
            assert sub_res["event"] == "subscribed"
            assert "SYS" in sub_res["symbols"]
            assert "LUCK" in sub_res["symbols"]

            # Optional initial snapshot after subscribe (may be empty if cache cold)
            maybe = ws.receive_json()
            assert maybe["event"] in ("snapshot", "error", "pong", "ping")

            stats_res = client.get("/api/v1/ws/stats")
            assert stats_res.json()["subscribed_symbols_count"] >= 2

            ws.send_json({"action": "unsubscribe", "symbols": ["LUCK"]})
            # Drain until unsubscribed (snapshot may still be in flight)
            for _ in range(5):
                unsub_res = ws.receive_json()
                if unsub_res.get("event") == "unsubscribed":
                    assert "LUCK" in unsub_res["symbols"]
                    break
            else:
                pytest.fail("Did not receive unsubscribed event")


def test_websocket_market_broadcast_delivery():
    """Verify live quote broadcast is delivered to subscribed client."""
    with TestClient(app) as client:
        with client.websocket_connect("/ws/market") as ws:
            _ = ws.receive_json()  # welcome

            ws.send_json({"action": "subscribe", "symbols": ["SYS"], "snapshot": False})
            _ = ws.receive_json()  # sub confirmation

            bcast_res = client.post(
                "/api/v1/ws/broadcast",
                json={
                    "symbol": "SYS",
                    "price": 445.50,
                    "change": 3.25,
                    "change_pct": 0.74,
                    "volume": 2500000,
                },
            )
            assert bcast_res.status_code == 200
            assert bcast_res.json()["clients_reached"] >= 1

            tick = ws.receive_json()
            assert tick["event"] == "quote_update"
            assert tick["symbol"] == "SYS"
            assert tick["data"]["price"] == 445.50


def test_websocket_alerts_authenticated_flow():
    """Verify authenticated user receives personal price trigger alerts."""
    test_user_id = "test-user-12345"
    token = create_access_token({"sub": test_user_id, "type": "access"})

    with TestClient(app) as client:
        with client.websocket_connect(f"/ws/alerts?token={token}") as ws:
            auth_msg = ws.receive_json()
            assert auth_msg["event"] == "authenticated"
            assert auth_msg["user_id"] == test_user_id

            stats_res = client.get("/api/v1/ws/stats")
            assert stats_res.json()["authenticated_users_count"] >= 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
