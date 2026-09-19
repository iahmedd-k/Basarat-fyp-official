from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    UpdateProfileRequest,
    UpdateRiskProfileRequest,
    UpdateNotificationPrefsRequest,
    UserProfileResponse,
    VALID_SECTORS,
    NO_PREFERENCE,
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
    return user


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
        return updated
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError("Failed to update profile")


@router.patch(
    "/users/me/risk-profile",
    response_model=dict,
    summary="Update user risk profile preferences",
)
async def update_risk_profile(
    data: UpdateRiskProfileRequest,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    try:
        updated = await service.update_risk_profile(
            user_id=user.id,
            risk_tolerance=data.risk_tolerance,
            sector_preferences=data.sector_preferences,
            investment_horizon=data.investment_horizon,
        )
        return {
            "message": "Risk profile updated",
            "risk_tolerance": updated.risk_tolerance,
            "sector_preferences": updated.sector_preferences,
            "investment_horizon": updated.investment_horizon,
        }
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError("Failed to update risk profile")


@router.patch(
    "/users/me/notification-preferences",
    response_model=dict,
    summary="Update notification preferences",
)
async def update_notification_preferences(
    data: UpdateNotificationPrefsRequest,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    try:
        updated = await service.update_notification_preferences(
            user_id=user.id,
            channels=data.channels,
            categories=data.categories,
        )
        prefs = updated.notification_preferences or {}
        return {
            "message": "Notification preferences updated",
            "channels": prefs.get("channels", []),
            "categories": prefs.get("categories", []),
        }
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError("Failed to update notification preferences")


@router.get(
    "/users/risk-profile/sectors",
    summary="Get valid sector options for risk profile preferences",
)
async def get_risk_profile_sectors():
    """Get list of valid sector options for risk profile sector preferences."""
    return {
        "sectors": VALID_SECTORS,
        "no_preference": NO_PREFERENCE,
        "description": "Select one or more sectors. Use 'All Sectors' for no preference.",
    }
