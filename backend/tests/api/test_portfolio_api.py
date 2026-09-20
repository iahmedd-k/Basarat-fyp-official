"""API tests for portfolio endpoints."""

import pytest
import pytest_asyncio
from decimal import Decimal
from datetime import date
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.stock import Stock
from app.core.security import create_access_token


@pytest_asyncio.fixture
async def portfolio_test_context(db_session: AsyncSession):
    """Seed test user and test stock."""
    user = User(
        id=uuid4().hex,
        email=f"port_{uuid4().hex[:8]}@test.com",
        username=f"port_user_{uuid4().hex[:8]}",
        hashed_password="hashed_pass",
        is_active=True,
    )
    db_session.add(user)

    existing_stock = await db_session.execute(select(Stock).where(Stock.symbol == "OGDC"))
    if not existing_stock.scalars().first():
        stock = Stock(
            id=uuid4().hex,
            symbol="OGDC",
            name="Oil & Gas Development Company",
            sector="Oil & Gas Exploration",
        )
        db_session.add(stock)

    await db_session.flush()
    token = create_access_token({"sub": user.id})
    return {"Authorization": f"Bearer {token}"}, user.id


@pytest.mark.api
class TestPortfolioTransactions:
    async def test_create_buy_transaction(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["symbol"] == "OGDC"
        assert data["transaction_type"] == "BUY"
        assert Decimal(str(data["quantity"])) == Decimal("100")
        assert "id" in data

    async def test_create_sell_transaction_insufficient_holding(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "SELL",
                "quantity": "100",
                "price": "260.00",
                "fee": "100",
                "transaction_date": "2026-09-19",
            },
        )
        assert response.status_code in (400, 422)

    async def test_create_sell_after_buy(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "200",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        response = await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "SELL",
                "quantity": "50",
                "price": "260.00",
                "fee": "100",
                "transaction_date": "2026-09-19",
            },
        )
        assert response.status_code == 201
        data = response.json()
        assert data["transaction_type"] == "SELL"
        assert Decimal(str(data["quantity"])) == Decimal("50")

    async def test_create_completed_trade(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.post(
            "/api/v1/portfolio/transactions/completed-trade",
            headers=headers,
            json={
                "symbol": "OGDC",
                "quantity": "100",
                "buy_price": "200.00",
                "buy_date": "2026-09-10",
                "buy_fee": "10.00",
                "sell_price": "250.00",
                "sell_date": "2026-09-15",
                "sell_fee": "10.00",
            },
        )
        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["symbol"] == "OGDC"
        assert Decimal(str(data["quantity"])) == Decimal("100")
        assert data["holding_period_days"] == 5
        # total_invested: 100 * 200 + 10 = 20010
        # total_proceeds: 100 * 250 - 10 = 24990
        # realized_pnl: 24990 - 20010 = 4980
        assert Decimal(str(data["realized_pnl"])) == Decimal("4980.0000")
        assert data["buy_transaction"]["transaction_type"] == "BUY"
        assert data["sell_transaction"]["transaction_type"] == "SELL"

    async def test_create_completed_trade_invalid_dates(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.post(
            "/api/v1/portfolio/transactions/completed-trade",
            headers=headers,
            json={
                "symbol": "OGDC",
                "quantity": "100",
                "buy_price": "200.00",
                "buy_date": "2026-09-15",
                "buy_fee": "0",
                "sell_price": "250.00",
                "sell_date": "2026-09-10",
                "sell_fee": "0",
            },
        )
        assert response.status_code in (400, 422)

    async def test_invalid_symbol(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "NONEXISTENT",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        assert response.status_code in (400, 404, 422)

    async def test_get_transactions(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        response = await client.get("/api/v1/portfolio/transactions", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) >= 1

    async def test_get_transaction_by_id(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        create_resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        txn_id = create_resp.json()["id"]
        response = await client.get(f"/api/v1/portfolio/transactions/{txn_id}", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == txn_id

    async def test_update_transaction(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        create_resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        txn_id = create_resp.json()["id"]
        response = await client.patch(
            f"/api/v1/portfolio/transactions/{txn_id}",
            headers=headers,
            json={"quantity": "150"},
        )
        assert response.status_code == 200
        data = response.json()
        assert Decimal(str(data["quantity"])) == Decimal("150")

    async def test_delete_transaction(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        create_resp = await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "250.00",
                "fee": "100",
                "transaction_date": "2026-09-18",
            },
        )
        txn_id = create_resp.json()["id"]
        del_resp = await client.delete(f"/api/v1/portfolio/transactions/{txn_id}", headers=headers)
        assert del_resp.status_code == 204

        get_resp = await client.get(f"/api/v1/portfolio/transactions/{txn_id}", headers=headers)
        assert get_resp.status_code == 404


@pytest.mark.api
class TestPortfolioSummary:
    async def test_empty_portfolio(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.get("/api/v1/portfolio", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "summary" in data
        assert "holdings" in data

    async def test_holdings_endpoint(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.get("/api/v1/portfolio/holdings", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_pnl_endpoint(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.get("/api/v1/portfolio/pnl", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "total_pnl" in data

    async def test_allocation_endpoint(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.get("/api/v1/portfolio/allocation", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "by_stock" in data
        assert "by_sector" in data

    async def test_performance_endpoint(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.get("/api/v1/portfolio/performance?period=1M", headers=headers)
        assert response.status_code == 200
        data = response.json()
        assert "period" in data
        assert "data" in data


@pytest.mark.api
class TestPortfolioAuthorization:
    async def test_unauthorized_access(self, client: AsyncClient):
        response = await client.get("/api/v1/portfolio")
        assert response.status_code in (401, 403)

        response = await client.post("/api/v1/portfolio/transactions", json={})
        assert response.status_code in (401, 403)