"""Redis cache client interface with automatic in-memory fallback."""

from typing import Any

from app.core import redis as core_redis
from app.core.config import get_settings

settings = get_settings()


class _LazyRedisProxy:
    """Proxy object so legacy imports of redis_client work transparently.

    NOTE: this wraps the **async** client. Every attribute access therefore
    returns a coroutine, which is truthy and unawaited. Never call it from sync
    code -- a bare `if redis_client:` check is always True and `.set()` silently
    does nothing. Use `app.core.redis.get_sync_redis_client()` in sync code, or
    `await` the result here. See `ingestion_lock` in market_schedule for the
    pattern that was previously broken by this.
    """

    def __getattr__(self, name: str) -> Any:
        client = core_redis.get_redis_client()
        if client is None:
            raise RuntimeError("Redis is disabled or unreachable")
        return getattr(client, name)


redis_client = _LazyRedisProxy()


async def cache_get(key: str) -> Any | None:
    return await core_redis.cache_get(key)


async def cache_set(key: str, value: Any, ttl: int | None = None) -> None:
    ttl_seconds = ttl if ttl is not None else settings.CACHE_TTL_SECONDS
    await core_redis.cache_set(key, value, ttl_seconds=ttl_seconds)


async def cache_invalidate(key: str) -> None:
    await core_redis.cache_invalidate(key)


async def cache_invalidate_pattern(pattern: str) -> None:
    await core_redis.cache_invalidate_pattern(pattern)
