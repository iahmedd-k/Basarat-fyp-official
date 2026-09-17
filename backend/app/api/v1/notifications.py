from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.alert import Alert
from app.models.user import User
from app.schemas.auth import AlertResponse, NotificationsListResponse

router = APIRouter()


@router.get(
    "/notifications",
    response_model=NotificationsListResponse,
    summary="Get user notifications",
)
async def get_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        base_filter = Alert.user_id == user.id
        if unread_only:
            base_filter = base_filter & (Alert.is_read == False)

        from sqlalchemy import func
        total_result = await db.execute(
            select(func.count(Alert.id)).where(base_filter)
        )
        total = total_result.scalar() or 0

        query = (
            select(Alert)
            .where(base_filter)
            .order_by(Alert.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
        )

        result = await db.execute(query)
        alerts = result.scalars().all()

        items = [
            AlertResponse(
                id=a.id,
                user_id=a.user_id,
                rule_id=a.rule_id,
                title=a.title,
                message=a.message,
                is_read=a.is_read,
                created_at=a.created_at.isoformat() if a.created_at else "",
            )
            for a in alerts
        ]

        return NotificationsListResponse(
            notifications=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )
    except Exception as exc:
        raise ServiceUnavailableError("Failed to fetch notifications")


@router.patch(
    "/notifications/{notification_id}/read",
    status_code=204,
    summary="Mark a notification as read",
)
async def mark_notification_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(Alert).where(
                Alert.id == notification_id,
                Alert.user_id == user.id,
            )
        )
        alert = result.scalars().first()
        if alert is None:
            raise NotFoundError(f"Notification '{notification_id}' not found.")

        alert.is_read = True
        await db.flush()
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError("Failed to mark notification as read")
