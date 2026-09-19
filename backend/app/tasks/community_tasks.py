import logging
from datetime import datetime, timezone

from celery import shared_task
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery
from app.db.session import async_session_factory
from app.models.community import (
    CommunityPost,
    CommunityReport,
    CommunityModerationAction,
    CommunityNotification,
    PostStatus,
    ReportStatus,
    ModerationActionType,
    NotificationType,
)

log = logging.getLogger(__name__)

REPORT_THRESHOLD = 10


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 5},
    name="app.tasks.community_tasks.process_post_report_threshold",
)
def process_post_report_threshold(self, post_id: str) -> dict:
    return _process_post_report_threshold_sync(post_id)


def _process_post_report_threshold_sync(post_id: str) -> dict:
    import asyncio

    async def _run():
        async with async_session_factory() as session:
            return await _process_report_threshold(session, post_id)

    try:
        return asyncio.run(_run())
    except Exception as e:
        log.exception("Failed to process report threshold for post %s: %s", post_id, e)
        raise


async def _process_report_threshold(session: AsyncSession, post_id: str) -> dict:
    post = await session.get(CommunityPost, post_id)
    if not post:
        log.warning("Post %s not found for report threshold processing", post_id)
        return {"post_id": post_id, "action": "post_not_found"}

    if post.status != PostStatus.PUBLISHED.value:
        log.info("Post %s is not PUBLISHED (status=%s), skipping threshold check", post_id, post.status)
        return {"post_id": post_id, "action": "skipped", "reason": f"status_{post.status}"}

    pending_count_result = await session.execute(
        select(func.count(CommunityReport.id)).where(
            CommunityReport.post_id == post_id,
            CommunityReport.status == ReportStatus.PENDING.value,
        )
    )
    pending_count = pending_count_result.scalar() or 0

    log.info("Post %s has %d pending reports (threshold: %d)", post_id, pending_count, REPORT_THRESHOLD)

    if pending_count >= REPORT_THRESHOLD:
        existing_action = await session.execute(
            select(CommunityModerationAction).where(
                CommunityModerationAction.post_id == post_id,
                CommunityModerationAction.action == ModerationActionType.AUTO_HIDDEN.value,
            )
        )
        if existing_action.scalars().first():
            log.info("Post %s already auto-hidden, skipping", post_id)
            return {"post_id": post_id, "action": "already_hidden"}

        post.status = PostStatus.TEMPORARILY_HIDDEN.value
        post.updated_at = datetime.now(timezone.utc)

        action = CommunityModerationAction(
            moderator_id=None,
            post_id=post_id,
            action=ModerationActionType.AUTO_HIDDEN.value,
            note=f"Auto-hidden after {pending_count} pending reports",
        )
        session.add(action)

        notification = CommunityNotification(
            recipient_id=post.author_id,
            actor_id=None,
            post_id=post_id,
            comment_id=None,
            type=NotificationType.POST_AUTO_HIDDEN.value,
            title="Post Temporarily Hidden",
            message="Your post has been temporarily hidden for review due to multiple reports.",
            is_read=False,
        )
        session.add(notification)

        await session.flush()
        log.info("Post %s auto-hidden due to %d pending reports", post_id, pending_count)
        return {"post_id": post_id, "action": "auto_hidden", "pending_count": pending_count}

    return {"post_id": post_id, "action": "threshold_not_met", "pending_count": pending_count}


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    name="app.tasks.community_tasks.cleanup_orphaned_reports",
)
def cleanup_orphaned_reports(self) -> dict:
    import asyncio

    async def _run():
        async with async_session_factory() as session:
            deleted_posts_result = await session.execute(
                select(CommunityReport.post_id)
                .where(CommunityReport.post_id.is_not(None))
                .distinct()
            )
            report_post_ids = {row[0] for row in deleted_posts_result.all()}

            existing_posts_result = await session.execute(
                select(CommunityPost.id).where(CommunityPost.id.in_(report_post_ids))
            )
            existing_post_ids = {row[0] for row in existing_posts_result.all()}

            orphaned_post_ids = report_post_ids - existing_post_ids
            deleted_count = 0

            for post_id in orphaned_post_ids:
                result = await session.execute(
                    delete(CommunityReport).where(CommunityReport.post_id == post_id)
                )
                deleted_count += result.rowcount

            deleted_comments_result = await session.execute(
                select(CommunityReport.comment_id)
                .where(CommunityReport.comment_id.is_not(None))
                .distinct()
            )
            report_comment_ids = {row[0] for row in deleted_comments_result.all()}

            existing_comments_result = await session.execute(
                select(CommunityComment.id).where(CommunityComment.id.in_(report_comment_ids))
            )
            existing_comment_ids = {row[0] for row in existing_comments_result.all()}

            orphaned_comment_ids = report_comment_ids - existing_comment_ids

            for comment_id in orphaned_comment_ids:
                result = await session.execute(
                    delete(CommunityReport).where(CommunityReport.comment_id == comment_id)
                )
                deleted_count += result.rowcount

            await session.flush()
            log.info("Cleaned up %d orphaned reports", deleted_count)
            return {"deleted_reports": deleted_count}

    try:
        return asyncio.run(_run())
    except Exception as e:
        log.exception("Failed to cleanup orphaned reports: %s", e)
        raise