from typing import Optional, List
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.authorization import get_current_user
from app.core.exceptions import (
    NotFoundError,
    ServiceUnavailableError,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.community import (
    CommunityProfileResponse,
    CommunityUnifiedProfileResponse,
    CommunityPostListResponse,
    CommunityPostResponse,
    PostType,
)
from app.services.community_service import CommunityService
from app.api.v1.community.posts import _build_post_response

router = APIRouter()
log = logging.getLogger(__name__)


async def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    return CommunityService(db)


@router.get(
    "/community/me",
    response_model=CommunityProfileResponse,
    summary="Get current user's community profile",
)
async def get_my_profile(
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        stats = await service.get_user_profile_stats(user.id, user.id)
        return CommunityProfileResponse(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            avatar_url=user.avatar_url,
            is_verified=getattr(user, "is_verified", False),
            followers_count=stats["followers_count"],
            following_count=stats["following_count"],
            published_post_count=stats["published_post_count"],
            is_following=False,
            is_own_profile=True,
        )
    except Exception:
        log.exception("Get my profile failed")
        raise ServiceUnavailableError("Failed to get profile")


@router.get(
    "/community/users/{user_id}/profile",
    response_model=CommunityUnifiedProfileResponse,
    summary="Unified profile screen endpoint (profile + follow stats + first page of posts in 1 API call)",
)
async def get_unified_user_profile(
    user_id: str,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    """Single-call endpoint to fully hydrate a profile screen."""
    try:
        target_user, stats = await service.get_user_profile_with_stats(user_id, user.id)
        profile_res = CommunityProfileResponse(
            id=target_user.id,
            username=target_user.username,
            full_name=target_user.full_name,
            avatar_url=target_user.avatar_url,
            is_verified=getattr(target_user, "is_verified", False),
            followers_count=stats["followers_count"],
            following_count=stats["following_count"],
            published_post_count=stats["published_post_count"],
            is_following=stats["is_following"],
            is_own_profile=stats["is_own_profile"],
        )

        posts, next_cursor, has_more = await service.get_user_posts(
            user_id=user_id,
            current_user_id=user.id,
            cursor=cursor,
            limit=limit,
        )

        post_ids = [p.id for p in posts]
        liked_set, bookmarked_set = await service.batch_fetch_post_interactions(post_ids, user.id)

        post_responses = [
            _build_post_response(
                p,
                liked_by_me=p.id in liked_set,
                bookmarked_by_me=p.id in bookmarked_set,
            )
            for p in posts
        ]

        return CommunityUnifiedProfileResponse(
            profile=profile_res,
            posts=post_responses,
            posts_cursor=next_cursor,
            posts_has_more=has_more,
        )
    except NotFoundError:
        raise
    except Exception:
        log.exception("Get unified profile failed")
        raise ServiceUnavailableError("Failed to get unified profile")


@router.get(
    "/community/me/posts",
    response_model=CommunityPostListResponse,
    summary="Get current user's posts with batched likes hydration",
)
async def get_my_posts(
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        posts, next_cursor, has_more = await service.get_user_posts(
            user_id=user.id,
            current_user_id=user.id,
            cursor=cursor,
            limit=limit,
        )

        post_ids = [p.id for p in posts]
        liked_set, bookmarked_set = await service.batch_fetch_post_interactions(post_ids, user.id)

        post_responses = [
            _build_post_response(
                p,
                liked_by_me=p.id in liked_set,
                bookmarked_by_me=p.id in bookmarked_set,
            )
            for p in posts
        ]

        return CommunityPostListResponse(
            posts=post_responses,
            cursor=next_cursor or "",
            next_cursor=next_cursor or "",
            has_more=has_more,
        )
    except Exception:
        log.exception("Get my posts failed")
        raise ServiceUnavailableError("Failed to get posts")


@router.get(
    "/community/users/{user_id}",
    response_model=CommunityProfileResponse,
    summary="Get another user's public community profile",
)
async def get_user_profile(
    user_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        target_user, stats = await service.get_user_profile_with_stats(user_id, user.id)

        return CommunityProfileResponse(
            id=target_user.id,
            username=target_user.username,
            full_name=target_user.full_name,
            avatar_url=target_user.avatar_url,
            is_verified=getattr(target_user, "is_verified", False),
            followers_count=stats["followers_count"],
            following_count=stats["following_count"],
            published_post_count=stats["published_post_count"],
            is_following=stats["is_following"],
            is_own_profile=stats["is_own_profile"],
        )
    except NotFoundError:
        raise
    except Exception:
        log.exception("Get user profile failed")
        raise ServiceUnavailableError("Failed to get user profile")


@router.get(
    "/community/users/{user_id}/posts",
    response_model=CommunityPostListResponse,
    summary="Get another user's public posts",
)
async def get_user_posts(
    user_id: str,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        target_user = await service.db.get(User, user_id)
        if not target_user:
            raise NotFoundError("User not found")

        posts, next_cursor, has_more = await service.get_user_posts(
            user_id=user_id,
            current_user_id=user.id,
            cursor=cursor,
            limit=limit,
        )

        post_ids = [p.id for p in posts]
        liked_set, bookmarked_set = await service.batch_fetch_post_interactions(post_ids, user.id)

        post_responses = [
            _build_post_response(
                p,
                liked_by_me=p.id in liked_set,
                bookmarked_by_me=p.id in bookmarked_set,
            )
            for p in posts
        ]

        return CommunityPostListResponse(
            posts=post_responses,
            cursor=next_cursor or "",
            next_cursor=next_cursor or "",
            has_more=has_more,
        )
    except NotFoundError:
        raise
    except Exception:
        log.exception("Get user posts failed")
        raise ServiceUnavailableError("Failed to get user posts")