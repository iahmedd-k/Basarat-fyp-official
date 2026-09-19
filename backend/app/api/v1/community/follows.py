from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.authorization import get_current_user
from app.core.exceptions import (
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.community import (
    CommunityFollowStatusResponse,
    CommunityFollowListResponse,
    CommunityUserSummary,
)
from app.services.community_service import CommunityService

router = APIRouter()
log = logging.getLogger(__name__)


async def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    return CommunityService(db)


@router.post(
    "/community/users/{user_id}/follow",
    status_code=204,
    summary="Follow a user",
)
async def follow_user(
    user_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.follow_user(user.id, user_id)
    except (NotFoundError, ValidationFailedError):
        raise
    except Exception as e:
        log.exception("Follow user failed")
        raise ServiceUnavailableError("Failed to follow user")


@router.delete(
    "/community/users/{user_id}/follow",
    status_code=204,
    summary="Unfollow a user",
)
async def unfollow_user(
    user_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.unfollow_user(user.id, user_id)
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Unfollow user failed")
        raise ServiceUnavailableError("Failed to unfollow user")


@router.get(
    "/community/users/{user_id}/follow-status",
    response_model=CommunityFollowStatusResponse,
    summary="Get follow status",
)
async def get_follow_status(
    user_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        is_following, followers_count, following_count = await service.get_follow_status(
            user.id, user_id
        )
        return CommunityFollowStatusResponse(
            is_following=is_following,
            followers_count=followers_count,
            following_count=following_count,
        )
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Get follow status failed")
        raise ServiceUnavailableError("Failed to get follow status")


@router.get(
    "/community/users/{user_id}/followers",
    response_model=CommunityFollowListResponse,
    summary="Get user's followers",
)
async def get_followers(
    user_id: str,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        target_user = await service.db.get(User, user_id)
        if not target_user:
            raise NotFoundError("User not found")

        users, next_cursor, has_more = await service.get_followers(user_id, cursor, limit)

        user_summaries = [
            CommunityUserSummary(
                id=u.id,
                username=u.username,
                full_name=u.full_name,
                avatar_url=u.avatar_url,
            )
            for u in users
        ]

        return CommunityFollowListResponse(
            users=user_summaries,
            cursor=next_cursor,
            has_more=has_more,
        )
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Get followers failed")
        raise ServiceUnavailableError("Failed to get followers")


@router.get(
    "/community/users/{user_id}/following",
    response_model=CommunityFollowListResponse,
    summary="Get users that user is following",
)
async def get_following(
    user_id: str,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        target_user = await service.db.get(User, user_id)
        if not target_user:
            raise NotFoundError("User not found")

        users, next_cursor, has_more = await service.get_following(user_id, cursor, limit)

        user_summaries = [
            CommunityUserSummary(
                id=u.id,
                username=u.username,
                full_name=u.full_name,
                avatar_url=u.avatar_url,
            )
            for u in users
        ]

        return CommunityFollowListResponse(
            users=user_summaries,
            cursor=next_cursor,
            has_more=has_more,
        )
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Get following failed")
        raise ServiceUnavailableError("Failed to get following")