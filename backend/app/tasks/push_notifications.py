"""Durable FCM delivery tasks for Android device tokens."""

import logging

from app.celery_app import celery

log = logging.getLogger(__name__)


@celery.task(name="app.tasks.push_notifications.send_to_user", bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def send_to_user(self, user_id: str, title: str, body: str, data: dict[str, str] | None = None) -> dict:
    from sqlalchemy import select, update
    from app.db.base import get_sync_session_factory
    from app.models.user import Device
    from app.services.notification_service import NotificationService

    service = NotificationService()
    if not service.is_configured:
        return {"status": "disabled", "sent": 0}
    session = get_sync_session_factory()()
    redis_client = None
    try:
        from app.core.redis import get_sync_redis_client
        redis_client = get_sync_redis_client()
    except Exception:
        pass

    # Prevent duplicate push delivery if Celery retries this task
    task_id = getattr(self.request, "id", None) if hasattr(self, "request") else None
    idempotency_key = f"fcm:task_delivered:{task_id}" if task_id else None
    already_delivered = False
    if redis_client and idempotency_key:
        try:
            already_delivered = bool(redis_client.get(idempotency_key))
        except Exception:
            pass

    try:
        raw_tokens = list(session.scalars(select(Device.fcm_token).where(
            Device.user_id == user_id,
            Device.is_active.is_(True),
        )))
        # Deduplicate tokens so multiple registered rows don't cause duplicate alerts on the same phone
        tokens = list(dict.fromkeys(t.strip() for t in raw_tokens if t and t.strip()))
        if not tokens:
            return {"status": "no_devices", "sent": 0}

        if already_delivered:
            log.info("Push notification task %s already delivered to FCM; skipping re-send", task_id)
            return {"status": "already_delivered", "sent": len(tokens)}

        sent, invalid_tokens = service.send_bulk_notification(tokens, title, body, data)

        if redis_client and idempotency_key and sent > 0:
            try:
                redis_client.set(idempotency_key, "1", ex=600)
            except Exception:
                pass

        if invalid_tokens:
            session.execute(update(Device).where(Device.fcm_token.in_(invalid_tokens)).values(is_active=False))
            session.commit()
        return {"status": "completed", "sent": sent, "deactivated": len(invalid_tokens)}
    except Exception as exc:
        log.exception("Push notification task failed for user %s", user_id)
        raise self.retry(exc=exc)
    finally:
        session.close()
