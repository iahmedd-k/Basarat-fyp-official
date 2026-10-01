from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock

import app.services.market_service as market_service_module
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


async def test_market_data_does_not_serve_saved_closes_when_reference_disabled(monkeypatch):
    """Persisted OHLCV closes must never be presented as live quotes.

    This is the regression guard for the incident where a 30-day-TTL snapshot of
    yesterday's closes was written to `market:quotes`, so every reader served
    stale prices as if they were live.
    """
    rows = [{
        "symbol": "HBL", "name": "HBL", "sector": "COMMERCIAL BANKS",
        "ldcp": 300.0, "open": 301.0, "high": 305.0, "low": 299.0,
        "current": 304.0, "change": 4.0, "change_pct": 1.33,
        "volume": 1000, "market_cap_m": None,
    }]
    monkeypatch.setattr(market_service_module, "cache_get", AsyncMock(return_value=None))
    written: dict = {}
    monkeypatch.setattr(
        market_service_module, "cache_set", AsyncMock(side_effect=lambda k, v, t: written.__setitem__(k, t))
    )
    monkeypatch.setattr(market_service_module, "cache_set_sync", lambda *_args: None)
    monkeypatch.setattr(
        MarketService, "_saved_scraper_snapshot", staticmethod(lambda: (rows, "2026-09-18T00:00:00+00:00"))
    )
    monkeypatch.setattr(
        MarketService,
        "_reference_snapshot_allowed",
        staticmethod(lambda as_of: (False, "reference data disabled")),
    )

    result = await MarketService().get_market_data()

    assert result == []
    # Nothing may be written to the live quote keys or the live freshness stamp.
    assert "market:quotes" not in written
    assert "market:quotes:last_known" not in written
    assert "market:quotes:fetched_at" not in written


async def test_reference_quotes_use_separate_namespace_and_never_backdate_live_stamp(monkeypatch):
    """When explicitly enabled, reference data stays in its own namespace."""
    rows = [{
        "symbol": "HBL", "name": "HBL", "sector": "COMMERCIAL BANKS",
        "ldcp": 300.0, "current": 304.0, "change": 4.0, "change_pct": 1.33,
        "volume": 1000, "market_cap_m": None,
    }]
    written: dict = {}
    monkeypatch.setattr(
        market_service_module, "cache_set", AsyncMock(side_effect=lambda k, v, t: written.__setitem__(k, t))
    )
    monkeypatch.setattr(
        MarketService, "_saved_scraper_snapshot", staticmethod(lambda: (rows, "2026-09-30T00:00:00+00:00"))
    )
    monkeypatch.setattr(
        MarketService, "_reference_snapshot_allowed", staticmethod(lambda as_of: (True, "ok"))
    )

    result_rows, as_of = await MarketService._reference_quotes()

    assert result_rows == rows
    assert as_of == "2026-09-30T00:00:00+00:00"
    assert set(written) == {"market:reference:quotes", "market:reference:fetched_at"}
    # The live freshness stamp must not carry a historical date.
    assert "market:quotes:fetched_at" not in written


def test_reference_snapshot_rejects_aged_data(monkeypatch):
    monkeypatch.setattr(
        market_service_module.get_settings(),
        "MARKET_SERVE_STALE_REFERENCE_DATA",
        True,
        raising=False,
    )
    allowed, reason = MarketService._reference_snapshot_allowed("2020-01-01T00:00:00+00:00")
    assert allowed is False
    assert "old" in reason


def test_reference_snapshot_allows_recent_data_when_explicitly_enabled(monkeypatch):
    from datetime import datetime, timedelta, timezone

    monkeypatch.setattr(
        market_service_module.get_settings(),
        "MARKET_SERVE_STALE_REFERENCE_DATA",
        True,
        raising=False,
    )
    fresh = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    allowed, _reason = MarketService._reference_snapshot_allowed(fresh)
    assert allowed is True


def test_reference_snapshot_is_available_as_age_limited_reference_data():
    allowed, reason = MarketService._reference_snapshot_allowed("2026-09-30T00:00:00+00:00")
    assert allowed is True
    assert reason == "ok"


def test_reference_snapshot_rejects_missing_as_of():
    allowed, _reason = MarketService._reference_snapshot_allowed(None)
    assert allowed is False


def test_quotes_acceptable_rejects_when_never_scraped(monkeypatch):
    monkeypatch.setattr(market_service_module, "cache_get_sync", lambda _key: None)
    acceptable, reason = MarketService.quotes_acceptable()
    assert acceptable is False
    assert "no successful market scrape" in reason


def test_quotes_acceptable_rejects_data_beyond_max_stale(monkeypatch):
    stale = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    monkeypatch.setattr(market_service_module, "cache_get_sync", lambda _key: stale)
    acceptable, reason = MarketService.quotes_acceptable()
    assert acceptable is False
    assert "old" in reason


def test_quotes_acceptable_allows_fresh_data(monkeypatch):
    fresh = (datetime.now(timezone.utc) - timedelta(seconds=5)).isoformat()
    monkeypatch.setattr(market_service_module, "cache_get_sync", lambda _key: fresh)
    acceptable, _reason = MarketService.quotes_acceptable()
    assert acceptable is True


async def test_constituents_do_not_serve_reference_data_when_disabled(monkeypatch):
    rows = [{
        "symbol": "HBL", "name": "HBL", "ldcp": 300.0, "current": 304.0,
        "change": 4.0, "change_pct": 1.33, "weight_pct": None,
        "index_points": None, "volume": 1000, "freefloat_m": None,
        "market_cap_m": None,
    }]
    monkeypatch.setattr(market_service_module, "cache_get", AsyncMock(return_value=None))
    written: dict = {}
    monkeypatch.setattr(
        market_service_module, "cache_set", AsyncMock(side_effect=lambda k, v, t: written.__setitem__(k, t))
    )
    monkeypatch.setattr(
        MarketService,
        "_saved_index_constituents",
        staticmethod(lambda code: (rows if code == "KSE100" else [], "2026-09-18T00:00:00+00:00")),
    )
    monkeypatch.setattr(
        MarketService,
        "_reference_snapshot_allowed",
        staticmethod(lambda as_of: (False, "reference data disabled")),
    )

    result = await MarketService().get_index_constituents("KSE100")

    assert result == []
    assert "market:constituents:KSE100" not in written
    assert "market:constituents:last_known:KSE100" not in written
    assert "market:constituents:KSE100:fetched_at" not in written


def test_persist_symbol_universe_writes_scraped_membership(tmp_path, monkeypatch):
    target = tmp_path / "symbol_universe.json"
    monkeypatch.setattr(
        MarketService,
        "get_index_constituents_sync",
        staticmethod(
            lambda code: {
                "KSE100": [{"symbol": "HBL"}, {"symbol": "UBL"}],
                "KSE30": [{"symbol": "HBL"}],
                "KMI30": [{"symbol": "HBL"}],
            }.get(code, [])
        ),
    )
    monkeypatch.setattr(
        MarketService,
        "_UNIVERSE_PATH_OVERRIDE",
        target,
        raising=False,
    )

    written = MarketService.persist_symbol_universe()

    assert written == 2
    import json

    payload = json.loads(target.read_text(encoding="utf-8"))
    assert [entry["symbol"] for entry in payload] == ["HBL", "UBL"]
    assert payload[0]["indices"] == ["KMI30", "KSE100", "KSE30"]
    assert payload[1]["indices"] == ["KSE100"]


def test_persist_symbol_universe_refuses_to_clobber_on_empty_scrape(tmp_path, monkeypatch):
    target = tmp_path / "symbol_universe.json"
    target.write_text('[{"symbol": "HBL", "indices": ["KSE100"]}]', encoding="utf-8")
    monkeypatch.setattr(MarketService, "get_index_constituents_sync", staticmethod(lambda code: []))
    monkeypatch.setattr(MarketService, "_UNIVERSE_PATH_OVERRIDE", target, raising=False)

    assert MarketService.persist_symbol_universe() == 0
    assert target.read_text(encoding="utf-8").strip() == '[{"symbol": "HBL", "indices": ["KSE100"]}]'


def test_market_watch_does_not_retry_allshr_after_psx_denies_request(monkeypatch):
    calls = []

    class Denied(Exception):
        status_code = 403

    monkeypatch.setattr(market_service_module.pypsx_toolkit, "market_watch", lambda: (_ for _ in ()).throw(Denied("forbidden")))
    monkeypatch.setattr(market_service_module.pypsx_toolkit, "index_constituents", lambda code: calls.append(code))

    try:
        MarketService._fetch_market_watch_frame()
    except market_service_module.PSXAccessDeniedError:
        pass
    else:
        raise AssertionError("PSX denial should stop the fallback request")

    assert calls == []
