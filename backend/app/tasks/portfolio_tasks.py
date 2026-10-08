"""Celery tasks for portfolio precomputation."""

import logging
from datetime import datetime

from celery import shared_task

log = logging.getLogger(__name__)


def _get_sync_db():
    """Get a synchronous DB session for Celery tasks."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import get_settings

    engine = create_engine(get_settings().DATABASE_URL_SYNC, pool_pre_ping=True)
    Session = sessionmaker(bind=engine)
    return Session()


@shared_task(
    name="app.tasks.portfolio_tasks.precompute_all_portfolio_performance",
    bind=True,
    max_retries=1,
    acks_late=True,
    soft_time_limit=3600,
    time_limit=4200,
)
def precompute_all_portfolio_performance(self):
    """Precompute portfolio performance for all users with active holdings.
    
    Runs daily after market close to populate Redis cache with performance data.
    """
    from app.models.portfolio import PortfolioTransaction
    from sqlalchemy import select
    
    db = _get_sync_db()
    try:
        # Get all users with portfolio transactions
        user_ids = list(db.scalars(
            select(PortfolioTransaction.user_id).distinct()
        ))
        
        log.info("Precomputing portfolio performance for %d users", len(user_ids))
        
        completed = 0
        errors = 0
        
        for user_id in user_ids:
            try:
                # Run the async precomputation in a new event loop
                import asyncio
                from app.db.session import async_session_factory
                from app.services.portfolio_service import PortfolioService
                
                async def run_precompute():
                    async with async_session_factory() as session:
                        service = PortfolioService(session)
                        return await service.precompute_all_performance(user_id)
                
                loop = asyncio.new_event_loop()
                try:
                    result = loop.run_until_complete(run_precompute())
                    log.debug("Precomputed performance for user %s: %s", user_id, list(result.keys()))
                finally:
                    loop.close()
                
                completed += 1
                
            except Exception as e:
                log.warning("Portfolio performance precompute failed for user %s: %s", user_id, e)
                errors += 1
        
        return {
            "status": "completed",
            "total_users": len(user_ids),
            "completed": completed,
            "errors": errors,
            "completed_at": datetime.utcnow().isoformat(),
        }
    finally:
        db.close()


@shared_task(
    name="app.tasks.portfolio_tasks.precompute_user_portfolio_performance",
    bind=True,
    max_retries=2,
    acks_late=True,
)
def precompute_user_portfolio_performance(self, user_id: str):
    """Precompute portfolio performance for a single user (on-demand)."""
    try:
        import asyncio
        from app.db.session import async_session_factory
        from app.services.portfolio_service import PortfolioService
        
        async def run_precompute():
            async with async_session_factory() as session:
                service = PortfolioService(session)
                return await service.precompute_all_performance(user_id)
        
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(run_precompute())
        finally:
            loop.close()
        
        return {
            "status": "completed",
            "user_id": user_id,
            "periods": list(result.keys()),
            "completed_at": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        log.exception("User portfolio performance precompute failed: user=%s", user_id)
        raise self.retry(exc=exc, countdown=60)