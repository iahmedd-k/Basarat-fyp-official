"""High-performance multi-level cache-aside and feed generation service."""

import asyncio
import json
import logging
import random
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.redis import get_redis_client

log = logging.getLogger(__name__)

# Local in-process LRU / hot-key cache (L1 cache: 2-3 second TTL)
_L1_CACHE: Dict[str, Tuple[Any, float]] = {}
_L1_MAX_SIZE = 5000

# Single-flight / request coalescing locks to prevent cache stampedes on hot keys
_SINGLE_FLIGHT_LOCKS: Dict[str, asyncio.Lock] = {}
_FLIGHT_META_LOCK = asyncio.Lock()


class FeedCacheService:
    POST_TTL_BASE = 3600  # 1 hour
    USER_TTL_BASE = 1800  # 30 minutes
    FEED_TTL_BASE = 900   # 15 minutes
    FEED_MAX_ITEMS = 1000 # Max post IDs retained in Redis sorted sets

    @classmethod
    def _jitter(cls, base_ttl: int) -> int:
        """Add 10-20% TTL jitter to prevent synchronized cache expiration stampedes."""
        return base_ttl + random.randint(0, max(5, int(base_ttl * 0.15)))

    # -------------------------------------------------------------------------
    # L1 In-Process Memory Cache (Hot Key Protection)
    # -------------------------------------------------------------------------

    @classmethod
    def get_l1(cls, key: str) -> Optional[Any]:
        if key in _L1_CACHE:
            val, exp = _L1_CACHE[key]
            if exp > time.monotonic():
                return val
            _L1_CACHE.pop(key, None)
        return None

    @classmethod
    def set_l1(cls, key: str, val: Any, ttl_seconds: float = 2.5) -> None:
        if len(_L1_CACHE) >= _L1_MAX_SIZE:
            # Purge expired or evict oldest items
            now = time.monotonic()
            to_del = [k for k, (_, exp) in _L1_CACHE.items() if exp <= now]
            for k in to_del:
                _L1_CACHE.pop(k, None)
            if len(_L1_CACHE) >= _L1_MAX_SIZE:
                _L1_CACHE.clear()
        _L1_CACHE[key] = (val, time.monotonic() + ttl_seconds)

    @classmethod
    def invalidate_l1(cls, key: str) -> None:
        _L1_CACHE.pop(key, None)

    # -------------------------------------------------------------------------
    # Single-Flight Lock Helper
    # -------------------------------------------------------------------------

    @classmethod
    async def get_single_flight_lock(cls, key: str) -> asyncio.Lock:
        async with _FLIGHT_META_LOCK:
            if key not in _SINGLE_FLIGHT_LOCKS:
                _SINGLE_FLIGHT_LOCKS[key] = asyncio.Lock()
            return _SINGLE_FLIGHT_LOCKS[key]

    # -------------------------------------------------------------------------
    # Post Entity Cache-Aside
    # -------------------------------------------------------------------------

    @classmethod
    async def get_cached_post(cls, post_id: str) -> Optional[dict]:
        """Fetch post dictionary from L1 or Redis."""
        l1_k = f"post:{post_id}"
        l1_hit = cls.get_l1(l1_k)
        if l1_hit is not None:
            return l1_hit

        redis = get_redis_client()
        if not redis:
            return None

        try:
            raw = await redis.get(f"post:{post_id}")
            if raw:
                data = json.loads(raw)
                cls.set_l1(l1_k, data, ttl_seconds=3.0)
                return data
        except Exception as e:
            log.debug("Redis get post error: %s", e)
        return None

    @classmethod
    async def cache_posts_batch(cls, posts_dict_list: List[dict]) -> None:
        """Cache multiple post dictionaries using Redis pipelining."""
        redis = get_redis_client()
        if not redis or not posts_dict_list:
            return

        try:
            pipe = redis.pipeline()
            for p in posts_dict_list:
                post_id = p.get("id")
                if post_id:
                    k = f"post:{post_id}"
                    ttl = cls._jitter(cls.POST_TTL_BASE)
                    pipe.setex(k, ttl, json.dumps(p, default=str))
                    cls.set_l1(k, p, ttl_seconds=3.0)
            await pipe.execute()
        except Exception as e:
            log.debug("Redis batch cache posts error: %s", e)

    @classmethod
    async def get_cached_posts_multi(cls, post_ids: List[str]) -> Tuple[Dict[str, dict], List[str]]:
        """Fetch multiple posts using pipelined MGET. Returns (found_map, missing_ids)."""
        if not post_ids:
            return {}, []

        found: Dict[str, dict] = {}
        missing_from_l1: List[str] = []

        # Check L1 first
        for pid in post_ids:
            hit = cls.get_l1(f"post:{pid}")
            if hit is not None:
                found[pid] = hit
            else:
                missing_from_l1.append(pid)

        if not missing_from_l1:
            return found, []

        redis = get_redis_client()
        if not redis:
            return found, missing_from_l1

        missing_ids: List[str] = []
        try:
            keys = [f"post:{pid}" for pid in missing_from_l1]
            raw_vals = await redis.mget(keys)
            for pid, raw in zip(missing_from_l1, raw_vals):
                if raw:
                    try:
                        p_data = json.loads(raw)
                        found[pid] = p_data
                        cls.set_l1(f"post:{pid}", p_data, ttl_seconds=3.0)
                    except Exception:
                        missing_ids.append(pid)
                else:
                    missing_ids.append(pid)
        except Exception as e:
            log.debug("Redis mget error: %s", e)
            missing_ids.extend(missing_from_l1)

        return found, missing_ids

    # -------------------------------------------------------------------------
    # Feed Sorted Sets (ZADD / ZREVRANGEBYSCORE)
    # -------------------------------------------------------------------------

    @classmethod
    async def push_post_to_feed(cls, feed_key: str, post_id: str, score: float) -> None:
        """Add post ID to a Redis sorted set feed, scored by timestamp."""
        redis = get_redis_client()
        if not redis:
            return
        try:
            pipe = redis.pipeline()
            pipe.zadd(feed_key, {post_id: score})
            # Trim feed to max capacity
            pipe.zremrangebyrank(feed_key, 0, -(cls.FEED_MAX_ITEMS + 1))
            pipe.expire(feed_key, cls._jitter(cls.FEED_TTL_BASE))
            await pipe.execute()
            cls.invalidate_l1(feed_key)
        except Exception as e:
            log.debug("Redis push to feed error: %s", e)

    @classmethod
    async def get_feed_post_ids(
        cls,
        feed_key: str,
        max_score: float = float("inf"),
        limit: int = 20,
    ) -> Optional[List[str]]:
        """Fetch post IDs from a sorted set feed using ZREVRANGEBYSCORE."""
        redis = get_redis_client()
        if not redis:
            return None

        try:
            # Fetch limit + 1 items to know if has_more
            max_str = f"({max_score}" if max_score != float("inf") else "+inf"
            ids = await redis.zrevrangebyscore(
                feed_key,
                max=max_str,
                min="-inf",
                start=0,
                num=limit + 1,
            )
            return list(ids) if ids is not None else None
        except Exception as e:
            log.debug("Redis get feed error: %s", e)
            return None

    # -------------------------------------------------------------------------
    # User Interaction Sets (Likes & Bookmarks)
    # -------------------------------------------------------------------------

    @classmethod
    async def get_user_liked_post_ids(cls, user_id: str, candidate_post_ids: List[str]) -> Optional[Set[str]]:
        """Check which post IDs in candidate list are liked by user using Redis Set or SMISMEMBER."""
        if not user_id or not candidate_post_ids:
            return set()

        redis = get_redis_client()
        if not redis:
            return None

        key = f"user:{user_id}:likes"
        try:
            exists = await redis.exists(key)
            if not exists:
                return None  # Cache miss, need DB hydration

            # Check members
            if hasattr(redis, "smismember"):
                is_members = await redis.smismember(key, candidate_post_ids)
                return {pid for pid, is_m in zip(candidate_post_ids, is_members) if is_m}
            else:
                pipe = redis.pipeline()
                for pid in candidate_post_ids:
                    pipe.sismember(key, pid)
                results = await pipe.execute()
                return {pid for pid, is_m in zip(candidate_post_ids, results) if is_m}
        except Exception as e:
            log.debug("Redis check liked posts error: %s", e)
            return None

    @classmethod
    async def cache_user_likes_set(cls, user_id: str, post_ids: Set[str]) -> None:
        redis = get_redis_client()
        if not redis or not user_id:
            return
        key = f"user:{user_id}:likes"
        try:
            pipe = redis.pipeline()
            pipe.delete(key)
            if post_ids:
                pipe.sadd(key, *list(post_ids))
            pipe.expire(key, cls._jitter(cls.FEED_TTL_BASE))
            await pipe.execute()
        except Exception as e:
            log.debug("Redis cache likes set error: %s", e)

    @classmethod
    async def record_user_like(cls, user_id: str, post_id: str, is_like: bool) -> None:
        redis = get_redis_client()
        if not redis or not user_id or not post_id:
            return
        key = f"user:{user_id}:likes"
        try:
            if is_like:
                await redis.sadd(key, post_id)
            else:
                await redis.srem(key, post_id)
        except Exception as e:
            log.debug("Redis record like error: %s", e)

    # -------------------------------------------------------------------------
    # Granular Invalidation Matrix
    # -------------------------------------------------------------------------

    @classmethod
    async def invalidate_post(cls, post_id: str, stock_symbol: Optional[str] = None, author_id: Optional[str] = None) -> None:
        """Invalidate all cache entries related to a post."""
        cls.invalidate_l1(f"post:{post_id}")
        cls.invalidate_l1("feed:global")
        if stock_symbol:
            cls.invalidate_l1(f"feed:ticker:{stock_symbol.upper()}")
        if author_id:
            cls.invalidate_l1(f"feed:user:{author_id}")

        redis = get_redis_client()
        if not redis:
            return

        try:
            pipe = redis.pipeline()
            pipe.delete(f"post:{post_id}")
            pipe.zrem("feed:global", post_id)
            if stock_symbol:
                pipe.zrem(f"feed:ticker:{stock_symbol.upper()}", post_id)
            if author_id:
                pipe.zrem(f"feed:user:{author_id}", post_id)
            await pipe.execute()
        except Exception as e:
            log.debug("Redis invalidate post error: %s", e)

    @classmethod
    async def invalidate_user_profile(cls, user_id: str) -> None:
        cls.invalidate_l1(f"user:{user_id}:profile")
        redis = get_redis_client()
        if redis:
            try:
                await redis.delete(f"user:{user_id}:profile")
            except Exception as e:
                log.debug("Redis invalidate profile error: %s", e)
