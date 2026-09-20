from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.user import Device, User
from app.schemas.auth import DeviceRegisterRequest, DeviceResponse

router = APIRouter()


@router.post(
    "/devices/register",
    response_model=DeviceResponse,
    status_code=201,
    summary="Register a device for push notifications",
)
async def register_device(
    data: DeviceRegisterRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Register or refresh an FCM device token for mobile push notifications.

    - **fcm_token**: Firebase Cloud Messaging registration token generated on client.
    - **platform**: Client OS (`android`, `ios`, `web`).
    - **device_name**: Optional human-readable device identifier (e.g. `Samsung S23`).

    If the token already exists for the user, it reactivates the device (`is_active = true`).
    """
    try:
        result = await db.execute(
            select(Device).where(
                Device.user_id == user.id,
                Device.fcm_token == data.fcm_token,
            )
        )
        existing = result.scalars().first()

        if existing:
            existing.platform = data.platform
            existing.device_name = data.device_name
            existing.is_active = True
            await db.flush()
            await db.refresh(existing)
            return DeviceResponse(
                id=existing.id,
                fcm_token=existing.fcm_token,
                device_name=existing.device_name,
                platform=existing.platform,
                is_active=existing.is_active,
                created_at=existing.created_at.isoformat() if existing.created_at else "",
            )

        device = Device(
            user_id=user.id,
            fcm_token=data.fcm_token,
            platform=data.platform,
            device_name=data.device_name,
        )
        db.add(device)
        await db.flush()
        await db.refresh(device)

        return DeviceResponse(
            id=device.id,
            fcm_token=device.fcm_token,
            device_name=device.device_name,
            platform=device.platform,
            is_active=device.is_active,
            created_at=device.created_at.isoformat() if device.created_at else "",
        )
    except Exception as exc:
        raise ServiceUnavailableError("Failed to register device")


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Deactivate a push notification device")
async def unregister_device(
    device_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Deactivate an FCM device token so the device no longer receives push notifications."""
    result = await db.execute(select(Device).where(Device.id == device_id, Device.user_id == user.id))
    device = result.scalars().first()
    if device is None:
        from app.core.exceptions import NotFoundError
        raise NotFoundError("Device not found")
    device.is_active = False
    await db.flush()
