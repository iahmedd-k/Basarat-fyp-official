from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    UpdateProfileRequest,
    UpdateRiskProfileRequest,
    UpdateNotificationPrefsRequest,
    UserProfileResponse,
)
from app.services.auth_service import AuthService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.get(
    "/users/me",
    response_model=UserProfileResponse,
    summary="Get current user profile",
)
async def get_profile(
    user: User = Depends(get_current_user),
):
    try:
        return UserProfileResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            is_active=user.is_active,
            is_verified=user.is_verified,
            is_admin=user.is_admin,
            created_at=user.created_at.isoformat() if user.created_at else "",
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch profile: {exc}")


@router.patch(
    "/users/me",
    response_model=UserProfileResponse,
    summary="Update current user profile",
)
async def update_profile(
    data: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    try:
        updated = await service.update_profile(
            user_id=user.id,
            full_name=data.full_name,
            avatar_url=data.avatar_url,
        )
        return UserProfileResponse(
            id=updated.id,
            email=updated.email,
            username=updated.username,
            full_name=updated.full_name,
            avatar_url=updated.avatar_url,
            is_active=updated.is_active,
            is_verified=updated.is_verified,
            is_admin=updated.is_admin,
            created_at=updated.created_at.isoformat() if updated.created_at else "",
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to update profile: {exc}")


@router.patch(
    "/users/me/risk-profile",
    response_model=dict,
    summary="Update user risk profile preferences",
)
async def update_risk_profile(
    data: UpdateRiskProfileRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        if data.risk_tolerance is not None:
            user.risk_tolerance = data.risk_tolerance
        if data.sector_preferences is not None:
            user.sector_preferences = data.sector_preferences
        if data.investment_horizon is not None:
            user.investment_horizon = data.investment_horizon
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return {
            "message": "Risk profile updated",
            "risk_tolerance": user.risk_tolerance,
            "sector_preferences": user.sector_preferences,
            "investment_horizon": user.investment_horizon,
        }
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to update risk profile: {exc}")


@router.patch(
    "/users/me/notification-preferences",
    response_model=dict,
    summary="Update notification preferences",
)
async def update_notification_preferences(
    data: UpdateNotificationPrefsRequest,
    user: User = Depends(get_current_user),
):
    return {"message": "Notification preferences updated"}
