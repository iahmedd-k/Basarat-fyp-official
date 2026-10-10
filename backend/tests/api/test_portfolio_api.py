"""API tests for portfolio endpoints."""

import pytest
import pytest_asyncio
import time
from statistics import median
from decimal import Decimal
from datetime import date
from uuid import uuid4

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.portfolio import PortfolioSnapshot, PortfolioTransaction, TransactionType
from app.models.stock import Stock, StockPrice
from app.core.security import create_access_token
from app.services.portfolio_service import PortfolioService
from app.core.redis import cache_get


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
async def test_portfolio_snapshot_uses_latest_close_and_prewarm_caches(
    client: AsyncClient, db_session: AsyncSession, portfolio_test_context
):
    headers, user_id = portfolio_test_context
    stock = await db_session.scalar(select(Stock).where(Stock.symbol == "OGDC"))
    assert stock is not None

    transaction = PortfolioTransaction(
        user_id=user_id,
        symbol="OGDC",
        transaction_type=TransactionType.BUY,
        quantity=Decimal("2"),
        price=Decimal("12"),
        fee=Decimal("0"),
        transaction_date=date(2025, 1, 2),
    )
    db_session.add_all(
        [
            StockPrice(
                stock_id=stock.id,
                date=date(2025, 1, 2),
                open=10,
                high=10,
                low=10,
                close=10,
                adjusted_close=10,
            ),
            StockPrice(
                stock_id=stock.id,
                date=date(2025, 1, 3),
                open=20,
                high=20,
                low=20,
                close=20,
                adjusted_close=20,
            ),
            transaction,
        ]
    )
    await db_session.flush()

    service = PortfolioService(db_session)
    warm_result = await service.prewarm_portfolio_get_caches(user_id)
    snapshot = await db_session.get(PortfolioSnapshot, user_id)

    assert snapshot is not None
    assert snapshot.snapshot_date == date(2025, 1, 3)
    assert Decimal(snapshot.payload["portfolio"]["summary"]["current_value"]) == Decimal("40")
    assert Decimal(snapshot.payload["portfolio"]["holdings"][0]["current_price"]) == Decimal("20")
    assert warm_result["holding_details"] == 1
    assert len(warm_result["performance_periods"]) == 7
    assert await cache_get(f"portfolio:summary:{user_id}") is not None
    assert await cache_get(f"portfolio:pnl:{user_id}") is not None
    assert await cache_get(f"portfolio:allocation:{user_id}") is not None
    assert await cache_get(f"portfolio:performance:{user_id}:1M") is not None
    assert await cache_get(f"portfolio:holding_detail:{user_id}:OGDC") is not None
    assert await cache_get(f"portfolio:txns:{user_id}:1:20:None:None:None:None") is not None

    paths = {
        "portfolio": "/api/v1/portfolio",
        "holdings": "/api/v1/portfolio/holdings",
        "holding_detail": "/api/v1/portfolio/holdings/OGDC",
        "pnl": "/api/v1/portfolio/pnl",
        "allocation": "/api/v1/portfolio/allocation",
        "performance": "/api/v1/portfolio/performance?period=1M",
        "transactions": "/api/v1/portfolio/transactions",
        "transaction_detail": f"/api/v1/portfolio/transactions/{transaction.id}",
    }
    latency_samples: dict[str, list[float]] = {name: [] for name in paths}
    for _ in range(3):
        for name, path in paths.items():
            started = time.perf_counter()
            response = await client.get(path, headers=headers)
            latency_samples[name].append((time.perf_counter() - started) * 1000)
            assert response.status_code == 200, response.text

    latency_medians = {
        name: round(median(samples), 2)
        for name, samples in latency_samples.items()
    }
    print(f"Portfolio GET latency, warm local SQLite (median ms): {latency_medians}")


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

    async def test_create_transaction_price_outlier_warning_and_confirm(
        self, client: AsyncClient, portfolio_test_context, db_session: AsyncSession
    ):
        headers, _ = portfolio_test_context
        stock = await db_session.scalar(select(Stock).where(Stock.symbol == "OGDC"))
        assert stock is not None
        
        # Seed historical price of Rs. 250.0 on 2026-09-18
        db_session.add(
            StockPrice(
                stock_id=stock.id,
                date=date(2026, 9, 18),
                open=248.0,
                high=255.0,
                low=247.0,
                close=250.0,
                volume=10000,
                adjusted_close=250.0,
            )
        )
        await db_session.flush()

        # Attempt to enter price Rs. 1.00 with confirm_outlier=False -> Should trigger OUTLIER_PRICE_WARNING (422)
        resp_warning = await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "1.00",
                "fee": "0",
                "transaction_date": "2026-09-18",
                "confirm_outlier": False,
            },
        )
        assert resp_warning.status_code == 422
        assert "OUTLIER_PRICE_WARNING" in resp_warning.text or "deviates" in resp_warning.text

        # Re-attempt with confirm_outlier=True (e.g. rights issue or bonus share) -> Should succeed (201)
        resp_confirm = await client.post(
            "/api/v1/portfolio/transactions",
            headers=headers,
            json={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": "100",
                "price": "1.00",
                "fee": "0",
                "transaction_date": "2026-09-18",
                "confirm_outlier": True,
            },
        )
        assert resp_confirm.status_code == 201
        assert Decimal(str(resp_confirm.json()["price"])) == Decimal("1.0000")

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
        assert data["total"] >= len(data["items"])

        next_page = await client.get(
            "/api/v1/portfolio/transactions?page=2&limit=1",
            headers=headers,
        )
        assert next_page.status_code == 200
        assert next_page.json()["total"] == data["total"]

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

    async def test_put_transaction_method_not_allowed(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.put(
            f"/api/v1/portfolio/transactions/{uuid4().hex}",
            headers=headers,
            json={"quantity": "150"},
        )
        assert response.status_code == 405

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

    async def test_holding_detail_endpoint(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        create_response = await client.post(
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
        assert create_response.status_code == 201, create_response.text

        response = await client.get(
            "/api/v1/portfolio/holdings/OGDC",
            headers=headers,
        )

        assert response.status_code == 200, response.text
        data = response.json()
        assert data["symbol"] == "OGDC"
        assert Decimal(str(data["quantity"])) == Decimal("100")
        assert len(data["transactions"]) == 1

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

    async def test_empty_transaction_history(self, client: AsyncClient, portfolio_test_context):
        headers, _ = portfolio_test_context
        response = await client.get("/api/v1/portfolio/transactions", headers=headers)

        assert response.status_code == 200
        assert response.json()["items"] == []
        assert response.json()["total"] == 0


@pytest.mark.api
class TestPortfolioAuthorization:
    async def test_unauthorized_access(self, client: AsyncClient):
        response = await client.get("/api/v1/portfolio")
        assert response.status_code in (401, 403)

        response = await client.post("/api/v1/portfolio/transactions", json={})
        assert response.status_code in (401, 403)