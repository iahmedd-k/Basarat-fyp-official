"""Transactional email tasks."""

import logging
import smtplib
from email.message import EmailMessage
from urllib.parse import quote

from app.celery_app import celery
from app.core.config import get_settings

log = logging.getLogger(__name__)


@celery.task(name="app.tasks.email.send_password_reset_email", bind=True, max_retries=3, default_retry_delay=120, acks_late=True)
def send_password_reset_email(self, recipient: str, raw_token: str) -> dict:
    settings = get_settings()
    if not all((settings.SMTP_HOST, settings.SMTP_FROM_EMAIL, settings.PASSWORD_RESET_URL)):
        log.error("Password reset email requested but SMTP is not configured")
        return {"status": "disabled"}

    reset_url = settings.PASSWORD_RESET_URL.replace("{token}", quote(raw_token, safe=""))
    if "{token}" not in settings.PASSWORD_RESET_URL:
        separator = "&" if "?" in reset_url else "?"
        reset_url = f"{reset_url}{separator}token={quote(raw_token, safe='')}"
    message = EmailMessage()
    message["Subject"] = "Reset your Basarat password"
    message["From"] = settings.SMTP_FROM_EMAIL
    message["To"] = recipient
    message.set_content(
        "A password reset was requested for your Basarat account. "
        f"Use this link within one hour: {reset_url}\n\n"
        "If you did not request this, you can ignore this email."
    )
    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15) as smtp:
            if settings.SMTP_USE_TLS:
                smtp.starttls()
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
        return {"status": "sent"}
    except Exception as exc:
        log.exception("Password reset delivery failed")
        raise self.retry(exc=exc)
