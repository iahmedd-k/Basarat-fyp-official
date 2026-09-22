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
    ResetPasswordRequest,
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
    except ConflictError:
        raise
    except ValidationFailedError:
        raise
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.exception("Signup failed")
        raise ServiceUnavailableError("Signup failed")


@router.post(
    "/auth/verify-email",
    response_model=TokenResponse,
    summary="Verify email with 6-digit code",
)
@limiter.limit("10/minute")
async def verify_email(
    request: Request,
    data: VerifyEmailRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.verify_email(data.email, data.code)
    except BadRequestError:
        raise
    except NotFoundError:
        raise
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.exception("Email verification failed")
        raise ServiceUnavailableError("Email verification failed")


@router.post(
    "/auth/resend-verification",
    response_model=MessageResponse,
    status_code=202,
    summary="Resend verification email",
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
    except UnauthorizedError:
        raise
    except ValidationFailedError:
        raise
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.exception("Login failed")
        raise ServiceUnavailableError("Login failed")


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using refresh token",
)
@limiter.limit("10/minute")
async def refresh_token(
    request: Request,
    data: RefreshRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.refresh_token(data.refresh_token)
    except UnauthorizedError:
        raise
    except ValidationFailedError:
        raise
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.exception("Token refresh failed")
        raise ServiceUnavailableError("Token refresh failed")


# NOTE: Logout is intentionally unauthenticated. SPAs and mobile apps often
# lose their access token but still need to invalidate the refresh token to
# complete a logout. The endpoint returns 204 regardless of whether the token
# was valid, invalid, or already revoked — no information leakage.
@router.post(
    "/auth/logout",
    status_code=204,
    summary="Logout and invalidate refresh token",
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
    status_code=202,
    summary="Request a password reset link",
)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    service: AuthService = Depends(_get_service),
):
    await service.forgot_password(data.email)
    return MessageResponse(message="If the email exists, a reset link has been sent.")


@router.post(
    "/auth/change-password",
    status_code=204,
    summary="Change password (authenticated)",
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
    except UnauthorizedError:
        raise
    except NotFoundError:
        raise
    except ValidationFailedError:
        raise
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.exception("Password change failed")
        raise ServiceUnavailableError("Password change failed")


@router.post(
    "/auth/reset-password",
    status_code=204,
    summary="Reset password using email + code",
)
@limiter.limit("3/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        await service.reset_password(data.email, data.code, data.new_password)
    except BadRequestError:
        raise
    except ValidationFailedError:
        raise
    except NotFoundError:
        raise
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.exception("Password reset failed")
        raise ServiceUnavailableError("Password reset failed")
