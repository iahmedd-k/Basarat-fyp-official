# app/services/device_service.py
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Device, User
from app.schemas.user import DeviceRegisterRequest


async def register_device(
    db: AsyncSession, user: User, payload: DeviceRegisterRequest
) -> Device:
    # A given fcm_token is unique per physical device/app-install, not per user —
    # if it already exists (e.g. re-registering, or a token that moved to a
    # different account after a logout/login on the same phone), reassign
    # rather than error, so re-registration is idempotent.
    result = await db.execute(select(Device).where(Device.fcm_token == payload.fcm_token))
    device = result.scalar_one_or_none()

    if device is None:
        device = Device(user_id=user.id, fcm_token=payload.fcm_token, platform=payload.platform)
        db.add(device)
    else:
        device.user_id = user.id
        device.platform = payload.platform
        device.is_active = True

    await db.flush()
    await db.refresh(device)
    return device