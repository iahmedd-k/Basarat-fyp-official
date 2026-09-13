# app/services/user_service.py
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.schemas.user import UpdateProfileRequest

from sqlalchemy import select

from app.models.risk_profile import RiskProfile
from app.schemas.user import RiskProfileRequest

from app.models.notification_preference import NotificationPreference
from app.schemas.user import NotificationPrefsRequest


async def update_profile(db: AsyncSession, user: User, payload: UpdateProfileRequest) -> User:
    data = payload.model_dump(exclude_unset=True)
    for field, value in data.items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return user



async def upsert_risk_profile(
    db: AsyncSession, user: User, payload: RiskProfileRequest
) -> RiskProfile:
    result = await db.execute(select(RiskProfile).where(RiskProfile.user_id == user.id))
    profile = result.scalar_one_or_none()

    if profile is None:
        profile = RiskProfile(user_id=user.id)
        db.add(profile)

    profile.risk_tolerance = payload.risk_tolerance
    profile.sector_preferences = payload.sector_preferences
    profile.investment_horizon = payload.investment_horizon

    await db.flush()
    await db.refresh(profile)
    return profile



async def upsert_notification_prefs(
    db: AsyncSession, user: User, payload: NotificationPrefsRequest
) -> NotificationPreference:
    result = await db.execute(
        select(NotificationPreference).where(NotificationPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()

    if prefs is None:
        prefs = NotificationPreference(user_id=user.id)
        db.add(prefs)

    prefs.channels = payload.channels
    prefs.categories = payload.categories

    await db.flush()
    await db.refresh(prefs)
    return prefs