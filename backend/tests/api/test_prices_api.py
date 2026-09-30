from datetime import date, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from app.models.stock import Stock, StockPrice


@pytest.mark.asyncio
async def test_price_route_returns_real_stale_close_when_live_sources_are_empty(
    client, auth_headers, db_session
):
    stock = Stock(symbol="PRCST", name="Price Cache Test")
    db_session.add(stock)
    await db_session.flush()
    db_session.add_all([
        StockPrice(stock_id=stock.id, date=date.today() - timedelta(days=1), open=100.0, high=100.0, low=100.0, close=100.0, adjusted_close=100.0, volume=1200),
        StockPrice(stock_id=stock.id, date=date.today(), open=105.5, high=105.5, low=105.5, close=105.5, adjusted_close=105.5, volume=2400),
    ])
    await db_session.flush()

    with patch("app.services.stock_service.StockService.get_quote", return_value={"symbol": "PRCST", "current": 0}), \
         patch("app.services.market_service.MarketService.get_market_data", new=AsyncMock(return_value=[])), \
         patch("app.services.portfolio.price_cache_service.cache_get", new=AsyncMock(return_value=None)), \
         patch("app.services.portfolio.price_cache_service.cache_set", new=AsyncMock()):
        response = await client.get("/api/v1/prices/prcst", headers=auth_headers)

    assert response.status_code == 200
    payload = response.json()
    assert payload["symbol"] == "PRCST"
    assert payload["current_price"] == 105.5
    assert payload["ldcp"] == 100.0
    assert payload["change"] == 5.5
    assert payload["volume"] == 2400
    assert payload["available"] is True
    assert payload["stale"] is True
