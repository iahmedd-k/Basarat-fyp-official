from datetime import date

import requests

import app.data.scraper.ohlcv as ohlcv


def test_historical_404_stops_month_loop_immediately(monkeypatch):
    ohlcv.reset_psx_access_denied()
    calls = []

    def missing_endpoint(*_args, **_kwargs):
        calls.append(True)
        response = requests.Response()
        response.status_code = 404
        raise requests.HTTPError("not found", response=response)

    monkeypatch.setattr(ohlcv, "_fetch_month", missing_endpoint)

    result = ohlcv._fetch_symbol_direct(
        "HBL", date(2026, 9, 1), date(2026, 10, 1), request_interval_seconds=0,
    )

    assert result.empty
    assert len(calls) == 1
    assert ohlcv.psx_source_failure() == "endpoint_not_found"
    ohlcv.reset_psx_access_denied()


def test_historical_429_marks_denial_and_stops_month_loop(monkeypatch):
    ohlcv.reset_psx_access_denied()
    calls = []

    def rate_limited(*_args, **_kwargs):
        calls.append(True)
        response = requests.Response()
        response.status_code = 429
        raise requests.HTTPError("too many requests", response=response)

    monkeypatch.setattr(ohlcv, "_fetch_month", rate_limited)

    result = ohlcv._fetch_symbol_direct(
        "HBL", date(2026, 9, 1), date(2026, 10, 1), request_interval_seconds=0,
    )

    assert result.empty
    assert len(calls) == 1
    assert ohlcv.psx_access_denied()
    ohlcv.reset_psx_access_denied()
