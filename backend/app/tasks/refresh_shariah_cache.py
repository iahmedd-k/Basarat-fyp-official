"""Pre-warm Shariah index and membership data outside API request handlers."""

from __future__ import annotations

import asyncio
import json
import logging
from uuid import uuid4

from app.celery_app import celery
from app.core.redis import (
    cache_set,
    close_async_redis_client,
    get_sync_redis_client,
    set_dataset_status_sync,
)
from app.schemas.shariah import ShariahKMI30Response, ShariahScreeningDatasetResponse
from app.services.shariah_service import (
    KMI30_MEMBERSHIP_CACHE_KEY,
    PSX_KMI30_SCREENING,
    ShariahService,
)

log = logging.getLogger(__name__)

KMI30_RESPONSE_CACHE_KEY = "shariah:kmi30:constituents"
SCREENING_DATASET_CACHE_KEY = "shariah:screening:dataset:kmi30"
KMI30_CACHE_TTL_SECONDS = 3600
KMI30_MEMBERSHIP_TTL_SECONDS = 86400
LOCK_KEY = "jobs:shariah-cache:refresh-lock"


async def _refresh_shariah_cache() -> dict[str, int]:
    from app.services.market_service import MarketService

    service = ShariahService(None)
    constituents = await service.get_kmi30_constituents()
    if not constituents:
        raise RuntimeError("The dated PSX KMI-30 screening roster is empty")

    snapshot = service.screening_snapshot_freshness()
    response = ShariahKMI30Response(
        index="KMI-30",
        total_constituents=len(constituents),
        as_of=f"{PSX_KMI30_SCREENING['accounts_as_of']}T00:00:00+00:00",
        is_stale=snapshot["data_is_stale"],
        effective_from=snapshot["effective_from"],
        source_url=snapshot["source_url"],
        constituents=constituents,
    )
    await cache_set(
        KMI30_RESPONSE_CACHE_KEY,
        response.model_dump(mode="json"),
        ttl_seconds=KMI30_CACHE_TTL_SECONDS,
    )

    dataset = ShariahScreeningDatasetResponse(
        **service.get_screening_dataset()
    )
    dataset_payload = dataset.model_dump(mode="json")
    await cache_set(
        SCREENING_DATASET_CACHE_KEY,
        dataset_payload,
        ttl_seconds=24 * 60 * 60,
    )
    redis = get_sync_redis_client()
    if redis is None:
        raise RuntimeError("Redis is unavailable while publishing Shariah screening data")
    raw_dataset = redis.get(SCREENING_DATASET_CACHE_KEY)
    if raw_dataset is None:
        raise RuntimeError("Shariah screening dataset was not written to Redis")
    published_dataset = json.loads(raw_dataset)
    if len(published_dataset.get("screenings", [])) != dataset.total:
        raise RuntimeError("Redis contains an incomplete Shariah screening dataset")
    set_dataset_status_sync("shariah_screening", "success")

    market_service = MarketService()
    members = await market_service.get_index_constituents(
        "KMI30",
        force_refresh=True,
        read_only=False,
    )
    freshness = MarketService.constituents_freshness("KMI30")
    if members and not freshness.get("is_stale", True):
        symbols = sorted(
            {
                str(row["symbol"]).strip().upper()
                for row in members
                if row.get("symbol")
            }
        )
        if symbols:
            await cache_set(
                KMI30_MEMBERSHIP_CACHE_KEY,
                symbols,
                ttl_seconds=KMI30_MEMBERSHIP_TTL_SECONDS,
            )
        else:
            log.warning("Fresh PSX KMI-30 constituents did not include symbols")
    else:
        log.warning(
            "Keeping prior KMI-30 membership cache; refresh returned no fresh "
            "constituents (rows=%d, freshness=%s)",
            len(members or []),
            freshness,
        )

    return {
        "screening_constituents": len(constituents),
        "market_constituents": len(members or []),
    }


def _run_async_refresh() -> dict[str, int]:
    async def run() -> dict[str, int]:
        try:
            return await _refresh_shariah_cache()
        finally:
            await close_async_redis_client()

    return asyncio.run(run())


@celery.task(
    name="app.tasks.refresh_shariah_cache.refresh_shariah_cache",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
    soft_time_limit=60,
    time_limit=90,
)
def refresh_shariah_cache(self):
    client = get_sync_redis_client()
    if client is None:
        error = RuntimeError("Redis is unavailable for Shariah cache refresh")
        log.error("%s", error)
        raise self.retry(exc=error)

    token = uuid4().hex
    try:
        acquired = client.set(LOCK_KEY, token, nx=True, ex=90)
    except Exception as exc:
        log.exception("Could not acquire Shariah cache refresh lock")
        raise self.retry(exc=exc)
    if not acquired:
        log.info("Skipping Shariah cache refresh; another task holds the lock")
        return {"status": "skipped", "reason": "already_running"}

    try:
        result = _run_async_refresh()
        log.info("Shariah Redis cache refresh completed: %s", result)
        return {"status": "completed", **result}
    except Exception as exc:
        log.exception("Shariah Redis cache refresh failed")
        raise self.retry(exc=exc)
    finally:
        try:
            client.eval(
                "if redis.call('get', KEYS[1]) == ARGV[1] "
                "then return redis.call('del', KEYS[1]) else return 0 end",
                1,
                LOCK_KEY,
                token,
            )
        except Exception:
            log.exception("Could not release Shariah cache refresh lock")
