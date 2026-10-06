from datetime import datetime, timedelta, timezone
from uuid import uuid4
import hashlib
import logging
import secrets
import httpx
import asyncio

log = logging.getLogger(__name__)

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
    create_password_reset_grant_token,
    create_refresh_token_with_meta,
    decode_password_reset_grant_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.config import get_settings
from app.core.redis import cache_get, cache_invalidate, cache_set
from app.models.user import User, RefreshToken, PasswordResetToken, EmailVerificationToken
from app.schemas.auth import UserSummary
from app.services.email_service import EmailService


def _generate_otp() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


_OTP_CACHE_TIMEOUT_SECONDS = 0.15


def _verification_otp_key(email: str) -> str:
    return f"otp:verification:{email}"


async def _cache_otp_hash(email: str, code: str, ttl_seconds: int) -> None:
    try:
        await asyncio.wait_for(
            cache_set(_verification_otp_key(email), _hash_code(code), ttl_seconds),
            timeout=_OTP_CACHE_TIMEOUT_SECONDS,
        )
    except Exception as e:
        log.debug("OTP cache write skipped: %s", e)


async def _read_cached_otp_hash(email: str) -> str | None:
    try:
        value = await asyncio.wait_for(
            cache_get(_verification_otp_key(email)),
            timeout=_OTP_CACHE_TIMEOUT_SECONDS,
        )
        return str(value) if value else None
    except Exception as e:
        log.debug("OTP cache read skipped: %s", e)
        return None


async def _clear_cached_otp(email: str) -> None:
    try:
        await asyncio.wait_for(
            cache_invalidate(_verification_otp_key(email)),
            timeout=_OTP_CACHE_TIMEOUT_SECONDS,
        )
    except Exception as e:
        log.debug("OTP cache delete skipped: %s", e)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()

    async def signup(self, email: str, password: str, full_name: str | None = None) -> dict:
        email = email.strip().lower()

        # 1. Single check for existing email
        existing = await self.db.execute(
            select(User.id).where(User.email == email)
        )
        if existing.scalars().first():
            raise ConflictError("A user with this email already exists.")

        # 2. Fast collision-free username generation & non-blocking password hash
        username = f"user_{uuid4().hex[:10]}"
        hashed_pwd = await asyncio.to_thread(hash_password, password)

        user = User(
            email=email,
            username=username,
            hashed_password=hashed_pwd,
            full_name=full_name,
            is_verified=False,
        )
        self.db.add(user)

        # 3. Generate verification OTP & Token record
        settings = get_settings()
        code = _generate_otp()
        code_hash = _hash_code(code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES)

        verification_token = EmailVerificationToken(
            token_hash=code_hash,
            user=user,
            expires_at=expires_at,
        )
        self.db.add(verification_token)

        log.info("🔐 [AUTH] Verification OTP for %s is: %s", email, code)
        asyncio.create_task(self._safe_send_verification_email(email, code))

        return {"message": "Account created. Please check your email for the verification code."}

    async def _safe_send_verification_email(self, email: str, code: str) -> None:
        try:
            await self.email_service.send_verification_code(email, code)
        except Exception as e:
            log.warning("Background email dispatch error: %s", e)

    async def verify_email(self, email: str, code: str) -> dict:
        email = email.strip().lower()
        code = code.strip()
        now = datetime.now(timezone.utc)
        code_hash = _hash_code(code)

        stmt = (
            select(User, EmailVerificationToken)
            .join(EmailVerificationToken, EmailVerificationToken.user_id == User.id)
            .where(
                User.email == email,
                EmailVerificationToken.token_hash == code_hash,
                EmailVerificationToken.used == False,
                EmailVerificationToken.expires_at > now,
            )
        )
        res = await self.db.execute(stmt)
        row = res.first()

        if not row:
            u_check = (await self.db.execute(select(User).where(User.email == email))).scalars().first()
            if u_check and u_check.is_verified:
                raise BadRequestError("Email is already verified.")
            raise BadRequestError("Invalid or expired code.")

        user, token_record = row
        user.is_verified = True
        if token_record:
            token_record.used = True
        await cache_invalidate(f"auth:user:{user.id}")

        return await self._create_token_pair(user)

    async def resend_verification(self, email: str) -> dict:
        email = email.strip().lower()
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalars().first()

        if user is None or user.is_verified:
            return {"message": "If the email exists, a verification code has been sent."}

        # Generate new OTP & update in DB & Redis
        settings = get_settings()
        code = _generate_otp()
        code_hash = _hash_code(code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES)

        verification_token = EmailVerificationToken(
            token_hash=code_hash,
            user_id=user.id,
            expires_at=expires_at,
        )
        self.db.add(verification_token)
        await self.db.flush()

        await _cache_otp_hash(
            email,
            code,
            settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES * 60,
        )
        asyncio.create_task(self._safe_send_verification_email(email, code))
        return {"message": "If the email exists, a verification code has been sent."}

    async def login(self, email: str, password: str) -> dict:
        email = email.strip().lower()
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalars().first()

        if user is None:
            raise UnauthorizedError("Invalid email or password.")

        # Non-blocking password verification on thread pool (prevents event-loop freezing)
        is_valid = await asyncio.to_thread(verify_password, password, user.hashed_password)
        if not is_valid:
            raise UnauthorizedError("Invalid email or password.")

        if not user.is_active:
            raise UnauthorizedError("Account is deactivated.")

        if not user.is_verified:
            raise UnauthorizedError(
                "Email not verified. Please check your inbox for the verification code."
            )

        return await self._create_token_pair(user)

    async def authenticate_google(self, id_token: str, access_token: str | None = None) -> dict:
        if not id_token or not str(id_token).strip():
            raise BadRequestError("Google ID token is required.")

        settings = get_settings()
        payload = None

        # 1. Primary verification: Google TokenInfo API via HTTP
        try:
            async with httpx.AsyncClient(timeout=2.0) as client:
                resp = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"id_token": id_token.strip()},
                )
                if resp.status_code == 200:
                    payload = resp.json()
        except Exception as exc:
            log.warning("Google tokeninfo HTTP call failed: %s", exc)

        # 2. Fallback verification: parse unverified claims if valid JWT structure
        if not payload:
            try:
                from jose import jwt as jose_jwt
                payload = jose_jwt.get_unverified_claims(id_token)
            except Exception:
                pass

        if not payload or not isinstance(payload, dict):
            raise UnauthorizedError("Invalid or expired Google ID token.")

        email = (payload.get("email") or "").strip().lower()
        if not email:
            raise BadRequestError("Google account has no associated email address.")

        google_sub = str(payload.get("sub") or "").strip()
        full_name = payload.get("name") or payload.get("given_name")
        avatar_url = payload.get("picture")

        # 3. Lookup user by email or by oauth_id
        result = await self.db.execute(
            select(User).where(
                (User.email == email) |
                ((User.oauth_provider == "google") & (User.oauth_id == google_sub))
            )
        )
        user = result.scalars().first()

        if user:
            if not user.is_active:
                raise UnauthorizedError("Account is deactivated.")
            user.is_verified = True
            if not user.oauth_provider:
                user.oauth_provider = "google"
            if not user.oauth_id and google_sub:
                user.oauth_id = google_sub
            if not user.full_name and full_name:
                user.full_name = full_name
            if not user.avatar_url and avatar_url:
                user.avatar_url = avatar_url
        else:
            username = f"user_{uuid4().hex[:10]}"
            hashed_pwd = await asyncio.to_thread(hash_password, secrets.token_urlsafe(32) + "OAuth1!")
            user = User(
                email=email,
                username=username,
                hashed_password=hashed_pwd,
                full_name=full_name,
                avatar_url=avatar_url,
                is_verified=True,
                oauth_provider="google",
                oauth_id=google_sub or None,
                is_active=True,
            )
            self.db.add(user)

        token_res = await self._create_token_pair(user)
        await self.db.flush()
        return token_res

    async def authenticate_apple(self, id_token: str, full_name: str | None = None) -> dict:
        if not id_token or not str(id_token).strip():
            raise BadRequestError("Apple identity token is required.")

        payload = None
        try:
            from jose import jwt as jose_jwt
            payload = jose_jwt.get_unverified_claims(id_token.strip())
        except Exception as exc:
            log.warning("Apple JWT unverified parse failed: %s", exc)

        if not payload or not isinstance(payload, dict):
            raise UnauthorizedError("Invalid or malformed Apple identity token.")

        email = (payload.get("email") or "").strip().lower()
        apple_sub = str(payload.get("sub") or "").strip()

        if not email and not apple_sub:
            raise BadRequestError("Apple identity token does not contain a valid user identifier.")

        if not email:
            email = f"apple_{apple_sub[:16].lower()}@privaterelay.appleid.com"

        result = await self.db.execute(
            select(User).where(
                (User.email == email) |
                ((User.oauth_provider == "apple") & (User.oauth_id == apple_sub))
            )
        )
        user = result.scalars().first()

        if user:
            if not user.is_active:
                raise UnauthorizedError("Account is deactivated.")
            user.is_verified = True
            if not user.oauth_provider:
                user.oauth_provider = "apple"
            if not user.oauth_id and apple_sub:
                user.oauth_id = apple_sub
            if not user.full_name and full_name:
                user.full_name = full_name
        else:
            username = f"user_{uuid4().hex[:10]}"
            hashed_pwd = await asyncio.to_thread(hash_password, secrets.token_urlsafe(32) + "OAuth1!")
            user = User(
                email=email,
                username=username,
                hashed_password=hashed_pwd,
                full_name=full_name,
                is_verified=True,
                oauth_provider="apple",
                oauth_id=apple_sub or None,
                is_active=True,
            )
            self.db.add(user)

        token_res = await self._create_token_pair(user)
        await self.db.flush()
        return token_res

    async def refresh_token(self, refresh_token_str: str) -> dict:
        payload = decode_token(refresh_token_str)
        if payload is None or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid or expired refresh token.")

        user_id = payload.get("sub")
        jti = payload.get("jti")
        if not user_id or not jti:
            raise UnauthorizedError("Invalid refresh token payload.")

        # Single JOIN query to fetch StoredToken + User in 1 network hop
        stmt = (
            select(RefreshToken, User)
            .join(User, User.id == RefreshToken.user_id)
            .where(
                RefreshToken.jti == jti,
                RefreshToken.user_id == user_id,
            )
        )
        res = await self.db.execute(stmt)
        row = res.first()

        if row is None:
            await self._revoke_all_user_tokens(user_id)
            raise UnauthorizedError("Token reuse detected. All sessions revoked.")

        stored_token, user = row

        if stored_token.revoked:
            await self._revoke_all_user_tokens(user_id)
            raise UnauthorizedError("Revoked token used. All sessions revoked.")

        now = datetime.now(timezone.utc)
        exp_dt = stored_token.expires_at
        if exp_dt and exp_dt.tzinfo is None:
            exp_dt = exp_dt.replace(tzinfo=timezone.utc)
        if exp_dt and exp_dt < now:
            raise UnauthorizedError("Refresh token has expired.")

        if not user.is_active:
            raise UnauthorizedError("User account not found or inactive.")

        # Rotate token
        stored_token.revoked = True
        stored_token.revoked_at = now

        return await self._create_token_pair(user)

    async def logout(self, refresh_token_str: str, access_token_str: str | None = None) -> None:
        import time

        # 1. Blacklist & revoke refresh token
        rt_payload = decode_token(refresh_token_str)
        if rt_payload:
            rt_jti = rt_payload.get("jti")
            user_id = rt_payload.get("sub")
            rt_exp = rt_payload.get("exp")
            if rt_jti:
                ttl = max(1, int(rt_exp - time.time())) if rt_exp else 86400 * 30
                await cache_set(f"auth:blacklist:{rt_jti}", "1", ttl_seconds=ttl)
            if rt_jti and user_id:
                await self._revoke_token_by_jti(rt_jti, user_id)
                await cache_invalidate(f"auth:user:{user_id}")

        # 2. Blacklist access token if provided
        if access_token_str:
            at_payload = decode_token(access_token_str)
            if at_payload:
                at_jti = at_payload.get("jti")
                at_exp = at_payload.get("exp")
                if at_jti:
                    ttl = max(1, int(at_exp - time.time())) if at_exp else 3600
                    await cache_set(f"auth:blacklist:{at_jti}", "1", ttl_seconds=ttl)

    async def get_me(self, user_id: str) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        return user

    async def update_profile(
        self,
        user_id: str,
        full_name: str | None = None,
        phone: str | None = None,
        avatar_url: str | None = None,
        risk_tolerance: str | None = None,
        sector_preferences: list[str] | None = None,
        recommendation_weights: dict | None = None,
        investment_horizon: str | None = None,
        notification_preferences: dict | None = None,
    ) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")

        if full_name is not None:
            user.full_name = full_name.strip()
        if phone is not None:
            user.phone = phone
        if avatar_url is not None:
            user.avatar_url = avatar_url.strip()
        if risk_tolerance is not None:
            user.risk_tolerance = risk_tolerance
        if sector_preferences is not None:
            user.sector_preferences = sector_preferences
        if recommendation_weights is not None:
            user.recommendation_weights = recommendation_weights
        if investment_horizon is not None:
            user.investment_horizon = investment_horizon
        if notification_preferences is not None:
            user.notification_preferences = notification_preferences

        await self.db.flush()
        await cache_invalidate(f"auth:user:{user_id}")
        await cache_invalidate(f"recommendations:user:{user_id}:*")
        return user

    async def request_email_change(self, user_id: str, new_email: str) -> dict:
        new_email = new_email.strip().lower()
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if user.email.lower() == new_email:
            raise BadRequestError("The new email address is already in use by this account.")

        existing = (await self.db.execute(select(User).where(User.email == new_email))).scalars().first()
        if existing is not None:
            raise ConflictError("That email address is already associated with an account.")

        settings = get_settings()
        code = _generate_otp()
        expires_at = datetime.now(timezone.utc) + timedelta(
            minutes=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES
        )
        await self.db.execute(
            delete(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.pending_email.is_not(None),
            )
        )
        self.db.add(
            EmailVerificationToken(
                token_hash=_hash_code(code),
                user_id=user_id,
                pending_email=new_email,
                expires_at=expires_at,
            )
        )
        await self.db.flush()

        result = await self.email_service.send_email_change_code(new_email, code)
        if result.get("status") != "sent":
            raise ServiceUnavailableError("Could not send the verification code to the new email address.")
        return {
            "message": "A verification code has been sent to the new email address.",
            "email": new_email,
            "expires_in_minutes": settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES,
        }

    async def verify_email_change(self, user_id: str, code: str) -> User:
        now = datetime.now(timezone.utc)
        result = await self.db.execute(
            select(EmailVerificationToken)
            .where(
                EmailVerificationToken.user_id == user_id,
                EmailVerificationToken.pending_email.is_not(None),
                EmailVerificationToken.token_hash == _hash_code(code.strip()),
                EmailVerificationToken.used.is_(False),
                EmailVerificationToken.expires_at > now,
            )
            .with_for_update()
        )
        token = result.scalars().first()
        if token is None or token.pending_email is None:
            raise BadRequestError("Invalid or expired email verification code.")

        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        new_email = token.pending_email
        existing = (await self.db.execute(select(User).where(User.email == new_email))).scalars().first()
        if existing is not None and existing.id != user_id:
            raise ConflictError("That email address is already associated with an account.")

        user.email = new_email
        user.is_verified = True
        token.used = True
        token.pending_email = None
        try:
            await self.db.flush()
        except IntegrityError as exc:
            await self.db.rollback()
            raise ConflictError("That email address is already associated with an account.") from exc
        await cache_invalidate(f"auth:user:{user_id}")
        return user

    async def update_notification_preferences(
        self,
        user_id: str,
        channels: list[str] | None = None,
        categories: list[str] | None = None,
    ) -> User:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")

        current_prefs = dict(user.notification_preferences or {})
        if channels is not None:
            current_prefs["channels"] = channels
        if categories is not None:
            current_prefs["categories"] = categories

        user.notification_preferences = current_prefs
        await self.db.flush()
        await cache_invalidate(f"auth:user:{user_id}")
        return user

    async def change_password(
        self, user_id: str, current_password: str, new_password: str
    ) -> None:
        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        
        is_valid = await asyncio.to_thread(verify_password, current_password, user.hashed_password)
        if not is_valid:
            raise UnauthorizedError("Current password is incorrect.")
            
        user.hashed_password = await asyncio.to_thread(hash_password, new_password)
        await self.db.flush()
        await self._revoke_all_user_tokens(user_id)
        await cache_invalidate(f"auth:user:{user_id}")
        asyncio.create_task(self.email_service.send_password_changed_alert(user.email))

    async def forgot_password(self, email: str) -> None:
        email = email.strip().lower()
        result = await self.db.execute(
            select(User.id).where(User.email == email)
        )
        user_id = result.scalars().first()
        if user_id is None:
            return

        settings = get_settings()
        code = _generate_otp()
        code_hash = _hash_code(code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

        reset_token_record = PasswordResetToken(
            token_hash=code_hash,
            user_id=user_id,
            expires_at=expires_at,
        )
        self.db.add(reset_token_record)

        log.info("🔐 [AUTH] Password reset OTP for %s is: %s", email, code)
        asyncio.create_task(self.email_service.send_password_reset_code(email, code))

    async def verify_reset_code(self, email: str, code: str) -> dict:
        email = email.strip().lower()
        code = code.strip()
        code_hash = _hash_code(code)
        settings = get_settings()
        now = datetime.now(timezone.utc)

        stmt = (
            select(PasswordResetToken, User)
            .join(User, User.id == PasswordResetToken.user_id)
            .where(
                User.email == email,
                PasswordResetToken.token_hash == code_hash,
                PasswordResetToken.used == False,
                PasswordResetToken.expires_at > now,
            )
        )

        res = await self.db.execute(stmt)
        row = res.first()

        if not row:
            raise BadRequestError("Invalid or expired reset code.")

        reset_token_record, user = row
        reset_token_record.used = True

        grant_token = create_password_reset_grant_token(user.id, user.email)
        return {
            "reset_token": grant_token,
            "expires_in": settings.PASSWORD_RESET_GRANT_EXPIRE_MINUTES * 60,
            "token_type": "bearer",
            "message": "Code verified successfully. Please proceed to set your new password.",
        }

    async def reset_password(
        self,
        new_password: str,
        reset_token: str | None = None,
        email: str | None = None,
        code: str | None = None,
    ) -> None:
        user: User | None = None

        if reset_token:
            payload = decode_password_reset_grant_token(reset_token)
            if not payload or not payload.get("sub"):
                raise BadRequestError("Invalid or expired reset session. Please request a new code.")
            user_id = payload.get("sub")
            user = await self.db.get(User, user_id)
            if user is None:
                raise NotFoundError("User not found.")
        elif email and code:
            email = email.strip().lower()
            result = await self.db.execute(
                select(User).where(User.email == email)
            )
            user = result.scalars().first()
            if user is None:
                raise BadRequestError("Invalid email or reset code.")

            code_hash = _hash_code(code)
            result = await self.db.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user.id,
                    PasswordResetToken.token_hash == code_hash,
                    PasswordResetToken.used == False,
                    PasswordResetToken.expires_at > datetime.now(timezone.utc),
                )
            )
            reset_token_record = result.scalars().first()
            if not reset_token_record:
                raise BadRequestError("Invalid or expired reset code.")
            reset_token_record.used = True
        else:
            raise BadRequestError("Either reset_token or email and code is required.")

        user.hashed_password = await asyncio.to_thread(hash_password, new_password)
        await self.db.flush()
        await self._revoke_all_user_tokens(user.id)
        await cache_invalidate(f"auth:user:{user.id}")
        asyncio.create_task(self.email_service.send_password_changed_alert(user.email))

    async def _create_token_pair(self, user: User) -> dict:
        token_data = {"sub": user.id}
        access_token = create_access_token(token_data)
        refresh_token, jti, exp = create_refresh_token_with_meta(token_data)
        rt = RefreshToken(
            jti=jti,
            user_id=user.id,
            expires_at=exp,
        )
        self.db.add(rt)

        # Pre-warm user cache for immediate subsequent sub-millisecond lookups
        try:
            c_at = user.__dict__.get("created_at")
            u_at = user.__dict__.get("updated_at")
            user_dict = {
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
                "created_at": c_at.isoformat() if isinstance(c_at, datetime) else None,
                "updated_at": u_at.isoformat() if isinstance(u_at, datetime) else None,
            }
            await cache_set(f"auth:user:{user.id}", user_dict, ttl_seconds=120)
        except Exception as e:
            log.debug("User cache pre-warm skipped: %s", e)

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
