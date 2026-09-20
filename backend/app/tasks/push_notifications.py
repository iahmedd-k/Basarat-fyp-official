"""Durable FCM delivery tasks for Android device tokens."""

import logging

from app.celery_app import celery

log = logging.getLogger(__name__)


@celery.task(name="app.tasks.push_notifications.send_to_user", bind=True, max_retries=3, default_retry_delay=60, acks_late=True)
def send_to_user(self, user_id: str, title: str, body: str, data: dict[str, str] | None = None) -> dict:
    from sqlalchemy import create_engine, select, update
    from sqlalchemy.orm import Session

    from app.core.config import get_settings
    from app.models.user import Device
    from app.services.notification_service import NotificationService

    service = NotificationService()
    if not service.is_configured:
        return {"status": "disabled", "sent": 0}
    engine = create_engine(get_settings().DATABASE_URL_SYNC, pool_pre_ping=True)
    try:
        with Session(engine) as session:
            tokens = list(session.scalars(select(Device.fcm_token).where(
                Device.user_id == user_id, Device.platform == "android", Device.is_active.is_(True)
            )))
            sent, invalid_tokens = service.send_bulk_notification(tokens, title, body, data)
            if invalid_tokens:
                session.execute(update(Device).where(Device.fcm_token.in_(invalid_tokens)).values(is_active=False))
                session.commit()
            return {"status": "completed", "sent": sent, "deactivated": len(invalid_tokens)}
    except Exception as exc:
        log.exception("Push notification task failed for user %s", user_id)
        raise self.retry(exc=exc)
    finally:
        engine.dispose()
