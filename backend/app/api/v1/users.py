from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    InvestmentHorizon,
    NO_PREFERENCE,
    RiskTolerance,
    SectorPreference,
    UpdateNotificationPrefsRequest,
    UpdateProfileRequest,
    UserProfileResponse,
    VALID_SECTORS,
)
from app.services.auth_service import AuthService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(db)


@router.get(
    "/users/me",
    response_model=UserProfileResponse,
    summary="Get current user profile & investment preferences",
)
@router.get(
    "/users/me/investment-profile",
    response_model=UserProfileResponse,
    summary="Get current user investment profile",
    include_in_schema=False,
)
@router.get(
    "/users/me/risk-profile",
    response_model=UserProfileResponse,
    summary="Get current user risk profile (alias)",
    include_in_schema=False,
)
async def get_profile(
    user: User = Depends(get_current_user),
):
    """Retrieve full profile including contact details and investment preferences."""
    return user


@router.patch(
    "/users/me",
    response_model=UserProfileResponse,
    summary="Update current user profile and investment preferences",
)
@router.post(
    "/users/me",
    response_model=UserProfileResponse,
    summary="Set current user profile and investment preferences",
)
@router.patch(
    "/users/me/investment-profile",
    response_model=UserProfileResponse,
    summary="Update investment profile preferences",
    include_in_schema=False,
)
@router.post(
    "/users/me/investment-profile",
    response_model=UserProfileResponse,
    summary="Set investment profile preferences",
    include_in_schema=False,
)
@router.patch(
    "/users/me/risk-profile",
    response_model=UserProfileResponse,
    summary="Update risk profile preferences (alias)",
    include_in_schema=False,
)
@router.post(
    "/users/me/risk-profile",
    response_model=UserProfileResponse,
    summary="Set risk profile preferences (alias)",
    include_in_schema=False,
)
async def update_profile(
    data: UpdateProfileRequest,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    """
    Unified endpoint to update personal details (full_name, avatar_url)
    and/or investment profile (risk_tolerance, sector_preferences, investment_horizon).
    """
    try:
        risk_tol = data.risk_tolerance.value if data.risk_tolerance else None
        inv_horiz = data.investment_horizon.value if data.investment_horizon else None

        updated = await service.update_profile(
            user_id=user.id,
            full_name=data.full_name,
            avatar_url=data.avatar_url,
            risk_tolerance=risk_tol,
            sector_preferences=data.sector_preferences,
            investment_horizon=inv_horiz,
        )
        return updated
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError("Failed to update profile")


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
    "/users/investment-profile/options",
    summary="Get valid options for risk tolerance, investment horizon, and sector preferences",
)
@router.get(
    "/users/risk-profile/options",
    summary="Get valid options for risk tolerance, investment horizon, and sector preferences (alias)",
    include_in_schema=False,
)
@router.get(
    "/users/risk-profile/sectors",
    summary="Get valid sector options (alias)",
    include_in_schema=False,
)
@router.get(
    "/users/sectors",
    summary="Get valid sector options (alias)",
    include_in_schema=False,
)
async def get_investment_profile_options():
    """Get all allowed enum options for user investment profile configuration."""
    return {
        "risk_tolerances": [rt.value for rt in RiskTolerance],
        "investment_horizons": [ih.value for ih in InvestmentHorizon],
        "sectors": [s.value for s in SectorPreference],
        "no_preference": NO_PREFERENCE,
        "description": "Select allowed risk tolerances, investment horizons, and sector preferences.",
    }
