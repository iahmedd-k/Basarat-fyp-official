"""Central, scheduled refresh of shared PSX market snapshots."""

import asyncio
import logging
from uuid import uuid4

from app.celery_app import celery

log = logging.getLogger(__name__)


@celery.task(
    name="app.tasks.refresh_market_cache.refresh_market_cache",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def refresh_market_cache(self, refresh_reference: bool = False, refresh_constituents: bool = False):
    """Refresh PSX once in a worker; API handlers only read shared cache."""
    lock_client = None
    lock_token = uuid4().hex
    lock_key = "jobs:market-cache:lock"
    try:
        from app.core.redis import get_sync_redis_client
        lock_client = get_sync_redis_client()
        if lock_client and not lock_client.set(lock_key, lock_token, nx=True, ex=900):
            log.info("Skipping market refresh; another worker holds the refresh lock")
            return {"status": "skipped", "reason": "already_running"}
    except Exception as exc:
        log.warning("Redis market refresh lock unavailable; continuing without distributed lock: %s", exc)
        lock_client = None

    async def _refresh():
        from app.services.market_service import MarketService

        service = MarketService()
        results = {"quotes": 0, "indices": 0, "constituents": {}}
        try:
            quotes = await service.get_market_data(force_refresh=True, read_only=False)
            results["quotes"] = len(quotes)

            if refresh_reference:
                indices = await service.get_indices(force_refresh=True, read_only=False)
                results["indices"] = len(indices)

            if refresh_constituents:
                for code in ("KSE100",):
                    values = await service.get_index_constituents(
                        code, force_refresh=True, read_only=False
                    )
                    results["constituents"][code] = len(values)
            return results
        finally:
            # Celery tasks use a short-lived asyncio loop. Do not retain an
            # async Redis connection pool bound to the loop after it closes.
            from app.core.redis import close_async_redis_client
            await close_async_redis_client()

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_refresh())
        log.info("PSX market cache refresh completed: %s", result)
        return {"status": "completed", **result}
    except Exception as exc:
        log.exception("PSX market cache refresh failed")
        raise self.retry(exc=exc)
    finally:
        loop.close()
        if lock_client:
            try:
                lock_client.eval(
                    "if redis.call('get', KEYS[1]) == ARGV[1] then return redis.call('del', KEYS[1]) else return 0 end",
                    1, lock_key, lock_token,
                )
            except Exception:
                log.warning("Could not release market refresh lock", exc_info=True)
