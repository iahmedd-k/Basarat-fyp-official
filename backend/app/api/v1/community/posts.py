from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.authorization import get_current_user
from app.core.rate_limiter import limiter
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.community import (
    CommunityPostCreate,
    CommunityPostUpdate,
    CommunityPostResponse,
    CommunityPostListResponse,
    FeedQueryParams,
    PostType,
)
from app.services.community_service import CommunityService
from app.services.cloudinary_service import cloudinary_service

router = APIRouter()
log = logging.getLogger(__name__)


async def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    return CommunityService(db)


@router.post(
    "/community/posts",
    response_model=CommunityPostResponse,
    status_code=201,
    summary="Create a new community post",
)
@limiter.limit("1/30seconds")
async def create_post(
    request: Request,
    content: str = Form(..., min_length=1, max_length=5000),
    post_type: PostType = Form(...),
    stock_symbol: str | None = Form(None),
    image: UploadFile | None = File(None),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        if image:
            if not cloudinary_service.is_configured():
                raise ServiceUnavailableError("Image upload service not configured")

            image_url, image_public_id = await cloudinary_service.upload_image(image)
        else:
            image_url = None
            image_public_id = None

        post = await service.create_post(
            author_id=user.id,
            content=content,
            post_type=post_type,
            stock_symbol=stock_symbol.upper() if stock_symbol else None,
            image_url=image_url,
            image_public_id=image_public_id,
        )

        post_data = await service.get_post_with_details(post.id, current_user_id=user.id)
        post_obj = post_data["post"]

        return CommunityPostResponse(
            id=post_obj.id,
            author_id=post_obj.author_id,
            author_username=post_obj.author.username if post_obj.author else None,
            author_full_name=post_obj.author.full_name if post_obj.author else None,
            author_avatar_url=post_obj.author.avatar_url if post_obj.author else None,
            post_type=PostType(post_obj.post_type),
            stock_symbol=post_obj.stock_symbol,
            stock_name=post_obj.stock.name if post_obj.stock else None,
            content=post_obj.content,
            image_url=post_obj.image_url,
            like_count=post_obj.like_count,
            comment_count=post_obj.comment_count,
            report_count=post_obj.report_count,
            status=post_obj.status,
            removed_reason=post_obj.removed_reason,
            liked_by_me=post_data["liked_by_me"],
            created_at=post_obj.created_at,
            updated_at=post_obj.updated_at,
        )
    except (ValidationFailedError, ConflictError, NotFoundError, BadRequestError):
        if image_public_id:
            await cloudinary_service.delete_image(image_public_id)
        raise
    except Exception as e:
        if image_public_id:
            await cloudinary_service.delete_image(image_public_id)
        log.exception("Create post failed")
        raise ServiceUnavailableError("Failed to create post")


@router.get(
    "/community/feed",
    response_model=CommunityPostListResponse,
    summary="Get community feed",
)
async def get_feed(
    stock_symbol: str | None = Query(None),
    post_type: PostType | None = Query(None),
    mine: bool = Query(False),
    following: bool = Query(False),
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        posts, next_cursor, has_more = await service.get_feed(
            current_user_id=user.id,
            stock_symbol=stock_symbol,
            post_type=post_type,
            mine=mine,
            following=following,
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
        log.exception("Get feed failed")
        raise ServiceUnavailableError("Failed to get feed")


@router.get(
    "/community/posts/{post_id}",
    response_model=CommunityPostResponse,
    summary="Get a single post",
)
async def get_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        is_admin = user.is_admin
        post_data = await service.get_post_with_details(
            post_id,
            current_user_id=user.id,
            include_hidden=is_admin or True,
        )
        post = post_data["post"]

        if post.status != "PUBLISHED" and post.author_id != user.id and not is_admin:
            raise NotFoundError("Post not found")

        return CommunityPostResponse(
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
            liked_by_me=post_data["liked_by_me"],
            created_at=post.created_at,
            updated_at=post.updated_at,
        )
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Get post failed")
        raise ServiceUnavailableError("Failed to get post")


@router.patch(
    "/community/posts/{post_id}",
    response_model=CommunityPostResponse,
    summary="Update own post",
)
async def update_post(
    post_id: str,
    data: CommunityPostUpdate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        post = await service.update_post(post_id, user.id, data.content)

        post_data = await service.get_post_with_details(post.id, current_user_id=user.id)
        post_obj = post_data["post"]

        return CommunityPostResponse(
            id=post_obj.id,
            author_id=post_obj.author_id,
            author_username=post_obj.author.username if post_obj.author else None,
            author_full_name=post_obj.author.full_name if post_obj.author else None,
            author_avatar_url=post_obj.author.avatar_url if post_obj.author else None,
            post_type=PostType(post_obj.post_type),
            stock_symbol=post_obj.stock_symbol,
            stock_name=post_obj.stock.name if post_obj.stock else None,
            content=post_obj.content,
            image_url=post_obj.image_url,
            like_count=post_obj.like_count,
            comment_count=post_obj.comment_count,
            report_count=post_obj.report_count,
            status=post_obj.status,
            removed_reason=post_obj.removed_reason,
            liked_by_me=post_data["liked_by_me"],
            created_at=post_obj.created_at,
            updated_at=post_obj.updated_at,
        )
    except (NotFoundError, ForbiddenError, ConflictError, ValidationFailedError):
        raise
    except Exception as e:
        log.exception("Update post failed")
        raise ServiceUnavailableError("Failed to update post")


@router.delete(
    "/community/posts/{post_id}",
    status_code=204,
    summary="Delete own post",
)
async def delete_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.delete_post(post_id, user.id)
    except (NotFoundError, ForbiddenError):
        raise
    except Exception as e:
        log.exception("Delete post failed")
        raise ServiceUnavailableError("Failed to delete post")


@router.post(
    "/community/posts/{post_id}/like",
    status_code=204,
    summary="Like a post",
)
async def like_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.like_post(post_id, user.id)
    except (NotFoundError, ConflictError):
        raise
    except Exception as e:
        log.exception("Like post failed")
        raise ServiceUnavailableError("Failed to like post")


@router.delete(
    "/community/posts/{post_id}/like",
    status_code=204,
    summary="Unlike a post",
)
async def unlike_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.unlike_post(post_id, user.id)
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Unlike post failed")
        raise ServiceUnavailableError("Failed to unlike post")


@router.post(
    "/community/posts/{post_id}/report",
    status_code=201,
    summary="Report a post",
)
async def report_post(
    post_id: str,
    reason: str = Form(...),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        from app.schemas.community import ReportReason
        await service.create_report(
            reporter_id=user.id,
            reason=ReportReason(reason),
            post_id=post_id,
        )

        from app.tasks.community_tasks import process_post_report_threshold
        process_post_report_threshold.delay(post_id)
    except (NotFoundError, ConflictError, ValidationFailedError):
        raise
    except Exception as e:
        log.exception("Report post failed")
        raise ServiceUnavailableError("Failed to report post")