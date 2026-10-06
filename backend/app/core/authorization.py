from typing import Awaitable, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

from app.core.redis import cache_get, cache_set

bearer_scheme = HTTPBearer(auto_error=False)


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise UnauthorizedError()
    token_str = credentials.credentials
    payload = decode_token(token_str)
    if payload is None or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired token")
    jti = payload.get("jti")
    if jti:
        is_revoked = await cache_get(f"auth:blacklist:{jti}")
        if is_revoked:
            raise UnauthorizedError("Token has been revoked")
    return payload


from app.core.redis import cache_get, cache_set

from datetime import datetime, timezone

def _user_from_dict(cached_data: dict) -> User:
    created_at_val = cached_data.get("created_at")
    updated_at_val = cached_data.get("updated_at")
    sub_exp_val = cached_data.get("subscription_expires_at")
    return User(
        id=cached_data.get("id"),
        email=cached_data.get("email"),
        username=cached_data.get("username"),
        full_name=cached_data.get("full_name"),
        avatar_url=cached_data.get("avatar_url"),
        is_active=cached_data.get("is_active", True),
        is_verified=cached_data.get("is_verified", False),
        is_admin=cached_data.get("is_admin", False),
        hashed_password=cached_data.get("hashed_password", ""),
        risk_tolerance=cached_data.get("risk_tolerance"),
        investment_horizon=cached_data.get("investment_horizon"),
        sector_preferences=cached_data.get("sector_preferences"),
        notification_preferences=cached_data.get("notification_preferences"),
        recommendation_weights=cached_data.get("recommendation_weights"),
        subscription_tier=cached_data.get("subscription_tier", "free"),
        subscription_expires_at=datetime.fromisoformat(sub_exp_val) if sub_exp_val else None,
        stripe_customer_id=cached_data.get("stripe_customer_id"),
        stripe_subscription_id=cached_data.get("stripe_subscription_id"),
        created_at=datetime.fromisoformat(created_at_val) if created_at_val else datetime.now(timezone.utc),
        updated_at=datetime.fromisoformat(updated_at_val) if updated_at_val else None,
    )


def _user_to_dict(user: User) -> dict:
    c_at = user.__dict__.get("created_at")
    u_at = user.__dict__.get("updated_at")
    s_exp = getattr(user, "subscription_expires_at", None)
    return {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "avatar_url": getattr(user, "avatar_url", None),
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_admin": user.is_admin,
        "hashed_password": user.hashed_password,
        "risk_tolerance": getattr(user, "risk_tolerance", None),
        "investment_horizon": getattr(user, "investment_horizon", None),
        "sector_preferences": getattr(user, "sector_preferences", None),
        "notification_preferences": getattr(user, "notification_preferences", None),
        "recommendation_weights": getattr(user, "recommendation_weights", None),
        "subscription_tier": getattr(user, "subscription_tier", "free"),
        "subscription_expires_at": s_exp.isoformat() if isinstance(s_exp, datetime) else None,
        "stripe_customer_id": getattr(user, "stripe_customer_id", None),
        "stripe_subscription_id": getattr(user, "stripe_subscription_id", None),
        "created_at": c_at.isoformat() if isinstance(c_at, datetime) else None,
        "updated_at": u_at.isoformat() if isinstance(u_at, datetime) else None,
    }


async def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")

    cache_key = f"auth:user:{user_id}"
    cached_data = await cache_get(cache_key)
    if cached_data is not None:
        user = _user_from_dict(cached_data)
        if not user.is_active:
            raise ForbiddenError("Inactive user")
        return user

    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise ForbiddenError("Inactive user")

    await cache_set(cache_key, _user_to_dict(user), ttl_seconds=300)
    return user


async def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User | None:
    """Extract user if valid Authorization header present; otherwise returns None without throwing."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials)
        if payload is None or payload.get("type") != "access":
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None

        cache_key = f"auth:user:{user_id}"
        cached_data = await cache_get(cache_key)
        if cached_data is not None:
            user = _user_from_dict(cached_data)
            if not user.is_active:
                return None
            return user

        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            return None

        await cache_set(cache_key, _user_to_dict(user), ttl_seconds=300)
        return user
    except Exception:
        return None



async def get_current_admin(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_admin:
        raise ForbiddenError("Admin privileges required")
    return current_user


def require_roles(*roles: str) -> Callable[..., Awaitable[User]]:
    async def role_dependency(
        current_user: User = Depends(get_current_user),
    ) -> User:
        role = "admin" if current_user.is_admin else "user"
        if role not in roles:
            raise ForbiddenError()
        return current_user

    return role_dependency