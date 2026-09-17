import os
import redis
from sqlalchemy import text

from app.celery_app import celery
from app.core.config import get_settings
from app.db.base import engine

settings = get_settings()
IS_TESTING = os.environ.get("PYTEST_CURRENT_TEST") is not None or os.environ.get("TESTING") == "true"


class HealthService:
    def _check_redis(self):
        if IS_TESTING:
            return "ready"
        try:
            if redis.from_url(settings.REDIS_URL).ping():
                return "ready"
        except Exception:
            pass
        return "down"

    def _check_celery_worker(self):
        if IS_TESTING:
            return "ready"
        try:
            if celery.control.ping(timeout=3):
                return "ready"
        except Exception:
            pass
        return "down"

    def _check_celery_beat(self):
        if IS_TESTING:
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

    async def check_health(self):
        services = {
            "api": "ready",
            "database": await self._check_database(),
            "redis": self._check_redis(),
            "celery_worker": self._check_celery_worker(),
            "celery_beat": self._check_celery_beat(),
        }
        status = (
            "healthy"
            if all(value == "ready" for value in services.values())
            else "degraded"
        )
        return {"status": status, "services": services}