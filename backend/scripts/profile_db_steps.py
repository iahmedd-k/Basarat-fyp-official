"""Profile DB & Watchlist/Portfolio Mutation Latencies Step-by-Step."""

import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db.session import async_session_factory
from sqlalchemy import text, select
from app.models.user import User
from app.models.stock import Stock
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.watchlist import WatchlistCreate
from app.services.watchlist_service import WatchlistService
from app.services.stock_service import StockService
from app.core.redis import cache_get, cache_set, cache_invalidate

async def profile_database():
    print("\n" + "="*70)
    print("  STEP-BY-STEP PROFILING OF DB & MUTATION LATENCY")
    print("="*70)

    # 1. Test raw DB ping
    t0 = time.perf_counter()
    async with async_session_factory() as db:
        res = await db.execute(text("SELECT 1"))
        val = res.scalar()
    t_ping = (time.perf_counter() - t0) * 1000
    print(f"1. Raw DB Connection + SELECT 1: {t_ping:.2f}ms")

    # 2. Test Fetching User
    t0 = time.perf_counter()
    async with async_session_factory() as db:
        res = await db.execute(select(User).limit(1))
        user = res.scalars().first()
    t_user = (time.perf_counter() - t0) * 1000
    user_id = str(user.id) if user else "test_user"
    print(f"2. Fetch User ({user_id}): {t_user:.2f}ms")

    # 3. Test Redis Ping / Set / Invalidate
    t0 = time.perf_counter()
    await cache_set("profile:test_key", {"a": 1}, ttl_seconds=60)
    t_red_set = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    val = await cache_get("profile:test_key")
    t_red_get = (time.perf_counter() - t0) * 1000
    t0 = time.perf_counter()
    await cache_invalidate("profile:test_key")
    t_red_inv = (time.perf_counter() - t0) * 1000
    print(f"3. Redis Set: {t_red_set:.2f}ms | Get: {t_red_get:.2f}ms | Invalidate: {t_red_inv:.2f}ms")

    # 4. Profile WatchlistService.create_watchlist step by step
    service = WatchlistService(stock_service=StockService())
    data = WatchlistCreate(name=f"Profile WL {time.time()}", description="Testing", symbols=["OGDC", "PPL"])
    
    async with async_session_factory() as db:
        # Step 4a: count query
        t0 = time.perf_counter()
        count_stmt = select(text("count(id)")).select_from(Watchlist).where(Watchlist.user_id == user_id)
        c_res = await db.execute(count_stmt)
        c_val = c_res.scalar()
        t_4a = (time.perf_counter() - t0) * 1000
        print(f"4a. Check existing watchlists count: {t_4a:.2f}ms")

        # Step 4b: insert watchlist row + flush
        t0 = time.perf_counter()
        wl = Watchlist(user_id=user_id, name=data.name, description=data.description, is_default=False)
        db.add(wl)
        await db.flush()
        t_4b = (time.perf_counter() - t0) * 1000
        print(f"4b. Add Watchlist model + db.flush(): {t_4b:.2f}ms")

        # Step 4c: resolve stocks
        t0 = time.perf_counter()
        for sym in ["OGDC", "PPL"]:
            t_s0 = time.perf_counter()
            stock = await service._resolve_stock_reference(db, sym)
            t_s = (time.perf_counter() - t_s0) * 1000
            print(f"   4c. Resolve symbol '{sym}': {t_s:.2f}ms")
            db.add(WatchlistItem(watchlist_id=wl.id, stock_id=stock.id, symbol=stock.symbol))
        t_4c = (time.perf_counter() - t0) * 1000
        print(f"4c. Total Symbol Resolutions: {t_4c:.2f}ms")

        # Step 4d: commit
        t0 = time.perf_counter()
        await db.commit()
        t_4d = (time.perf_counter() - t0) * 1000
        print(f"4d. db.commit(): {t_4d:.2f}ms")

        # Step 4e: refresh
        t0 = time.perf_counter()
        await db.refresh(wl)
        t_4e = (time.perf_counter() - t0) * 1000
        print(f"4e. db.refresh(wl): {t_4e:.2f}ms")

        # Step 4f: cache invalidation
        t0 = time.perf_counter()
        await service._invalidate_watchlist_cache(user_id, wl.id)
        t_4f = (time.perf_counter() - t0) * 1000
        print(f"4f. _invalidate_watchlist_cache: {t_4f:.2f}ms")

        # Cleanup
        await db.delete(wl)
        await db.commit()

if __name__ == "__main__":
    asyncio.run(profile_database())
