from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

from app.core.config import get_settings

settings = get_settings()

# Async engine (for FastAPI)
engine = create_async_engine(settings.DATABASE_URL, echo=settings.DEBUG, future=True)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine (for Celery tasks) — lazy initialization
_sync_engine = None
_sync_session_factory = None


def get_sync_engine():
    """Lazy-init sync engine for Celery tasks."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True, future=True)
    return _sync_engine


def get_sync_session_factory():
    """Lazy-init sync session factory for Celery tasks."""
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(bind=get_sync_engine())
    return _sync_session_factory


class Base(DeclarativeBase):
    pass
