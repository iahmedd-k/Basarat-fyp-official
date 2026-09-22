"""Manual admin seeding script for Basarat backend.

Usage (development/test only):
    Set ALLOW_ADMIN_SEED=1 and provide ADMIN_EMAIL, ADMIN_PASSWORD, and ADMIN_USERNAME.
    Prefer `python -m scripts.seed_route_test_accounts` to provision both route-test accounts.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path
from uuid import uuid4

# Ensure backend root is on sys.path
backend_dir = Path(__file__).resolve().parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from sqlalchemy import select
from app.core.security import hash_password
from app.core.config import get_settings
from app.db.base import async_session_factory, engine
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("seed_admin")


async def seed_admin_user(
    email: str,
    password: str,
    username: str,
    full_name: str | None = None,
) -> User:
    """Seed or update the single admin account in the database."""
    async with async_session_factory() as session:
        # Check by email or username
        stmt = select(User).where((User.email == email) | (User.username == username))
        result = await session.execute(stmt)
        user = result.scalars().first()

        if user and (user.email.lower() != email.lower() or user.username != username):
            raise RuntimeError(
                "The requested admin email/username conflicts with a different account; refusing to modify it."
            )

        password_hashed = hash_password(password)

        if user:
            log.info("Existing user '%s' (%s) found. Updating credentials and assigning admin role...", user.username, user.email)
            user.email = email
            user.username = username
            if full_name:
                user.full_name = full_name
            user.hashed_password = password_hashed
            user.is_admin = True
            user.is_active = True
            user.is_verified = True
        else:
            log.info("Creating new admin user '%s' (%s)...", username, email)
            user = User(
                id=str(uuid4()),
                email=email,
                username=username,
                full_name=full_name or "System Administrator",
                hashed_password=password_hashed,
                is_admin=True,
                is_active=True,
                is_verified=True,
            )
            session.add(user)

        await session.commit()
        await session.refresh(user)
        log.info("Admin account successfully provisioned: ID=%s, username=%s, email=%s, is_admin=%s", user.id, user.username, user.email, user.is_admin)
        return user


def main():
    if os.getenv("ALLOW_ADMIN_SEED") != "1":
        raise SystemExit("Set ALLOW_ADMIN_SEED=1 to explicitly enable admin seeding.")
    if get_settings().ENVIRONMENT not in {"development", "test"}:
        raise SystemExit("Refusing to seed an admin account outside development/test.")

    parser = argparse.ArgumentParser(description="Seed manual admin credentials in the database.")
    parser.add_argument(
        "--email",
        default=os.getenv("ADMIN_EMAIL"),
        required=not bool(os.getenv("ADMIN_EMAIL")),
        help="Admin email address (or ADMIN_EMAIL environment variable)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("ADMIN_PASSWORD"),
        required=not bool(os.getenv("ADMIN_PASSWORD")),
        help="Admin password (or ADMIN_PASSWORD environment variable)",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("ADMIN_USERNAME"),
        required=not bool(os.getenv("ADMIN_USERNAME")),
        help="Admin username (or ADMIN_USERNAME environment variable)",
    )
    parser.add_argument(
        "--full-name",
        default=os.getenv("ADMIN_FULL_NAME", "System Administrator"),
        help="Admin full name (default: ADMIN_FULL_NAME env var or System Administrator)",
    )

    args = parser.parse_args()

    async def _run():
        try:
            await seed_admin_user(
                email=args.email.strip(),
                password=args.password,
                username=args.username.strip(),
                full_name=args.full_name.strip() if args.full_name else None,
            )
        finally:
            await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
