"""Tests for restored unreachable portfolio/prices routes."""

import inspect
from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1 import prices as prices_mod
from app.api.v1 import portfolio as portfolio_mod
from app.main import app
from app.services.portfolio.price_cache_service import PriceCacheService
from app.models.stock import Stock, StockPrice


def test_prices_and_summary_routes_are_mounted():
    path_set = set(app.openapi().get("paths", {}))
    assert "/api/v1/prices/{symbol}" in path_set
    assert "/api/v1/prices/bulk" in path_set
    assert "/api/v1/portfolio/summary" in path_set
    assert "/api/v1/portfolio/transactions/{transaction_id}" in path_set

    methods_by_path = {
        path: {method.upper() for method in operations}
        for path, operations in app.openapi().get("paths", {}).items()
    }
    assert "PUT" in methods_by_path.get("/api/v1/portfolio/transactions/{transaction_id}", set())
    assert "PATCH" in methods_by_path.get("/api/v1/portfolio/transactions/{transaction_id}", set())


@pytest.mark.asyncio
async def test_price_cache_service_maps_stock_quote():
    svc = PriceCacheService(stock_service=MagicMock())
    svc.market_service.get_market_data = AsyncMock(return_value=[])
    svc.stock_service.get_quote.return_value = {
        "symbol": "SYS",
        "ldcp": 100.0,
        "current": 105.0,
        "change": 5.0,
        "change_pct": 5.0,
        "volume": 1000,
    }

    with patch("app.services.portfolio.price_cache_service.cache_get", new=AsyncMock(return_value=None)), \
         patch("app.services.portfolio.price_cache_service.cache_set", new=AsyncMock()):
        result = await svc.get_price("sys")

    assert result["symbol"] == "SYS"
    assert result["current_price"] == 105.0
    assert result["available"] is True
    assert result["stale"] is False


@pytest.mark.asyncio
async def test_price_cache_service_uses_historical_close_when_live_quote_is_unavailable(db_session):
    stock = Stock(symbol="PRCST", name="Price Cache Test")
    db_session.add(stock)
    await db_session.flush()
    db_session.add_all([
        StockPrice(stock_id=stock.id, date=date.today() - timedelta(days=1), open=100.0, high=100.0, low=100.0, close=100.0, adjusted_close=100.0, volume=1200),
        StockPrice(stock_id=stock.id, date=date.today(), open=105.5, high=105.5, low=105.5, close=105.5, adjusted_close=105.5, volume=2400),
    ])
    await db_session.flush()

    stock_service = MagicMock()
    stock_service.get_quote.return_value = {"symbol": "PRCST", "current": 0}
    market_service = MagicMock()
    market_service.get_market_data = AsyncMock(return_value=[])
    service = PriceCacheService(stock_service=stock_service, market_service=market_service, db=db_session)

    with patch("app.services.portfolio.price_cache_service.cache_get", new=AsyncMock(return_value=None)), \
         patch("app.services.portfolio.price_cache_service.cache_set", new=AsyncMock()):
        result = await service.get_price("prcst")

    assert result["symbol"] == "PRCST"
    assert result["current_price"] == 105.5
    assert result["ldcp"] == 100.0
    assert result["change"] == 5.5
    assert result["volume"] == 2400
    assert result["available"] is True
    assert result["stale"] is True


@pytest.mark.asyncio
async def test_bulk_price_request_normalizes_symbols():
    data = prices_mod.BulkPriceRequest(symbols=["sys", " SYS ", "OGDC", "sys"])
    assert data.symbols == ["SYS", "OGDC"]


def test_portfolio_summary_handler_exists():
    assert hasattr(portfolio_mod, "get_portfolio_summary")
    assert hasattr(portfolio_mod, "put_transaction")
    src = inspect.getsource(portfolio_mod.get_portfolio_summary)
    assert "get_portfolio" in src
