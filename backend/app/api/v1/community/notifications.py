from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.authorization import get_current_user
from app.core.exceptions import (
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.community import (
    CommunityNotificationsListResponse,
    CommunityNotificationResponse,
    NotificationType,
)
from app.services.community_service import CommunityService

router = APIRouter()
log = logging.getLogger(__name__)


async def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    return CommunityService(db)


from app.core.redis import cache_get, cache_set
from app.services.community_cache_service import CommunityCacheService


@router.get(
    "/community/notifications",
    response_model=CommunityNotificationsListResponse,
    summary="Get community notifications",
)
async def get_notifications(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        cache_key = CommunityCacheService.notifications_key(user.id, page, limit, unread_only)
        cached = await cache_get(cache_key)
        if cached is not None:
            return CommunityNotificationsListResponse(**cached)

        notifications, total = await service.get_notifications(
            user_id=user.id,
            page=page,
            limit=limit,
            unread_only=unread_only,
        )

        notification_responses = []
        for n in notifications:
            notification_responses.append(
                CommunityNotificationResponse(
                    id=n.id,
                    recipient_id=n.recipient_id,
                    actor_id=n.actor_id,
                    actor_username=n.actor.username if n.actor else None,
                    post_id=n.post_id,
                    comment_id=n.comment_id,
                    type=NotificationType(n.type),
                    title=n.title,
                    message=n.message,
                    is_read=n.is_read,
                    created_at=n.created_at,
                )
            )

        resp = CommunityNotificationsListResponse(
            notifications=notification_responses,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )
        await cache_set(cache_key, resp.model_dump(mode="json"), ttl_seconds=15)
        return resp
    except Exception as e:
        log.exception("Get notifications failed")
        raise ServiceUnavailableError("Failed to get notifications")


@router.get(
    "/community/notifications/unread-count",
    summary="Get unread notification count",
)
async def get_unread_count(
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        cache_key = CommunityCacheService.unread_count_key(user.id)
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        count = await service.get_unread_count(user.id)
        result = {"unread_count": count}
        await cache_set(cache_key, result, ttl_seconds=15)
        return result
    except Exception as e:
        log.exception("Get unread count failed")
        raise ServiceUnavailableError("Failed to get unread count")


@router.post(
    "/community/notifications/{notification_id}/read",
    status_code=204,
    summary="Mark notification as read",
)
async def mark_notification_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.mark_notification_read(notification_id, user.id)
        await CommunityCacheService.invalidate_notification_mutations(user.id)
    except (NotFoundError, ForbiddenError):
        raise
    except Exception as e:
        log.exception("Mark notification read failed")
        raise ServiceUnavailableError("Failed to mark notification as read")


@router.post(
    "/community/notifications/read-all",
    status_code=204,
    summary="Mark all notifications as read",
)
async def mark_all_notifications_read(
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.mark_all_notifications_read(user.id)
        await CommunityCacheService.invalidate_notification_mutations(user.id)
    except Exception as e:
        log.exception("Mark all notifications read failed")
        raise ServiceUnavailableError("Failed to mark all notifications as read")