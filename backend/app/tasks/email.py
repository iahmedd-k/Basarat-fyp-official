"""Transactional email tasks (deprecated — use app.services.email_service instead)."""

import logging

from app.celery_app import celery

log = logging.getLogger(__name__)


@celery.task(name="app.tasks.email.send_password_reset_email", bind=True, max_retries=3, default_retry_delay=120, acks_late=True)
def send_password_reset_email(self, recipient: str, raw_token: str) -> dict:
    """Legacy Celery task — now delegates to EmailService synchronously."""
    from app.services.email_service import EmailService
    from app.core.async_bridge import run_sync

    log.warning("Legacy Celery send_password_reset_email called — use EmailService directly")
    try:
        result = run_sync(EmailService().send_password_reset_email(recipient, raw_token))
        return result
    except Exception as exc:
        log.exception("Password reset delivery failed")
        raise self.retry(exc=exc)
