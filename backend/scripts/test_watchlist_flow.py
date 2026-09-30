"""Comprehensive Direct Service Test for Watchlist Flow & Logic."""

import os
import sys
import asyncio
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.base import async_session_factory
from app.models.user import User
from app.models.stock import Stock
from app.models.prediction import Prediction
from app.models.sentiment import SentimentAggregate
from app.services.stock_service import StockService
from app.services.watchlist_service import WatchlistService
from app.schemas.watchlist import WatchlistCreate, WatchlistItemCreate, WatchlistItemUpdate
from sqlalchemy import select, delete


async def run_direct_service_test():
    print("=" * 60)
    print("RUNNING DIRECT WATCHLIST SERVICE & ENRICHMENT TEST")
    print("=" * 60)

    stock_service = StockService()
    watchlist_service = WatchlistService(stock_service=stock_service)

    async with async_session_factory() as db:
        # 1. Setup test user
        email = "wl_tester_direct@basarat.test"
        res = await db.execute(select(User).where(User.email == email))
        user = res.scalar_one_or_none()
        if not user:
            user = User(
                email=email,
                username="wl_direct_user",
                hashed_password="hashed_pw_test",
                full_name="Direct Tester",
                is_active=True,
                is_verified=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

        user_id = user.id
        print(f"[1] Test user ready: ID={user_id}")

        # 2. Setup test stocks & mock prediction / sentiment if needed
        for sym, name, sec in [
            ("LUCK", "Lucky Cement Limited", "Cement"),
            ("OGDC", "Oil & Gas Development Co", "Oil & Gas"),
            ("SYS", "Systems Limited", "Technology"),
        ]:
            s_res = await db.execute(select(Stock).where(Stock.symbol == sym))
            st = s_res.scalar_one_or_none()
            if not st:
                db.add(Stock(symbol=sym, name=name, sector=sec, is_active=True))
        await db.commit()
        print("[2] Reference stocks confirmed in DB.")

        # 3. Test get or create default watchlist
        print("\n[3] Testing get_or_create_default_watchlist ...")
        default_wl = await watchlist_service.get_or_create_default_watchlist(db, user_id)
        assert default_wl.is_default is True
        print(f"    [OK] Default watchlist ID: {default_wl.id}, Name: '{default_wl.name}'")

        # 4. Test 1-Tap Toggle (Toggle ON)
        print("\n[4] Testing toggle_symbol_in_default_watchlist (ADD) ...")
        # First ensure LUCK is not in the watchlist
        is_in, wl_id, item = await watchlist_service.toggle_symbol_in_default_watchlist(db, user_id, "LUCK")
        if not is_in:
            # Was removed, add it back
            is_in, wl_id, item = await watchlist_service.toggle_symbol_in_default_watchlist(db, user_id, "LUCK")
        assert is_in is True
        assert item is not None
        assert item.symbol == "LUCK"
        print(f"    [OK] Toggle ON succeeded: is_in_watchlist={is_in}, action=added")

        # 5. Test Check symbol
        print("\n[5] Testing check_symbol ...")
        is_in, wl_ids = await watchlist_service.check_symbol(db, user_id, "LUCK")
        assert is_in is True
        print(f"    [OK] Check symbol succeeded: is_in={is_in}, watchlist_ids={wl_ids}")

        # 6. Test Get default watchlist with enrichment
        print("\n[6] Testing get_watchlist (Detail with Enrichment) ...")
        wl = await watchlist_service.get_watchlist(db, default_wl.id, user_id)
        assert wl is not None
        detail = await watchlist_service.build_detail_response(db, wl)
        assert len(detail.items) >= 1
        luck_item = next((item for item in detail.items if item.symbol == "LUCK"), None)
        assert luck_item is not None, "LUCK not found in enriched items"
        print(f"    [OK] LUCK enriched item details:")
        print(f"      - Symbol: {luck_item.symbol}")
        print(f"      - Company Name: {luck_item.name}")
        print(f"      - Sector: {luck_item.sector}")
        print(f"      - Added Price: {luck_item.added_price}")
        print(f"      - Current Price: {luck_item.current_price}")
        print(f"      - Change Since Added: {luck_item.change_since_added}")
        print(f"      - Change Since Added %: {luck_item.change_since_added_pct}%")
        print(f"      - Forecast Direction: {luck_item.forecast_direction}")
        print(f"      - FinBERT Sentiment: {luck_item.sentiment_label}")

        # 7. Test 1-Tap Toggle (Toggle OFF)
        print("\n[7] Testing toggle_symbol_in_default_watchlist (REMOVE) ...")
        is_in, wl_id, item = await watchlist_service.toggle_symbol_in_default_watchlist(db, user_id, "LUCK")
        assert is_in is False
        # Now returns enriched removed item for better UX
        assert item is not None
        assert item.symbol == "LUCK"
        print(f"    [OK] Toggle OFF succeeded: is_in_watchlist={is_in}, action=removed, returned item={item.symbol}")

        # 8. Test Custom Watchlist CRUD
        print("\n[8] Testing Custom Watchlist Creation with symbols & target prices ...")
        custom_wl = await watchlist_service.create_watchlist(
            db,
            user_id,
            WatchlistCreate(
                name="AI Tech Picks",
                description="High momentum tech picks",
                symbols=["SYS", "OGDC"],
            ),
        )
        # Count items in the new watchlist
        item_count = len(custom_wl.items) if custom_wl.items else 0
        print(f"    [OK] Custom Watchlist created: ID={custom_wl.id}, Name='{custom_wl.name}', Count={item_count}")

        # 9. Test update item target price and notes
        print("\n[9] Testing update_item ...")
        # First get the item to update
        item = await watchlist_service.get_item(db, custom_wl.id, "SYS")
        assert item is not None
        updated_item = await watchlist_service.update_item(
            db,
            item,
            WatchlistItemUpdate(target_price=Decimal("520.00"), notes="Target 520 breakout"),
        )
        assert updated_item.target_price == Decimal("520.00")
        assert updated_item.notes == "Target 520 breakout"
        print(f"    [OK] Item updated: target_price={updated_item.target_price}, notes='{updated_item.notes}'")

        # 10. Clean up test custom watchlist
        print("\n[10] Testing delete_watchlist ...")
        await watchlist_service.delete_watchlist(db, custom_wl)
        print("    [OK] Custom watchlist deleted successfully.")

    print("\n" + "=" * 60)
    print("ALL DIRECT SERVICE & ENRICHMENT CHECKS PASSED (0 ERRORS)!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_direct_service_test())
