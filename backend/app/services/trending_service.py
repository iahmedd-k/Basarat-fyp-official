"""Trending cashtags, viral posts, and ranked For-You feed computation."""

import json
import logging
import math
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

from sqlalchemy import select, func, distinct, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.community import (
    CommunityPost,
    CommunityPostTicker,
    PostStatus,
)

log = logging.getLogger(__name__)


class TrendingService:
    TRENDING_TICKERS_KEY = "trending:tickers"
    TRENDING_POSTS_KEY = "trending:posts"
    CACHE_TTL_SECONDS = 120  # 2 minutes

    @staticmethod
    def calculate_post_rank_score(
        like_count: int,
        comment_count: int,
        view_count: int,
        bookmark_count: int,
        created_at: datetime,
    ) -> float:
        """Calculate time-decayed engagement ranking score (Hacker News / Reddit style)."""
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        
        hours_old = max(0.0, (now - created_at).total_seconds() / 3600.0)
        
        # Weighted engagement score
        engagement = (
            (like_count * 1.5) +
            (comment_count * 3.0) +
            (bookmark_count * 2.0) +
            (min(view_count, 1000) * 0.05)
        )
        
        # Gravity / recency decay
        gravity = 1.6
        score = (engagement + 1.0) / math.pow(hours_old + 2.0, gravity)
        return round(score, 6)

    @classmethod
    async def get_trending_tickers(
        cls,
        session: AsyncSession,
        limit: int = 10,
    ) -> List[dict]:
        """Fetch top trending tickers over the last 24 hours."""
        redis = get_redis_client()
        if redis:
            try:
                cached = await redis.get(cls.TRENDING_TICKERS_KEY)
                if cached:
                    return json.loads(cached)[:limit]
            except Exception as e:
                log.debug("Redis get trending tickers error: %s", e)

        # Compute from DB
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        stmt = (
            select(
                CommunityPostTicker.ticker,
                func.count(CommunityPostTicker.id).label("mention_count"),
                func.count(distinct(CommunityPost.author_id)).label("unique_authors"),
            )
            .join(CommunityPost, CommunityPost.id == CommunityPostTicker.post_id)
            .where(
                CommunityPostTicker.created_at >= since,
                CommunityPost.status == PostStatus.PUBLISHED.value,
            )
            .group_by(CommunityPostTicker.ticker)
            .order_by(desc("unique_authors"), desc("mention_count"))
            .limit(limit * 2)
        )
        res = await session.execute(stmt)
        rows = res.all()

        trending = []
        for r in rows:
            trending.append({
                "ticker": r.ticker,
                "mention_count": r.mention_count,
                "unique_authors": r.unique_authors,
                "velocity_score": round(r.mention_count * 1.0 + r.unique_authors * 2.0, 2),
            })

        trending.sort(key=lambda x: x["velocity_score"], reverse=True)
        result = trending[:limit]

        if redis and result:
            try:
                await redis.setex(cls.TRENDING_TICKERS_KEY, cls.CACHE_TTL_SECONDS, json.dumps(result, default=str))
            except Exception:
                pass

        return result

    @classmethod
    async def get_trending_posts(
        cls,
        session: AsyncSession,
        limit: int = 20,
    ) -> List[str]:
        """Fetch IDs of trending posts computed via engagement decay."""
        redis = get_redis_client()
        if redis:
            try:
                cached = await redis.get(cls.TRENDING_POSTS_KEY)
                if cached:
                    return json.loads(cached)[:limit]
            except Exception as e:
                log.debug("Redis get trending posts error: %s", e)

        since = datetime.now(timezone.utc) - timedelta(days=7)
        stmt = (
            select(
                CommunityPost.id,
                CommunityPost.like_count,
                CommunityPost.comment_count,
                CommunityPost.view_count,
                CommunityPost.bookmark_count,
                CommunityPost.created_at,
            )
            .where(
                CommunityPost.created_at >= since,
                CommunityPost.status == PostStatus.PUBLISHED.value,
            )
            .order_by(CommunityPost.like_count.desc(), CommunityPost.comment_count.desc())
            .limit(100)
        )
        res = await session.execute(stmt)
        rows = res.all()

        scored_posts = []
        for r in rows:
            score = cls.calculate_post_rank_score(
                r.like_count, r.comment_count, r.view_count, r.bookmark_count, r.created_at
            )
            scored_posts.append((r.id, score))

        scored_posts.sort(key=lambda x: x[1], reverse=True)
        top_ids = [p_id for p_id, _ in scored_posts[:limit]]

        if redis and top_ids:
            try:
                await redis.setex(cls.TRENDING_POSTS_KEY, cls.CACHE_TTL_SECONDS, json.dumps(top_ids))
            except Exception:
                pass

        return top_ids
