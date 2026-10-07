import time

import pytest

from app.services import health_service
from app.services.health_service import HealthService


@pytest.mark.asyncio
async def test_readiness_marks_slow_sync_dependencies_down(monkeypatch):
    monkeypatch.setattr(health_service, "HEALTH_CHECK_TIMEOUT_SECONDS", 0.01)
    service = HealthService()

    async def database_ready():
        return "ready"

    def slow_dependency():
        time.sleep(0.05)
        return "ready"

    monkeypatch.setattr(service, "_check_database", database_ready)
    monkeypatch.setattr(service, "_check_redis", slow_dependency)
    monkeypatch.setattr(service, "_check_celery_worker", slow_dependency)
    monkeypatch.setattr(service, "_check_celery_beat", slow_dependency)
    monkeypatch.setattr(service, "_check_model", slow_dependency)

    result = await service.check_health()

    assert result["status"] == "degraded"
    assert result["services"] == {
        "api": "ready",
        "database": "ready",
        "redis": "down",
        "celery_worker": "down",
        "celery_beat": "down",
        "ml_model": "down",
    }
