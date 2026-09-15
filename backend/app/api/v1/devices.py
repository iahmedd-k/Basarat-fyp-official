from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
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
        raise ServiceUnavailableError(f"Failed to register device: {exc}")
