import pytest


@pytest.mark.asyncio
async def test_shared_market_refresh_orders_data_and_marks_each_dataset_ready(monkeypatch):
    from app.services.market_service import MarketService
    from app.tasks import refresh_market_cache

    calls = []

    class FakeMarketService:
        async def get_market_data(self, **kwargs):
            calls.append("quotes")
            return [{"symbol": "OGDC"}]

        async def get_indices(self, **kwargs):
            calls.append("indices")
            return [{"symbol": "KSE100"}]

        async def get_index_constituents(self, code, **kwargs):
            calls.append(f"constituents:{code}")
            return [{"symbol": code}]

    async def warm_universe(**kwargs):
        calls.append("assistant_universe")
        return {"symbol_count": 1}

    async def close_redis():
        return None

    monkeypatch.setattr(MarketService, "__new__", lambda cls: FakeMarketService())
    monkeypatch.setattr(
        "app.services.assistant_context_cache.warm_assistant_universe",
        warm_universe,
    )
    monkeypatch.setattr(
        "app.core.redis.set_dataset_status_sync",
        lambda dataset, status: calls.append(f"status:{dataset}:{status}"),
    )
    monkeypatch.setattr(
        "app.core.redis.close_async_redis_client",
        close_redis,
    )

    result = await refresh_market_cache._refresh_quotes_and_optional_reference(
        refresh_quotes=True,
        refresh_screener=False,
        refresh_reference=True,
        refresh_constituents=True,
        publish_live=False,
        source="test",
    )

    assert result["quotes"] == 1
    assert result["indices"] == 1
    assert result["constituents"] == {"KSE100": 1, "KSE30": 1, "KMI30": 1}
    assert calls.index("quotes") < calls.index("indices") < calls.index("constituents:KSE100")
    assert "status:market_quotes:success" in calls
    assert "status:market_indices:success" in calls
    assert "status:market_constituents_kmi30:success" in calls
