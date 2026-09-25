from unittest.mock import AsyncMock

from app.services.market_service import MarketService


def test_normalize_quotes_marks_zero_ohlc_as_unavailable():
    rows = [{
        "symbol": "HBL",
        "open": 0,
        "high": 0,
        "low": 0,
        "current": 304.12,
        "ldcp": 303.3,
        "change": 0.82,
        "change_pct": 0.27,
    }]

    result = MarketService._normalize_quotes(rows)

    assert result[0]["open"] is None
    assert result[0]["high"] is None
    assert result[0]["low"] is None
    assert result[0]["change"] == 0.82
    assert result[0]["change_pct"] == 0.27


def test_normalize_quotes_keeps_reported_positive_ohlc():
    rows = [{
        "symbol": "HBL",
        "open": 302,
        "high": 305,
        "low": 301,
        "current": 304.12,
        "ldcp": 303.3,
    }]

    result = MarketService._normalize_quotes(rows)

    assert (result[0]["open"], result[0]["high"], result[0]["low"]) == (302, 305, 301)


def test_normalize_quotes_marks_zero_current_and_change_unavailable():
    rows = [{"symbol": "AAL", "ldcp": 16, "current": 0, "change": 0, "change_pct": 0, "volume": 0}]

    result = MarketService._normalize_quotes(rows)

    assert result[0]["current"] is None
    assert result[0]["change"] is None
    assert result[0]["change_pct"] is None


def test_normalize_quotes_preserves_missing_metadata_without_failing_response_schema():
    from app.schemas.market import MarketQuoteItem

    rows = [{
        "symbol": "AAL",
        "sector": None,
        "ldcp": 16,
        "current": 0,
        "open": 0,
        "high": 0,
        "low": 0,
        "change": 0,
        "change_pct": 0,
        "volume": None,
        "market_cap_m": 0,
    }]

    normalized = MarketService._normalize_quotes(rows)
    response_item = MarketQuoteItem.model_validate(normalized[0])

    assert response_item.sector is None
    assert response_item.current is None
    assert response_item.open is None
    assert response_item.volume == 0
    assert response_item.market_cap_m is None


async def test_top_losers_excludes_zero_volume_stale_quotes(monkeypatch):
    service = MarketService()
    monkeypatch.setattr(service, "get_market_data", AsyncMock(return_value=[
        {"symbol": "SWL", "ldcp": 316.53, "current": 44, "change_pct": -86.1, "volume": 0},
        {"symbol": "GOOD", "ldcp": 100, "current": 90, "change_pct": -10, "volume": 1000},
    ]))

    result = await service.get_top_losers()

    assert [row["symbol"] for row in result] == ["GOOD"]
