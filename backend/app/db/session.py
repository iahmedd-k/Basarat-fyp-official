from collections.abc import AsyncGenerator

from app.db.base import async_session_factory


async def get_db() -> AsyncGenerator:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
