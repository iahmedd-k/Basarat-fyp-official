from collections.abc import AsyncGenerator

from app.db.base import async_session_factory


async def get_db() -> AsyncGenerator:
    async with async_session_factory() as session:
        try:
            yield session
            if session.is_active and (session.dirty or session.new or session.deleted):
                await session.commit()
        except Exception:
            if session.is_active:
                await session.rollback()
            raise
        finally:
            await session.close()
