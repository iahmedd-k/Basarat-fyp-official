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
    CommunityPostListResponse,
    CommunityPostResponse,
    PostType,
)
from app.services.community_service import CommunityService

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
            followers_count=stats["followers_count"],
            following_count=stats["following_count"],
            published_post_count=stats["published_post_count"],
            is_following=False,
            is_own_profile=True,
        )
    except Exception as e:
        log.exception("Get my profile failed")
        raise ServiceUnavailableError("Failed to get profile")


@router.get(
    "/community/me/posts",
    response_model=CommunityPostListResponse,
    summary="Get current user's posts",
)
async def get_my_posts(
    cursor: str | None = Query(None),
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

        post_responses = []
        for post in posts:
            liked_by_me = await service.has_liked(post.id, user.id)
            post_responses.append(
                CommunityPostResponse(
                    id=post.id,
                    author_id=post.author_id,
                    author_username=post.author.username if post.author else None,
                    author_full_name=post.author.full_name if post.author else None,
                    author_avatar_url=post.author.avatar_url if post.author else None,
                    post_type=PostType(post.post_type),
                    stock_symbol=post.stock_symbol,
                    stock_name=post.stock.name if post.stock else None,
                    content=post.content,
                    image_url=post.image_url,
                    like_count=post.like_count,
                    comment_count=post.comment_count,
                    report_count=post.report_count,
                    status=post.status,
                    removed_reason=post.removed_reason,
                    liked_by_me=liked_by_me,
                    created_at=post.created_at,
                    updated_at=post.updated_at,
                )
            )

        return CommunityPostListResponse(
            posts=post_responses,
            cursor=next_cursor,
            has_more=has_more,
        )
    except Exception as e:
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
        target_user = await service.db.get(User, user_id)
        if not target_user:
            raise NotFoundError("User not found")

        stats = await service.get_user_profile_stats(user_id, user.id)

        return CommunityProfileResponse(
            id=target_user.id,
            username=target_user.username,
            full_name=target_user.full_name,
            avatar_url=target_user.avatar_url,
            followers_count=stats["followers_count"],
            following_count=stats["following_count"],
            published_post_count=stats["published_post_count"],
            is_following=stats["is_following"],
            is_own_profile=False,
        )
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Get user profile failed")
        raise ServiceUnavailableError("Failed to get user profile")


@router.get(
    "/community/users/{user_id}/posts",
    response_model=CommunityPostListResponse,
    summary="Get another user's public posts",
)
async def get_user_posts(
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

        posts, next_cursor, has_more = await service.get_user_posts(
            user_id=user_id,
            current_user_id=user.id,
            cursor=cursor,
            limit=limit,
        )

        post_responses = []
        for post in posts:
            liked_by_me = await service.has_liked(post.id, user.id)
            post_responses.append(
                CommunityPostResponse(
                    id=post.id,
                    author_id=post.author_id,
                    author_username=post.author.username if post.author else None,
                    author_full_name=post.author.full_name if post.author else None,
                    author_avatar_url=post.author.avatar_url if post.author else None,
                    post_type=PostType(post.post_type),
                    stock_symbol=post.stock_symbol,
                    stock_name=post.stock.name if post.stock else None,
                    content=post.content,
                    image_url=post.image_url,
                    like_count=post.like_count,
                    comment_count=post.comment_count,
                    report_count=post.report_count,
                    status=post.status,
                    removed_reason=post.removed_reason,
                    liked_by_me=liked_by_me,
                    created_at=post.created_at,
                    updated_at=post.updated_at,
                )
            )

        return CommunityPostListResponse(
            posts=post_responses,
            cursor=next_cursor,
            has_more=has_more,
        )
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Get user posts failed")
        raise ServiceUnavailableError("Failed to get user posts")