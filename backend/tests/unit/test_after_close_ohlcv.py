import asyncio
import sys
from datetime import date, datetime, timedelta
from types import ModuleType, SimpleNamespace

import pandas as pd
import pytest

import app.data.scraper.ohlcv as ohlcv
import app.data.scraper.run_after_close as after_close
from app.data.scraper import run_scrape
from app.celery_app import celery
from app.tasks import daily_workflow


def test_daily_pipeline_is_scheduled_five_minutes_after_psx_close():
    mon_thu = celery.conf.beat_schedule["daily-workflow"]["schedule"]
    friday = celery.conf.beat_schedule["daily-workflow-friday"]["schedule"]

    assert celery.conf.timezone == "Asia/Karachi"
    assert (mon_thu.hour, mon_thu.minute, mon_thu.day_of_week) == (
        {15},
        {35},
        {1, 2, 3, 4},
    )
    assert (friday.hour, friday.minute, friday.day_of_week) == ({16}, {35}, {5})


@pytest.mark.parametrize(
    ("holiday_check", "expected_reason"),
    [
        (True, "exchange_holiday"),
        (RuntimeError("calendar unavailable"), "holiday_check_unavailable"),
    ],
)
def test_daily_pipeline_does_not_dispatch_on_holidays_or_calendar_errors(
    monkeypatch, holiday_check, expected_reason
):
    class FridayDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 2, 16, 35, tzinfo=tz)

    def check_holiday(coroutine):
        coroutine.close()
        if isinstance(holiday_check, Exception):
            raise holiday_check
        return holiday_check

    monkeypatch.setattr(daily_workflow, "datetime", FridayDateTime)
    monkeypatch.setattr(asyncio, "run", check_holiday)

    result = daily_workflow.run_daily_pipeline.run()

    assert result == {"status": "skipped", "reason": expected_reason}


def test_primary_ohlcv_fetch_normalizes_and_sorts_source_data(monkeypatch):
    source = ModuleType("psx")
    source_frame = pd.DataFrame(
        {
            "Date": pd.to_datetime(["2026-01-02", "2026-01-01"]),
            "Open": [11.0, 10.0],
            "High": [12.0, 11.0],
            "Low": [10.0, 9.0],
            "Close": [11.5, 10.5],
            "Volume": [200, 100],
        }
    )
    source.stocks = lambda *_args, **_kwargs: source_frame.copy()
    monkeypatch.setitem(sys.modules, "psx", source)

    result = ohlcv.fetch_ohlcv(
        "TESTPSX",
        start=date(2026, 1, 1),
        end=date(2026, 1, 2),
    )

    assert list(result.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert list(result["date"].dt.strftime("%Y-%m-%d")) == ["2026-01-01", "2026-01-02"]
    assert list(result["close"]) == [10.5, 11.5]


def test_direct_ohlcv_fallback_parses_psx_history(monkeypatch):
    source_frame = pd.DataFrame(
        {
            "DATE": ["Jan 02, 2026", "Jan 01, 2026"],
            "OPEN": ["11.00", "10.00"],
            "HIGH": ["12.00", "11.00"],
            "LOW": ["10.00", "9.00"],
            "CLOSE": ["11.50", "10.50"],
            "VOLUME": ["2,000", "1,000"],
        }
    )
    monkeypatch.setattr(ohlcv, "_fetch_month", lambda *_args: source_frame.copy())
    monkeypatch.setattr(ohlcv.time, "sleep", lambda *_args: None)

    result = ohlcv._fetch_symbol_direct(
        "TESTPSX",
        start=date(2026, 1, 1),
        end=date(2026, 1, 2),
        request_interval_seconds=0,
    )

    assert list(result.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert list(result["date"].dt.strftime("%Y-%m-%d")) == ["2026-01-01", "2026-01-02"]
    assert list(result["close"]) == [10.5, 11.5]
    assert list(result["volume"]) == [1000.0, 2000.0]


def test_incremental_scrape_refreshes_existing_latest_session(tmp_path, monkeypatch):
    symbol = "TESTCLOSE"
    session_date = date(2026, 10, 2)
    existing = pd.DataFrame(
        {
            "date": pd.to_datetime([session_date - timedelta(days=1), session_date]),
            "open": [9.0, 10.0],
            "high": [11.0, 12.0],
            "low": [8.0, 9.0],
            "close": [10.0, 11.0],
            "volume": [100, 200],
        }
    )
    existing.to_parquet(tmp_path / f"{symbol}.parquet", index=False)
    fresh = pd.DataFrame(
        {
            "date": pd.to_datetime([session_date]),
            "open": [10.5],
            "high": [12.5],
            "low": [10.0],
            "close": [12.0],
            "volume": [500],
        }
    )
    requested = {}

    def fetch(requested_symbol, start, end):
        requested.update(symbol=requested_symbol, start=start, end=end)
        return fresh.copy()

    monkeypatch.setattr(run_scrape, "fetch_ohlcv", fetch)

    result = run_scrape._scrape_symbol(
        symbol=symbol,
        start=session_date - timedelta(days=365),
        end=session_date,
        output_dir=tmp_path,
        incremental=True,
        delay=0,
    )

    updated = pd.read_parquet(tmp_path / f"{symbol}.parquet")
    assert result["status"] == "ok"
    assert requested["start"] == session_date
    assert len(updated) == 2
    assert updated.iloc[-1]["close"] == 12.0


def test_incremental_scrape_limits_first_fetch_for_new_symbol(tmp_path, monkeypatch):
    session_date = date(2026, 10, 2)
    requested = {}
    monkeypatch.setattr(
        run_scrape,
        "fetch_ohlcv",
        lambda symbol, start, end: requested.update(
            symbol=symbol, start=start, end=end
        )
        or pd.DataFrame(
            {
                "date": pd.to_datetime([session_date]),
                "open": [10.0],
                "high": [11.0],
                "low": [9.0],
                "close": [10.5],
                "volume": [100],
            }
        ),
    )

    result = run_scrape._scrape_symbol(
        symbol="NEWQUOTE",
        start=session_date - timedelta(days=5 * 365),
        end=session_date,
        output_dir=tmp_path,
        incremental=True,
        delay=0,
        initial_lookback_days=365,
    )

    assert result["status"] == "ok"
    assert requested["start"] == session_date - timedelta(days=365)


def test_refresh_symbol_universe_includes_registered_quotes_and_files(
    tmp_path, monkeypatch
):
    class FakeResult:
        def all(self):
            return ["HBL", "UBL", "TEST_SYM_01"]

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def scalars(self, _statement):
            return FakeResult()

    (tmp_path / "LUCK.parquet").touch()
    (tmp_path / "all_symbols.parquet").touch()
    monkeypatch.setattr(after_close, "get_sync_session_factory", lambda: FakeSession)
    monkeypatch.setattr(
        after_close,
        "cache_get_sync",
        lambda key: (
            [{"symbol": "OGDC"}, {"symbol": "HBL"}]
            if key == "market:quotes"
            else [{"symbol": "GCWL"}]
        ),
    )
    monkeypatch.setattr(
        after_close,
        "get_active_symbols",
        lambda: [{"symbol": "KSE100ONLY"}],
    )

    assert after_close.get_refresh_symbols(tmp_path) == [
        "GCWL",
        "HBL",
        "KSE100ONLY",
        "LUCK",
        "OGDC",
        "UBL",
    ]


def test_materialize_database_history_writes_missing_symbol_files(
    tmp_path, monkeypatch
):
    rows = [
        SimpleNamespace(
            symbol="GCWL",
            date=date(2026, 10, 6),
            open=12.0,
            high=13.0,
            low=11.0,
            close=12.5,
            volume=1000,
        )
    ]

    class FakeSession:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def execute(self, _statement):
            return SimpleNamespace(all=lambda: rows)

    monkeypatch.setattr(after_close, "get_sync_session_factory", lambda: FakeSession)

    materialized = after_close._materialize_database_history(tmp_path, ["GCWL"])

    assert materialized == 1
    frame = pd.read_parquet(tmp_path / "GCWL.parquet")
    assert frame.to_dict(orient="records") == [
        {
            "date": pd.Timestamp("2026-10-06"),
            "open": 12.0,
            "high": 13.0,
            "low": 11.0,
            "close": 12.5,
            "volume": 1000,
        }
    ]


def test_after_close_runner_refreshes_full_universe_and_rebuilds_all_symbols(
    tmp_path, monkeypatch
):
    symbols = [f"TEST{index:02d}" for index in range(11)]
    session_date = date(2026, 10, 2)
    for symbol in symbols:
        pd.DataFrame(
            {
                "date": pd.to_datetime([session_date - timedelta(days=1), session_date]),
                "open": [9.0, 10.0],
                "high": [11.0, 12.0],
                "low": [8.0, 9.0],
                "close": [10.0, 11.0],
                "volume": [100, 200],
            }
        ).to_parquet(tmp_path / f"{symbol}.parquet", index=False)

    requested_symbols = []
    pauses = []

    def fetch(symbol, start, end):
        requested_symbols.append(symbol)
        return pd.DataFrame(
            {
                "date": pd.to_datetime([session_date]),
                "open": [10.5],
                "high": [12.5],
                "low": [10.0],
                "close": [12.0],
                "volume": [500],
            }
        )

    monkeypatch.setattr(after_close, "get_refresh_symbols", lambda _out_dir: symbols)
    monkeypatch.setattr(after_close, "_materialize_database_history", lambda *_args: 0)
    monkeypatch.setattr(after_close, "reset_psx_access_denied", lambda: None)
    monkeypatch.setattr(after_close, "psx_access_denied", lambda: False)
    monkeypatch.setattr(after_close.time, "sleep", pauses.append)
    monkeypatch.setattr(run_scrape, "fetch_ohlcv", fetch)
    monkeypatch.setattr(after_close, "_save_fetch_log", lambda *_args: None)

    result = after_close.run_after_close_scrape(
        output_dir=tmp_path,
        batch_size=10,
        pause_seconds=150,
        end_date=session_date,
    )

    combined = pd.read_parquet(tmp_path / "all_symbols.parquet")
    assert requested_symbols == symbols
    assert [pause for pause in pauses if pause > 0] == [150]
    assert result["ok"] == len(symbols)
    assert len(combined["symbol"].unique()) == len(symbols)
    assert set(combined.loc[combined["date"].dt.date == session_date, "close"]) == {12.0}
