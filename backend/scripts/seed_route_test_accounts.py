"""Provision reproducible local API-test accounts without checked-in passwords.

Create backend/.route-test-secrets (ignored by Git) with E2E_ADMIN_EMAIL,
E2E_ADMIN_USERNAME, E2E_ADMIN_PASSWORD, E2E_USER_EMAIL, E2E_USER_USERNAME,
and E2E_USER_PASSWORD. Then run inside the API container:
    SEED_ROUTE_TEST_ACCOUNTS=1 python -m scripts.seed_route_test_accounts

This command is deliberately restricted to development/test environments.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import or_, select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings
from app.core.security import hash_password
from app.db.base import async_session_factory, engine
from app.models.user import User
from app.models.alert import Alert
from app.models.community import CommunityNotification

log = logging.getLogger("seed_route_test_accounts")


def _load_local_secrets() -> None:
    """Load simple KEY=VALUE pairs from the ignored local credential file."""
    path = BACKEND_DIR / ".route-test-secrets"
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip())


def _account(prefix: str) -> dict[str, str]:
    keys = ("EMAIL", "USERNAME", "PASSWORD")
    values = {key.lower(): os.getenv(f"E2E_{prefix}_{key}", "").strip() for key in keys}
    missing = [f"E2E_{prefix}_{key}" for key in keys if not values[key.lower()]]
    if missing:
        raise RuntimeError("Missing required seed settings: " + ", ".join(missing))
    if len(values["password"]) < 16:
        raise RuntimeError(f"E2E_{prefix}_PASSWORD must be at least 16 characters")
    return values


async def _upsert_account(session, *, email: str, username: str, password: str, full_name: str, is_admin: bool) -> User:
    result = await session.execute(
        select(User).where(or_(User.email == email, User.username == username))
    )
    user = result.scalars().first()
    if user and (user.email.lower() != email.lower() or user.username != username):
        raise RuntimeError(
            f"Seed identity collision for {email!r}/{username!r}; refusing to modify another account"
        )

    if user is None:
        user = User(email=email.lower(), username=username)
        session.add(user)

    user.email = email.lower()
    user.username = username
    user.full_name = full_name
    user.hashed_password = hash_password(password)
    user.is_active = True
    user.is_verified = True
    user.is_admin = is_admin
    return user


async def seed() -> None:
    settings = get_settings()
    if settings.ENVIRONMENT not in {"development", "test"}:
        raise RuntimeError("Refusing to seed route-test users outside development/test")
    if os.getenv("SEED_ROUTE_TEST_ACCOUNTS") != "1":
        raise RuntimeError("Set SEED_ROUTE_TEST_ACCOUNTS=1 to confirm local test-account seeding")

    _load_local_secrets()
    admin = _account("ADMIN")
    test_user = _account("USER")
    if admin["email"].lower() == test_user["email"].lower() or admin["username"] == test_user["username"]:
        raise RuntimeError("Admin and test user must have distinct email addresses and usernames")

    async with async_session_factory() as session:
        admin_row = await _upsert_account(
            session,
            email=admin["email"],
            username=admin["username"],
            password=admin["password"],
            full_name="Route Test Admin",
            is_admin=True,
        )
        user_row = await _upsert_account(
            session,
            email=test_user["email"],
            username=test_user["username"],
            password=test_user["password"],
            full_name="Route Test User",
            is_admin=False,
        )
        await session.flush()

        # A deterministic unread alert lets the notification read routes be
        # exercised without touching a real user's inbox.
        alert_id = uuid5(NAMESPACE_URL, f"basarat-route-test-alert:{user_row.id}").hex
        alert = await session.get(Alert, alert_id)
        if alert is None:
            alert = Alert(
                id=alert_id,
                user_id=user_row.id,
                title="Seeded route-test notification",
                message="Disposable fixture for notification endpoint verification.",
                is_read=False,
            )
            session.add(alert)
        else:
            alert.user_id = user_row.id
            alert.title = "Seeded route-test notification"
            alert.message = "Disposable fixture for notification endpoint verification."
            alert.is_read = False

        community_notification_id = uuid5(
            NAMESPACE_URL, f"basarat-route-test-community-notification:{user_row.id}"
        ).hex
        community_notification = await session.get(CommunityNotification, community_notification_id)
        if community_notification is None:
            community_notification = CommunityNotification(
                id=community_notification_id,
                recipient_id=user_row.id,
                type="USER_FOLLOWED",
                title="Seeded community route-test notification",
                message="Disposable fixture for community notification endpoint verification.",
                is_read=False,
            )
            session.add(community_notification)
        else:
            community_notification.recipient_id = user_row.id
            community_notification.type = "USER_FOLLOWED"
            community_notification.title = "Seeded community route-test notification"
            community_notification.message = "Disposable fixture for community notification endpoint verification."
            community_notification.is_read = False
        await session.commit()
        log.info("Seeded admin account id=%s username=%s", admin_row.id, admin_row.username)
        log.info("Seeded regular test account id=%s username=%s", user_row.id, user_row.username)
        log.info("Seeded unread notification fixture id=%s", alert_id)
        log.info("Seeded unread community notification fixture id=%s", community_notification_id)


async def _run() -> None:
    try:
        await seed()
    finally:
        await engine.dispose()


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    asyncio.run(_run())


if __name__ == "__main__":
    main()
