"""API tests for portfolio endpoints (new transaction-based API)."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Transaction, TransactionType
from app.models.user import User


@pytest.mark.api
class TestTransactionCreate:
    async def test_create_buy_transaction(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "OGDC",
                "type": "BUY",
                "quantity": 100,
                "price": 98.50,
                "fees": 25.00,
                "transaction_date": "2026-09-15",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "OGDC"
        assert data["type"] == "BUY"
        assert data["quantity"] == 100
        assert data["price"] == 98.50
        assert data["fees"] == 25.00
        assert "id" in data
        assert "created_at" in data

    async def test_create_sell_transaction_valid(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        # First create a BUY transaction
        await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "HBL",
                "type": "BUY",
                "quantity": 100,
                "price": 150.0,
                "fees": 10.0,
                "transaction_date": "2026-09-01",
            },
        )
        # Now sell some
        resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "HBL",
                "type": "SELL",
                "quantity": 50,
                "price": 155.0,
                "fees": 10.0,
                "transaction_date": "2026-09-15",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["type"] == "SELL"
        assert data["quantity"] == 50

    async def test_create_sell_insufficient_quantity(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "LUCK",
                "type": "SELL",
                "quantity": 100,
                "price": 500.0,
                "fees": 0.0,
                "transaction_date": "2026-09-15",
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "INSUFFICIENT_QUANTITY"

    async def test_create_transaction_invalid_symbol(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "INVALIDXYZ",
                "type": "BUY",
                "quantity": 100,
                "price": 100.0,
                "fees": 0.0,
                "transaction_date": "2026-09-15",
            },
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "INVALID_SYMBOL"

    async def test_create_transaction_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/portfolio/transactions",
            json={
                "symbol": "OGDC",
                "type": "BUY",
                "quantity": 100,
                "price": 98.50,
                "fees": 25.00,
                "transaction_date": "2026-09-15",
            },
        )
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestTransactionList:
    async def test_list_transactions(self, client: AsyncClient, auth_headers, test_user: User):
        await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "OGDC",
                "type": "BUY",
                "quantity": 100,
                "price": 98.50,
                "fees": 25.00,
                "transaction_date": "2026-09-15",
            },
        )
        resp = await client.get("/api/v1/portfolio/transactions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "data" in data
        assert "pagination" in data
        assert len(data["data"]) >= 1
        assert data["pagination"]["page"] == 1
        assert data["pagination"]["limit"] == 20

    async def test_list_transactions_filter_by_symbol(self, client: AsyncClient, auth_headers, test_user: User):
        await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "OGDC",
                "type": "BUY",
                "quantity": 100,
                "price": 98.50,
                "fees": 25.00,
                "transaction_date": "2026-09-15",
            },
        )
        await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "HBL",
                "type": "BUY",
                "quantity": 50,
                "price": 150.0,
                "fees": 10.0,
                "transaction_date": "2026-09-15",
            },
        )
        resp = await client.get("/api/v1/portfolio/transactions?symbol=OGDC", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert all(t["symbol"] == "OGDC" for t in data["data"])

    async def test_list_transactions_pagination(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.get("/api/v1/portfolio/transactions?page=1&limit=5", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["pagination"]["limit"] == 5

    async def test_list_transactions_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/portfolio/transactions")
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestTransactionGet:
    async def test_get_transaction(self, client: AsyncClient, auth_headers, test_user: User):
        create_resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "OGDC",
                "type": "BUY",
                "quantity": 100,
                "price": 98.50,
                "fees": 25.00,
                "transaction_date": "2026-09-15",
            },
        )
        txn_id = create_resp.json()["id"]
        resp = await client.get(f"/api/v1/portfolio/transactions/{txn_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == txn_id

    async def test_get_transaction_not_found(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.get("/api/v1/portfolio/transactions/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404


@pytest.mark.api
class TestTransactionUpdate:
    async def test_update_transaction_quantity(self, client: AsyncClient, auth_headers, test_user: User):
        create_resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "OGDC",
                "type": "BUY",
                "quantity": 100,
                "price": 98.50,
                "fees": 25.00,
                "transaction_date": "2026-09-15",
            },
        )
        txn_id = create_resp.json()["id"]
        resp = await client.put(
            f"/api/v1/portfolio/transactions/{txn_id}",
            headers=auth_headers,
            json={"quantity": 120},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["quantity"] == 120

    async def test_update_transaction_not_found(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.put(
            "/api/v1/portfolio/transactions/nonexistent-id",
            headers=auth_headers,
            json={"quantity": 120},
        )
        assert resp.status_code == 404

    async def test_update_sell_transaction_insufficient_quantity(self, client: AsyncClient, auth_headers, test_user: User):
        # Create a BUY for 50 shares
        create_resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "HBL",
                "type": "BUY",
                "quantity": 50,
                "price": 150.0,
                "fees": 10.0,
                "transaction_date": "2026-09-01",
            },
        )
        # Create a SELL for 50 shares
        sell_resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "HBL",
                "type": "SELL",
                "quantity": 50,
                "price": 155.0,
                "fees": 10.0,
                "transaction_date": "2026-09-15",
            },
        )
        sell_id = sell_resp.json()["id"]
        # Try to update SELL to 60 shares (would exceed net holding of 0)
        resp = await client.put(
            f"/api/v1/portfolio/transactions/{sell_id}",
            headers=auth_headers,
            json={"quantity": 60},
        )
        assert resp.status_code == 400
        data = resp.json()
        assert data["error"] == "INSUFFICIENT_QUANTITY"


@pytest.mark.api
class TestTransactionDelete:
    async def test_delete_transaction(self, client: AsyncClient, auth_headers, test_user: User):
        create_resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "OGDC",
                "type": "BUY",
                "quantity": 100,
                "price": 98.50,
                "fees": 25.00,
                "transaction_date": "2026-09-15",
            },
        )
        txn_id = create_resp.json()["id"]
        resp = await client.delete(f"/api/v1/portfolio/transactions/{txn_id}", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_delete_transaction_not_found(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.delete("/api/v1/portfolio/transactions/nonexistent-id", headers=auth_headers)
        assert resp.status_code == 404


@pytest.mark.api
class TestPriceEndpoints:
    async def test_get_price(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.get("/api/v1/prices/OGDC", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "OGDC"
        assert "current_price" in data
        assert "ldcp" in data
        assert "change_percent" in data
        assert "market_status" in data

    async def test_get_bulk_prices(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.post(
            "/api/v1/prices/bulk",
            headers=auth_headers,
            json={"symbols": ["OGDC", "HBL", "LUCK"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "prices" in data
        assert "OGDC" in data["prices"]
        assert "HBL" in data["prices"]
        assert "LUCK" in data["prices"]
        for sym in ["OGDC", "HBL", "LUCK"]:
            assert "current_price" in data["prices"][sym]
            assert "change_percent" in data["prices"][sym]
            assert "market_status" in data["prices"][sym]


@pytest.mark.api
class TestPortfolioSummary:
    async def test_get_portfolio_summary_empty(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.get("/api/v1/portfolio/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_invested"] == 0.0
        assert data["total_current_value"] == 0.0
        assert data["holdings"] == []

    async def test_get_portfolio_summary_with_holdings(self, client: AsyncClient, auth_headers, test_user: User):
        # Add some transactions
        await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "OGDC",
                "type": "BUY",
                "quantity": 100,
                "price": 98.50,
                "fees": 25.00,
                "transaction_date": "2026-09-15",
            },
        )
        resp = await client.get("/api/v1/portfolio/summary", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_invested"] > 0
        assert data["total_current_value"] > 0
        assert "holdings" in data
        assert len(data["holdings"]) >= 1
        holding = data["holdings"][0]
        assert "symbol" in holding
        assert "quantity" in holding
        assert "avg_cost" in holding
        assert "current_price" in holding
        assert "unrealized_pnl" in holding
        assert "weight_in_portfolio" in holding

    async def test_get_holding_detail(self, client: AsyncClient, auth_headers, test_user: User):
        await client.post(
            "/api/v1/portfolio/transactions",
            headers=auth_headers,
            json={
                "symbol": "OGDC",
                "type": "BUY",
                "quantity": 100,
                "price": 98.50,
                "fees": 25.00,
                "transaction_date": "2026-09-15",
            },
        )
        resp = await client.get("/api/v1/portfolio/holdings/OGDC", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "OGDC"
        assert data["quantity"] == 100
        assert "avg_cost" in data
        assert "current_price" in data
        assert "unrealized_pnl" in data
        assert "transactions" in data
        assert len(data["transactions"]) >= 1

    async def test_get_holding_detail_not_found(self, client: AsyncClient, auth_headers, test_user: User):
        resp = await client.get("/api/v1/portfolio/holdings/NONEXISTENT", headers=auth_headers)
        assert resp.status_code == 404