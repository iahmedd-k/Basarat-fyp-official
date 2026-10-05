from typing import Optional, List
from fastapi import APIRouter, Depends, Query, Form, Header, Request
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
    CommunityAuthorSummary,
    ReportReason,
    CommentStatus,
)
from app.services.community_service import CommunityService
from app.services.idempotency_service import IdempotencyService

router = APIRouter()
log = logging.getLogger(__name__)


async def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    return CommunityService(db)


def _build_comment_response(comment, reply_count: int = 0) -> CommunityCommentResponse:
    author = comment.author
    author_obj = None
    if author:
        author_obj = CommunityAuthorSummary(
            id=author.id,
            username=author.username,
            full_name=author.full_name or "",
            avatar_url=author.avatar_url or "",
            is_verified=getattr(author, "is_verified", False),
        )

    return CommunityCommentResponse(
        id=comment.id,
        post_id=comment.post_id,
        author_id=comment.author_id,
        author_username=author.username if author else "",
        author_full_name=author.full_name if author else "",
        author_avatar_url=author.avatar_url if author else "",
        author_verified=getattr(author, "is_verified", False) if author else False,
        author=author_obj,
        parent_comment_id=comment.parent_comment_id or "",
        content=comment.content,
        status=CommentStatus(comment.status) if hasattr(CommentStatus, comment.status) else CommentStatus.PUBLISHED,
        reply_count=reply_count,
        created_at=comment.created_at,
        updated_at=comment.updated_at,
    )


@router.post(
    "/community/posts/{post_id}/comments",
    response_model=CommunityCommentResponse,
    status_code=201,
    summary="Create a comment on a post",
)
async def create_comment(
    post_id: str,
    data: CommunityCommentCreate,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    if idempotency_key:
        cached_res = await IdempotencyService.get_stored_response(
            service.db, user.id, idempotency_key, f"/community/posts/{post_id}/comments"
        )
        if cached_res:
            code, body = cached_res
            return CommunityCommentResponse(**body)

    try:
        comment = await service.create_comment(
            post_id=post_id,
            author_id=user.id,
            content=data.content,
            parent_comment_id=data.parent_comment_id,
        )

        res = _build_comment_response(comment, reply_count=0)

        if idempotency_key:
            await IdempotencyService.record_response(
                service.db,
                user.id,
                idempotency_key,
                f"/community/posts/{post_id}/comments",
                201,
                res.model_dump(mode="json"),
            )

        return res
    except (NotFoundError, ConflictError, BadRequestError, ValidationFailedError):
        raise
    except Exception:
        log.exception("Create comment failed")
        raise ServiceUnavailableError("Failed to create comment")


@router.get(
    "/community/posts/{post_id}/comments",
    response_model=CommunityCommentListResponse,
    summary="Get comments for a post with batched reply counting",
)
async def get_comments(
    post_id: str,
    cursor: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        post = await service.get_post_by_id(post_id)
        if post.status != "PUBLISHED" and post.author_id != user.id and not getattr(user, "is_admin", False):
            raise NotFoundError("Post not found")

        comments, next_cursor, has_more = await service.get_comments(post_id, cursor, limit)

        # Batch fetch reply counts in ONE single query (Kills N+1 comment replies queries!)
        comment_ids = [c.id for c in comments]
        reply_counts_map = await service.batch_fetch_comment_reply_counts(comment_ids)

        comment_responses = [
            _build_comment_response(
                c,
                reply_count=reply_counts_map.get(c.id, getattr(c, "reply_count", 0)),
            )
            for c in comments
        ]

        return CommunityCommentListResponse(
            comments=comment_responses,
            cursor=next_cursor,
            next_cursor=next_cursor,
            has_more=has_more,
        )
    except NotFoundError:
        raise
    except Exception:
        log.exception("Get comments failed")
        raise ServiceUnavailableError("Failed to get comments")


@router.get(
    "/community/comments/{comment_id}/replies",
    response_model=CommunityCommentListResponse,
    summary="Get nested replies for a specific parent comment",
)
async def get_comment_replies(
    comment_id: str,
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        replies = await service.get_replies(comment_id, limit=limit)
        return CommunityCommentListResponse(
            comments=[_build_comment_response(r, reply_count=0) for r in replies],
            cursor=None,
            next_cursor=None,
            has_more=len(replies) >= limit,
        )
    except Exception:
        log.exception("Get replies failed")
        raise ServiceUnavailableError("Failed to get replies")


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
    except Exception:
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
    except ValueError as e:
        raise ValidationFailedError(f"Invalid report reason: {e}")
    except Exception:
        log.exception("Report comment failed")
        raise ServiceUnavailableError("Failed to report comment")
