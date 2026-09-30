from datetime import datetime, timedelta, timezone
from uuid import uuid4
import hashlib
import logging
import secrets
import httpx

log = logging.getLogger(__name__)

from sqlalchemy import select, delete
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
    UnauthorizedError,
    ValidationFailedError,
)
from app.core.security import (
    create_access_token,
    create_password_reset_grant_token,
    create_refresh_token,
    decode_password_reset_grant_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.core.config import get_settings
from app.models.user import User, RefreshToken, PasswordResetToken, EmailVerificationToken
from app.schemas.auth import UserSummary
from app.services.email_service import EmailService


def _generate_otp() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.email_service = EmailService()

    async def signup(self, email: str, password: str, full_name: str | None = None) -> dict:
        email = email.strip().lower()
        generic_message = "Account created. Please check your email for the verification code."

        existing = await self.db.execute(
            select(User).where((User.email == email))
        )
        existing_user = existing.scalars().first()
        if existing_user:
            # Anti-enumeration: same response whether email exists or not.
            # Re-send OTP only for unverified accounts so signup can continue.
            if not existing_user.is_verified:
                try:
                    await self._send_verification_otp(existing_user)
                except Exception:
                    log.warning("Failed to re-send verification OTP for existing signup attempt")
            return {"message": generic_message}

        username = await self._generate_unique_username()

        user = User(
            email=email,
            username=username,
            hashed_password=hash_password(password),
            full_name=full_name,
            is_verified=False,
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

        # Generate and send OTP
        await self._send_verification_otp(user)

        return {"message": generic_message}

    async def verify_email(self, email: str, code: str) -> dict:
        email = email.strip().lower()
        settings = get_settings()

        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalars().first()
        if user is None:
            raise BadRequestError("Invalid email or code.")

        if user.is_verified:
            raise BadRequestError("Email is already verified.")

        code_hash = _hash_code(code)
        result = await self.db.execute(
            select(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.token_hash == code_hash,
                EmailVerificationToken.used == False,
                EmailVerificationToken.expires_at > datetime.now(timezone.utc),
            )
        )
        token = result.scalars().first()
        if not token:
            raise BadRequestError("Invalid or expired code.")

        user.is_verified = True
        token.used = True
        await self.db.flush()

        return await self._create_token_pair(user)

    async def resend_verification(self, email: str) -> dict:
        email = email.strip().lower()
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalars().first()

        if user is None or user.is_verified:
            return {"message": "If the email exists, a verification code has been sent."}

        # Invalidate old codes
        await self.db.execute(
            delete(EmailVerificationToken).where(
                EmailVerificationToken.user_id == user.id,
                EmailVerificationToken.used == False,
            )
        )
        await self.db.flush()

        await self._send_verification_otp(user)

        return {"message": "If the email exists, a verification code has been sent."}

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

        if not user.is_verified:
            raise UnauthorizedError(
                "Email not verified. Please check your inbox for the verification code."
            )

        return await self._create_token_pair(user)

    async def authenticate_google(self, id_token: str, access_token: str | None = None) -> dict:
        if not id_token or not str(id_token).strip():
            raise BadRequestError("Google ID token is required.")

        settings = get_settings()
        if not settings.GOOGLE_CLIENT_ID:
            raise UnauthorizedError("Google sign-in is not configured.")

        payload = None
        # Signature + claims verification via Google tokeninfo only (no unverified fallback).
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    "https://oauth2.googleapis.com/tokeninfo",
                    params={"id_token": id_token.strip()},
                )
                if resp.status_code == 200:
                    payload = resp.json()
                else:
                    log.warning("Google tokeninfo rejected token: HTTP %s", resp.status_code)
        except Exception as exc:
            log.warning("Google tokeninfo HTTP call failed: %s", exc)

        if not payload or not isinstance(payload, dict):
            raise UnauthorizedError("Invalid or expired Google ID token.")

        aud = payload.get("aud")
        if isinstance(aud, (list, tuple)):
            aud_ok = settings.GOOGLE_CLIENT_ID in aud
        else:
            aud_ok = aud == settings.GOOGLE_CLIENT_ID
        if not aud_ok:
            raise UnauthorizedError("Invalid Google ID token audience.")

        iss = str(payload.get("iss") or "")
        if iss not in {"accounts.google.com", "https://accounts.google.com"}:
            raise UnauthorizedError("Invalid Google ID token issuer.")

        try:
            exp = int(payload.get("exp") or 0)
        except (TypeError, ValueError):
            exp = 0
        if exp and exp < int(datetime.now(timezone.utc).timestamp()):
            raise UnauthorizedError("Google ID token has expired.")

        email_verified = payload.get("email_verified")
        if email_verified is not None and str(email_verified).lower() not in {"true", "1"}:
            raise UnauthorizedError("Google account email is not verified.")

        email = (payload.get("email") or "").strip().lower()
        if not email:
            raise BadRequestError("Google account has no associated email address.")

        google_sub = str(payload.get("sub") or "").strip()
        if not google_sub:
            raise UnauthorizedError("Invalid Google ID token subject.")
        full_name = payload.get("name") or payload.get("given_name")
        avatar_url = payload.get("picture")

        # 3. Lookup user by email or by (oauth_provider == 'google' and oauth_id == google_sub)
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
            await self.db.flush()
            await self.db.refresh(user)
        else:
            username = await self._generate_unique_username()
            user = User(
                email=email,
                username=username,
                hashed_password=hash_password(secrets.token_urlsafe(32) + "OAuth1!"),
                full_name=full_name,
                avatar_url=avatar_url,
                is_verified=True,
                oauth_provider="google",
                oauth_id=google_sub or None,
                is_active=True,
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

    async def authenticate_apple(self, id_token: str, full_name: str | None = None) -> dict:
        if not id_token or not str(id_token).strip():
            raise BadRequestError("Apple identity token is required.")

        settings = get_settings()
        if not settings.APPLE_CLIENT_ID:
            raise UnauthorizedError("Apple sign-in is not configured.")

        try:
            payload = await self._verify_apple_identity_token(
                id_token.strip(),
                audience=settings.APPLE_CLIENT_ID,
            )
        except UnauthorizedError:
            raise
        except Exception as exc:
            log.warning("Apple token verification failed: %s", exc)
            raise UnauthorizedError("Invalid Apple identity token.")

        if not payload or not isinstance(payload, dict):
            raise UnauthorizedError("Invalid Apple identity token.")

        apple_sub = str(payload.get("sub") or "").strip()
        if not apple_sub:
            raise BadRequestError("Apple token contains no subject identifier.")

        email = (payload.get("email") or "").strip().lower()
        if not email:
            result = await self.db.execute(
                select(User).where(
                    (User.oauth_provider == "apple") & (User.oauth_id == apple_sub)
                )
            )
            user = result.scalars().first()
            if not user:
                raise BadRequestError("Email address missing from Apple token and no linked user found.")
        else:
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
            await self.db.flush()
            await self.db.refresh(user)
        else:
            username = await self._generate_unique_username()
            user = User(
                email=email,
                username=username,
                hashed_password=hash_password(secrets.token_urlsafe(32) + "OAuth1!"),
                full_name=full_name,
                is_verified=True,
                oauth_provider="apple",
                oauth_id=apple_sub,
                is_active=True,
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

    async def refresh_token(self, refresh_token: str) -> dict:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise UnauthorizedError("Invalid or expired refresh token.")

        jti = payload.get("jti")
        user_id = payload.get("sub")
        if not jti or not user_id:
            raise UnauthorizedError("Invalid refresh token payload.")

        rt = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.jti == jti,
                RefreshToken.user_id == user_id,
            ).with_for_update()
        )
        stored_token = rt.scalars().first()
        if not stored_token:
            raise UnauthorizedError("Invalid or expired refresh token.")
        if stored_token.revoked:
            # Persist the replay response's account-wide revocation before the
            # route raises 401 (the request dependency rolls back on exceptions).
            await self._revoke_all_user_tokens(user_id)
            await self.db.commit()
            raise UnauthorizedError("Invalid or reused refresh token. Please log in again.")
        expires_at = stored_token.expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at <= datetime.now(timezone.utc):
            raise UnauthorizedError("Invalid or expired refresh token.")

        user = await self.db.get(User, user_id)
        if user is None:
            raise NotFoundError("User not found.")
        if not user.is_active:
            raise UnauthorizedError("Account is deactivated.")

        stored_token.revoked = True
        stored_token.revoked_at = datetime.now(timezone.utc)
        await self.db.flush()

        return await self._create_token_pair(user)

    async def logout(self, refresh_token: str) -> None:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            return
        jti = payload.get("jti")
        user_id = payload.get("sub")
        if not jti or not user_id:
            return
        await self._revoke_token_by_jti(jti, user_id)

    async def logout_all(self, user_id: str) -> None:
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
        await self._revoke_all_user_tokens(user_id)
        await self.email_service.send_password_changed_alert(user.email)

    async def forgot_password(self, email: str) -> None:
        email = email.strip().lower()
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        user = result.scalars().first()
        if user is None:
            return

        # Invalidate old unused reset codes
        await self.db.execute(
            delete(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used == False,
            )
        )
        await self.db.flush()

        # Generate 6-digit OTP
        settings = get_settings()
        code = _generate_otp()
        code_hash = _hash_code(code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)

        reset_token_record = PasswordResetToken(
            token_hash=code_hash,
            user_id=user.id,
            expires_at=expires_at,
        )
        self.db.add(reset_token_record)
        await self.db.flush()
        await self.db.commit()

        await self.email_service.send_password_reset_code(user.email, code)

    async def verify_reset_code(self, email: str, code: str) -> dict:
        """
        Step 2 of 3: Verify the 6-digit reset code, mark OTP used immediately,
        and issue a temporary signed reset_token grant.
        """
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

        # Consume / Burn the OTP immediately so it cannot be reused
        reset_token_record.used = True
        await self.db.flush()

        # Create temporary signed JWT grant for setting the password (single-use via DB jti)
        settings = get_settings()
        grant_token = create_password_reset_grant_token(user.id, user.email)
        grant_payload = decode_password_reset_grant_token(grant_token)
        grant_jti = (grant_payload or {}).get("jti")
        if not grant_jti:
            raise BadRequestError("Failed to issue reset session. Please try again.")

        grant_expires = datetime.now(timezone.utc) + timedelta(
            minutes=settings.PASSWORD_RESET_GRANT_EXPIRE_MINUTES
        )
        grant_record = PasswordResetToken(
            token_hash=_hash_code(f"grant:{grant_jti}"),
            user_id=user.id,
            expires_at=grant_expires,
            used=False,
        )
        self.db.add(grant_record)
        await self.db.flush()

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
        """
        Step 3 of 3: Set new password using reset_token grant (or email+code fallback).
        Revokes all active sessions on all devices and sends security notification email.
        """
        user: User | None = None

        if reset_token:
            payload = decode_password_reset_grant_token(reset_token)
            if not payload or not payload.get("sub") or not payload.get("jti"):
                raise BadRequestError("Invalid or expired reset session. Please request a new code.")
            user_id = payload.get("sub")
            grant_jti = payload.get("jti")
            grant_hash = _hash_code(f"grant:{grant_jti}")
            grant_result = await self.db.execute(
                select(PasswordResetToken).where(
                    PasswordResetToken.user_id == user_id,
                    PasswordResetToken.token_hash == grant_hash,
                    PasswordResetToken.used == False,
                    PasswordResetToken.expires_at > datetime.now(timezone.utc),
                )
            )
            grant_record = grant_result.scalars().first()
            if not grant_record:
                raise BadRequestError("Invalid or expired reset session. Please request a new code.")
            grant_record.used = True
            user = await self.db.get(User, user_id)
            if user is None:
                raise NotFoundError("User not found.")
        elif email and code:
            # Fallback for direct code redemption
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

        user.hashed_password = hash_password(new_password)
        await self.db.flush()
        await self._revoke_all_user_tokens(user.id)
        await self.email_service.send_password_changed_alert(user.email)

    async def _verify_apple_identity_token(self, id_token: str, audience: str) -> dict:
        """Verify Apple identity token signature against Apple JWKS (RS256)."""
        import base64

        from cryptography.hazmat.primitives.asymmetric import rsa
        from jose import jwt as jose_jwt
        from jose.exceptions import JWTError as JoseJWTError

        try:
            header = jose_jwt.get_unverified_header(id_token)
        except Exception as exc:
            raise UnauthorizedError("Invalid Apple identity token.") from exc

        kid = header.get("kid")
        alg = header.get("alg") or "RS256"
        if not kid or alg != "RS256":
            raise UnauthorizedError("Invalid Apple identity token header.")

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get("https://appleid.apple.com/auth/keys")
                resp.raise_for_status()
                jwks = resp.json()
        except Exception as exc:
            log.warning("Failed to fetch Apple JWKS: %s", exc)
            raise UnauthorizedError("Unable to verify Apple identity token.") from exc

        key_data = next((k for k in (jwks.get("keys") or []) if k.get("kid") == kid), None)
        if not key_data or key_data.get("kty") != "RSA":
            raise UnauthorizedError("Apple identity token signing key not found.")

        def _b64url_uint(val: str) -> int:
            pad = "=" * (-len(val) % 4)
            return int.from_bytes(base64.urlsafe_b64decode(val + pad), "big")

        try:
            public_numbers = rsa.RSAPublicNumbers(
                _b64url_uint(key_data["e"]),
                _b64url_uint(key_data["n"]),
            )
            public_key = public_numbers.public_key()
            from cryptography.hazmat.primitives import serialization

            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            payload = jose_jwt.decode(
                id_token,
                public_pem,
                algorithms=["RS256"],
                audience=audience,
                issuer="https://appleid.apple.com",
                options={"verify_at_hash": False},
            )
        except JoseJWTError as exc:
            raise UnauthorizedError("Invalid Apple identity token.") from exc
        except Exception as exc:
            log.warning("Apple token cryptographic verification failed: %s", exc)
            raise UnauthorizedError("Invalid Apple identity token.") from exc

        return payload

    async def _send_verification_otp(self, user: User) -> None:
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

        await self.email_service.send_verification_code(user.email, code)

    async def _generate_unique_username(self) -> str:
        for _ in range(10):
            username = f"user_{uuid4().hex[:12]}"
            existing = await self.db.execute(
                select(User).where(User.username == username)
            )
            if not existing.scalars().first():
                return username
        return f"user_{uuid4().hex[:8]}_{int(datetime.now(timezone.utc).timestamp())}"

    async def _create_token_pair(self, user: User) -> dict:
        token_data = {
            "sub": user.id,
            "tv": int(getattr(user, "token_version", 0) or 0),
        }
        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)
        rt_payload = decode_token(refresh_token)
        jti = rt_payload.get("jti")
        exp = rt_payload.get("exp")
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

    async def _bump_token_version(self, user_id: str) -> None:
        user = await self.db.get(User, user_id)
        if user is None:
            return
        user.token_version = int(getattr(user, "token_version", 0) or 0) + 1
        await self.db.flush()

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
        await self._bump_token_version(user_id)
        await self.db.flush()
