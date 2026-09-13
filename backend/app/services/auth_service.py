# app/services/auth_service.py
import re
import unicodedata
from uuid import uuid4
import secrets
from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, create_access_token, create_refresh_token
from app.models.user import User
from app.schemas.user import SignupRequest


from datetime import datetime, timezone

from app.core.security import decode_token
from app.cache.redis_client import redis_client
from app.schemas.user import RefreshRequest


from app.core.config import get_settings
from app.models.password_reset_token import PasswordResetToken
from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest

settings = get_settings()

def _slugify_username_base(email: str, full_name: str) -> str:
    """Derive a username seed from full_name (fallback: email local-part)."""
    source = full_name.strip() or email.split("@")[0]
    normalized = unicodedata.normalize("NFKD", source).encode("ascii", "ignore").decode()
    slug = re.sub(r"[^a-zA-Z0-9]+", "", normalized).lower()
    return slug[:80] or "user"


async def _generate_unique_username(db: AsyncSession, email: str, full_name: str) -> str:
    base = _slugify_username_base(email, full_name)
    candidate = base
    while True:
        result = await db.execute(select(User.id).where(User.username == candidate))
        if result.scalar_one_or_none() is None:
            return candidate
        candidate = f"{base}{uuid4().hex[:6]}"


async def create_user(db: AsyncSession, payload: SignupRequest) -> User:
    existing = await db.execute(select(User).where(User.email == payload.email))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    username = await _generate_unique_username(db, payload.email, payload.full_name)

    user = User(
        email=payload.email,
        username=username,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


def issue_tokens(user: User) -> tuple[str, str]:
    access = create_access_token({"sub": user.id})
    refresh = create_refresh_token({"sub": user.id})
    return access, refresh


from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
)
from app.schemas.user import SignupRequest, LoginRequest


async def authenticate_user(db: AsyncSession, payload: LoginRequest) -> User:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Deliberately identical error for "no such user" and "wrong password" —
    # don't let a caller enumerate registered emails.
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is disabled",
        )

    return user    





def _blacklist_key(jti: str) -> str:
    return f"blacklist:refresh:{jti}"


async def _blacklist_jti(jti: str, exp_timestamp: float) -> None:
    ttl = int(exp_timestamp - datetime.now(timezone.utc).timestamp())
    if ttl > 0:
        await redis_client.set(_blacklist_key(jti), "1", ex=ttl)


async def rotate_refresh_token(db: AsyncSession, payload: RefreshRequest) -> tuple[str, str]:
    decoded = decode_token(payload.refresh_token)
    if decoded is None or decoded.get("type") != "refresh":
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid refresh token")

    jti = decoded.get("jti")
    if jti is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Malformed refresh token")

    if await redis_client.get(_blacklist_key(jti)):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Refresh token has been revoked")

    user_id = decoded.get("sub")
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "User no longer valid")

    # rotation: this refresh token can never be used again, even if replayed
    await _blacklist_jti(jti, decoded["exp"])

    new_access = create_access_token({"sub": user.id})
    new_refresh = create_refresh_token({"sub": user.id})
    return new_access, new_refresh


async def revoke_refresh_token(payload: RefreshRequest) -> None:
    decoded = decode_token(payload.refresh_token)
    if decoded is None or decoded.get("type") != "refresh":
        # Logout is idempotent — an already-invalid token is still a "successful" logout
        return
    jti = decoded.get("jti")
    if jti:
        await _blacklist_jti(jti, decoded["exp"])




async def request_password_reset(db: AsyncSession, payload: ForgotPasswordRequest) -> None:
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()

    # Deliberately do nothing detectable if the email doesn't exist — the
    # endpoint always returns 200 either way, so a caller can't use this to
    # discover which emails are registered.
    if user is None:
        return

    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + timedelta(minutes=15)

    reset_token = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
    db.add(reset_token)
    await db.flush()

    # TODO: send `token` via email once email delivery is wired up.
    # For now, log it so it's usable during development/testing.
    print(f"[password-reset] user={user.email} token={token} expires_at={expires_at.isoformat()}")


async def reset_password(db: AsyncSession, payload: ResetPasswordRequest) -> None:
    result = await db.execute(
        select(PasswordResetToken).where(PasswordResetToken.token == payload.token)
    )
    reset_token = result.scalar_one_or_none()

    if (
        reset_token is None
        or reset_token.used
        or reset_token.expires_at < datetime.utcnow()
    ):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    user_result = await db.execute(select(User).where(User.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Invalid or expired reset token")

    user.hashed_password = hash_password(payload.new_password)
    reset_token.used = True
    await db.flush()