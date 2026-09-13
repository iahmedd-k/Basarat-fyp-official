# app/api/v1/auth.py
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.rate_limit import limiter
from app.db.session import get_db
from app.schemas.user import SignupRequest, LoginRequest, RefreshRequest, TokenResponse
from app.services.auth_service import (
    create_user,
    authenticate_user,
    issue_tokens,
    rotate_refresh_token,
    revoke_refresh_token,
)

from app.schemas.user import ForgotPasswordRequest, ResetPasswordRequest
from app.services.auth_service import request_password_reset, reset_password as reset_password_service

router = APIRouter()


@router.post(
    "/auth/signup",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
)
async def signup(payload: SignupRequest, db: AsyncSession = Depends(get_db)):
    user = await create_user(db, payload)
    access_token, refresh_token = issue_tokens(user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/login", response_model=TokenResponse)
@limiter.limit("20/minute")
async def login(request: Request, payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, payload)
    access_token, refresh_token = issue_tokens(user)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/refresh", response_model=TokenResponse)
async def refresh(payload: RefreshRequest, db: AsyncSession = Depends(get_db)):
    access_token, refresh_token = await rotate_refresh_token(db, payload)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(payload: RefreshRequest):
    await revoke_refresh_token(payload)



@router.post("/auth/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(payload: ForgotPasswordRequest, db: AsyncSession = Depends(get_db)):
    await request_password_reset(db, payload)
    return {"detail": "If that email is registered, a reset link has been sent"}


@router.post("/auth/reset-password", status_code=status.HTTP_200_OK)
async def reset_password_endpoint(payload: ResetPasswordRequest, db: AsyncSession = Depends(get_db)):
    await reset_password_service(db, payload)
    return {"detail": "Password reset successful"}