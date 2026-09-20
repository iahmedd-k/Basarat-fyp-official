"""Celery tasks for PSX company announcements synchronization."""

import asyncio
import logging
from celery import shared_task
from sqlalchemy import select

log = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@shared_task(
    name="app.tasks.news_tasks.sync_portfolio_announcements",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def sync_portfolio_announcements(self):
    """Periodic Celery task: fetches and pre-warms announcements in Redis for all active portfolio stocks."""
    from app.db.session import async_session_factory
    from app.models.portfolio import PortfolioTransaction
    from app.services.psx_announcement_service import PSXAnnouncementService

    async def _execute():
        async with async_session_factory() as db:
            result = await db.execute(
                select(PortfolioTransaction.symbol).distinct()
            )
            symbols = [row[0].upper() for row in result.all() if row[0]]
            log.info("Starting background PSX announcement sync for %d portfolio symbols: %s", len(symbols), symbols)

            psx_svc = PSXAnnouncementService(db)
            synced_counts = {}
            for sym in symbols:
                try:
                    items = await psx_svc.get_stock_announcements(sym, limit=20)
                    synced_counts[sym] = len(items)
                except Exception as exc:
                    log.warning("Failed to sync announcements for %s: %s", sym, exc)

            return synced_counts

    try:
        counts = _run_async(_execute())
        log.info("Portfolio announcements background sync complete: %s", counts)
        return {"status": "completed", "synced": counts}
    except Exception as exc:
        log.exception("Background portfolio announcement sync failed")
        raise self.retry(exc=exc, countdown=60)
