from fastapi import APIRouter, Depends, Request, status
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
    UserProfileResponse,
    VerifyEmailRequest,
    VerifyResetCodeRequest,
    VerifyResetCodeResponse,
)
from app.services.auth_service import AuthService

router = APIRouter(tags=["Authentication"])
log = logging.getLogger(__name__)


def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


# ============================================================================
# 1. Registration & Email Verification (OTP) Flow
# ============================================================================

@router.post(
    "/auth/signup",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account (Sends 6-digit OTP)",
    description=(
        "**Step 1 of Signup Flow:**\n\n"
        "- Registers an unverified user account.\n"
        "- Automatically sends a 6-digit verification code to the given email (expires in 10 minutes).\n"
        "- **Next Mobile/Client Step:** Prompt user to enter the OTP received in email, then call `POST /auth/verify-email`."
    ),
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
    status_code=status.HTTP_200_OK,
    summary="Verify email OTP & login (Returns JWT tokens)",
    description=(
        "**Step 2 of Signup Flow:**\n\n"
        "- Verifies the 6-digit OTP code sent during signup.\n"
        "- Activates the user account (`is_verified = True`).\n"
        "- Returns JWT `access_token` and rotating `refresh_token` so the user is immediately logged in.\n"
        "- **Next Mobile/Client Step:** Save `access_token` for Bearer headers and `refresh_token` in secure storage."
    ),
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
    status_code=status.HTTP_200_OK,
    summary="Resend email verification OTP code",
    description=(
        "**Resend Signup OTP:**\n\n"
        "- Invalidates previous pending signup codes and generates a fresh 6-digit OTP.\n"
        "- Sends the new code to the user's email address.\n"
        "- Returns generic success message to prevent user enumeration."
    ),
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


# ============================================================================
# 2. Login, Token Refresh & Session Management
# ============================================================================

@router.post(
    "/auth/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate user with email and password",
    description=(
        "**Login:**\n\n"
        "- Authenticates user credentials.\n"
        "- Ensures account is active and email has been verified with OTP.\n"
        "- Returns short-lived `access_token` (Bearer) and long-lived `refresh_token`."
    ),
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
    status_code=status.HTTP_200_OK,
    summary="Refresh access token (With automatic token rotation)",
    description=(
        "**Token Rotation:**\n\n"
        "- Exchanges a valid `refresh_token` for a fresh `access_token` and a new `refresh_token`.\n"
        "- The old refresh token is revoked immediately.\n"
        "- If a revoked refresh token is reused, all active sessions for the user are invalidated as a security defense."
    ),
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


@router.get(
    "/auth/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current logged-in user profile & status",
    description=(
        "**Current User Profile:**\n\n"
        "- Requires `Authorization: Bearer <access_token>`.\n"
        "- Returns the authenticated user's ID, email, username, verification state, and profile settings."
    ),
)
async def get_me(
    user: User = Depends(get_current_user),
):
    return user


@router.post(
    "/auth/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Logout single session (Revoke refresh token)",
    description=(
        "**Logout:**\n\n"
        "- Invalides the provided `refresh_token` in the database.\n"
        "- Returns HTTP 204 No Content."
    ),
)
@limiter.limit("10/minute")
async def logout(
    request: Request,
    data: LogoutRequest,
    service: AuthService = Depends(_get_service),
):
    await service.logout(data.refresh_token)


@router.post(
    "/auth/logout-all",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Logout all devices (Revoke all active sessions)",
    description=(
        "**Global Logout:**\n\n"
        "- Requires `Authorization: Bearer <access_token>`.\n"
        "- Revokes all refresh tokens across all devices/browsers for the logged-in user."
    ),
)
@limiter.limit("5/minute")
async def logout_all(
    request: Request,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    try:
        await service.logout_all(user.id)
        return MessageResponse(message="All active sessions have been logged out.")
    except Exception:
        log.exception("Logout all failed")
        raise ServiceUnavailableError("Logout all failed")


# ============================================================================
# 3. Professional 3-Step Forgot Password Flow (OTP + Grant Token)
# ============================================================================

@router.post(
    "/auth/forgot-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 1 of 3: Request 6-digit password reset OTP",
    description=(
        "**Step 1 of 3 (Forgot Password):**\n\n"
        "- Client sends registered account email.\n"
        "- If account exists, generates and emails a 6-digit OTP code (valid for 10 minutes).\n"
        "- Returns generic success response to prevent account enumeration.\n"
        "- **Next Mobile/Client Step:** Prompt user for the 6-digit code, then call `POST /auth/verify-reset-code`."
    ),
)
@limiter.limit("3/minute")
async def forgot_password(
    request: Request,
    data: ForgotPasswordRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        await service.forgot_password(data.email)
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.exception("Forgot password failed")
        raise ServiceUnavailableError("Forgot password failed")
    return MessageResponse(message="If the email exists, a 6-digit reset code has been sent.")


@router.post(
    "/auth/verify-reset-code",
    response_model=VerifyResetCodeResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 2 of 3: Verify 6-digit OTP (Returns reset_token grant)",
    description=(
        "**Step 2 of 3 (Forgot Password):**\n\n"
        "- Client sends email and the 6-digit OTP code.\n"
        "- Backend verifies OTP and immediately burns/consumes it (prevents replay attacks).\n"
        "- Returns a temporary signed `reset_token` (valid for 15 minutes).\n"
        "- **Next Mobile/Client Step:** Take the `reset_token` and user's new password, then call `POST /auth/reset-password`."
    ),
)
@limiter.limit("10/minute")
async def verify_reset_code(
    request: Request,
    data: VerifyResetCodeRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.verify_reset_code(data.email, data.code)
    except (BadRequestError, NotFoundError):
        raise
    except RateLimitExceeded:
        raise
    except Exception as e:
        log.exception("Verify reset code failed")
        raise ServiceUnavailableError("Verify reset code failed")


@router.post(
    "/auth/reset-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Step 3 of 3: Set new password using reset_token grant",
    description=(
        "**Step 3 of 3 (Forgot Password):**\n\n"
        "- Client submits `reset_token` (from Step 2), `new_password`, and `confirm_password`.\n"
        "- Updates user password and revokes ALL existing refresh tokens on all devices.\n"
        "- Sends security notification email alert to user.\n"
        "- **Next Mobile/Client Step:** Navigate user to login screen to log in with their new password."
    ),
)
@limiter.limit("3/minute")
async def reset_password(
    request: Request,
    data: ResetPasswordRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        await service.reset_password(
            new_password=data.new_password,
            reset_token=data.reset_token,
            email=data.email,
            code=data.code,
        )
        return MessageResponse(
            message="Password has been reset successfully. Please log in with your new password."
        )
    except (BadRequestError, ValidationFailedError, NotFoundError, RateLimitExceeded):
        raise
    except Exception as e:
        log.exception("Password reset failed")
        raise ServiceUnavailableError("Password reset failed")


# ============================================================================
# 4. Authenticated Password Change
# ============================================================================

@router.post(
    "/auth/change-password",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Change password while logged in (Authenticated)",
    description=(
        "**Change Password:**\n\n"
        "- Requires `Authorization: Bearer <access_token>`.\n"
        "- Validates `current_password` before setting `new_password`.\n"
        "- Revokes all other refresh tokens for security and sends security email alert."
    ),
)
@limiter.limit("5/minute")
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
        return MessageResponse(message="Password changed successfully. Other sessions have been revoked.")
    except (UnauthorizedError, NotFoundError, ValidationFailedError, RateLimitExceeded):
        raise
    except Exception as e:
        log.exception("Password change failed")
        raise ServiceUnavailableError("Password change failed")
