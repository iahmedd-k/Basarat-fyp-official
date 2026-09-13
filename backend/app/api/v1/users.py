# app/api/v1/users.py
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserResponse, UpdateProfileRequest
from app.schemas.user import RiskProfileRequest, RiskProfileResponse
from app.services.user_service import update_profile, upsert_risk_profile
from app.schemas.user import NotificationPrefsRequest, NotificationPrefsResponse
from app.services.user_service import upsert_notification_prefs

router = APIRouter()


@router.get("/users/me", response_model=UserResponse)
async def read_current_user(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/users/me", response_model=UserResponse)
async def patch_current_user(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    updated = await update_profile(db, current_user, payload)
    return updated


@router.patch("/users/me/risk-profile", response_model=RiskProfileResponse)
async def patch_risk_profile(
    payload: RiskProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    profile = await upsert_risk_profile(db, current_user, payload)
    return profile




@router.patch("/users/me/notification-preferences", response_model=NotificationPrefsResponse)
async def patch_notification_preferences(
    payload: NotificationPrefsRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    prefs = await upsert_notification_prefs(db, current_user, payload)
    return prefs