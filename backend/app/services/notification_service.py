"""Firebase Cloud Messaging delivery for Android devices."""

import logging
from pathlib import Path
from typing import Any

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

    def _build_configs(self, data: dict[str, str] | None = None) -> tuple[Any, Any]:
        """Build Android and APNs configurations with collapse_key and tags for notification grouping."""
        tag = None
        collapse_key = None
        if data:
            symbol = data.get("symbol")
            notif_type = data.get("type") or data.get("notification_type")
            if symbol:
                tag = f"stock_{symbol.upper()}"
                collapse_key = f"stock_{symbol.upper()}"
            elif notif_type:
                tag = f"alert_{notif_type}"
                collapse_key = f"alert_{notif_type}"

        android_config = self._messaging.AndroidConfig(
            priority="high",
            collapse_key=collapse_key,
            notification=self._messaging.AndroidNotification(
                tag=tag,
                channel_id="market_alerts",
                sound="default",
                default_vibrate_timings=True,
            ),
        )
        apns_config = self._messaging.APNSConfig(
            headers={"apns-collapse-id": tag} if tag else None,
            payload=self._messaging.APNSPayload(
                aps=self._messaging.Aps(sound="default", badge=1)
            ),
        )
        return android_config, apns_config

    def send_push_notification(self, fcm_token: str, title: str, body: str, data: dict[str, str] | None = None) -> bool:
        if not self._ready or not fcm_token:
            return False
        try:
            android_config, apns_config = self._build_configs(data)
            message = self._messaging.Message(
                token=fcm_token,
                notification=self._messaging.Notification(title=title, body=body),
                data={str(k): str(v) for k, v in (data or {}).items()},
                android=android_config,
                apns=apns_config,
            )
            self._messaging.send(message)
            return True
        except Exception:
            log.warning("Firebase delivery failed", exc_info=True)
            return False

    def send_bulk_notification(self, tokens: list[str], title: str, body: str, data: dict[str, str] | None = None) -> tuple[int, list[str]]:
        if not self._ready or not tokens:
            return 0, []
        # Deduplicate tokens while preserving order
        unique_tokens = list(dict.fromkeys(t for t in tokens if t))
        if not unique_tokens:
            return 0, []

        android_config, apns_config = self._build_configs(data)
        message = self._messaging.MulticastMessage(
            tokens=unique_tokens,
            notification=self._messaging.Notification(title=title, body=body),
            data={str(k): str(v) for k, v in (data or {}).items()},
            android=android_config,
            apns=apns_config,
        )
        try:
            response = self._messaging.send_each_for_multicast(message)
        except Exception:
            log.exception("Firebase multicast delivery failed")
            return 0, []
        invalid_tokens: list[str] = []
        for token, result in zip(unique_tokens, response.responses):
            if not result.success:
                code = getattr(getattr(result, "exception", None), "code", "")
                if code in {"registration-token-not-registered", "invalid-registration-token"}:
                    invalid_tokens.append(token)
        return response.success_count, invalid_tokens

