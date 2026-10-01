"""Tests for the news ingestion single-flight lock.

Regression guard: the lock previously called `.set()` on the *async* Redis proxy,
which returns an un-awaited coroutine. A coroutine is always truthy, so
`acquired` was always True and no key was ever written -- the lock provided no
mutual exclusion at all.
"""

from unittest.mock import MagicMock

import pytest

from app.services.news_pipeline import market_schedule


class _FakeRedis:
    def __init__(self, acquire: bool = True):
        self._acquire = acquire
        self.set_calls: list[tuple] = []
        self.deleted: list[str] = []

    def set(self, key, value, nx=False, ex=None):
        self.set_calls.append((key, value, nx, ex))
        return self._acquire

    def delete(self, key):
        self.deleted.append(key)
        return 1


async def test_lock_acquires_via_sync_redis(monkeypatch):
    client = _FakeRedis(acquire=True)
    monkeypatch.setattr(
        "app.core.redis.get_sync_redis_client", lambda: client, raising=False
    )

    async with market_schedule.ingestion_lock() as acquired:
        assert acquired is True

    assert client.set_calls, "the lock must actually call Redis SET"
    assert client.deleted == [market_schedule._LOCK_KEY]


async def test_lock_reports_not_acquired_when_redis_holds_it(monkeypatch):
    client = _FakeRedis(acquire=False)
    monkeypatch.setattr(
        "app.core.redis.get_sync_redis_client", lambda: client, raising=False
    )

    # The advisory-lock fallback must not silently report success either.
    class _Result:
        @staticmethod
        def scalar():
            return False

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, *_args, **_kwargs):
            return _Result()

    monkeypatch.setattr(market_schedule, "async_session_factory", lambda: _Session())

    async with market_schedule.ingestion_lock() as acquired:
        assert acquired is False

    # Nothing was taken, so nothing may be released.
    assert client.deleted == []


async def test_lock_falls_back_to_advisory_lock_without_redis(monkeypatch):
    monkeypatch.setattr(
        "app.core.redis.get_sync_redis_client", lambda: None, raising=False
    )

    class _Result:
        @staticmethod
        def scalar():
            return True

    class _Session:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, *_args, **_kwargs):
            return _Result()

    monkeypatch.setattr(market_schedule, "async_session_factory", lambda: _Session())

    async with market_schedule.ingestion_lock() as acquired:
        assert acquired is True


async def test_lock_never_awaits_a_coroutine(monkeypatch):
    """A coroutine result would be truthy even when the lock was never taken."""
    client = _FakeRedis(acquire=True)
    monkeypatch.setattr(
        "app.core.redis.get_sync_redis_client", lambda: client, raising=False
    )

    async with market_schedule.ingestion_lock() as acquired:
        assert not asyncio_iscoroutine(acquired)


def asyncio_iscoroutine(value) -> bool:
    import asyncio

    return asyncio.iscoroutine(value)
