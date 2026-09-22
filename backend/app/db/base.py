from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy import create_engine

from app.core.config import get_settings
from app.core.database_urls import async_database_url, sync_database_url

settings = get_settings()

# Supabase free databases have tight connection limits. Keep a small bounded
# pool; transaction-pooler-specific asyncpg options are applied automatically.
async_url, async_connect_args = async_database_url(settings.DATABASE_URL)
engine = create_async_engine(
    async_url,
    echo=settings.DEBUG,
    future=True,
    pool_pre_ping=True,
    pool_size=3,
    max_overflow=2,
    pool_recycle=1200,
    connect_args=async_connect_args,
)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Sync engine (for Celery tasks) — lazy initialization
_sync_engine = None
_sync_session_factory = None


def get_sync_engine():
    """Lazy-init sync engine for Celery tasks."""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            sync_database_url(settings.DATABASE_URL, settings.DATABASE_URL_SYNC),
            pool_pre_ping=True,
            pool_size=2,
            max_overflow=0,
            pool_recycle=1200,
            future=True,
        )
    return _sync_engine


def get_sync_session_factory():
    """Lazy-init sync session factory for Celery tasks."""
    global _sync_session_factory
    if _sync_session_factory is None:
        _sync_session_factory = sessionmaker(bind=get_sync_engine())
    return _sync_session_factory


class Base(DeclarativeBase):
    pass
