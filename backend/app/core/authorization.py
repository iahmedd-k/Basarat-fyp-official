from typing import Awaitable, Callable

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)


async def get_token_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise UnauthorizedError()
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise UnauthorizedError("Invalid or expired token")
    return payload


from app.core.redis import cache_get, cache_set

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
        user = User(
            id=cached_data.get("id"),
            email=cached_data.get("email"),
            username=cached_data.get("username"),
            full_name=cached_data.get("full_name"),
            is_active=cached_data.get("is_active", True),
            is_verified=cached_data.get("is_verified", False),
            is_admin=cached_data.get("is_admin", False),
            hashed_password=cached_data.get("hashed_password", ""),
        )
        if not user.is_active:
            raise ForbiddenError("Inactive user")
        return user

    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise ForbiddenError("Inactive user")

    user_dict = {
        "id": user.id,
        "email": user.email,
        "username": user.username,
        "full_name": user.full_name,
        "is_active": user.is_active,
        "is_verified": user.is_verified,
        "is_admin": user.is_admin,
        "hashed_password": user.hashed_password,
    }
    await cache_set(cache_key, user_dict, ttl_seconds=120)
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
        user = await db.get(User, user_id)
        if user is None or not user.is_active:
            return None
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