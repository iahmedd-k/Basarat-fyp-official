"""Write-behind counter buffer and reconciliation service for Community metrics."""

import logging
from typing import Dict, List, Tuple
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.community import (
    CommunityPost,
    CommunityPostLike,
    CommunityComment,
    CommunityBookmark,
    CommentStatus,
    PostStatus,
)

log = logging.getLogger(__name__)


class CounterService:
    """Manages high-throughput counters via Redis buffering and batched write-behind flushes."""

    @classmethod
    async def increment_post_like(cls, post_id: str, delta: int = 1) -> int:
        """Increment or decrement post like counter in Redis."""
        redis = get_redis_client()
        if not redis:
            return 0
        try:
            # 1. Update live counter
            new_val = await redis.incrby(f"counter:post:{post_id}:likes", delta)
            if new_val < 0:
                await redis.set(f"counter:post:{post_id}:likes", 0)
                new_val = 0
            # 2. Record in write-behind dirty set
            await redis.hincrby("buffer:post_likes_delta", post_id, delta)
            return new_val
        except Exception as e:
            log.debug("Redis incr like error: %s", e)
            return 0

    @classmethod
    async def increment_post_comment(cls, post_id: str, delta: int = 1) -> int:
        """Increment or decrement post comment counter in Redis."""
        redis = get_redis_client()
        if not redis:
            return 0
        try:
            new_val = await redis.incrby(f"counter:post:{post_id}:comments", delta)
            if new_val < 0:
                await redis.set(f"counter:post:{post_id}:comments", 0)
                new_val = 0
            await redis.hincrby("buffer:post_comments_delta", post_id, delta)
            return new_val
        except Exception as e:
            log.debug("Redis incr comment error: %s", e)
            return 0

    @classmethod
    async def increment_post_view(cls, post_id: str, delta: int = 1) -> None:
        """Sampled / buffered view count increment."""
        redis = get_redis_client()
        if not redis:
            return
        try:
            await redis.hincrby("buffer:post_views_delta", post_id, delta)
        except Exception as e:
            log.debug("Redis incr view error: %s", e)

    @classmethod
    async def flush_buffered_counters_to_db(cls, session: AsyncSession) -> Dict[str, int]:
        """Flush all buffered counter deltas to PostgreSQL in bulk."""
        redis = get_redis_client()
        if not redis:
            return {"likes": 0, "comments": 0, "views": 0}

        flushed = {"likes": 0, "comments": 0, "views": 0}

        # 1. Flush Likes
        try:
            likes_deltas = await redis.hgetall("buffer:post_likes_delta")
            if likes_deltas:
                # Remove from buffer first
                await redis.delete("buffer:post_likes_delta")
                for post_id, delta_str in likes_deltas.items():
                    delta = int(delta_str)
                    if delta != 0:
                        await session.execute(
                            update(CommunityPost)
                            .where(CommunityPost.id == post_id)
                            .values(like_count=func.greatest(0, CommunityPost.like_count + delta))
                        )
                        flushed["likes"] += 1
        except Exception as e:
            log.warning("Failed flushing buffered likes: %s", e)

        # 2. Flush Comments
        try:
            comments_deltas = await redis.hgetall("buffer:post_comments_delta")
            if comments_deltas:
                await redis.delete("buffer:post_comments_delta")
                for post_id, delta_str in comments_deltas.items():
                    delta = int(delta_str)
                    if delta != 0:
                        await session.execute(
                            update(CommunityPost)
                            .where(CommunityPost.id == post_id)
                            .values(comment_count=func.greatest(0, CommunityPost.comment_count + delta))
                        )
                        flushed["comments"] += 1
        except Exception as e:
            log.warning("Failed flushing buffered comments: %s", e)

        # 3. Flush Views
        try:
            views_deltas = await redis.hgetall("buffer:post_views_delta")
            if views_deltas:
                await redis.delete("buffer:post_views_delta")
                for post_id, delta_str in views_deltas.items():
                    delta = int(delta_str)
                    if delta > 0:
                        await session.execute(
                            update(CommunityPost)
                            .where(CommunityPost.id == post_id)
                            .values(view_count=CommunityPost.view_count + delta)
                        )
                        flushed["views"] += 1
        except Exception as e:
            log.warning("Failed flushing buffered views: %s", e)

        await session.flush()
        return flushed

    @classmethod
    async def reconcile_counters_for_post(cls, session: AsyncSession, post_id: str) -> None:
        """Reconcile counter drift between source tables and denormalized columns."""
        # Exact like count
        likes_res = await session.execute(
            select(func.count(CommunityPostLike.post_id)).where(CommunityPostLike.post_id == post_id)
        )
        real_likes = likes_res.scalar() or 0

        # Exact comment count
        comments_res = await session.execute(
            select(func.count(CommunityComment.id)).where(
                CommunityComment.post_id == post_id,
                CommunityComment.status == CommentStatus.PUBLISHED.value,
            )
        )
        real_comments = comments_res.scalar() or 0

        # Exact bookmark count
        bookmarks_res = await session.execute(
            select(func.count(CommunityBookmark.id)).where(CommunityBookmark.post_id == post_id)
        )
        real_bookmarks = bookmarks_res.scalar() or 0

        # Update DB row
        await session.execute(
            update(CommunityPost)
            .where(CommunityPost.id == post_id)
            .values(
                like_count=real_likes,
                comment_count=real_comments,
                bookmark_count=real_bookmarks,
            )
        )
        await session.flush()

        # Update Redis live counter
        redis = get_redis_client()
        if redis:
            try:
                await redis.set(f"counter:post:{post_id}:likes", real_likes)
                await redis.set(f"counter:post:{post_id}:comments", real_comments)
            except Exception:
                pass
