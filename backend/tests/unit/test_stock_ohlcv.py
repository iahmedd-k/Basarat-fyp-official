from datetime import date, timedelta

import pandas as pd
import pytest

import app.services.stock_service as stock_module
from app.services.stock_service import StockService


def test_stale_ohlcv_file_is_served_without_request_time_scraping(monkeypatch):
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

    monkeypatch.setattr(
        stock_module.pypsx_toolkit,
        "get_historical",
        lambda *_args, **_kwargs: pytest.fail("API history reads must not scrape"),
    )
    monkeypatch.setattr(stock_module, "cache_get_sync", lambda _key: None)
    monkeypatch.setattr(stock_module, "cache_set_sync", lambda *_args: None)

    result = service._get_ohlcv(symbol, start, end)

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


def test_price_history_falls_back_to_latest_available_bars_for_older_data(monkeypatch):
    service = StockService()
    symbol = "TESTOLDER"
    older_date = date.today() - timedelta(days=20)
    dates = pd.to_datetime([older_date - timedelta(days=2), older_date - timedelta(days=1), older_date])
    frame = pd.DataFrame(
        {"OPEN": [10.0, 10.5, 11.0], "HIGH": [11.0, 11.5, 12.0], "LOW": [9.5, 10.0, 10.5], "CLOSE": [10.5, 11.0, 11.5], "VOLUME": [100, 200, 300]},
        index=dates,
    )
    # _get_ohlcv returns empty when filtered with date.today() - lookback (e.g. 8 days)
    monkeypatch.setattr(service, "_get_ohlcv", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(service, "_get_ohlcv_from_file", lambda *_args, **_kwargs: frame.copy())
    monkeypatch.setattr(stock_module, "cache_get_sync", lambda _key: None)
    monkeypatch.setattr(stock_module, "cache_set_sync", lambda *_args: None)

    history_1d = service.get_price_history(symbol, "1D")
    assert len(history_1d["bars"]) > 0
    assert history_1d["bars"][-1]["close"] == 11.5
    assert history_1d["as_of_date"] == older_date.isoformat()
    assert history_1d["is_stale"] is True

    history_1w = service.get_price_history(symbol, "1W")
    assert len(history_1w["bars"]) > 0
    assert history_1w["bars"][-1]["close"] == 11.5



def test_technical_indicators_use_full_local_history_without_scraping(tmp_path, monkeypatch):
    symbol = "TESTTECH"
    dates = pd.bdate_range(
        end=pd.Timestamp(date.today() - timedelta(days=1)),
        periods=350,
    )
    close = [100.0 + index * 0.1 for index in range(len(dates))]
    frame = pd.DataFrame(
        {
            "date": dates,
            "open": close,
            "high": [value + 1 for value in close],
            "low": [value - 1 for value in close],
            "close": close,
            "volume": [1000 + index for index in range(len(dates))],
        }
    )
    frame.to_parquet(tmp_path / f"{symbol}.parquet", index=False)

    monkeypatch.setattr(stock_module, "OHLCV_DATA_DIR", tmp_path)
    monkeypatch.setattr(stock_module, "cache_get_sync", lambda _key: None)
    monkeypatch.setattr(stock_module, "cache_set_sync", lambda *_args: None)
    monkeypatch.setattr(
        stock_module.pypsx_toolkit,
        "get_historical",
        lambda *_args, **_kwargs: pytest.fail("Technical indicators must not scrape history"),
    )

    result = StockService().technical_indicators(
        symbol,
        indicators="RSI,MACD,BB,SMA,ADX",
        period=14,
        limit=365,
    )

    assert result["as_of_date"] == dates[-1].date().isoformat()
    assert len(result["indicators"]["SMA"]) == len(dates) - 14 + 1
    assert result["indicators"]["RSI"]
    assert result["indicators"]["MACD"]
    assert result["indicators"]["BB_UPPER"]
    assert result["indicators"]["ADX"]


def test_local_ohlcv_history_deduplicates_dates_using_latest_row(tmp_path, monkeypatch):
    symbol = "TESTDUP"
    dates = pd.to_datetime(["2026-01-02", "2026-01-01", "2026-01-02"])
    frame = pd.DataFrame(
        {
            "date": dates,
            "close": [12.0, 10.0, 13.0],
        }
    )
    frame.to_parquet(tmp_path / f"{symbol}.parquet", index=False)
    monkeypatch.setattr(stock_module, "OHLCV_DATA_DIR", tmp_path)

    result = StockService()._get_ohlcv_from_file(symbol)

    assert result is not None
    assert list(result.index.strftime("%Y-%m-%d")) == ["2026-01-01", "2026-01-02"]
    assert result.loc[pd.Timestamp("2026-01-02"), "CLOSE"] == 13.0


def test_adx_uses_wilder_warmup_and_is_not_a_directional_signal(monkeypatch):
    dates = pd.date_range("2026-01-01", periods=100)
    close = pd.Series([100.0 + index for index in range(len(dates))], index=dates)
    frame = pd.DataFrame(
        {"HIGH": close + 1, "LOW": close - 1, "CLOSE": close},
        index=dates,
    )
    service = StockService()
    monkeypatch.setattr(service, "_get_ohlcv_from_file", lambda *_args, **_kwargs: frame)
    monkeypatch.setattr(stock_module, "cache_get_sync", lambda _key: None)
    monkeypatch.setattr(stock_module, "cache_set_sync", lambda *_args: None)

    adx = service._adx(frame, period=14)
    result = service.technical_indicators("TESTADX", indicators="ADX", period=14)

    assert adx.first_valid_index() == dates[26]
    assert adx.iloc[-1] == pytest.approx(100.0)
    assert result["summary"]["adx"]["signal"] == "NEUTRAL"
    assert result["summary"]["adx"]["trend_strength"] == "STRONG"
    assert result["signals_breakdown"] == {"buy": 0, "neutral": 1, "sell": 0}


@pytest.mark.parametrize(
    ("macd_values", "signal_values", "expected_description"),
    [
        ([1.0, 2.0], [0.0, 1.0], "MACD is above its signal line"),
        ([-1.0, 1.0], [0.0, 0.0], "Bullish MACD crossover"),
        ([1.0, -1.0], [0.0, 0.0], "Bearish MACD crossover"),
    ],
)
def test_macd_description_only_reports_actual_crossovers(
    monkeypatch, macd_values, signal_values, expected_description
):
    dates = pd.date_range("2026-01-01", periods=2)
    close = pd.Series([100.0, 101.0], index=dates)
    frame = pd.DataFrame(
        {"HIGH": close + 1, "LOW": close - 1, "CLOSE": close},
        index=dates,
    )
    macd = pd.Series(macd_values, index=dates)
    signal = pd.Series(signal_values, index=dates)
    service = StockService()
    monkeypatch.setattr(service, "_get_ohlcv_from_file", lambda *_args, **_kwargs: frame)
    monkeypatch.setattr(stock_module, "cache_get_sync", lambda _key: None)
    monkeypatch.setattr(stock_module, "cache_set_sync", lambda *_args: None)
    monkeypatch.setattr(
        stock_module.pypsx_toolkit,
        "macd",
        lambda *_args, **_kwargs: (macd, signal, macd - signal),
    )

    result = service.technical_indicators("TESTMACD", indicators="MACD")

    assert expected_description in result["summary"]["macd"]["description"]
