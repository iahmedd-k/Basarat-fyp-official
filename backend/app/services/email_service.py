"""Transactional email service using SendGrid API."""

import html
import logging

import httpx

from app.core.config import get_settings

log = logging.getLogger(__name__)

SENDGRID_API_URL = "https://api.sendgrid.com/v3/mail/send"


def _render_email(
    preheader: str,
    category: str,
    title: str,
    body: str,
    footer: str,
) -> str:
    return f"""\
<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <meta name="color-scheme" content="light">
    <title>{html.escape(title)}</title>
</head>
<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:Arial,Helvetica,sans-serif;color:#172033;">
    <div style="display:none;max-height:0;overflow:hidden;opacity:0;color:transparent;">{html.escape(preheader)}</div>
    <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="100%" style="background-color:#f1f5f9;">
        <tr>
            <td align="center" style="padding:32px 16px;">
                <table role="presentation" cellpadding="0" cellspacing="0" border="0" width="600" style="width:100%;max-width:600px;background-color:#ffffff;border:1px solid #e2e8f0;border-radius:12px;overflow:hidden;">
                    <tr>
                        <td style="padding:24px 32px;background-color:#0f172a;border-bottom:3px solid #38bdf8;">
                            <div style="font-size:24px;line-height:30px;font-weight:700;letter-spacing:-0.4px;color:#ffffff;">Basarat</div>
                            <div style="padding-top:4px;font-size:13px;line-height:19px;color:#cbd5e1;">Smart PSX Investment Intelligence</div>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:32px;">
                            <div style="margin-bottom:10px;font-size:12px;line-height:18px;font-weight:700;letter-spacing:1.2px;text-transform:uppercase;color:#0284c7;">{html.escape(category)}</div>
                            <h1 style="margin:0 0 16px;font-size:24px;line-height:32px;font-weight:700;color:#0f172a;">{html.escape(title)}</h1>
                            {body}
                        </td>
                    </tr>
                    <tr>
                        <td style="padding:20px 32px;background-color:#f8fafc;border-top:1px solid #e2e8f0;">
                            <p style="margin:0;font-size:12px;line-height:19px;color:#64748b;">{footer}</p>
                            <p style="margin:12px 0 0;font-size:11px;line-height:17px;color:#94a3b8;">This is an automated message from Basarat. Please do not reply to this email.</p>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""


def _code_panel(code: str, label: str, expiry_min: int) -> str:
    return f"""\
<div style="margin:24px 0;padding:20px 16px;text-align:center;background-color:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;">
    <div style="margin-bottom:10px;font-size:11px;line-height:16px;font-weight:700;letter-spacing:1.4px;color:#64748b;">{html.escape(label)}</div>
    <div style="font-family:Consolas,'Courier New',monospace;font-size:34px;line-height:42px;font-weight:700;letter-spacing:8px;color:#0f172a;">{html.escape(code)}</div>
    <div style="margin-top:10px;font-size:13px;line-height:19px;color:#64748b;">Expires in {expiry_min} minutes</div>
</div>
"""


class EmailService:
    def __init__(self):
        settings = get_settings()
        self.api_key = settings.SENDGRID_API_KEY
        self.from_email = settings.SENDGRID_FROM_EMAIL

    async def _send(self, to: str, subject: str, html_content: str, text_content: str) -> dict:
        if not all((self.api_key, self.from_email)):
            log.error("Email requested but SendGrid is not configured")
            return {"status": "disabled"}

        payload = {
            "personalizations": [{"to": [{"email": to}]}],
            "from": {"email": self.from_email},
            "subject": subject,
            "content": [
                {"type": "text/plain", "value": text_content},
                {"type": "text/html", "value": html_content},
            ],
        }

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
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
        expiry_min = get_settings().EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES
        html_content = _render_email(
            "Use your verification code to finish creating your Basarat account.",
            "Account verification",
            "Verify your email address",
            f"""\
<p style="margin:0;font-size:15px;line-height:24px;color:#475569;">Thank you for creating a Basarat account. Enter this code in the app to verify your email address and complete registration.</p>
{_code_panel(code, "VERIFICATION CODE", expiry_min)}
<p style="margin:0;font-size:14px;line-height:22px;color:#475569;">For your security, do not share this code with anyone.</p>
""",
            "If you did not create a Basarat account, you can ignore this message.",
        )
        text_content = (
            "Basarat — Verify your email address\n\n"
            "Enter this code in the app to complete registration:\n"
            f"{code}\n\n"
            f"This code expires in {expiry_min} minutes. Do not share it with anyone.\n\n"
            "If you did not create a Basarat account, you can ignore this message."
        )
        return await self._send(
            recipient, "Verify your Basarat account", html_content, text_content
        )

    async def send_email_change_code(self, recipient: str, code: str) -> dict:
        expiry_min = get_settings().EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES
        html_content = _render_email(
            "Confirm the email address change requested for your Basarat account.",
            "Account security",
            "Confirm your new email address",
            f"""\
<p style="margin:0;font-size:15px;line-height:24px;color:#475569;">A request was made to change the email address on your Basarat account. Enter this code in your profile to confirm this address.</p>
{_code_panel(code, "CONFIRMATION CODE", expiry_min)}
<p style="margin:0;font-size:14px;line-height:22px;color:#475569;">Do not share this code. Your email address will not change until you confirm it in your profile.</p>
""",
            "If you did not request this change, ignore this message. Your email address will remain unchanged.",
        )
        text_content = (
            "Basarat — Confirm your new email address\n\n"
            "Enter this code in your profile to confirm the change:\n"
            f"{code}\n\n"
            f"This code expires in {expiry_min} minutes. Do not share it.\n"
            "Your email address will not change until you confirm it.\n\n"
            "If you did not request this change, ignore this message. Your email address will remain unchanged."
        )
        return await self._send(
            recipient, "Confirm your new Basarat email", html_content, text_content
        )

    async def send_password_reset_code(self, recipient: str, code: str) -> dict:
        expiry_min = get_settings().PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
        html_content = _render_email(
            "Use your password reset code to continue securing your Basarat account.",
            "Account recovery",
            "Reset your password",
            f"""\
<p style="margin:0;font-size:15px;line-height:24px;color:#475569;">We received a request to reset the password for your Basarat account. Enter this code in the app to continue.</p>
{_code_panel(code, "PASSWORD RESET CODE", expiry_min)}
<div style="margin-top:20px;padding:14px 16px;background-color:#fff7ed;border-left:3px solid #f59e0b;border-radius:4px;">
    <p style="margin:0;font-size:14px;line-height:21px;color:#9a3412;"><strong>Keep this code private.</strong> Basarat will never ask you to share it.</p>
</div>
""",
            "If you did not request a password reset, ignore this message. Your password will remain unchanged.",
        )
        text_content = (
            "Basarat — Reset your password\n\n"
            "Enter this code in the app to continue:\n"
            f"{code}\n\n"
            f"This code expires in {expiry_min} minutes. Keep it private; Basarat will never ask you to share it.\n\n"
            "If you did not request a password reset, ignore this message. Your password will remain unchanged."
        )
        return await self._send(
            recipient, "Your Basarat password reset code", html_content, text_content
        )

    async def send_password_changed_alert(self, recipient: str) -> dict:
        html_content = _render_email(
            "A password change was completed for your Basarat account.",
            "Security alert",
            "Your password was changed",
            """\
<p style="margin:0;font-size:15px;line-height:24px;color:#475569;">The password for your Basarat account was changed successfully. All other active sessions have been signed out.</p>
<div style="margin-top:20px;padding:14px 16px;background-color:#fef2f2;border-left:3px solid #ef4444;border-radius:4px;">
    <p style="margin:0;font-size:14px;line-height:21px;color:#991b1b;"><strong>Wasn't this you?</strong> Reset your password immediately to secure your account.</p>
</div>
""",
            "This security notification was sent because your Basarat account password changed.",
        )
        text_content = (
            "Basarat — Your password was changed\n\n"
            "The password for your Basarat account was changed successfully. "
            "All other active sessions have been signed out.\n\n"
            "If you did not make this change, reset your password immediately to secure your account."
        )
        return await self._send(
            recipient,
            "Security alert: Your Basarat password was changed",
            html_content,
            text_content,
        )
