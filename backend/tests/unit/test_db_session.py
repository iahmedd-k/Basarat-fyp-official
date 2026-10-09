import pytest
from sqlalchemy import String, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db import session as db_session_module


class SessionTestBase(DeclarativeBase):
    pass


class SessionTestRecord(SessionTestBase):
    __tablename__ = "session_test_records"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[str] = mapped_column(String, nullable=False)


@pytest.mark.asyncio
async def test_db_session_commits_flushed_changes_for_next_request(monkeypatch, tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'sessions.db'}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr(db_session_module, "async_session_factory", session_factory)

    try:
        async with engine.begin() as connection:
            await connection.run_sync(SessionTestBase.metadata.create_all)

        async with db_session_module.db_session() as session:
            session.add(SessionTestRecord(id="record-1", value="persisted"))
            await session.flush()

        async with session_factory() as verification_session:
            record = await verification_session.scalar(
                select(SessionTestRecord).where(SessionTestRecord.id == "record-1")
            )

        assert record is not None
        assert record.value == "persisted"

        async with db_session_module.db_session() as session:
            record = await session.get(SessionTestRecord, "record-1")
            assert record is not None
            record.value = "updated"
            await session.flush()

        async with session_factory() as verification_session:
            record = await verification_session.get(SessionTestRecord, "record-1")
        assert record is not None
        assert record.value == "updated"

        async with db_session_module.db_session() as session:
            record = await session.get(SessionTestRecord, "record-1")
            assert record is not None
            await session.delete(record)
            await session.flush()

        async with session_factory() as verification_session:
            record = await verification_session.get(SessionTestRecord, "record-1")
        assert record is None
    finally:
        await engine.dispose()
