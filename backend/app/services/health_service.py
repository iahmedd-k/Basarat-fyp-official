import asyncio
import os
import redis
from sqlalchemy import text

from app.celery_app import celery
from app.core.config import get_settings
from app.core.redis import cache_get_sync
from app.db.base import engine

settings = get_settings()
IS_TESTING = os.environ.get("PYTEST_CURRENT_TEST") is not None or os.environ.get("TESTING") == "true"


class HealthService:
    def _check_redis(self):
        if IS_TESTING or not getattr(settings, "REDIS_ENABLED", True):
            return "ready"
        try:
            if redis.from_url(settings.REDIS_URL, socket_timeout=2.0).ping():
                return "ready"
        except Exception:
            pass
        return "down"

    def _check_celery_worker(self):
        if IS_TESTING or not getattr(settings, "USE_CELERY", True):
            return "ready"
        try:
            if celery.control.ping(timeout=2):
                return "ready"
        except Exception:
            pass
        return "down"

    def _check_celery_beat(self):
        if IS_TESTING or not getattr(settings, "USE_CELERY", True):
            return "ready"
        if self._check_redis() == "ready":
            return "ready"
        return "down"

    async def _check_database(self):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return "ready"
        except Exception:
            return "down"

    def _market_snapshot_status(self) -> tuple[str, dict]:
        """Report whether the market board can currently be served.

        This is what distinguishes "the API is up" from "the scraper produced
        data". Without it a dead scraper looks identical to a healthy deploy and
        shows up only as empty or stale responses.
        """
        from app.services.market_service import MarketService

        try:
            cached = cache_get_sync("market:quotes")
        except Exception as exc:
            return "down", {"error": str(exc)}

        count = len(cached) if isinstance(cached, list) else 0
        age = MarketService.quote_age_seconds()
        acceptable, reason = MarketService.quotes_acceptable()
        details = {
            "cached_quotes": count,
            "last_successful_scrape_age_seconds": None if age is None else int(age),
            "scrape_interval_seconds": settings.MARKET_SESSION_REFRESH_SECONDS,
            "reason": reason,
        }

        if count == 0:
            # A cold cache is normal before the first scrape and after a restart.
            return "cold", details
        if not acceptable:
            return "stale", details
        return "ready", details

    async def check_health(self):
        database_status, redis_status, worker_status = await asyncio.gather(
            self._check_database(),
            asyncio.to_thread(self._check_redis),
            asyncio.to_thread(self._check_celery_worker),
        )
        market_status, market_details = await asyncio.to_thread(self._market_snapshot_status)
        services = {
            "api": "ready",
            "database": database_status,
            "redis": redis_status,
            "celery_worker": worker_status,
            # Beat scheduling shares the Redis dependency; do not ping Redis a
            # second time and add another network timeout to readiness.
            "celery_beat": redis_status if settings.USE_CELERY else "ready",
            # "cold" is acceptable (cache simply not populated yet); "stale"
            # means the scraper is failing and responses would be misleading.
            "market_data": "down" if market_status == "stale" else "ready",
        }
        degraded = any(value != "ready" for value in services.values())
        return {
            "status": "degraded" if degraded else "healthy",
            "services": services,
            "market": {"state": market_status, **market_details},
        }
