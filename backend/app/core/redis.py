"""Centralized Redis cache client with automatic serialization and in-memory fallback."""

import asyncio
import json
import logging
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

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
REDIS_CONNECT_TIMEOUT_SECONDS = 1.5
REDIS_SOCKET_TIMEOUT_SECONDS = 2.0
_L1_TTL_SECONDS = 5.0
_MISSING = object()


def _l1_ttl_seconds(ttl_seconds: int | float | None = None) -> float:
    try:
        configured = float(get_settings().CACHE_L1_TTL_SECONDS)
    except Exception:
        configured = _L1_TTL_SECONDS
    limit = configured if configured > 0 else _L1_TTL_SECONDS
    if ttl_seconds is None:
        return limit
    return max(0.5, min(float(ttl_seconds), limit))


def _mem_get(key: str) -> Any:
    cached = _mem_cache.get(key)
    if cached is None:
        return _MISSING
    data, expires_at = cached
    if expires_at > time.monotonic():
        return data
    _mem_cache.pop(key, None)
    return _MISSING


def _mem_store(key: str, value: Any, ttl_seconds: int | float) -> None:
    _mem_cache[key] = (value, time.monotonic() + _l1_ttl_seconds(ttl_seconds))


def _redis_available_for_attempt() -> bool:
    return time.monotonic() >= _redis_retry_after


def _mark_redis_failure(*, retry_primary: bool = True) -> None:
    global _redis_retry_after
    _redis_retry_after = (
        time.monotonic() + _REDIS_FAILURE_BACKOFF_SECONDS
        if retry_primary
        else 0.0
    )


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


def _switch_async_redis_url() -> bool:
    global _redis_client, _redis_url_index, _redis_fallback_since, _redis_retry_after
    urls = _redis_urls()
    if len(urls) > 1 and _redis_url_index == 0:
        _redis_url_index = 1
        _redis_client = None
        _redis_fallback_since = time.monotonic()
        _redis_retry_after = 0.0
        log.warning("Primary Redis unavailable; switching to configured Redis fallback")
        return True
    return False


def _switch_sync_redis_url() -> bool:
    global _sync_redis_client, _sync_redis_url_index, _sync_redis_fallback_since
    global _redis_retry_after
    urls = _redis_urls()
    if len(urls) > 1 and _sync_redis_url_index == 0:
        _sync_redis_url_index = 1
        _sync_redis_client = None
        _sync_redis_fallback_since = time.monotonic()
        _redis_retry_after = 0.0
        log.warning("Primary Redis unavailable; switching to configured Redis fallback")
        return True
    return False


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
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
                socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
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
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
                socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
            )
        except Exception as exc:
            log.warning("Could not initialize sync Redis client: %s", exc)
            _sync_redis_client = None
    return _sync_redis_client


async def redis_is_available() -> bool:
    """Check Redis before serving cache-only snapshots from an API request."""
    _restore_async_primary_if_due()
    for attempt in range(2):
        client = get_redis_client()
        if client is None or not _redis_available_for_attempt():
            return False
        try:
            await client.ping()
            _mark_redis_success()
            return True
        except Exception as exc:
            switched = _switch_async_redis_url()
            _mark_redis_failure(retry_primary=not switched)
            if switched and attempt == 0:
                continue
            log.warning(
                "Redis health check failed; request should compute data directly: %s",
                exc,
            )
            return False
    return False


def dataset_status_key(dataset: str, status_date: str | None = None) -> str:
    """Build an independent daily readiness key for one published dataset."""
    if status_date is None:
        status_date = datetime.now(ZoneInfo("Asia/Karachi")).date().isoformat()
    return f"datasets:{dataset}:status:{status_date}"


def set_dataset_status_sync(
    dataset: str,
    status: str,
    *,
    status_date: str | None = None,
    ttl_seconds: int = 36 * 60 * 60,
) -> None:
    """Persist and verify a dataset-specific job status in shared Redis."""
    client = get_sync_redis_client()
    if client is None:
        raise RuntimeError(f"Redis is unavailable while marking {dataset} as {status}")
    key = dataset_status_key(dataset, status_date)
    for attempt in range(2):
        try:
            client.set(key, status, ex=ttl_seconds)
            if client.get(key) != status:
                raise RuntimeError(f"Redis did not persist {dataset} status={status}")
            return
        except Exception:
            if attempt == 0:
                switched = _switch_sync_redis_url()
                _mark_redis_failure(retry_primary=not switched)
                if switched:
                    client = get_sync_redis_client()
                    if client is not None:
                        continue
            raise
    raise RuntimeError(f"Redis did not persist {dataset} status={status}")


async def dataset_refresh_ready(dataset: str) -> bool:
    """Return whether today's scheduled refresh for this dataset completed."""
    if not await redis_is_available():
        return False

    now_pkt = datetime.now(ZoneInfo("Asia/Karachi"))
    if now_pkt.weekday() >= 5:
        return True

    try:
        from app.services.news_pipeline.market_schedule import is_holiday

        if await is_holiday():
            return True
    except Exception as exc:
        log.warning("Could not verify exchange holiday before cache use: %s", exc)
        return False

    client = get_redis_client()
    if client is None or not _redis_available_for_attempt():
        return False
    status_key = dataset_status_key(dataset, now_pkt.date().isoformat())
    try:
        return await client.get(status_key) == "success"
    except Exception as exc:
        switched = _switch_async_redis_url()
        _mark_redis_failure(retry_primary=not switched)
        log.warning("Could not read pre-market refresh status; request should compute directly: %s", exc)
        return False


async def market_intelligence_cache_ready() -> bool:
    """Compatibility helper: require both forecast and recommendation datasets."""
    forecasts_ready, recommendations_ready = await asyncio.gather(
        dataset_refresh_ready("forecasts"),
        dataset_refresh_ready("recommendations"),
    )
    return forecasts_ready and recommendations_ready


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
    """Get item from L1 memory first, then Redis."""
    local = _mem_get(key)
    if local is not _MISSING:
        return local

    _restore_async_primary_if_due()
    for attempt in range(2):
        client = get_redis_client()
        if not client or not _redis_available_for_attempt():
            return None
        try:
            val = await client.get(key)
            _mark_redis_success()
            if val is not None:
                parsed = json.loads(val)
                _mem_store(key, parsed, _L1_TTL_SECONDS)
                return parsed
        except Exception as exc:
            switched = _switch_async_redis_url()
            _mark_redis_failure(retry_primary=not switched)
            if switched and attempt == 0:
                continue
            log.debug("Redis get error for key %s: %s", key, exc)
            return None
    return None


async def cache_get_many(keys: list[str]) -> dict[str, Any]:
    """Get multiple values from L1, then one Redis MGET for the remainder."""
    unique_keys = list(dict.fromkeys(keys))
    if not unique_keys:
        return {}

    values: dict[str, Any] = {}
    missing: list[str] = []
    for key in unique_keys:
        local = _mem_get(key)
        if local is not _MISSING:
            values[key] = local
        else:
            missing.append(key)

    client = get_redis_client()
    if missing and client and _redis_available_for_attempt():
        try:
            cached_values = await client.mget(missing)
            _mark_redis_success()
            for key, value in zip(missing, cached_values):
                if value is None:
                    continue
                parsed = json.loads(value)
                values[key] = parsed
                _mem_store(key, parsed, _L1_TTL_SECONDS)
        except Exception as exc:
            switched = _switch_async_redis_url()
            _mark_redis_failure(retry_primary=not switched)
            log.debug("Redis multi-get error: %s", exc)

    return values


async def cache_set(key: str, value: Any, ttl_seconds: int = 60) -> None:
    """Set item in Redis (full TTL) and L1 (short TTL unless Redis is down)."""
    redis_ok = False
    _restore_async_primary_if_due()
    raw = json.dumps(value, default=str)
    for attempt in range(2):
        client = get_redis_client()
        if not client or not _redis_available_for_attempt():
            break
        try:
            await client.setex(key, ttl_seconds, raw)
            _mark_redis_success()
            redis_ok = True
            break
        except Exception as exc:
            switched = _switch_async_redis_url()
            _mark_redis_failure(retry_primary=not switched)
            if switched and attempt == 0:
                continue
            log.debug("Redis set error for key %s: %s", key, exc)
            break

    l1_ttl = _l1_ttl_seconds() if redis_ok else float(ttl_seconds)
    _mem_cache[key] = (value, time.monotonic() + l1_ttl)


async def cache_invalidate(key: str) -> None:
    """Invalidate key in Redis and local memory cache."""
    _restore_async_primary_if_due()
    client = get_redis_client()
    if client and _redis_available_for_attempt():
        try:
            await client.delete(key)
            _mark_redis_success()
        except Exception as exc:
            switched = _switch_async_redis_url()
            _mark_redis_failure(retry_primary=not switched)
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
                cursor, keys = await client.scan(cursor, match=pattern, count=500)
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
    local = _mem_get(key)
    if local is not _MISSING:
        return local

    _restore_sync_primary_if_due()
    for attempt in range(2):
        client = get_sync_redis_client()
        if not client or not _redis_available_for_attempt():
            return None
        try:
            val = client.get(key)
            _mark_redis_success()
            if val is not None:
                parsed = json.loads(val)
                _mem_store(key, parsed, _L1_TTL_SECONDS)
                return parsed
        except Exception as exc:
            switched = _switch_sync_redis_url()
            _mark_redis_failure(retry_primary=not switched)
            if switched and attempt == 0:
                continue
            log.debug("Sync Redis get error for key %s: %s", key, exc)
            return None
    return None


def cache_set_sync(key: str, value: Any, ttl_seconds: int = 60) -> None:
    """Sync version of cache_set for synchronous services."""
    redis_ok = False
    _restore_sync_primary_if_due()
    raw = json.dumps(value, default=str)
    for attempt in range(2):
        client = get_sync_redis_client()
        if not client or not _redis_available_for_attempt():
            break
        try:
            client.setex(key, ttl_seconds, raw)
            _mark_redis_success()
            redis_ok = True
            break
        except Exception as exc:
            switched = _switch_sync_redis_url()
            _mark_redis_failure(retry_primary=not switched)
            if switched and attempt == 0:
                continue
            log.debug("Sync Redis set error for key %s: %s", key, exc)
            break

    l1_ttl = _l1_ttl_seconds() if redis_ok else float(ttl_seconds)
    _mem_cache[key] = (value, time.monotonic() + l1_ttl)
