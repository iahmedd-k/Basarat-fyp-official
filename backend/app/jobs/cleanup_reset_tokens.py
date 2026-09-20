"""Cleanup job for expired and used password reset tokens.

This module provides a standalone function to purge stale PasswordResetToken
rows. It can be wired into any scheduler (Celery beat, APScheduler, cron, etc.).

Usage with Celery beat (add to celery_app.py beat_schedule):
    "cleanup-reset-tokens": {
        "task": "app.jobs.cleanup_reset_tokens.cleanup_expired_reset_tokens_task",
        "schedule": 86400.0,  # daily
    }

Or call `cleanup_expired_reset_tokens(db)` directly from any async context.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import PasswordResetToken


async def cleanup_expired_reset_tokens(db: AsyncSession) -> int:
    """Delete PasswordResetToken rows that are used or older than 7 days.

    Returns the number of rows deleted.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=7)

    result = await db.execute(
        delete(PasswordResetToken).where(
            (PasswordResetToken.used == True)
            | (PasswordResetToken.expires_at < cutoff)
        )
    )
    await db.flush()
    return result.rowcount
