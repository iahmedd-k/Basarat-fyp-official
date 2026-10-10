import json
import time
from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.core import redis as redis_cache


@pytest.mark.asyncio
async def test_cache_get_many_uses_one_redis_round_trip_and_local_fallback(monkeypatch):
    client = AsyncMock()
    client.mget.return_value = [json.dumps({"price": 12})]
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: client)
    monkeypatch.setattr(redis_cache, "_redis_available_for_attempt", lambda: True)
    monkeypatch.setattr(
        redis_cache,
        "_mem_cache",
        {"local-only": ({"price": 9}, time.monotonic() + 60)},
    )

    result = await redis_cache.cache_get_many(["redis-value", "local-only", "local-only"])

    client.mget.assert_awaited_once_with(["redis-value"])
    assert result == {"redis-value": {"price": 12}, "local-only": {"price": 9}}


@pytest.mark.asyncio
async def test_cache_get_many_returns_empty_without_contacting_redis(monkeypatch):
    get_client = AsyncMock()
    monkeypatch.setattr(redis_cache, "get_redis_client", get_client)

    assert await redis_cache.cache_get_many([]) == {}

    get_client.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(("status", "expected"), [("success", True), ("pending", False), (None, False)])
async def test_market_intelligence_cache_requires_successful_daily_refresh(
    monkeypatch, status, expected
):
    class MondayMorning(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2026, 10, 5, 6, 0, tzinfo=tz)

    client = AsyncMock()
    client.get.return_value = status
    monkeypatch.setattr(redis_cache, "datetime", MondayMorning)
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: client)
    monkeypatch.setattr(redis_cache, "_restore_async_primary_if_due", lambda: None)
    monkeypatch.setattr(redis_cache, "_redis_available_for_attempt", lambda: True)
    monkeypatch.setattr(
        "app.services.news_pipeline.market_schedule.is_holiday",
        AsyncMock(return_value=False),
    )

    assert await redis_cache.market_intelligence_cache_ready() is expected
    assert client.ping.await_count == 2
    assert client.get.await_args_list[0].args == (
        "datasets:forecasts:status:2026-10-05",
    )
    assert client.get.await_args_list[1].args == (
        "datasets:recommendations:status:2026-10-05",
    )


@pytest.mark.asyncio
async def test_market_intelligence_cache_is_not_ready_when_redis_is_unavailable(monkeypatch):
    client = AsyncMock()
    client.ping.side_effect = ConnectionError("Redis unavailable")
    monkeypatch.setattr(redis_cache, "get_redis_client", lambda: client)
    monkeypatch.setattr(redis_cache, "_restore_async_primary_if_due", lambda: None)
    monkeypatch.setattr(redis_cache, "_redis_available_for_attempt", lambda: True)
    monkeypatch.setattr(redis_cache, "_switch_async_redis_url", lambda: None)
    monkeypatch.setattr(redis_cache, "_mark_redis_failure", lambda **_kwargs: None)

    assert await redis_cache.market_intelligence_cache_ready() is False
    client.get.assert_not_awaited()


@pytest.mark.asyncio
async def test_async_redis_health_check_fails_over_to_cloud_url(monkeypatch):
    from types import SimpleNamespace

    primary = AsyncMock()
    primary.ping.side_effect = ConnectionError("primary unavailable")
    fallback = AsyncMock()
    monkeypatch.setattr(
        redis_cache,
        "get_settings",
        lambda: SimpleNamespace(
            REDIS_URL="redis://primary:6379/0",
            CLOUD_REDIS_URL="rediss://cloud.example/0",
            REDIS_ENABLED=True,
        ),
    )
    monkeypatch.setattr(
        redis_cache,
        "_redis_url_index",
        0,
    )
    monkeypatch.setattr(redis_cache, "_redis_client", None)
    monkeypatch.setattr(redis_cache, "_redis_fallback_since", 0.0)
    monkeypatch.setattr(redis_cache, "_redis_retry_after", 0.0)
    monkeypatch.setattr(redis_cache, "_restore_async_primary_if_due", lambda: None)
    monkeypatch.setattr(redis_cache, "_redis_available_for_attempt", lambda: True)
    monkeypatch.setattr(
        redis_cache,
        "get_redis_client",
        lambda: primary if redis_cache._redis_url_index == 0 else fallback,
    )

    assert await redis_cache.redis_is_available() is True
    assert primary.ping.await_count == 1
    fallback.ping.assert_awaited_once()
    assert redis_cache._redis_url_index == 1
