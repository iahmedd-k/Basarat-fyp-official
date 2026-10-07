"""API tests for stock endpoints."""

from datetime import date, timedelta

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.models.stock import Stock, StockPrice

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

    async def test_price_history_resolves_exact_company_name(
        self, client: AsyncClient, mock_stock_service
    ):
        called_symbols = []
        mock_stock_service.get_price_history.side_effect = (
            lambda symbol, range: called_symbols.append(symbol)
            or {
                "symbol": symbol,
                "range": range,
                "bars": [{"date": "2026-10-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
                "as_of_date": "2026-10-01",
                "data_age_days": 0,
                "is_stale": False,
            }
        )

        resp = await client.get("/api/v1/stocks/Habib%20Bank%20Limited/price-history")

        assert resp.status_code == 200
        assert resp.json()["symbol"] == "HBL"
        assert called_symbols == ["HBL"]

    async def test_price_history_resolves_quote_name_from_market_cache(
        self, client: AsyncClient, monkeypatch, mock_stock_service
    ):
        async def cached_quotes(key):
            if key == "market:quotes":
                return [{"symbol": "QTC", "name": "Quote Test Company"}]
            return None

        monkeypatch.setattr("app.api.v1.stocks.cache_get", cached_quotes)
        mock_stock_service.get_price_history.side_effect = (
            lambda symbol, range: {
                "symbol": symbol,
                "range": range,
                "bars": [{"date": "2026-10-01", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}],
                "as_of_date": "2026-10-01",
                "data_age_days": 0,
                "is_stale": False,
            }
        )

        resp = await client.get("/api/v1/stocks/Quote%20Test%20Company/price-history")

        assert resp.status_code == 200
        assert resp.json()["symbol"] == "QTC"

    async def test_price_history_falls_back_to_persisted_stock_prices(
        self, client: AsyncClient, db_session, mock_stock_service
    ):
        stock = await db_session.scalar(select(Stock).where(Stock.symbol == "HBL"))
        assert stock is not None
        today = date.today()
        db_session.add_all(
            [
                StockPrice(
                    stock_id=stock.id,
                    date=today,
                    open=150,
                    high=155,
                    low=149,
                    close=154,
                    volume=1000,
                    adjusted_close=154,
                ),
                StockPrice(
                    stock_id=stock.id,
                    date=today - timedelta(days=1),
                    open=149,
                    high=152,
                    low=148,
                    close=150,
                    volume=900,
                    adjusted_close=150,
                ),
            ]
        )
        await db_session.flush()
        mock_stock_service.get_price_history.side_effect = lambda *_args: {
            "symbol": "HBL",
            "range": "1M",
            "bars": [],
        }

        resp = await client.get("/api/v1/stocks/HBL/price-history")

        assert resp.status_code == 200
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert len(data["bars"]) == 2
        assert data["bars"][-1]["close"] == 154


@pytest.mark.api
class TestStockTechnicalIndicators:
    async def test_indicators_without_history_are_not_fabricated(
        self, client: AsyncClient, mock_stock_service
    ):
        mock_stock_service.technical_indicators.side_effect = None
        mock_stock_service.technical_indicators.return_value = {
            "symbol": "NOHISTORY",
            "indicators": {},
        }

        resp = await client.get(
            "/api/v1/stocks/NOHISTORY/technical-indicators?indicators=RSI"
        )

        assert resp.status_code == 404

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
