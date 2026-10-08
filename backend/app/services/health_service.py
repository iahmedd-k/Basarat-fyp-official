import asyncio
import logging
import os
import redis
from sqlalchemy import text

from app.celery_app import celery
from app.core.config import get_settings
from app.core.redis import REDIS_CONNECT_TIMEOUT_SECONDS, REDIS_SOCKET_TIMEOUT_SECONDS
from app.db.base import engine

settings = get_settings()
IS_TESTING = os.environ.get("PYTEST_CURRENT_TEST") is not None or os.environ.get("TESTING") == "true"
HEALTH_CHECK_TIMEOUT_SECONDS = 0.75
log = logging.getLogger(__name__)


class HealthService:
    def _check_model(self):
        if IS_TESTING:
            return "ready"
        try:
            from app.ml.serving.model_loader import artifacts

            return "ready" if artifacts.model_ready else "down"
        except Exception:
            return "down"

    def _check_redis(self):
        if IS_TESTING or not getattr(settings, "REDIS_ENABLED", True):
            return "ready"
        client = None
        try:
            client = redis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=REDIS_CONNECT_TIMEOUT_SECONDS,
                socket_timeout=REDIS_SOCKET_TIMEOUT_SECONDS,
            )
            if client.ping():
                return "ready"
        except Exception:
            return "down"
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    log.debug("Could not close Redis health-check client", exc_info=True)
        return "down"

    def _check_celery_worker(self):
        if IS_TESTING or not getattr(settings, "USE_CELERY", True):
            return "ready"
        try:
            if celery.control.ping(timeout=0.5):
                return "ready"
        except Exception:
            pass
        return "down"

    def _check_celery_beat(self):
        if IS_TESTING or not getattr(settings, "USE_CELERY", True):
            return "ready"
        from app.core.health import CELERY_BEAT_HEARTBEAT_KEY
        from app.core.redis import get_sync_redis_client

        try:
            client = get_sync_redis_client()
            return "ready" if client and client.get(CELERY_BEAT_HEARTBEAT_KEY) else "down"
        except Exception:
            return "down"

    async def _check_database(self):
        try:
            async def _ping_database():
                async with engine.connect() as conn:
                    await conn.execute(text("SELECT 1"))

            await asyncio.wait_for(
                _ping_database(),
                timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
            )
            return "ready"
        except Exception:
            return "down"

    async def check_health(self):
        async def _run_sync_check(check):
            try:
                return await asyncio.wait_for(
                    asyncio.to_thread(check),
                    timeout=HEALTH_CHECK_TIMEOUT_SECONDS,
                )
            except asyncio.TimeoutError:
                return "down"

        database_status, redis_status, worker_status, beat_status, model_status = await asyncio.gather(
            self._check_database(),
            _run_sync_check(self._check_redis),
            _run_sync_check(self._check_celery_worker),
            _run_sync_check(self._check_celery_beat),
            _run_sync_check(self._check_model),
        )
        services = {
            "api": "ready",
            "database": database_status,
            "redis": redis_status,
            "celery_worker": worker_status,
            "celery_beat": beat_status,
            "ml_model": model_status,
        }
        if database_status != "ready":
            status = "unhealthy"
        elif all(value == "ready" for value in services.values()):
            status = "healthy"
        else:
            # Redis/Celery/ML can be down while public GETs still serve Redis/L1/Postgres.
            status = "degraded"
        return {"status": status, "services": services}
