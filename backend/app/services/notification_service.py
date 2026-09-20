"""Firebase Cloud Messaging delivery for Android devices."""

import logging
from pathlib import Path

from app.core.config import get_settings

log = logging.getLogger(__name__)


class NotificationService:
    """Optional FCM client; disabled configuration never claims delivery."""

    def __init__(self):
        self.settings = get_settings()
        self._messaging = None
        self._ready = False
        self._configure()

    def _configure(self) -> None:
        if not self.settings.FIREBASE_ENABLED:
            return
        credentials_path = Path(self.settings.FIREBASE_CREDENTIALS_PATH)
        if not credentials_path.is_file():
            log.error("Firebase is enabled but credentials file is unavailable")
            return
        try:
            import firebase_admin
            from firebase_admin import credentials, messaging
            if not firebase_admin._apps:
                firebase_admin.initialize_app(credentials.Certificate(str(credentials_path)))
            self._messaging = messaging
            self._ready = True
        except Exception:
            log.exception("Firebase initialization failed; push delivery disabled")

    @property
    def is_configured(self) -> bool:
        return self._ready

    def send_push_notification(self, fcm_token: str, title: str, body: str, data: dict[str, str] | None = None) -> bool:
        if not self._ready or not fcm_token:
            return False
        try:
            message = self._messaging.Message(
                token=fcm_token,
                notification=self._messaging.Notification(title=title, body=body),
                data={str(k): str(v) for k, v in (data or {}).items()},
                android=self._messaging.AndroidConfig(priority="high"),
            )
            self._messaging.send(message)
            return True
        except Exception:
            log.warning("Firebase delivery failed", exc_info=True)
            return False

    def send_bulk_notification(self, tokens: list[str], title: str, body: str, data: dict[str, str] | None = None) -> tuple[int, list[str]]:
        if not self._ready or not tokens:
            return 0, []
        message = self._messaging.MulticastMessage(
            tokens=tokens,
            notification=self._messaging.Notification(title=title, body=body),
            data={str(k): str(v) for k, v in (data or {}).items()},
            android=self._messaging.AndroidConfig(priority="high"),
        )
        try:
            response = self._messaging.send_each_for_multicast(message)
        except Exception:
            log.exception("Firebase multicast delivery failed")
            return 0, []
        invalid_tokens: list[str] = []
        for token, result in zip(tokens, response.responses):
            if not result.success:
                code = getattr(getattr(result, "exception", None), "code", "")
                if code in {"registration-token-not-registered", "invalid-registration-token"}:
                    invalid_tokens.append(token)
        return response.success_count, invalid_tokens
