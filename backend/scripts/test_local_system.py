"""Test script to verify Database, Redis, Task Runner, and App initialization locally."""

import asyncio
import sys
from pathlib import Path

# Ensure backend root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text

from app.core.config import get_settings
from app.db.base import engine, get_sync_session_factory
from app.core.redis import cache_set, cache_get, cache_invalidate
from app.core.task_runner import dispatch_task
from app.tasks.sentiment_tasks import rescore_failed_sentiment_task
from app.services.health_service import HealthService


async def test_database():
    print("\n--- 1. Testing Database ---")
    # Test Async DB (FastAPI)
    async with engine.connect() as conn:
        res = await conn.execute(text("SELECT 1 AS ok"))
        row = res.fetchone()
        print(f"  [Async DB] Connection OK (SELECT 1 -> {row[0]})")

    # Test Sync DB (Celery & Workers)
    SessionFactory = get_sync_session_factory()
    with SessionFactory() as sync_db:
        res = sync_db.execute(text("SELECT 1 AS ok"))
        row = res.fetchone()
        print(f"  [Sync DB] Connection OK (SELECT 1 -> {row[0]})")


async def test_redis_and_cache():
    print("\n--- 2. Testing Redis & Cache ---")
    test_key = "local_test_key_123"
    test_val = {"status": "ok", "app": "Basarat Local"}
    await cache_set(test_key, test_val, ttl_seconds=30)
    retrieved = await cache_get(test_key)
    print(f"  [Cache Get/Set] Result: {retrieved}")
    assert retrieved == test_val, "Cache retrieved value did not match!"
    await cache_invalidate(test_key)
    after_del = await cache_get(test_key)
    print(f"  [Cache Invalidate] Result after delete: {after_del}")
    assert after_del is None, "Cache value was not deleted!"


async def test_task_runner():
    print("\n--- 3. Testing Task Runner & Workers ---")
    settings = get_settings()
    print(f"  Config: USE_CELERY={settings.USE_CELERY}, REDIS_ENABLED={settings.REDIS_ENABLED}")

    # Dispatch task
    res_or_future = dispatch_task(rescore_failed_sentiment_task, 10)
    if hasattr(res_or_future, "get"):
        # Celery AsyncResult
        result = res_or_future.get(timeout=10)
    elif hasattr(res_or_future, "result"):
        # Future (in-process)
        result = res_or_future.result(timeout=10)
    else:
        result = res_or_future
    print(f"  [Task Execution] Result: {result}")


async def test_health_and_app():
    print("\n--- 4. Testing Health Service ---")
    hs = HealthService()
    health = await hs.check_health()
    print(f"  [Health Status]: {health['status']}")
    print(f"  [Services]: {health['services']}")


async def main():
    print("========================================")
    print("      BASARAT LOCAL SYSTEM TEST         ")
    print("========================================")
    try:
        await test_database()
        await test_redis_and_cache()
        await test_task_runner()
        await test_health_and_app()
        print("\n========================================")
        print("   ALL LOCAL TESTS PASSED SUCCESSFULLY! ")
        print("========================================")
    except Exception as e:
        print(f"\n[ERROR] Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
