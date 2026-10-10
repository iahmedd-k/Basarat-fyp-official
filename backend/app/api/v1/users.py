from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import AppError, NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    InvestmentHorizon,
    NO_PREFERENCE,
    RiskTolerance,
    RequestEmailChangeRequest,
    SectorPreference,
    UpdateNotificationPrefsRequest,
    UpdateProfileRequest,
    UserProfileResponse,
    VALID_SECTORS,
    VerifyEmailChangeRequest,
)
from app.services.auth_service import AuthService
from app.services.cloudinary_service import cloudinary_service
from app.core.redis import cache_invalidate, cache_invalidate_pattern

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
        risk_tol = data.risk_tolerance.value if hasattr(data.risk_tolerance, "value") else data.risk_tolerance
        inv_horiz = data.investment_horizon.value if hasattr(data.investment_horizon, "value") else data.investment_horizon

        updated = await service.update_profile(
            user_id=user.id,
            full_name=data.full_name,
            phone=data.phone,
            avatar_url=data.avatar_url,
            risk_tolerance=risk_tol,
            sector_preferences=(
                [sector.value if hasattr(sector, "value") else str(sector) for sector in data.sector_preferences]
                if data.sector_preferences is not None
                else None
            ),
            investment_horizon=inv_horiz,
        )
        await cache_invalidate(f"auth:user:{user.id}")
        await cache_invalidate_pattern(f"community:profile:{user.id}*")
        await cache_invalidate_pattern(f"rec:list:v3:{user.id}:*")
        return updated
    except AppError:
        raise
    except Exception:
        raise ServiceUnavailableError("Failed to update profile")


@router.post(
    "/users/me/email-change",
    summary="Send a verification code to a new email address",
)
async def request_email_change(
    data: RequestEmailChangeRequest,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    return await service.request_email_change(user.id, str(data.email))


@router.post(
    "/users/me/email-change/verify",
    response_model=UserProfileResponse,
    summary="Verify and update the current user's email address",
)
async def verify_email_change(
    data: VerifyEmailChangeRequest,
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    res = await service.verify_email_change(user.id, data.code)
    await cache_invalidate(f"auth:user:{user.id}")
    return res


@router.post(
    "/users/me/avatar",
    response_model=UserProfileResponse,
    summary="Upload the current user's profile image to Cloudinary",
)
async def upload_profile_image(
    image: UploadFile = File(...),
    user: User = Depends(get_current_user),
    service: AuthService = Depends(_get_service),
):
    avatar_url, _ = await cloudinary_service.upload_image(
        image,
        folder=f"profile-images/{user.id}",
    )
    res = await service.update_profile(user_id=user.id, avatar_url=avatar_url)
    await cache_invalidate(f"auth:user:{user.id}")
    await cache_invalidate_pattern(f"community:profile:{user.id}*")
    return res


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
        await cache_invalidate(f"auth:user:{user.id}")
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
