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


async def get_current_user(
    payload: dict = Depends(get_token_payload),
    db: AsyncSession = Depends(get_db),
) -> User:
    user_id = payload.get("sub")
    if not user_id:
        raise UnauthorizedError("Invalid token payload")
    user = await db.get(User, user_id)
    if user is None:
        raise UnauthorizedError("User not found")
    if not user.is_active:
        raise ForbiddenError("Inactive user")
    return user


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