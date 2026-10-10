import logging
from datetime import datetime, timezone
from typing import List

from celery import shared_task
from sqlalchemy import select, func, update, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.celery_app import celery
from app.db.session import async_session_factory
from app.models.community import (
    CommunityPost,
    CommunityReport,
    CommunityFollow,
    CommunityModerationAction,
    CommunityNotification,
    PostStatus,
    ReportStatus,
    ModerationActionType,
    NotificationType,
)
from app.services.counter_service import CounterService
from app.services.trending_service import TrendingService
from app.services.feed_cache_service import FeedCacheService

log = logging.getLogger(__name__)

REPORT_THRESHOLD = 10
CELEBRITY_FOLLOWER_THRESHOLD = 10000


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 5},
    name="app.tasks.community_tasks.process_post_report_threshold",
)
def process_post_report_threshold(self, post_id: str) -> dict:
    return _run_async(_process_report_threshold(post_id))


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    name="app.tasks.community_tasks.flush_counter_deltas",
)
def flush_counter_deltas(self) -> dict:
    """Flush write-behind counter buffers (likes, comments, views) to PostgreSQL."""
    return _run_async(_flush_counters())


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    name="app.tasks.community_tasks.reconcile_community_counters",
)
def reconcile_community_counters(self, batch_size: int = 100) -> dict:
    """Periodic job to reconcile any drift between denormalized count columns and actual rows."""
    return _run_async(_reconcile_counters(batch_size))


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    name="app.tasks.community_tasks.recompute_trending_feeds",
)
def recompute_trending_feeds(self) -> dict:
    """Precompute trending cashtags and ranked viral discussions into Redis."""
    return _run_async(_recompute_trending())


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    name="app.tasks.community_tasks.fanout_post_to_followers",
)
def fanout_post_to_followers(self, post_id: str, author_id: str, created_at_ts: float) -> dict:
    """Hybrid timeline fan-out: fan-out to followers' Redis timelines for standard authors."""
    return _run_async(_fanout_post(post_id, author_id, created_at_ts))


@shared_task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    name="app.tasks.community_tasks.cleanup_orphaned_reports",
)
def cleanup_orphaned_reports(self) -> dict:
    return _run_async(_cleanup_reports())


def _run_async(coro):
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(asyncio.run, coro).result()
    return asyncio.run(coro)


async def _process_report_threshold(post_id: str) -> dict:
    async with async_session_factory() as session:
        post = await session.get(CommunityPost, post_id)
        if not post or post.status != PostStatus.PUBLISHED.value:
            return {"post_id": post_id, "action": "skipped"}

        pending_count_result = await session.execute(
            select(func.count(CommunityReport.id)).where(
                CommunityReport.post_id == post_id,
                CommunityReport.status == ReportStatus.PENDING.value,
            )
        )
        pending_count = pending_count_result.scalar() or 0

        if pending_count >= REPORT_THRESHOLD:
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
            await session.commit()

            await FeedCacheService.invalidate_post(post_id, post.stock_symbol, post.author_id)
            return {"post_id": post_id, "action": "auto_hidden", "pending_count": pending_count}

        return {"post_id": post_id, "action": "threshold_not_met", "pending_count": pending_count}


async def _flush_counters() -> dict:
    async with async_session_factory() as session:
        flushed = await CounterService.flush_buffered_counters_to_db(session)
        await session.commit()
        return flushed


async def _reconcile_counters(batch_size: int) -> dict:
    async with async_session_factory() as session:
        # Reconcile recent active posts
        stmt = select(CommunityPost.id).order_by(CommunityPost.updated_at.desc()).limit(batch_size)
        res = await session.execute(stmt)
        post_ids = [row[0] for row in res.all()]

        for pid in post_ids:
            await CounterService.reconcile_counters_for_post(session, pid)

        await session.commit()
        return {"reconciled_posts": len(post_ids)}


async def _recompute_trending() -> dict:
    async with async_session_factory() as session:
        tickers = await TrendingService.get_trending_tickers(session, limit=15)
        posts = await TrendingService.get_trending_posts(session, limit=20)
        return {"trending_tickers_count": len(tickers), "trending_posts_count": len(posts)}


async def _fanout_post(post_id: str, author_id: str, created_at_ts: float) -> dict:
    async with async_session_factory() as session:
        # Check author follower count
        res = await session.execute(
            select(func.count(CommunityFollow.follower_id)).where(CommunityFollow.following_id == author_id)
        )
        follower_count = res.scalar() or 0

        if follower_count > CELEBRITY_FOLLOWER_THRESHOLD:
            # For celebrity accounts, merge on read to avoid massive fan-out writes
            return {"post_id": post_id, "strategy": "fanout_on_read", "followers": follower_count}

        # Fan-out in chunks to follower timeline Redis sorted sets
        offset = 0
        chunk_size = 500
        fanned_out = 0

        while True:
            stmt = (
                select(CommunityFollow.follower_id)
                .where(CommunityFollow.following_id == author_id)
                .offset(offset)
                .limit(chunk_size)
            )
            rows = (await session.execute(stmt)).all()
            if not rows:
                break

            for row in rows:
                follower_id = row[0]
                await FeedCacheService.push_post_to_feed(
                    f"feed:following:{follower_id}", post_id, created_at_ts
                )
                fanned_out += 1

            offset += chunk_size

        return {"post_id": post_id, "strategy": "fanout_on_write", "fanned_out_followers": fanned_out}


async def _cleanup_reports() -> dict:
    async with async_session_factory() as session:
        deleted_posts_result = await session.execute(
            select(CommunityReport.post_id).where(CommunityReport.post_id.is_not(None)).distinct()
        )
        report_post_ids = {row[0] for row in deleted_posts_result.all()}

        existing_posts_result = await session.execute(
            select(CommunityPost.id).where(CommunityPost.id.in_(report_post_ids))
        )
        existing_post_ids = {row[0] for row in existing_posts_result.all()}
        orphaned_post_ids = report_post_ids - existing_post_ids

        deleted_count = 0
        for post_id in orphaned_post_ids:
            res = await session.execute(delete(CommunityReport).where(CommunityReport.post_id == post_id))
            deleted_count += res.rowcount

        await session.commit()
        return {"deleted_orphaned_reports": deleted_count}