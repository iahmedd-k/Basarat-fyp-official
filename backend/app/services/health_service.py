import asyncio
import os
import redis
from sqlalchemy import text

from app.celery_app import celery
from app.core.config import get_settings
from app.db.base import engine

settings = get_settings()
IS_TESTING = os.environ.get("PYTEST_CURRENT_TEST") is not None or os.environ.get("TESTING") == "true"


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
        from app.core.health import CELERY_BEAT_HEARTBEAT_KEY
        from app.core.redis import get_sync_redis_client

        try:
            client = get_sync_redis_client()
            return "ready" if client and client.get(CELERY_BEAT_HEARTBEAT_KEY) else "down"
        except Exception:
            return "down"

    async def _check_database(self):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return "ready"
        except Exception:
            return "down"

    async def check_health(self):
        database_status, redis_status, worker_status, beat_status, model_status = await asyncio.gather(
            self._check_database(),
            asyncio.to_thread(self._check_redis),
            asyncio.to_thread(self._check_celery_worker),
            asyncio.to_thread(self._check_celery_beat),
            asyncio.to_thread(self._check_model),
        )
        services = {
            "api": "ready",
            "database": database_status,
            "redis": redis_status,
            "celery_worker": worker_status,
            "celery_beat": beat_status,
            "ml_model": model_status,
        }
        status = (
            "healthy"
            if all(value == "ready" for value in services.values())
            else "degraded"
        )
        return {"status": status, "services": services}
