"""API tests for portfolio endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import Portfolio, PortfolioHolding
from app.models.user import User


@pytest.mark.api
class TestPortfolioGet:
    async def test_get_portfolio_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/portfolio", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["holdings"] == []
        assert data["total_value"] == 0.0
        assert data["total_invested"] == 0.0
        assert data["total_pnl"] == 0.0

    async def test_get_portfolio_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/portfolio")
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestPortfolioHoldings:
    async def test_add_holding(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        resp = await client.post(
            "/api/v1/portfolio/holdings",
            headers=auth_headers,
            json={"symbol": "HBL", "quantity": 100, "avg_buy_price": 150.0, "purchase_date": "2025-01-01"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert data["quantity"] == 100
        assert data["avg_buy_price"] == 150.0

    async def test_add_holding_merges_duplicate(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        await client.post(
            "/api/v1/portfolio/holdings",
            headers=auth_headers,
            json={"symbol": "HBL", "quantity": 100, "avg_buy_price": 150.0, "purchase_date": "2025-01-01"},
        )
        resp = await client.post(
            "/api/v1/portfolio/holdings",
            headers=auth_headers,
            json={"symbol": "HBL", "quantity": 50, "avg_buy_price": 160.0, "purchase_date": "2025-02-01"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["quantity"] == 150
        expected_avg = (150.0 * 100 + 160.0 * 50) / 150
        assert abs(data["avg_buy_price"] - expected_avg) < 0.01

    async def test_add_holding_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/portfolio/holdings",
            json={"symbol": "HBL", "quantity": 100, "avg_buy_price": 150.0, "purchase_date": "2025-01-01"},
        )
        assert resp.status_code in (401, 403)

    async def test_update_holding(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        portfolio = Portfolio(user_id=test_user.id)
        db_session.add(portfolio)
        await db_session.flush()
        holding = PortfolioHolding(
            portfolio_id=portfolio.id, stock_id="stock-hbl",
            quantity=100, avg_buy_price=150.0,
        )
        db_session.add(holding)
        await db_session.flush()

        resp = await client.patch(
            f"/api/v1/portfolio/holdings/{holding.id}",
            headers=auth_headers,
            json={"quantity": 200},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["quantity"] == 200

    async def test_update_holding_empty_body_rejected(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        portfolio = Portfolio(user_id=test_user.id)
        db_session.add(portfolio)
        await db_session.flush()
        holding = PortfolioHolding(
            portfolio_id=portfolio.id, stock_id="stock-hbl",
            quantity=100, avg_buy_price=150.0,
        )
        db_session.add(holding)
        await db_session.flush()

        resp = await client.patch(
            f"/api/v1/portfolio/holdings/{holding.id}",
            headers=auth_headers,
            json={},
        )
        assert resp.status_code == 400

    async def test_delete_holding(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        portfolio = Portfolio(user_id=test_user.id)
        db_session.add(portfolio)
        await db_session.flush()
        holding = PortfolioHolding(
            portfolio_id=portfolio.id, stock_id="stock-hbl",
            quantity=100, avg_buy_price=150.0,
        )
        db_session.add(holding)
        await db_session.flush()

        resp = await client.delete(
            f"/api/v1/portfolio/holdings/{holding.id}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

    async def test_delete_holding_not_found(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        portfolio = Portfolio(user_id=test_user.id)
        db_session.add(portfolio)
        await db_session.flush()

        resp = await client.delete(
            "/api/v1/portfolio/holdings/nonexistent",
            headers=auth_headers,
        )
        assert resp.status_code == 404


@pytest.mark.api
class TestPortfolioPnL:
    async def test_get_pnl(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/portfolio/pnl", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total_invested" in data
        assert "total_current_value" in data
        assert "total_pnl" in data
        assert "holdings" in data

    async def test_get_pnl_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/portfolio/pnl")
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestPortfolioAllocation:
    async def test_get_allocation(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/portfolio/allocation", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "allocations" in data
        assert "total_value" in data

    async def test_get_allocation_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/portfolio/allocation")
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestPortfolioRiskMetrics:
    async def test_get_risk_metrics(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/portfolio/risk-metrics", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "var_95" in data
        assert "var_99" in data
        assert "sharpe_ratio" in data
        assert "max_drawdown" in data
        assert "volatility" in data

    async def test_get_risk_metrics_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/portfolio/risk-metrics")
        assert resp.status_code in (401, 403)
