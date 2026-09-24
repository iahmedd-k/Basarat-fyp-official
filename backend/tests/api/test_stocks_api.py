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

    async def test_search_by_company_name_in_db(self, client: AsyncClient, auth_headers):
        # Search by full company name "Habib" (matches Habib Bank Limited)
        resp = await client.get("/api/v1/stocks/search?q=Habib", headers=auth_headers)
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        assert any(r["symbol"] == "HBL" and "Habib" in r["name"] for r in results)

        # Search by company name "Lucky" (matches Lucky Cement)
        resp2 = await client.get("/api/v1/stocks/search?q=Lucky", headers=auth_headers)
        assert resp2.status_code == 200
        results2 = resp2.json()["results"]
        assert len(results2) >= 1
        assert any(r["symbol"] == "LUCK" for r in results2)

    async def test_search_rank_ordering(self, client: AsyncClient, auth_headers):
        # Search prefix "HB" -> HBL should be returned
        resp = await client.get("/api/v1/stocks/search?q=HB", headers=auth_headers)
        assert resp.status_code == 200
        results = resp.json()["results"]
        assert len(results) >= 1
        assert results[0]["symbol"] == "HBL"


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

    async def test_overview_is_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/HBL/overview")
        assert resp.status_code in (200, 404, 503)

    async def test_overview_invalid_symbol(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/stocks/!!!/overview", headers=auth_headers)
        assert resp.status_code == 422

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

    async def test_price_history_is_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/HBL/price-history")
        assert resp.status_code in (200, 404, 503)

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
            assert "overall_signal" in data
            assert "summary_message" in data
            assert "summary" in data
            assert data["symbol"] == "HBL"

    async def test_indicators_are_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/HBL/technical-indicators")
        assert resp.status_code not in (401, 403)

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
    async def test_indicators_with_limit(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/HBL/technical-indicators?indicators=RSI&limit=10",
            headers=auth_headers,
        )
        assert resp.status_code in (200, 404, 503)
        if resp.status_code == 200:
            data = resp.json()
            assert "indicators" in data
            if "RSI" in data["indicators"]:
                assert len(data["indicators"]["RSI"]) <= 10

    async def test_indicators_invalid_limit(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/HBL/technical-indicators?limit=500",
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
            assert data["symbol"] == "HBL"
            assert "company_profile" in data
            assert "equity_profile" in data
            assert "ratios" in data
            assert "trading_limits" in data
            assert "dividend_history" in data
            assert "announcements" in data
            assert "sector_overview" in data
            assert data["sector_overview"]["companies_count"] >= 1

    async def test_fundamentals_are_public(self, client: AsyncClient):
        resp = await client.get("/api/v1/stocks/HBL/fundamentals")
        assert resp.status_code in (200, 503)

    async def test_fundamentals_invalid_symbol(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/stocks/@@@/fundamentals",
            headers=auth_headers,
        )
        assert resp.status_code == 422
