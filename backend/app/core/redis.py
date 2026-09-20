"""Centralized Redis cache client with automatic serialization and in-memory fallback."""

import json
import logging
import time
from typing import Any

from app.core.config import get_settings

log = logging.getLogger(__name__)

_redis_client = None
_sync_redis_client = None

# In-memory fallback if Redis is unreachable (e.g. testing or local startup)
_mem_cache: dict[str, tuple[Any, float]] = {}


def get_redis_client():
    """Get or initialize the async redis client."""
    global _redis_client
    if _redis_client is None:
        try:
            import redis.asyncio as aioredis
            settings = get_settings()
            _redis_client = aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=3.0,
            )
        except Exception as exc:
            log.warning("Could not initialize async Redis client: %s", exc)
            _redis_client = None
    return _redis_client


def get_sync_redis_client():
    """Get or initialize the sync redis client for non-async services."""
    global _sync_redis_client
    if _sync_redis_client is None:
        try:
            import redis
            settings = get_settings()
            _sync_redis_client = redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=3.0,
            )
        except Exception as exc:
            log.warning("Could not initialize sync Redis client: %s", exc)
            _sync_redis_client = None
    return _sync_redis_client


async def cache_get(key: str) -> Any | None:
    """Get item from Redis, falling back to local memory cache."""
    client = get_redis_client()
    if client:
        try:
            val = await client.get(key)
            if val is not None:
                return json.loads(val)
        except Exception as exc:
            log.debug("Redis get error for key %s: %s", key, exc)

    # Local fallback
    if key in _mem_cache:
        data, exp = _mem_cache[key]
        if exp > time.monotonic():
            return data
        del _mem_cache[key]
    return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    """Set item in Redis and local memory cache."""
    client = get_redis_client()
    if client:
        try:
            raw = json.dumps(value)
            await client.setex(key, ttl_seconds, raw)
        except Exception as exc:
            log.debug("Redis set error for key %s: %s", key, exc)

    _mem_cache[key] = (value, time.monotonic() + ttl_seconds)


def cache_get_sync(key: str) -> Any | None:
    """Sync version of cache_get for synchronous services."""
    client = get_sync_redis_client()
    if client:
        try:
            val = client.get(key)
            if val is not None:
                return json.loads(val)
        except Exception as exc:
            log.debug("Sync Redis get error for key %s: %s", key, exc)

    if key in _mem_cache:
        data, exp = _mem_cache[key]
        if exp > time.monotonic():
            return data
        del _mem_cache[key]
    return None


def cache_set_sync(key: str, value: Any, ttl_seconds: int = 60) -> None:
    """Sync version of cache_set for synchronous services."""
    client = get_sync_redis_client()
    if client:
        try:
            raw = json.dumps(value)
            client.setex(key, ttl_seconds, raw)
        except Exception as exc:
            log.debug("Sync Redis set error for key %s: %s", key, exc)

    _mem_cache[key] = (value, time.monotonic() + ttl_seconds)
