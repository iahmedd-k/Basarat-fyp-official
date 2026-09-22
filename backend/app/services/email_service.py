"""Transactional email service using Resend API."""

import logging
from urllib.parse import quote

import resend

from app.core.config import get_settings

log = logging.getLogger(__name__)


class EmailService:
    def __init__(self):
        settings = get_settings()
        self.from_email = settings.RESEND_FROM_EMAIL
        self.frontend_url = settings.FRONTEND_URL.rstrip("/")
        if settings.RESEND_API_KEY:
            resend.api_key = settings.RESEND_API_KEY

    async def send_verification_email(self, recipient: str, token: str) -> dict:
        settings = get_settings()
        if not settings.RESEND_API_KEY or not self.from_email:
            log.error("Verification email requested but Resend is not configured")
            return {"status": "disabled"}

        verify_url = f"{self.frontend_url}/verify-email?token={quote(token, safe='')}"

        html_content = f"""
        <h2>Welcome to Basarat!</h2>
        <p>Thank you for creating an account. Please verify your email address by clicking the button below:</p>
        <p><a href="{verify_url}" style="display:inline-block;padding:12px 24px;background-color:#4F46E5;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Verify Email</a></p>
        <p>This link will expire in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES} minutes.</p>
        <p>If you did not create this account, you can ignore this email.</p>
        """

        try:
            params = resend.Emails.SendParams(
                from_=self.from_email,
                to=[recipient],
                subject="Verify your Basarat email",
                html=html_content,
            )
            result = resend.Emails.send(params)
            log.info("Verification email sent to %s", recipient)
            return {"status": "sent", "id": result.get("id")}
        except Exception:
            log.exception("Failed to send verification email to %s", recipient)
            return {"status": "failed"}

    async def send_password_reset_email(self, recipient: str, token: str) -> dict:
        settings = get_settings()
        if not settings.RESEND_API_KEY or not self.from_email:
            log.error("Password reset email requested but Resend is not configured")
            return {"status": "disabled"}

        reset_url = f"{self.frontend_url}/reset-password?token={quote(token, safe='')}"

        html_content = f"""
        <h2>Reset your Basarat password</h2>
        <p>A password reset was requested for your Basarat account.</p>
        <p><a href="{reset_url}" style="display:inline-block;padding:12px 24px;background-color:#4F46E5;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Reset Password</a></p>
        <p>This link will expire in 1 hour.</p>
        <p>If you did not request this, you can ignore this email.</p>
        """

        try:
            params = resend.Emails.SendParams(
                from_=self.from_email,
                to=[recipient],
                subject="Reset your Basarat password",
                html=html_content,
            )
            result = resend.Emails.send(params)
            log.info("Password reset email sent to %s", recipient)
            return {"status": "sent", "id": result.get("id")}
        except Exception:
            log.exception("Failed to send password reset email to %s", recipient)
            return {"status": "failed"}
