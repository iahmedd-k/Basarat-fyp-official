from fastapi import APIRouter, Depends, Query, Form
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.authorization import get_current_user
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.community import (
    CommunityCommentCreate,
    CommunityCommentResponse,
    CommunityCommentListResponse,
    ReportReason,
)
from app.services.community_service import CommunityService

router = APIRouter()
log = logging.getLogger(__name__)


async def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    return CommunityService(db)


@router.post(
    "/community/posts/{post_id}/comments",
    response_model=CommunityCommentResponse,
    status_code=201,
    summary="Create a comment on a post",
)
async def create_comment(
    post_id: str,
    data: CommunityCommentCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        comment = await service.create_comment(
            post_id=post_id,
            author_id=user.id,
            content=data.content,
            parent_comment_id=data.parent_comment_id,
        )

        author = comment.author
        return CommunityCommentResponse(
            id=comment.id,
            post_id=comment.post_id,
            author_id=comment.author_id,
            author_username=author.username if author else None,
            author_full_name=author.full_name if author else None,
            author_avatar_url=author.avatar_url if author else None,
            parent_comment_id=comment.parent_comment_id,
            content=comment.content,
            status=comment.status,
            reply_count=0,
            created_at=comment.created_at,
            updated_at=comment.updated_at,
        )
    except (NotFoundError, ConflictError, BadRequestError, ValidationFailedError):
        raise
    except Exception as e:
        log.exception("Create comment failed")
        raise ServiceUnavailableError("Failed to create comment")


@router.get(
    "/community/posts/{post_id}/comments",
    response_model=CommunityCommentListResponse,
    summary="Get comments for a post",
)
async def get_comments(
    post_id: str,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        post = await service.get_post_by_id(post_id)
        if post.status != "PUBLISHED" and post.author_id != user.id and not user.is_admin:
            raise NotFoundError("Post not found")

        comments, next_cursor, has_more = await service.get_comments(post_id, cursor, limit)

        comment_responses = []
        for comment in comments:
            author = comment.author
            replies = await service.get_replies(comment.id)
            comment_responses.append(
                CommunityCommentResponse(
                    id=comment.id,
                    post_id=comment.post_id,
                    author_id=comment.author_id,
                    author_username=author.username if author else None,
                    author_full_name=author.full_name if author else None,
                    author_avatar_url=author.avatar_url if author else None,
                    parent_comment_id=comment.parent_comment_id,
                    content=comment.content,
                    status=comment.status,
                    reply_count=len(replies),
                    created_at=comment.created_at,
                    updated_at=comment.updated_at,
                )
            )

        return CommunityCommentListResponse(
            comments=comment_responses,
            cursor=next_cursor,
            has_more=has_more,
        )
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Get comments failed")
        raise ServiceUnavailableError("Failed to get comments")


@router.delete(
    "/community/comments/{comment_id}",
    status_code=204,
    summary="Delete own comment",
)
async def delete_comment(
    comment_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.delete_comment(comment_id, user.id)
    except (NotFoundError, ForbiddenError):
        raise
    except Exception as e:
        log.exception("Delete comment failed")
        raise ServiceUnavailableError("Failed to delete comment")


@router.post(
    "/community/comments/{comment_id}/report",
    status_code=201,
    summary="Report a comment",
)
async def report_comment(
    comment_id: str,
    reason: str = Form(...),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.create_report(
            reporter_id=user.id,
            reason=ReportReason(reason),
            comment_id=comment_id,
        )
    except (NotFoundError, ConflictError, ValidationFailedError):
        raise
    except Exception as e:
        log.exception("Report comment failed")
        raise ServiceUnavailableError("Failed to report comment")