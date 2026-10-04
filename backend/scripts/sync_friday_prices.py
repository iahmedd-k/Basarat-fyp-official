"""
Sync Friday (2026-10-02) closing market prices into raw OHLCV, database, and feature store.
"""

import asyncio
import logging
from datetime import date, datetime
from pathlib import Path
from decimal import Decimal

import pandas as pd
from sqlalchemy import text

from app.db.session import async_session_factory
from app.services.market_service import MarketService
from app.data.scraper.symbol_universe import get_active_symbols

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("sync_friday")

OHLCV_PARQUET = Path("data/raw/ohlcv/all_symbols.parquet")
TARGET_DATE = date(2026, 10, 2)


async def sync_friday():
    log.info("Fetching latest market session closes from PSX Screener...")
    service = MarketService()
    quotes = await service.get_market_data(force_refresh=True, read_only=False)
    log.info("Fetched %d market quotes.", len(quotes))

    active = get_active_symbols()
    active_syms = {e["symbol"] for e in active}

    quotes_map = {q["symbol"]: q for q in quotes if q.get("symbol") in active_syms}
    log.info("Matched %d quotes for active universe.", len(quotes_map))

    # 1. Update Database stock_prices
    log.info("Syncing 2026-10-02 closes to PostgreSQL database...")
    async with async_session_factory() as session:
        # Get stock_id map
        res = await session.execute(text("SELECT id, symbol FROM stocks WHERE symbol IS NOT NULL"))
        stock_ids = {row[1]: row[0] for row in res.fetchall()}

        synced_db = 0
        for sym, q in quotes_map.items():
            stk_id = stock_ids.get(sym)
            if not stk_id:
                continue

            price = float(q.get("current") or q.get("ldcp") or 0.0)
            if price <= 0:
                continue

            vol = int(q.get("volume") or 0)
            open_p = float(q.get("open") or price)
            high_p = float(q.get("high") or price)
            low_p = float(q.get("low") or price)

            await session.execute(
                text("""
                    INSERT INTO stock_prices (id, stock_id, date, open, high, low, close, volume, adjusted_close)
                    VALUES (gen_random_uuid(), :stock_id, :date, :open, :high, :low, :close, :volume, :adj_close)
                    ON CONFLICT DO NOTHING
                """),
                {
                    "stock_id": stk_id,
                    "date": TARGET_DATE,
                    "open": open_p,
                    "high": high_p,
                    "low": low_p,
                    "close": price,
                    "volume": vol,
                    "adj_close": price,
                },
            )
            synced_db += 1

        await session.commit()
        log.info("Synced %d rows into DB stock_prices table for date %s", synced_db, TARGET_DATE)

    # 2. Update raw all_symbols.parquet
    if OHLCV_PARQUET.exists():
        log.info("Updating raw %s...", OHLCV_PARQUET)
        df_raw = pd.read_parquet(OHLCV_PARQUET)
        df_raw["date"] = pd.to_datetime(df_raw["date"])

        new_rows = []
        for sym, q in quotes_map.items():
            price = float(q.get("current") or q.get("ldcp") or 0.0)
            if price <= 0:
                continue
            vol = int(q.get("volume") or 0)
            new_rows.append({
                "symbol": sym,
                "date": pd.Timestamp(TARGET_DATE),
                "open": float(q.get("open") or price),
                "high": float(q.get("high") or price),
                "low": float(q.get("low") or price),
                "close": price,
                "volume": vol,
            })

        df_new = pd.DataFrame(new_rows)
        # Drop existing 2026-10-02 if any and concat
        df_raw = df_raw[df_raw["date"].dt.date != TARGET_DATE]
        combined = pd.concat([df_raw, df_new], ignore_index=True)
        combined = combined.sort_values(["symbol", "date"]).reset_index(drop=True)
        combined.to_parquet(OHLCV_PARQUET, index=False)
        log.info("Saved %d total rows into %s (Max date: %s)", len(combined), OHLCV_PARQUET, combined["date"].max())


if __name__ == "__main__":
    asyncio.run(sync_friday())
