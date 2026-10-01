from datetime import date, timedelta

import pandas as pd

import app.services.stock_service as stock_module
from app.services.stock_service import StockService


def test_stale_ohlcv_file_is_served_without_request_triggered_scrape(monkeypatch):
    symbol = "TESTOHLCV"
    start = date.today() - timedelta(days=30)
    end = date.today()
    old_date = date.today() - timedelta(days=6)
    new_date = date.today() - timedelta(days=1)
    old_frame = pd.DataFrame(
        {"OPEN": [10.0], "HIGH": [12.0], "LOW": [9.0], "CLOSE": [11.0], "VOLUME": [100]},
        index=pd.to_datetime([old_date]),
    )
    service = StockService()
    service._get_ohlcv_from_file = lambda *_: old_frame.copy()
    requested = {}

    def forbidden_fetch(*args, **kwargs):
        requested["called"] = True
        raise AssertionError("stock API must not scrape OHLCV on demand")

    monkeypatch.setattr(stock_module.pypsx_toolkit, "get_historical", forbidden_fetch)
    monkeypatch.setattr(stock_module, "cache_get_sync", lambda _key: None)
    monkeypatch.setattr(stock_module, "cache_set_sync", lambda *_args: None)

    result = service._get_ohlcv(symbol, start, end)

    assert requested == {}
    assert list(result.index.date) == [old_date]
    assert result.iloc[-1]["CLOSE"] == 11.0


def test_ohlcv_history_tolerates_missing_optional_columns(monkeypatch):
    service = StockService()
    symbol = "TESTNULLS"
    date_index = pd.to_datetime([date.today() - timedelta(days=1)])
    frame = pd.DataFrame({"CLOSE": [12.0]}, index=date_index)
    monkeypatch.setattr(service, "_get_ohlcv", lambda *_: frame)

    history = service.get_price_history(symbol, "1W")

    assert len(history["bars"]) == 1
    assert history["bars"][0] == {
        "date": date_index[0].date().isoformat(),
        "open": None,
        "high": None,
        "low": None,
        "close": 12.0,
        "volume": 0,
    }
