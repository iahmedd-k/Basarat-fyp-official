from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ChangePasswordRequest,
    ForgotPasswordRequest,
    LoginRequest,
    RefreshRequest,
    ResetPasswordRequest,
    SignupRequest,
    TokenResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.post(
    "/auth/signup",
    response_model=TokenResponse,
    status_code=201,
    summary="Register a new user account",
)
async def signup(
    data: SignupRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.signup(
            email=data.email,
            password=data.password,
            full_name=data.full_name,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Signup failed: {exc}")


@router.post(
    "/auth/login",
    response_model=TokenResponse,
    summary="Authenticate and get tokens",
)
async def login(
    data: LoginRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.login(
            email=data.email,
            password=data.password,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Login failed: {exc}")


@router.post(
    "/auth/refresh",
    response_model=TokenResponse,
    summary="Refresh access token using refresh token",
)
async def refresh_token(
    data: RefreshRequest,
    service: AuthService = Depends(_get_service),
):
    try:
        return await service.refresh_token(data.refresh_token)
    except Exception as exc:
        raise ServiceUnavailableError(f"Token refresh failed: {exc}")


@router.post(
    "/auth/logout",
    status_code=204,
    summary="Logout and invalidate refresh token",
)
async def logout(
    user: User = Depends(get_current_user),
):
    return None


@router.post(
    "/auth/forgot-password",
    status_code=202,
    summary="Request a password reset link",
)
async def forgot_password(
    data: ForgotPasswordRequest,
    service: AuthService = Depends(_get_service),
):
    return {"message": "If the email exists, a reset link has been sent."}


@router.post(
    "/auth/reset-password",
    status_code=204,
    summary="Reset password using token",
)
async def reset_password(
    data: ResetPasswordRequest,
    service: AuthService = Depends(_get_service),
):
    return None


@router.post(
    "/auth/change-password",
    status_code=204,
    summary="Change password (authenticated)",
)
async def change_password(
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
    except Exception as exc:
        raise ServiceUnavailableError(f"Password change failed: {exc}")
