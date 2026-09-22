from datetime import datetime, timedelta, timezone
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt

from app.core.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(
        plain_password.encode("utf-8"), hashed_password.encode("utf-8")
    )


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire, "type": "access", "jti": uuid4().hex})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    to_encode.update({"exp": expire, "type": "refresh", "jti": uuid4().hex})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        return None


def create_email_verification_token(user_id: str) -> str:
    to_encode = {"sub": user_id}
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire, "type": "email_verification", "jti": uuid4().hex})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_email_verification_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "email_verification":
            return None
        return payload
    except JWTError:
        return None


def create_password_reset_grant_token(user_id: str, email: str) -> str:
    """Creates a short-lived (15 min) JWT grant token returned after OTP verification in Step 2."""
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.PASSWORD_RESET_GRANT_EXPIRE_MINUTES)
    to_encode = {
        "sub": user_id,
        "email": email,
        "type": "password_reset_grant",
        "exp": expire,
        "jti": uuid4().hex,
    }
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_password_reset_grant_token(token: str) -> dict | None:
    """Validates and decodes the password reset grant token."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if payload.get("type") != "password_reset_grant":
            return None
        return payload
    except JWTError:
        return None
