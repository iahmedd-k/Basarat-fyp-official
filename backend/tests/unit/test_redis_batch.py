import json
import time
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
