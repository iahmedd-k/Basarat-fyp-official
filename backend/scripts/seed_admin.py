"""Manual admin seeding script for Basarat backend.

Usage:
    python -m scripts.seed_admin
    python scripts/seed_admin.py --email admin@example.com --password "SecurePass123!" --username admin --full-name "Admin"
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
    parser = argparse.ArgumentParser(description="Seed manual admin credentials in the database.")
    parser.add_argument(
        "--email",
        default=os.getenv("ADMIN_EMAIL", "admin@basarat.pk"),
        help="Admin email address (default: ADMIN_EMAIL env var or admin@basarat.pk)",
    )
    parser.add_argument(
        "--password",
        default=os.getenv("ADMIN_PASSWORD", "Admin1234!"),
        help="Admin password (default: ADMIN_PASSWORD env var or Admin1234!)",
    )
    parser.add_argument(
        "--username",
        default=os.getenv("ADMIN_USERNAME", "admin"),
        help="Admin username (default: ADMIN_USERNAME env var or admin)",
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
