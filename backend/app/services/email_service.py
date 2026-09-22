"""Transactional email service using SendGrid API."""

import json
import logging
from urllib.parse import quote

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class EmailService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL
        self.frontend_url = settings.FRONTEND_URL.rstrip("/")

    async def _send(self, to: str, subject: str, html: str) -> dict:
        if not all((self.api_key, self.from_email)):
            log.error("Email requested but SendGrid is not configured")
            return {"status": "disabled"}

        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self.from_email},
            "subject": subject,
            "content": [{"type": "text/html", "value": html}],
        }

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(
                    SENDGRID_API_URL,
                    json=payload,
                    headers={
                        "Authorization": f"Bearer {self.api_key}",
                        "Content-Type": "application/json",
                    },
                )
            if resp.status_code in (200, 202):
                log.info("Email sent to %s", to)
                return {"status": "sent"}
            else:
                log.error("SendGrid error %s: %s", resp.status_code, resp.text)
                return {"status": "failed", "error": resp.text}
        except Exception:
            log.exception("Failed to send email to %s", to)
            return {"status": "failed"}

    async def send_verification_email(self, recipient: str, token: str) -> dict:
        settings = get_settings()
        verify_url = f"{self.frontend_url}/verify-email?token={quote(token, safe='')}"

        html = f"""
        <h2>Welcome to Basarat!</h2>
        <p>Please verify your email address by clicking the button below:</p>
        <p><a href="{verify_url}" style="display:inline-block;padding:12px 24px;background-color:#4F46E5;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Verify Email</a></p>
        <p>This link will expire in {settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES} minutes.</p>
        <p>If you did not create this account, you can ignore this email.</p>
        """

        return await self._send(recipient, "Verify your Basarat email", html)

    async def send_password_reset_email(self, recipient: str, token: str) -> dict:
        reset_url = f"{self.frontend_url}/reset-password?token={quote(token, safe='')}"

        html = f"""
        <h2>Reset your Basarat password</h2>
        <p>A password reset was requested for your Basarat account.</p>
        <p><a href="{reset_url}" style="display:inline-block;padding:12px 24px;background-color:#4F46E5;color:#ffffff;text-decoration:none;border-radius:6px;font-weight:bold;">Reset Password</a></p>
        <p>This link will expire in 1 hour.</p>
        <p>If you did not request this, you can ignore this email.</p>
        """

        return await self._send(recipient, "Reset your Basarat password", html)
