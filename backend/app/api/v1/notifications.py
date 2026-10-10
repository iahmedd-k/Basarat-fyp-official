from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.redis import cache_get, cache_set, cache_invalidate, cache_invalidate_pattern
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
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    limit: int = Query(20, ge=1, le=100, description="Items per page"),
    unread_only: bool = Query(False, description="Filter for unread notifications only"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve the authenticated user's Notification Center inbox."""
    try:
        cache_key = f"notifications:list:{user.id}:{page}:{limit}:{unread_only}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return NotificationsListResponse(**cached)

        base_filter = Alert.user_id == user.id
        if unread_only:
            base_filter = base_filter & (Alert.is_read == False)

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
                rule_id=a.rule_id or "",
                title=a.title,
                message=a.message or "",
                is_read=a.is_read,
                created_at=a.created_at.isoformat() if a.created_at else "",
            )
            for a in alerts
        ]

        res = NotificationsListResponse(
            notifications=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )
        await cache_set(cache_key, res.model_dump(mode="json"), ttl_seconds=30)
        return res
    except Exception as exc:
        raise ServiceUnavailableError("Failed to fetch notifications")


@router.patch(
    "/notifications/read-all",
    status_code=204,
    summary="Mark all notifications as read",
)
async def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark all unread notifications for the authenticated user as read."""
    try:
        await db.execute(
            update(Alert)
            .where(Alert.user_id == user.id, Alert.is_read == False)
            .values(is_read=True)
        )
        await db.flush()
        await cache_invalidate_pattern(f"notifications:list:{user.id}:*")
        await cache_invalidate_pattern(f"alerts:list:{user.id}:*")
    except Exception as exc:
        raise ServiceUnavailableError("Failed to mark all notifications as read")


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
    """Mark an individual notification inbox item as read."""
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
        await cache_invalidate_pattern(f"notifications:list:{user.id}:*")
        await cache_invalidate_pattern(f"alerts:list:{user.id}:*")
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError("Failed to mark notification as read")
