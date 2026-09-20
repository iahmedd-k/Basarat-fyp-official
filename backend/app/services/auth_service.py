from datetime import datetime, timedelta, timezone
from uuid import uuid4
import hashlib
import secrets

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    UnauthorizedError,
    ValidationFailedError,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, RefreshToken, PasswordResetToken
from app.schemas.auth import UserSummary


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

        username = await self._generate_unique_username()

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
        )
        self.db.add(user)
        try:
            await self.db.flush()
        except IntegrityError:
            await self.db.rollback()
            username = await self._generate_unique_username()
            user.username = username
            self.db.add(user)
            await self.db.flush()
        await self.db.refresh(user)

        return await self._create_token_pair(user)

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

        return await self._create_token_pair(user)

    async def refresh_token(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid or expired refresh token.")

        jti = payload.get("jti")
        user_id = payload.get("sub")
        if not jti or not user_id:
            raise UnauthorizedError("Invalid refresh token payload.")

        # Check if refresh token exists and is not revoked
        rt = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.jti == jti,
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False,
                RefreshToken.expires_at > datetime.now(timezone.utc)
            )
        )
        stored_token = rt.scalars().first()
        if not stored_token:
            # Token reuse detected - revoke all user tokens
            await self._revoke_all_user_tokens(user_id)
            raise UnauthorizedError("Invalid or reused refresh token. Please log in again.")

        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if not user.is_active:
            raise UnauthorizedError("Account is deactivated.")

        # Rotate: revoke old token, create new pair
        stored_token.revoked = True
        stored_token.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

        # Store new tokens
        return await self._create_token_pair(user)

    async def logout(self, refresh_token: str) -> None:
        """Revoke a specific refresh token by its JWT payload."""
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            return  # Silent success - token already invalid

        jti = payload.get("jti")
        user_id = payload.get("sub")
        if not jti or not user_id:
            return

        await self._revoke_token_by_jti(jti, user_id)

    async def logout_all(self, user_id: str) -> None:
        """Revoke all refresh tokens for a user (e.g., on password change)."""
        await self._revoke_all_user_tokens(user_id)

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
        risk_tolerance: str | None = None,
        sector_preferences: list[str] | None = None,
        investment_horizon: str | None = None,
    ) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")

        if full_name is not None:
            user.full_name = full_name
        if avatar_url is not None:
            user.avatar_url = avatar_url
        if risk_tolerance is not None:
            user.risk_tolerance = risk_tolerance
        if sector_preferences is not None:
            user.sector_preferences = sector_preferences
        if investment_horizon is not None:
            user.investment_horizon = investment_horizon

        await self.db.flush()
        await self.db.refresh(user)
        return user

    async def update_risk_profile(
        self,
        user_id: str,
        risk_tolerance: str | None = None,
        sector_preferences: list[str] | None = None,
        investment_horizon: str | None = None,
    ) -> User:
        return await self.update_profile(
            user_id=user_id,
            risk_tolerance=risk_tolerance,
            sector_preferences=sector_preferences,
            investment_horizon=investment_horizon,
        )

    async def update_notification_preferences(
        self,
        user_id: str,
        channels: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")

        prefs = user.notification_preferences or {}
        if channels is not None:
            prefs["channels"] = channels
        if categories is not None:
            prefs["categories"] = categories
        user.notification_preferences = prefs

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

        # Revoke all refresh tokens on password change
        await self._revoke_all_user_tokens(user_id)

    async def forgot_password(self, email: str) -> None:
        email = email.strip().lower()
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalars().first()

        # Always return success to prevent email enumeration
        if user is None:
            return

        # Generate cryptographically random reset token
        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

        # Store hash with 1-hour expiry
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        reset_token = PasswordResetToken(
            token_hash=token_hash,
            user_id=user.id,
            expires_at=expires_at,
        )
        self.db.add(reset_token)
        await self.db.flush()
        # Commit before dispatching so a delivered link always maps to a durable token.
        await self.db.commit()
        from app.tasks.email import send_password_reset_email
        send_password_reset_email.delay(user.email, raw_token)

    async def reset_password(self, token: str, new_password: str) -> None:
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        result = await self.db.execute(
            select(PasswordResetToken).where(
                PasswordResetToken.token_hash == token_hash,
                PasswordResetToken.used == False,
                PasswordResetToken.expires_at > datetime.now(timezone.utc)
            )
        )
        reset_token = result.scalars().first()

        if not reset_token:
            raise ValidationFailedError("Invalid or expired reset token.")

        user = await self.db.get(User, reset_token.user_id)
        if user is None:
            raise NotFoundError("User not found.")

        user.hashed_password = hash_password(new_password)
        reset_token.used = True
        await self.db.flush()

        # Revoke all refresh tokens on password reset
        await self._revoke_all_user_tokens(user.id)

    async def _generate_unique_username(self) -> str:
        """Generate a random unique username."""
        for _ in range(10):
            username = f"user_{uuid4().hex[:12]}"
            existing = await self.db.execute(
                select(User).where(User.username == username)
            )
            if not existing.scalars().first():
                return username
        # Fallback with timestamp
        return f"user_{uuid4().hex[:8]}_{int(datetime.now(timezone.utc).timestamp())}"

    async def _create_token_pair(self, user: User) -> dict:
        token_data = {"sub": user.id}
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        # Decode refresh token to get jti and expiry for storage
        rt_payload = decode_token(refresh_token)
        jti = rt_payload.get("jti")
        exp = rt_payload.get("exp")

        # Store refresh token in DB
        rt = RefreshToken(
            jti=jti,
            user_id=user.id,
            expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
        )
        self.db.add(rt)
        await self.db.flush()

        return {
            "access_token": access_token,
            "refresh_token": refresh_token,
            "token_type": "bearer",
            "user": UserSummary.model_validate(user),
        }

    async def _revoke_token_by_jti(self, jti: str, user_id: str) -> None:
        rt = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.jti == jti,
                RefreshToken.user_id == user_id,
            )
        )
        token = rt.scalars().first()
        if token:
            token.revoked = True
            token.revoked_at = datetime.now(timezone.utc)
            await self.db.flush()

    async def _revoke_all_user_tokens(self, user_id: str) -> None:
        await self.db.execute(
            delete(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked == False
            )
        )
        await self.db.flush()
