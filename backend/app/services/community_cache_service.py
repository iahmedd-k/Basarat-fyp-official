"""Dedicated Redis cache layer and invalidation manager for high-throughput Community APIs."""

import asyncio
import logging
from typing import Any, Optional
from app.core.redis import (
    cache_get,
    cache_set,
    cache_invalidate,
    cache_invalidate_pattern,
)

log = logging.getLogger(__name__)


class CommunityCacheService:
    """Manages Redis caching, sub-millisecond retrieval, and granular invalidations."""

    # =========================================================================
    # Feed & Post Cache Helpers
    # =========================================================================

    @staticmethod
    def post_detail_key(post_id: str, viewer_id: str) -> str:
        return f"community:post_detail:{post_id}:{viewer_id}"

    @staticmethod
    def market_posts_key(cursor: Optional[str], limit: int, viewer_id: str, query: Optional[str] = None) -> str:
        q_part = f":q_{query.strip()}" if query and query.strip() else ""
        return f"community:feed:market:{viewer_id}:{cursor or 'first'}:{limit}{q_part}"

    @staticmethod
    def stock_posts_key(symbol: str, cursor: Optional[str], limit: int, viewer_id: str, query: Optional[str] = None) -> str:
        q_part = f":q_{query.strip()}" if query and query.strip() else ""
        return f"community:feed:stock:{symbol.upper()}:{viewer_id}:{cursor or 'first'}:{limit}{q_part}"

    @staticmethod
    def search_posts_key(query: str, symbol: Optional[str], post_type: Optional[str], author: Optional[str], cursor: Optional[str], limit: int, viewer_id: str) -> str:
        return f"community:search:{viewer_id}:{query or 'none'}:{symbol or 'none'}:{post_type or 'none'}:{author or 'none'}:{cursor or 'first'}:{limit}"

    @staticmethod
    def user_posts_key(user_id: str, cursor: Optional[str], limit: int, viewer_id: str) -> str:
        return f"community:user_posts:{user_id}:{viewer_id}:{cursor or 'first'}:{limit}"

    # =========================================================================
    # Profile & Follow Cache Helpers
    # =========================================================================

    @staticmethod
    def user_profile_key(user_id: str, viewer_id: str) -> str:
        return f"community:profile:{user_id}:{viewer_id}"

    @staticmethod
    def unified_profile_key(user_id: str, cursor: Optional[str], limit: int, viewer_id: str) -> str:
        return f"community:unified_profile:{user_id}:{viewer_id}:{cursor or 'first'}:{limit}"

    @staticmethod
    def follow_status_key(follower_id: str, following_id: str) -> str:
        return f"community:follow_status:{follower_id}:{following_id}"

    @staticmethod
    def followers_key(user_id: str, cursor: Optional[str], limit: int) -> str:
        return f"community:followers:{user_id}:{cursor or 'first'}:{limit}"

    @staticmethod
    def following_key(user_id: str, cursor: Optional[str], limit: int) -> str:
        return f"community:following:{user_id}:{cursor or 'first'}:{limit}"

    # =========================================================================
    # Comments & Replies Cache Helpers
    # =========================================================================

    @staticmethod
    def post_comments_key(
        post_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
        viewer_id: Optional[str] = None,
    ) -> str:
        if viewer_id:
            return f"community:comments:{post_id}:{cursor or 'first'}:{limit}:{viewer_id}"
        return f"community:comments:{post_id}:{cursor or 'first'}:{limit}"

    @staticmethod
    def comment_replies_key(comment_id: str, limit: int) -> str:
        return f"community:replies:{comment_id}:{limit}"

    # =========================================================================
    # Notifications Cache Helpers
    # =========================================================================

    @staticmethod
    def unread_count_key(user_id: str) -> str:
        return f"community:unread_count:{user_id}"

    @staticmethod
    def notifications_key(user_id: str, page: int, limit: int, unread_only: bool) -> str:
        return f"community:notifications:{user_id}:{page}:{limit}:{unread_only}"

    # =========================================================================
    # Invalidation Hooks (Triggered on Mutations)
    # =========================================================================

    @classmethod
    async def invalidate_post_mutations(
        cls,
        post_id: str,
        author_id: Optional[str] = None,
        stock_symbol: Optional[str] = None,
    ) -> None:
        """Invalidate all caches related to a post update, deletion, creation, like, or bookmark in parallel."""
        try:
            tasks = [
                cache_invalidate_pattern(f"community:post_detail:{post_id}:*"),
                cache_invalidate_pattern(f"community:comments:{post_id}:*"),
                cache_invalidate_pattern("community:feed:*"),
                cache_invalidate_pattern("community:trending*"),
                cache_invalidate_pattern("community:search:*"),
            ]
            if author_id:
                tasks.extend([
                    cache_invalidate_pattern(f"community:user_posts:{author_id}:*"),
                    cache_invalidate_pattern(f"community:unified_profile:{author_id}:*"),
                    cache_invalidate_pattern(f"community:profile:{author_id}:*"),
                ])
            if stock_symbol:
                tasks.append(cache_invalidate_pattern(f"community:feed:stock:{stock_symbol.upper()}:*"))
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            log.warning("Failed invalidating post cache for %s: %s", post_id, e)

    @classmethod
    async def invalidate_comment_mutations(
        cls,
        post_id: str,
        comment_id: Optional[str] = None,
    ) -> None:
        """Invalidate caches related to new or deleted comments in parallel."""
        try:
            tasks = [
                cache_invalidate_pattern(f"community:comments:{post_id}:*"),
                cache_invalidate_pattern(f"community:post_detail:{post_id}:*"),
            ]
            if comment_id:
                tasks.append(cache_invalidate_pattern(f"community:replies:{comment_id}:*"))
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            log.warning("Failed invalidating comment cache for post %s: %s", post_id, e)

    @classmethod
    async def invalidate_follow_mutations(
        cls,
        follower_id: str,
        following_id: str,
    ) -> None:
        """Invalidate follow status, followers/following lists, and affected user profiles in parallel."""
        try:
            tasks = [
                cache_invalidate(cls.follow_status_key(follower_id, following_id)),
                cache_invalidate_pattern(f"community:followers:{following_id}:*"),
                cache_invalidate_pattern(f"community:following:{follower_id}:*"),
                cache_invalidate_pattern(f"community:profile:{following_id}:*"),
                cache_invalidate_pattern(f"community:profile:{follower_id}:*"),
                cache_invalidate_pattern(f"community:unified_profile:{following_id}:*"),
                cache_invalidate_pattern(f"community:unified_profile:{follower_id}:*"),
                cache_invalidate_pattern(f"community:feed:{follower_id}:*"),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            log.warning("Failed invalidating follow cache: %s", e)

    @classmethod
    async def invalidate_notification_mutations(cls, user_id: str) -> None:
        """Invalidate notifications and unread counts for a user in parallel."""
        try:
            tasks = [
                cache_invalidate(cls.unread_count_key(user_id)),
                cache_invalidate_pattern(f"community:notifications:{user_id}:*"),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            log.warning("Failed invalidating notification cache for %s: %s", user_id, e)
