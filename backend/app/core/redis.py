"""Centralized Redis cache client with automatic serialization and in-memory fallback."""

import json
import logging
import time
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

from app.core.config import get_settings

log = logging.getLogger(__name__)

_redis_client = None
_sync_redis_client = None
_redis_url_index = 0
_sync_redis_url_index = 0
_redis_fallback_since = 0.0
_sync_redis_fallback_since = 0.0

# In-memory fallback if Redis is disabled or unreachable
_mem_cache: dict[str, tuple[Any, float]] = {}
_redis_retry_after = 0.0
_REDIS_FAILURE_BACKOFF_SECONDS = 30.0
_REDIS_PRIMARY_RETRY_SECONDS = 30.0


def _redis_available_for_attempt() -> bool:
    return time.monotonic() >= _redis_retry_after


def _mark_redis_failure() -> None:
    global _redis_retry_after
    _redis_retry_after = time.monotonic() + _REDIS_FAILURE_BACKOFF_SECONDS


def _mark_redis_success() -> None:
    global _redis_retry_after
    _redis_retry_after = 0.0


def _redis_urls() -> list[str]:
    settings = get_settings()
    urls = [str(getattr(settings, "REDIS_URL", "") or "").strip()]
    cloud_url = str(getattr(settings, "CLOUD_REDIS_URL", "") or "").strip()
    if cloud_url and cloud_url not in urls:
        urls.append(cloud_url)
    return [url for url in urls if url]


def _switch_async_redis_url() -> None:
    global _redis_client, _redis_url_index, _redis_fallback_since
    urls = _redis_urls()
    if len(urls) > 1:
        _redis_url_index = (_redis_url_index + 1) % len(urls)
        _redis_client = None
        if _redis_url_index != 0:
            _redis_fallback_since = time.monotonic()
        log.warning("Primary Redis unavailable; switching to configured Redis fallback")


def _switch_sync_redis_url() -> None:
    global _sync_redis_client, _sync_redis_url_index, _sync_redis_fallback_since
    urls = _redis_urls()
    if len(urls) > 1:
        _sync_redis_url_index = (_sync_redis_url_index + 1) % len(urls)
        _sync_redis_client = None
        if _sync_redis_url_index != 0:
            _sync_redis_fallback_since = time.monotonic()
        log.warning("Primary Redis unavailable; switching to configured Redis fallback")


def _restore_async_primary_if_due() -> None:
    global _redis_client, _redis_url_index, _redis_fallback_since
    if (
        _redis_url_index != 0
        and _redis_fallback_since
        and time.monotonic() - _redis_fallback_since >= _REDIS_PRIMARY_RETRY_SECONDS
    ):
        _redis_url_index = 0
        _redis_fallback_since = 0.0
        _redis_client = None
        log.info("Retrying primary Redis after fallback interval")


def _restore_sync_primary_if_due() -> None:
    global _sync_redis_client, _sync_redis_url_index, _sync_redis_fallback_since
    if (
        _sync_redis_url_index != 0
        and _sync_redis_fallback_since
        and time.monotonic() - _sync_redis_fallback_since >= _REDIS_PRIMARY_RETRY_SECONDS
    ):
        _sync_redis_url_index = 0
        _sync_redis_fallback_since = 0.0
        _sync_redis_client = None
        log.info("Retrying primary Redis after fallback interval")


@contextmanager
def distributed_lock(key: str, ttl_seconds: int):
    """Acquire a Redis lock and release it only if this owner still holds it.

    The in-memory fallback is intentionally not treated as a distributed lock.
    Callers continue without coordination when Redis is unavailable.
    """
    client = get_sync_redis_client()
    if client is None:
        yield True
        return

    token = uuid4().hex
    acquired = False
    try:
        try:
            acquired = bool(client.set(key, token, nx=True, ex=max(1, int(ttl_seconds))))
        except Exception as exc:
            log.warning("Redis distributed lock set failed; proceeding without lock: %s", exc)
            yield True
            return
        yield acquired
    finally:
        if acquired:
            try:
                client.eval(
                    "if redis.call('get', KEYS[1]) == ARGV[1] "
                    "then return redis.call('del', KEYS[1]) else return 0 end",
                    1,
                    key,
                    token,
                )
            except Exception:
                log.warning("Could not release distributed lock %s", key, exc_info=True)


def get_redis_client():
    """Get or initialize the async redis client."""
    global _redis_client
    _restore_async_primary_if_due()
    settings = get_settings()
    if not getattr(settings, "REDIS_ENABLED", True):
        return None

    urls = _redis_urls()
    if _redis_client is None and urls:
        try:
            import redis.asyncio as aioredis
            _redis_client = aioredis.from_url(
                urls[_redis_url_index % len(urls)],
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
    _restore_sync_primary_if_due()
    settings = get_settings()
    if not getattr(settings, "REDIS_ENABLED", True):
        return None

    urls = _redis_urls()
    if _sync_redis_client is None and urls:
        try:
            import redis
            _sync_redis_client = redis.from_url(
                urls[_sync_redis_url_index % len(urls)],
                decode_responses=True,
                socket_connect_timeout=2.0,
                socket_timeout=3.0,
            )
        except Exception as exc:
            log.warning("Could not initialize sync Redis client: %s", exc)
            _sync_redis_client = None
    return _sync_redis_client


async def close_async_redis_client() -> None:
    """Close and reset the async pool when a short-lived worker loop exits."""
    global _redis_client
    client, _redis_client = _redis_client, None
    if client is not None:
        try:
            await client.aclose()
        except Exception as exc:
            log.debug("Redis close error: %s", exc)


async def cache_get(key: str) -> Any | None:
    """Get item from Redis, falling back to local memory cache."""
    _restore_async_primary_if_due()
    client = get_redis_client()
    if client and _redis_available_for_attempt():
        try:
            val = await client.get(key)
            _mark_redis_success()
            if val is not None:
                return json.loads(val)
        except Exception as exc:
            _switch_async_redis_url()
            _mark_redis_failure()
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
    _restore_async_primary_if_due()
    client = get_redis_client()
    if client and _redis_available_for_attempt():
        try:
            raw = json.dumps(value, default=str)
            await client.setex(key, ttl_seconds, raw)
            _mark_redis_success()
        except Exception as exc:
            _switch_async_redis_url()
            _mark_redis_failure()
            log.debug("Redis set error for key %s: %s", key, exc)

    _mem_cache[key] = (value, time.monotonic() + ttl_seconds)


async def cache_invalidate(key: str) -> None:
    """Invalidate key in Redis and local memory cache."""
    _restore_async_primary_if_due()
    client = get_redis_client()
    if client and _redis_available_for_attempt():
        try:
            await client.delete(key)
            _mark_redis_success()
        except Exception as exc:
            _switch_async_redis_url()
            _mark_redis_failure()
            log.debug("Redis delete error for key %s: %s", key, exc)
    _mem_cache.pop(key, None)


async def cache_invalidate_pattern(pattern: str) -> None:
    """Invalidate keys matching pattern."""
    _restore_async_primary_if_due()
    client = get_redis_client()
    if client:
        try:
            cursor = 0
            while True:
                cursor, keys = await client.scan(cursor, match=pattern, count=100)
                if keys:
                    await client.delete(*keys)
                if cursor == 0:
                    break
        except Exception as exc:
            log.debug("Redis scan/delete error: %s", exc)

    # Also clean matching keys in memory cache
    import fnmatch
    for k in list(_mem_cache.keys()):
        if fnmatch.fnmatch(k, pattern):
            del _mem_cache[k]


def cache_get_sync(key: str) -> Any | None:
    """Sync version of cache_get for synchronous services."""
    _restore_sync_primary_if_due()
    client = get_sync_redis_client()
    if client and _redis_available_for_attempt():
        try:
            val = client.get(key)
            _mark_redis_success()
            if val is not None:
                return json.loads(val)
        except Exception as exc:
            _switch_sync_redis_url()
            _mark_redis_failure()
            log.debug("Sync Redis get error for key %s: %s", key, exc)

    if key in _mem_cache:
        data, exp = _mem_cache[key]
        if exp > time.monotonic():
            return data
        del _mem_cache[key]
    return None


def cache_set_sync(key: str, value: Any, ttl_seconds: int = 60) -> None:
    """Sync version of cache_set for synchronous services."""
    _restore_sync_primary_if_due()
    client = get_sync_redis_client()
    if client and _redis_available_for_attempt():
        try:
            raw = json.dumps(value, default=str)
            client.setex(key, ttl_seconds, raw)
            _mark_redis_success()
        except Exception as exc:
            _switch_sync_redis_url()
            _mark_redis_failure()
            log.debug("Sync Redis set error for key %s: %s", key, exc)

    _mem_cache[key] = (value, time.monotonic() + ttl_seconds)
