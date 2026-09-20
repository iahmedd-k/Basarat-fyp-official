from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.authorization import get_current_admin
from app.core.exceptions import (
    ConflictError,
    NotFoundError,
    ServiceUnavailableError,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.community import (
    CommunityReportAdminResponse,
    CommunityReportStatusUpdate,
    CommunityModerationActionResponse,
    CommunityPostResponse,
    PostType,
    PostStatus,
    ReportStatus,
    ModerationActionType,
)
from app.services.community_service import CommunityService

router = APIRouter(prefix="/admin/community", tags=["Admin Community"])
log = logging.getLogger(__name__)


async def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    return CommunityService(db)


@router.get(
    "/reports",
    summary="Get reports for admin review",
)
async def get_reports(
    status: ReportStatus | None = Query(None),
    post_id: str | None = Query(None),
    comment_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    admin: User = Depends(get_current_admin),
    service: CommunityService = Depends(_get_service),
):
    try:
        reports = await service.get_reports_for_admin(
            status=status,
            post_id=post_id,
            comment_id=comment_id,
            limit=limit,
            offset=offset,
        )

        report_responses = []
        for r in reports:
            post_content = None
            comment_content = None
            post_author_id = None
            post_author_username = None
            post_type = None
            stock_symbol = None

            if r.post:
                post_content = r.post.content[:500] if r.post.content else None
                post_author_id = r.post.author_id
                post_author_username = r.post.author.username if r.post.author else None
                post_type = PostType(r.post.post_type)
                stock_symbol = r.post.stock_symbol

            if r.comment:
                comment_content = r.comment.content[:500] if r.comment.content else None

            report_responses.append(
                CommunityReportAdminResponse(
                    id=r.id,
                    reporter_id=r.reporter_id,
                    reporter_username=r.reporter.username if r.reporter else None,
                    post_id=r.post_id,
                    comment_id=r.comment_id,
                    post_content=post_content,
                    comment_content=comment_content,
                    post_author_id=post_author_id,
                    post_author_username=post_author_username,
                    post_type=post_type,
                    stock_symbol=stock_symbol,
                    reason=r.reason,
                    status=ReportStatus(r.status),
                    reviewed_by=r.reviewed_by,
                    reviewed_at=r.reviewed_at,
                    created_at=r.created_at,
                )
            )

        return {"reports": report_responses}
    except Exception as e:
        log.exception("Get admin reports failed")
        raise ServiceUnavailableError("Failed to get reports")


@router.patch(
    "/reports/{report_id}",
    summary="Update report status",
)
async def update_report_status(
    report_id: str,
    data: CommunityReportStatusUpdate,
    admin: User = Depends(get_current_admin),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.update_report_status(report_id, data.status, admin.id)
        return {"message": "Report status updated"}
    except (NotFoundError, ConflictError):
        raise
    except Exception as e:
        log.exception("Update report status failed")
        raise ServiceUnavailableError("Failed to update report status")


@router.get(
    "/posts/{post_id}",
    response_model=CommunityPostResponse,
    summary="Get post for admin review",
)
async def get_post_for_admin(
    post_id: str,
    admin: User = Depends(get_current_admin),
    service: CommunityService = Depends(_get_service),
):
    try:
        post_data = await service.get_post_with_details(
            post_id,
            current_user_id=admin.id,
            include_hidden=True,
        )
        post = post_data["post"]

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
        log.exception("Get post for admin failed")
        raise ServiceUnavailableError("Failed to get post")


@router.post(
    "/posts/{post_id}/restore",
    status_code=204,
    summary="Restore a temporarily hidden post",
)
async def restore_post(
    post_id: str,
    admin: User = Depends(get_current_admin),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.admin_restore_post(post_id, admin.id)
    except (NotFoundError, ConflictError):
        raise
    except Exception as e:
        log.exception("Restore post failed")
        raise ServiceUnavailableError("Failed to restore post")


@router.delete(
    "/posts/{post_id}",
    status_code=204,
    summary="Delete a post (admin)",
)
async def admin_delete_post(
    post_id: str,
    admin: User = Depends(get_current_admin),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.admin_delete_post(post_id, admin.id)
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Admin delete post failed")
        raise ServiceUnavailableError("Failed to delete post")


@router.post(
    "/posts/{post_id}/remove",
    status_code=204,
    summary="Directly remove a post (admin)",
)
async def direct_remove_post(
    post_id: str,
    admin: User = Depends(get_current_admin),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.admin_direct_remove_post(post_id, admin.id)
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Direct remove post failed")
        raise ServiceUnavailableError("Failed to remove post")


@router.delete(
    "/comments/{comment_id}",
    status_code=204,
    summary="Delete a comment (admin)",
)
async def admin_delete_comment(
    comment_id: str,
    admin: User = Depends(get_current_admin),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.admin_delete_comment(comment_id, admin.id)
    except NotFoundError:
        raise
    except Exception as e:
        log.exception("Admin delete comment failed")
        raise ServiceUnavailableError("Failed to delete comment")


@router.get(
    "/moderation-actions",
    summary="Get moderation audit log",
)
async def get_moderation_actions(
    post_id: str | None = Query(None),
    comment_id: str | None = Query(None),
    limit: int = Query(50, ge=1, le=100),
    admin: User = Depends(get_current_admin),
    service: CommunityService = Depends(_get_service),
):
    try:
        actions = await service.get_moderation_actions(post_id, comment_id, limit)

        action_responses = []
        for a in actions:
            action_responses.append(
                CommunityModerationActionResponse(
                    id=a.id,
                    moderator_id=a.moderator_id,
                    moderator_username=a.moderator.username if a.moderator else None,
                    post_id=a.post_id,
                    comment_id=a.comment_id,
                    action=ModerationActionType(a.action),
                    note=a.note,
                    created_at=a.created_at,
                )
            )

        return {"actions": action_responses}
    except Exception as e:
        log.exception("Get moderation actions failed")
        raise ServiceUnavailableError("Failed to get moderation actions")