"""API tests for stock watchlist endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.stock import Stock
from app.models.watchlist import Watchlist, WatchlistItem


@pytest.mark.api
class TestWatchlistEndpoints:
    async def test_get_watchlists_empty(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/watchlists", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 0

    async def test_create_watchlist_basic(self, client: AsyncClient, auth_headers: dict):
        payload = {
            "name": "Tech Focus",
            "description": "Top technology sector stocks",
            "is_default": False,
        }
        resp = await client.post("/api/v1/watchlists", headers=auth_headers, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Tech Focus"
        assert data["description"] == "Top technology sector stocks"
        # Since it's the first watchlist, it auto-defaults to True
        assert data["is_default"] is True
        assert data["item_count"] == 0

    async def test_create_watchlist_with_symbols(self, client: AsyncClient, auth_headers: dict):
        payload = {
            "name": "Dividend Gems",
            "description": "High dividend yield stocks",
            "is_default": True,
            "symbols": ["OGDC", "PPL", "ENGRO"],
        }
        resp = await client.post("/api/v1/watchlists", headers=auth_headers, json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Dividend Gems"
        assert data["item_count"] == 3

    async def test_get_default_watchlist_auto_create(self, client: AsyncClient, auth_headers: dict):
        resp = await client.get("/api/v1/watchlists/default", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["is_default"] is True
        assert "items" in data
        assert isinstance(data["items"], list)

    async def test_add_and_enrich_watchlist_item(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        # Seed a Stock for company name lookup
        stock = Stock(symbol="SYS", name="Systems Limited", sector="Technology")
        db_session.add(stock)
        await db_session.flush()

        # Create watchlist
        create_resp = await client.post(
            "/api/v1/watchlists",
            headers=auth_headers,
            json={"name": "Growth Stocks"},
        )
        assert create_resp.status_code == 201
        wl_id = create_resp.json()["id"]

        # Add item
        item_resp = await client.post(
            f"/api/v1/watchlists/{wl_id}/items",
            headers=auth_headers,
            json={"symbol": "SYS", "target_price": 450.0, "notes": "Buy on pullback"},
        )
        assert item_resp.status_code == 201
        item_data = item_resp.json()
        assert item_data["symbol"] == "SYS"
        assert item_data["name"] == "Systems Limited"
        assert item_data["sector"] == "Technology"
        assert item_data["target_price"] == 450.0
        assert item_data["notes"] == "Buy on pullback"

        # Check detail endpoint
        detail_resp = await client.get(f"/api/v1/watchlists/{wl_id}", headers=auth_headers)
        assert detail_resp.status_code == 200
        detail_data = detail_resp.json()
        assert len(detail_data["items"]) == 1
        assert detail_data["items"][0]["symbol"] == "SYS"

    async def test_add_duplicate_symbol_fails(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/watchlists",
            headers=auth_headers,
            json={"name": "Dupe Test"},
        )
        wl_id = create_resp.json()["id"]

        # First add
        resp1 = await client.post(
            f"/api/v1/watchlists/{wl_id}/items",
            headers=auth_headers,
            json={"symbol": "HUBC"},
        )
        assert resp1.status_code == 201

        # Second add of same symbol should return conflict 409
        resp2 = await client.post(
            f"/api/v1/watchlists/{wl_id}/items",
            headers=auth_headers,
            json={"symbol": "HUBC"},
        )
        assert resp2.status_code == 409

    async def test_update_watchlist_item(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/watchlists",
            headers=auth_headers,
            json={"name": "Update Item Test"},
        )
        wl_id = create_resp.json()["id"]

        add_resp = await client.post(
            f"/api/v1/watchlists/{wl_id}/items",
            headers=auth_headers,
            json={"symbol": "LUCK", "target_price": 800.0, "notes": "Initial note"},
        )
        assert add_resp.status_code == 201

        # Update via symbol
        patch_resp = await client.patch(
            f"/api/v1/watchlists/{wl_id}/items/LUCK",
            headers=auth_headers,
            json={"target_price": 850.5, "notes": "Updated target"},
        )
        assert patch_resp.status_code == 200
        patch_data = patch_resp.json()
        assert patch_data["target_price"] == 850.5
        assert patch_data["notes"] == "Updated target"

    async def test_delete_watchlist_item(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/watchlists",
            headers=auth_headers,
            json={"name": "Delete Item Test"},
        )
        wl_id = create_resp.json()["id"]

        await client.post(
            f"/api/v1/watchlists/{wl_id}/items",
            headers=auth_headers,
            json={"symbol": "MEBL"},
        )

        del_resp = await client.delete(
            f"/api/v1/watchlists/{wl_id}/items/MEBL",
            headers=auth_headers,
        )
        assert del_resp.status_code == 204

        # Verify it's gone
        detail_resp = await client.get(f"/api/v1/watchlists/{wl_id}", headers=auth_headers)
        assert len(detail_resp.json()["items"]) == 0

    async def test_check_symbol_in_watchlists(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/watchlists",
            headers=auth_headers,
            json={"name": "Check Test", "symbols": ["MCB", "UBL"]},
        )
        wl_id = create_resp.json()["id"]

        # Present symbol
        check_resp = await client.get("/api/v1/watchlists/check/MCB", headers=auth_headers)
        assert check_resp.status_code == 200
        check_data = check_resp.json()
        assert check_data["symbol"] == "MCB"
        assert check_data["is_in_watchlist"] is True
        assert wl_id in check_data["watchlist_ids"]

        # Absent symbol
        check_resp_absent = await client.get("/api/v1/watchlists/check/KAPCO", headers=auth_headers)
        assert check_resp_absent.status_code == 200
        assert check_resp_absent.json()["is_in_watchlist"] is False
        assert len(check_resp_absent.json()["watchlist_ids"]) == 0

    async def test_update_watchlist_metadata(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/watchlists",
            headers=auth_headers,
            json={"name": "Old Name", "description": "Old Desc"},
        )
        wl_id = create_resp.json()["id"]

        patch_resp = await client.patch(
            f"/api/v1/watchlists/{wl_id}",
            headers=auth_headers,
            json={"name": "New Name", "description": "New Desc"},
        )
        assert patch_resp.status_code == 200
        data = patch_resp.json()
        assert data["name"] == "New Name"
        assert data["description"] == "New Desc"

    async def test_delete_watchlist(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/watchlists",
            headers=auth_headers,
            json={"name": "To Delete"},
        )
        wl_id = create_resp.json()["id"]

        del_resp = await client.delete(f"/api/v1/watchlists/{wl_id}", headers=auth_headers)
        assert del_resp.status_code == 204

        # 404 on subsequent get
        get_resp = await client.get(f"/api/v1/watchlists/{wl_id}", headers=auth_headers)
        assert get_resp.status_code == 404

    async def test_watchlist_isolated_per_user(
        self, client: AsyncClient, auth_headers: dict, db_session: AsyncSession
    ):
        # Create a watchlist owned by a different user
        other_user = User(
            email="otheruser@example.com",
            username="otheruser",
            hashed_password="hashed_pw_xyz",
        )
        db_session.add(other_user)
        await db_session.flush()

        other_wl = Watchlist(
            user_id=other_user.id,
            name="Private Watchlist",
        )
        db_session.add(other_wl)
        await db_session.flush()

        # Logged-in user should not be able to view or modify other_wl
        resp = await client.get(f"/api/v1/watchlists/{other_wl.id}", headers=auth_headers)
        assert resp.status_code == 404

        del_resp = await client.delete(f"/api/v1/watchlists/{other_wl.id}", headers=auth_headers)
        assert del_resp.status_code == 404

    async def test_watchlists_require_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/watchlists")
        assert resp.status_code in (401, 403)

        post_resp = await client.post("/api/v1/watchlists", json={"name": "Unauthorized"})
        assert post_resp.status_code in (401, 403)

    async def test_invalid_symbol_rejected(self, client: AsyncClient, auth_headers: dict):
        create_resp = await client.post(
            "/api/v1/watchlists",
            headers=auth_headers,
            json={"name": "Validation Test"},
        )
        wl_id = create_resp.json()["id"]

        # Invalid symbol with special chars
        bad_resp = await client.post(
            f"/api/v1/watchlists/{wl_id}/items",
            headers=auth_headers,
            json={"symbol": "123$$$BAD"},
        )
        assert bad_resp.status_code == 422

    async def test_toggle_watchlist_item(self, client: AsyncClient, auth_headers: dict):
        # 1. Toggle ON (symbol added to default watchlist)
        toggle_on = await client.post("/api/v1/watchlists/toggle/OGDC", headers=auth_headers)
        assert toggle_on.status_code == 200
        data_on = toggle_on.json()
        assert data_on["symbol"] == "OGDC"
        assert data_on["is_in_watchlist"] is True
        assert data_on["action"] == "added"
        assert "watchlist_id" in data_on

        # 2. Toggle OFF (symbol removed from default watchlist)
        toggle_off = await client.post("/api/v1/watchlists/toggle/OGDC", headers=auth_headers)
        assert toggle_off.status_code == 200
        data_off = toggle_off.json()
        assert data_off["symbol"] == "OGDC"
        assert data_off["is_in_watchlist"] is False
        assert data_off["action"] == "removed"

