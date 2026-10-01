"""Tests for the shared event-loop bridge used by sync Celery tasks."""

import asyncio
import threading

import pytest

from app.core import async_bridge


def test_run_sync_executes_coroutine():
    async def work():
        await asyncio.sleep(0)
        return "done"

    assert async_bridge.run_sync(work()) == "done"


def test_run_sync_reuses_one_loop_across_calls():
    async def current_loop():
        return id(asyncio.get_running_loop())

    first = async_bridge.run_sync(current_loop())
    second = async_bridge.run_sync(current_loop())

    # A fresh loop per call is what previously left SQLAlchemy/Redis pools bound
    # to a closed loop, so the bridge must hand back the same loop every time.
    assert first == second


def test_run_sync_works_from_a_worker_thread():
    results: list[str] = []

    async def work():
        await asyncio.sleep(0)
        return "threaded"

    def target():
        results.append(async_bridge.run_sync(work()))

    thread = threading.Thread(target=target)
    thread.start()
    thread.join(timeout=30)

    assert results == ["threaded"]


def test_run_sync_rejects_reentrant_call_from_bridge_thread():
    async def reentrant():
        async def inner():
            return "inner"

        return async_bridge.run_sync(inner())

    with pytest.raises(RuntimeError, match="async bridge thread"):
        async_bridge.run_sync(reentrant())


def test_run_sync_propagates_exceptions():
    async def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError, match="nope"):
        async_bridge.run_sync(boom())
