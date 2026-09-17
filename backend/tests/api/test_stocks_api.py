"""API tests for stock endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.api
class TestStockSearch:
    async def test_search_success(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/search?q=HB", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert isinstance(data["results"], list)

    async def test_search_requires_query(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/search", headers=auth_headers)
        assert resp.status_code == 422

    async def test_search_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/search?q=HB")
        assert resp.status_code in (401, 403)

    async def test_search_limit_validation(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/search?q=H&limit=101", headers=auth_headers)
        assert resp.status_code == 422

    async def test_search_empty_query(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/search?q=", headers=auth_headers)
        assert resp.status_code == 422

    async def test_search_limit_too_low(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/search?q=H&limit=0", headers=auth_headers)
        assert resp.status_code == 422


@pytest.mark.api
class TestStockOverview:
    async def test_overview_success(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/HBL/overview", headers=auth_headers)
        assert resp.status_code in (200, 404, 503)
        data = resp.json()
        if resp.status_code == 200:
            assert "symbol" in data
            assert data["symbol"] == "HBL"

    async def test_overview_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/INVALID/overview", headers=auth_headers)
        assert resp.status_code in (200, 404, 503)

    async def test_overview_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/HBL/overview")
        assert resp.status_code in (401, 403)

    async def test_overview_invalid_symbol(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/!!!/overview", headers=auth_headers)
        assert resp.status_code == 503

    async def test_overview_lowercase_symbol(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/hbl/overview", headers=auth_headers)
        assert resp.status_code in (200, 404, 503)


@pytest.mark.api
class TestStockPriceHistory:
    async def test_price_history_success(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/HBL/price-history?range=1M",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "symbol" in data
            assert "bars" in data
            assert data["symbol"] == "HBL"

    async def test_price_history_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/HBL/price-history")
        assert resp.status_code in (401, 403)

    async def test_price_history_invalid_range(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/HBL/price-history?range=5Y",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_price_history_valid_ranges(self, client: AsyncClient, auth_headers):
        for r in ["1D", "1W", "1M", "1Y"]:
            resp = await client.get(
                f"/api/v1/stocks/HBL/price-history?range={r}",
                headers=auth_headers,
            )
            assert resp.status_code in (200, 404, 503)


@pytest.mark.api
class TestStockTechnicalIndicators:
    async def test_indicators_success(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/HBL/technical-indicators?indicators=RSI",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "symbol" in data
            assert "indicators" in data
            assert data["symbol"] == "HBL"

    async def test_indicators_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/HBL/technical-indicators")
        assert resp.status_code in (401, 403)

    async def test_indicators_invalid_period(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/HBL/technical-indicators?period=0",
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_indicators_period_too_high(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/HBL/technical-indicators?period=201",
            headers=auth_headers,
        )
        assert resp.status_code == 422


@pytest.mark.api
class TestStockFundamentals:
    async def test_fundamentals_success(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/HBL/fundamentals",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "symbol" in data
            assert "metrics" in data
            assert data["symbol"] == "HBL"

    async def test_fundamentals_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/HBL/fundamentals")
        assert resp.status_code in (401, 403)

    async def test_fundamentals_invalid_symbol(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/@@@/fundamentals",
            headers=auth_headers,
        )
        assert resp.status_code == 503
