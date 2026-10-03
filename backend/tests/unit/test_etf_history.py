from datetime import date

import pandas as pd
import pytest

import app.services.etf_service as etf_module
from app.services.etf_service import ETFService


@pytest.mark.asyncio
async def test_etf_history_reads_persisted_ohlcv_without_scraping(tmp_path, monkeypatch):
    symbol = "MIIETF"
    frame = pd.DataFrame(
        {
            "date": pd.to_datetime([date(2026, 9, 1), date(2026, 9, 2)]),
            "open": [10.0, 10.2],
            "high": [10.4, 10.5],
            "low": [9.8, 10.0],
            "close": [10.2, 10.4],
            "volume": [1000, 1200],
        }
    )
    frame.to_parquet(tmp_path / f"{symbol}.parquet", index=False)
    monkeypatch.setattr(etf_module, "OHLCV_DATA_DIR", tmp_path)
    async def cache_miss(*_args, **_kwargs):
        return None

    async def cache_noop(*_args, **_kwargs):
        return None

    monkeypatch.setattr(etf_module, "cache_get", cache_miss)
    monkeypatch.setattr(etf_module, "cache_set", cache_noop)

    result = await ETFService(None).get_history(symbol, timeframe="1M")

    assert result.count == 2
    assert result.history[-1].close == 10.4
