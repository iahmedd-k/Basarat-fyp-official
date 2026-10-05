"""Idempotency service to guarantee exactly-once write processing for community actions."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Tuple

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis_client
from app.models.community import CommunityIdempotencyKey

log = logging.getLogger(__name__)


class IdempotencyService:
    DEFAULT_TTL_SECONDS = 86400  # 24 hours

    @staticmethod
    async def get_stored_response(
        db: AsyncSession,
        user_id: str,
        idempotency_key: str,
        endpoint: str,
    ) -> Optional[Tuple[int, Any]]:
        """Check if an operation with the given idempotency key was already completed."""
        if not idempotency_key or not user_id:
            return None

        # 1. Fast path: Redis check
        redis = get_redis_client()
        if redis:
            try:
                cache_k = f"idempotency:{user_id}:{idempotency_key}"
                cached = await redis.get(cache_k)
                if cached:
                    data = json.loads(cached)
                    return data.get("status_code", 200), data.get("body")
            except Exception as e:
                log.debug("Redis idempotency get error: %s", e)

        # 2. Durable path: DB check
        try:
            now = datetime.now(timezone.utc)
            stmt = select(CommunityIdempotencyKey).where(
                CommunityIdempotencyKey.user_id == user_id,
                CommunityIdempotencyKey.key == idempotency_key,
                CommunityIdempotencyKey.expires_at > now,
            )
            res = await db.execute(stmt)
            record = res.scalars().first()
            if record and record.response_code is not None:
                body = json.loads(record.response_body) if record.response_body else None
                return record.response_code, body
        except Exception as e:
            log.warning("DB idempotency lookup failed: %s", e)

        return None

    @staticmethod
    async def record_response(
        db: AsyncSession,
        user_id: str,
        idempotency_key: str,
        endpoint: str,
        status_code: int,
        response_body: Any,
        ttl_seconds: int = DEFAULT_TTL_SECONDS,
    ) -> None:
        """Record the final response for an idempotency key."""
        if not idempotency_key or not user_id:
            return

        body_json = json.dumps(response_body, default=str) if response_body is not None else None

        # 1. Store in Redis
        redis = get_redis_client()
        if redis:
            try:
                cache_k = f"idempotency:{user_id}:{idempotency_key}"
                val = json.dumps({"status_code": status_code, "body": response_body}, default=str)
                await redis.setex(cache_k, ttl_seconds, val)
            except Exception as e:
                log.debug("Redis idempotency set error: %s", e)

        # 2. Store in DB
        try:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)
            item = CommunityIdempotencyKey(
                key=idempotency_key,
                user_id=user_id,
                endpoint=endpoint,
                response_code=status_code,
                response_body=body_json,
                expires_at=expires_at,
            )
            db.add(item)
            await db.flush()
        except Exception as e:
            log.warning("DB idempotency record insert failed (likely concurrent duplicate): %s", e)
