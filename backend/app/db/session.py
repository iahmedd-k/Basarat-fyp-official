from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from app.db.base import async_session_factory


@asynccontextmanager
async def db_session() -> AsyncGenerator:
    """Open a Postgres session only for the caller's `async with` block."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            if session.is_active:
                await session.rollback()
            raise


async def get_db() -> AsyncGenerator:
    async with db_session() as session:
        yield session
