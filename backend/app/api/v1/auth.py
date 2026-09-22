from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.authorization import get_current_user
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    UnauthorizedError,
    ValidationFailedError,
)
from app.core.rate_limiter import limiter
from slowapi.errors import RateLimitExceeded
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    RefreshRequest,
    ResendVerificationRequest,
    SignupRequest,
    TokenResponse,
    VerifyEmailRequest,
)
from app.services.auth_service import AuthService

router = APIRouter()
log = logging.getLogger(__name__)


def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post(
    "/auth/signup",
    response_model=MessageResponse,
    status_code=201,
    summary="Register a new user account",
    description="Creates a new account and sends a 6-digit verification code to the provided email.",
)
@limiter.limit("5/minute")
async def signup(
    request: Request,
    data: SignupRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.signup(
            email=data.email,
            password=data.password,
            full_name=data.full_name,
        )
    except (ConflictError, ValidationFailedError, RateLimitExceeded):
        raise
    except Exception as e:
        log.exception("Signup failed")
        raise ServiceUnavailableError("Signup failed")


@router.post(
    "/auth/verify-email",
    response_model=TokenResponse,
    summary="Verify email address",
    description="Verifies the user's email using the 6-digit code sent during signup. Returns access and refresh tokens on success.",
)
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    data: VerifyEmailRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.verify_email(data.email, data.code)
    except (BadRequestError, NotFoundError, RateLimitExceeded):
        raise
    except Exception as e:
        log.exception("Email verification failed")
        raise ServiceUnavailableError("Email verification failed")


@router.post(
    "/auth/resend-verification",
    response_model=MessageResponse,
    status_code=200,
    summary="Resend verification code",
    description="Generates a new 6-digit verification code and sends it to the user's email. Previous codes are invalidated.",
)
@limiter.limit("3/minute")
async def resend_verification(
    request: Request,
    data: ResendVerificationRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.resend_verification(data.email)
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.exception("Resend verification failed")
        raise ServiceUnavailableError("Resend verification failed")


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Authenticate and get tokens",
    description="Authenticates a verified user with email and password. Returns access and refresh tokens.",
)
@limiter.limit("5/minute")
async def login(
    request: Request,
    data: LoginRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.login(
            email=data.email,
            password=data.password,
        )
    except (UnauthorizedError, ValidationFailedError, RateLimitExceeded):
        raise
    except Exception as e:
        log.exception("Login failed")
        raise ServiceUnavailableError("Login failed")


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Refresh access token",
    description="Exchanges a valid refresh token for a new access/refresh token pair. The old refresh token is revoked (rotation).",
)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    data: RefreshRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.refresh_token(data.refresh_token)
    except (UnauthorizedError, ValidationFailedError, RateLimitExceeded):
        raise
    except Exception as e:
        log.exception("Token refresh failed")
        raise ServiceUnavailableError("Token refresh failed")


@router.post(
    "/auth/logout",
    status_code=204,
    summary="Logout and invalidate refresh token",
    description="Revokes the given refresh token. Always returns 204 regardless of token validity to prevent token enumeration.",
)
@limiter.limit("10/minute")
async def logout(
    request: Request,
    data: LogoutRequest,
    service: AuthService = Depends(_get_service),
):
    await service.logout(data.refresh_token)


@router.post(
    "/auth/forgot-password",
    response_model=MessageResponse,
    status_code=200,
    summary="Request password reset code or reset password",
    description=(
        "Step 1 – Send code: provide {email}. Sends a 6-digit code to the user's email.\n\n"
        "Step 2 – Reset: provide {email, code, new_password}. Resets the password.\n\n"
        "Always returns success to prevent email enumeration."
    ),
)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        if data.code and data.new_password:
            await service.reset_password(data.email, data.code, data.new_password)
            return MessageResponse(message="Password has been reset successfully.")
        else:
            await service.forgot_password(data.email)
            return MessageResponse(message="If the email exists, a reset code has been sent.")
    except (BadRequestError, ValidationFailedError, NotFoundError, RateLimitExceeded):
        raise
    except Exception as e:
        log.exception("Forgot password failed")
        raise ServiceUnavailableError("Forgot password failed")


@router.post(
    "/auth/change-password",
    status_code=204,
    summary="Change password (authenticated)",
    description="Changes the authenticated user's password. All existing refresh tokens are revoked.",
)
@limiter.limit("10/minute")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    try:
        await service.change_password(
            user_id=user.id,
            current_password=data.current_password,
            new_password=data.new_password,
        )
    except (UnauthorizedError, NotFoundError, ValidationFailedError, RateLimitExceeded):
        raise
    except Exception as e:
        log.exception("Password change failed")
        raise ServiceUnavailableError("Password change failed")
