import json
from typing import Any

import redis.asyncio as aioredis

from app.core.config import get_settings

settings = get_settings()
redis_client = aioredis.from_url(settings.REDIS_URL, decode_responses=True)


async def cache_get(key: str) -> Any | None:
    raw = await redis_client.get(key)
    if raw is None:
        return None
    return json.loads(raw)


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    serialized = json.dumps(value, default=str)
    if ttl is None:
        ttl = settings.CACHE_TTL_SECONDS
    await redis_client.set(key, serialized, ex=ttl)


async def cache_invalidate(key: str) -> None:
    await redis_client.delete(key)


async def cache_invalidate_pattern(pattern: str) -> None:
    cursor = 0
    while True:
        cursor, keys = await redis_client.scan(cursor, match=pattern, count=100)
        if keys:
            await redis_client.delete(*keys)
        if cursor == 0:
            break
