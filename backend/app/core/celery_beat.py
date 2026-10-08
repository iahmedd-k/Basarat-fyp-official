import logging
import time
from celery.beat import PersistentScheduler

from app.core.health import (
    CELERY_BEAT_HEARTBEAT_KEY,
    CELERY_BEAT_HEARTBEAT_TTL_SECONDS,
)
from app.core.redis import get_sync_redis_client

logger = logging.getLogger(__name__)


class HeartbeatPersistentScheduler(PersistentScheduler):
    """
    Celery Beat PersistentScheduler that directly records heartbeat in Redis on tick.

    This decouples Celery Beat's health status from Celery Worker availability,
    ensuring that the scheduler is accurately reported as 'ready' whenever the beat
    process is alive and running its schedule loop.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._last_heartbeat_time: float = 0.0

    def setup_schedule(self):
        super().setup_schedule()
        self._record_heartbeat()

    def tick(self, *args, **kwargs):
        now = time.monotonic()
        if now - self._last_heartbeat_time >= 15.0:
            self._record_heartbeat()
        return super().tick(*args, **kwargs)

    def _record_heartbeat(self):
        self._last_heartbeat_time = time.monotonic()
        try:
            client = get_sync_redis_client()
            if client is not None:
                client.set(
                    CELERY_BEAT_HEARTBEAT_KEY,
                    "1",
                    ex=CELERY_BEAT_HEARTBEAT_TTL_SECONDS,
                )
        except Exception as exc:
            logger.debug("Failed to record Celery Beat heartbeat: %s", exc)
