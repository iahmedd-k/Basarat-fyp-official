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
        settings = get_settings()
        expiry_min = settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES
        html = f"""
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 540px; margin: 0 auto; padding: 32px 24px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; color: #1a202c;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #0f172a; font-size: 24px; font-weight: 700; margin: 0;">Basarat</h1>
                <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Smart PSX Investment Intelligence</p>
            </div>
            <div style="background-color: #f8fafc; border-radius: 8px; padding: 24px; border: 1px solid #e2e8f0;">
                <h2 style="font-size: 18px; color: #1e293b; margin-top: 0; margin-bottom: 12px;">Verify your email address</h2>
                <p style="font-size: 14px; color: #475569; line-height: 1.6; margin-bottom: 20px;">
                    Thank you for joining Basarat. Please enter the verification code below on your app or browser to complete your registration.
                </p>
                <div style="font-size: 36px; font-weight: 800; letter-spacing: 10px; text-align: center; padding: 18px 24px; background-color: #0f172a; color: #38bdf8; border-radius: 8px; font-family: monospace; margin: 20px 0;">
                    {code}
                </div>
                <p style="font-size: 13px; color: #64748b; text-align: center; margin-bottom: 0;">
                    ⏱️ This verification code expires in <strong>{expiry_min} minutes</strong>.
                </p>
            </div>
            <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 24px; line-height: 1.5;">
                If you did not sign up for a Basarat account, please safely ignore this email.
            </p>
        </div>
        """
        return await self._send(recipient, "Verify your Basarat account", html)

    async def send_password_reset_code(self, recipient: str, code: str) -> dict:
        settings = get_settings()
        expiry_min = settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        html = f"""
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 540px; margin: 0 auto; padding: 32px 24px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; color: #1a202c;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #0f172a; font-size: 24px; font-weight: 700; margin: 0;">Basarat</h1>
                <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Security & Account Recovery</p>
            </div>
            <div style="background-color: #f8fafc; border-radius: 8px; padding: 24px; border: 1px solid #e2e8f0;">
                <h2 style="font-size: 18px; color: #1e293b; margin-top: 0; margin-bottom: 12px;">Password Reset Request</h2>
                <p style="font-size: 14px; color: #475569; line-height: 1.6; margin-bottom: 20px;">
                    We received a request to reset the password for your Basarat account. Use the 6-digit code below to proceed:
                </p>
                <div style="font-size: 36px; font-weight: 800; letter-spacing: 10px; text-align: center; padding: 18px 24px; background-color: #0f172a; color: #38bdf8; border-radius: 8px; font-family: monospace; margin: 20px 0;">
                    {code}
                </div>
                <p style="font-size: 13px; color: #64748b; text-align: center; margin-bottom: 0;">
                    ⏱️ This password reset code expires in <strong>{expiry_min} minutes</strong>.
                </p>
            </div>
            <div style="margin-top: 20px; padding: 12px 16px; background-color: #fef2f2; border: 1px solid #fee2e2; border-radius: 6px;">
                <p style="font-size: 12px; color: #991b1b; margin: 0; line-height: 1.4;">
                    🔒 <strong>Security Warning:</strong> Never share this code with anyone. Basarat support will never ask for your code.
                </p>
            </div>
            <p style="font-size: 12px; color: #94a3b8; text-align: center; margin-top: 24px; line-height: 1.5;">
                If you did not request a password reset, you can safely ignore this email or change your password if you suspect unauthorized activity.
            </p>
        </div>
        """
        return await self._send(recipient, "Your Basarat password reset code", html)

    async def send_password_changed_alert(self, recipient: str) -> dict:
        html = """
        <div style="font-family: 'Helvetica Neue', Arial, sans-serif; max-width: 540px; margin: 0 auto; padding: 32px 24px; background-color: #ffffff; border: 1px solid #e2e8f0; border-radius: 12px; color: #1a202c;">
            <div style="text-align: center; margin-bottom: 24px;">
                <h1 style="color: #0f172a; font-size: 24px; font-weight: 700; margin: 0;">Basarat</h1>
                <p style="color: #64748b; font-size: 14px; margin-top: 4px;">Security Alert</p>
            </div>
            <div style="background-color: #f8fafc; border-radius: 8px; padding: 24px; border: 1px solid #e2e8f0;">
                <h2 style="font-size: 18px; color: #1e293b; margin-top: 0; margin-bottom: 12px;">Password Changed Successfully</h2>
                <p style="font-size: 14px; color: #475569; line-height: 1.6; margin-bottom: 12px;">
                    The password for your Basarat account was recently changed. All other active sessions have been terminated for security.
                </p>
                <p style="font-size: 14px; color: #475569; line-height: 1.6;">
                    If you performed this action, no further steps are necessary.
                </p>
            </div>
            <div style="margin-top: 20px; padding: 12px 16px; background-color: #fef2f2; border: 1px solid #fee2e2; border-radius: 6px;">
                <p style="font-size: 12px; color: #991b1b; margin: 0; line-height: 1.4;">
                    ⚠️ If you did not make this change, please contact support or reset your password immediately.
                </p>
            </div>
        </div>
        """
        return await self._send(recipient, "Security Alert: Basarat Password Changed", html)
