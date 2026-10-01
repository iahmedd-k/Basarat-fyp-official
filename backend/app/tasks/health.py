from celery import shared_task

from app.core.health import (
    CELERY_BEAT_HEARTBEAT_KEY,
    CELERY_BEAT_HEARTBEAT_TTL_SECONDS,
)


@shared_task(name="app.tasks.health.beat_heartbeat")
def beat_heartbeat() -> bool:
    from app.core.redis import get_sync_redis_client

    client = get_sync_redis_client()
    if client is None:
        return False
    return bool(
        client.set(
            CELERY_BEAT_HEARTBEAT_KEY,
            "1",
            ex=CELERY_BEAT_HEARTBEAT_TTL_SECONDS,
        )
    )