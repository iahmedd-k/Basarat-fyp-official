"""Transactional email service using SendGrid API."""

import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


class EmailService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL

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

    async def send_verification_code(self, recipient: str, code: str) -> dict:
        html = (
            "<h2>Verify your email</h2>"
            "<p>Your verification code is:</p>"
            f'<p style="font-size:32px;font-weight:bold;letter-spacing:8px;text-align:center;'
            f'padding:20px;background:#f4f4f4;border-radius:8px;">{code}</p>'
            "<p>This code expires in <b>1 minute</b>.</p>"
            "<p>If you did not create this account, ignore this email.</p>"
        )
        return await self._send(recipient, "Your Basarat verification code", html)

    async def send_password_reset_code(self, recipient: str, code: str) -> dict:
        html = (
            "<h2>Reset your password</h2>"
            "<p>Your password reset code is:</p>"
            f'<p style="font-size:32px;font-weight:bold;letter-spacing:8px;text-align:center;'
            f'padding:20px;background:#f4f4f4;border-radius:8px;">{code}</p>'
            "<p>This code expires in <b>1 minute</b>.</p>"
            "<p>If you did not request this, ignore this email.</p>"
        )
        return await self._send(recipient, "Your Basarat password reset code", html)
