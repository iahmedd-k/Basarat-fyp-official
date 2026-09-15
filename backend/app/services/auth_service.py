from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def signup(self, email: str, password: str, full_name: str | None = None) -> dict:
        email = email.strip().lower()

        existing = await self.db.execute(
            select(User).where((User.email == email))
        )
        if existing.scalars().first():
            raise ConflictError("A user with this email already exists.")

        username = email.split("@")[0]
        base_username = username
        counter = 1
        while True:
            dup = await self.db.execute(
                select(User).where(User.username == username)
            )
            if not dup.scalars().first():
                break
            username = f"{base_username}{counter}"
            counter += 1

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        self.db.add(user)
        await self.db.flush()
        await self.db.refresh(user)

        return self._create_token_pair(user)

    async def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalars().first()

        if user is None or not verify_password(password, user.hashed_password):
            raise UnauthorizedError("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated.")

        return self._create_token_pair(user)

    async def refresh_token(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid or expired refresh token.")

        user_id = payload.get("sub")
        if not user_id:
            raise UnauthorizedError("Invalid refresh token payload.")

        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if not user.is_active:
            raise UnauthorizedError("Account is deactivated.")

        return self._create_token_pair(user)

    async def get_current_user(self, user_id: str) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def update_profile(
        self,
        user_id: str,
        full_name: str | None = None,
        avatar_url: str | None = None,
    ) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")

        if full_name is not None:
            user.full_name = full_name
        if avatar_url is not None:
            user.avatar_url = avatar_url

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> None:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")

        if not verify_password(current_password, user.hashed_password):
            raise UnauthorizedError("Current password is incorrect.")

        user.hashed_password = hash_password(new_password)
        await self.db.flush()

    @staticmethod
    def _create_token_pair(user: User) -> dict:
        token_data = {"sub": user.id}
        return {
            "access_token": create_access_token(token_data),
            "refresh_token": create_refresh_token(token_data),
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": user.email,
                "username": user.username,
                "full_name": user.full_name,
                "is_admin": user.is_admin,
            },
        }
