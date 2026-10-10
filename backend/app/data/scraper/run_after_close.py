"""Paced daily OHLCV refresh using latest market quotes from Redis."""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd
from sqlalchemy import select

from app.core.redis import cache_get_sync
from app.db.base import get_sync_session_factory
from app.data.scraper.symbol_universe import get_active_symbols
from app.data.scraper.writers import write_combined_parquet, write_symbol_parquet
from app.data.scraper.ohlcv import psx_access_denied, reset_psx_access_denied
from app.data.scraper.run_scrape import (
    _DEFAULT_OUTPUT_DIR,
    _save_fetch_log,
)
from app.models.stock import Stock, StockPrice

log = logging.getLogger(__name__)

_BATCH_SIZE = 50
_BATCH_PAUSE_SECONDS = 0
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{1,20}$")
_PKT = ZoneInfo("Asia/Karachi")


def get_refresh_symbols(output_dir: Path | None = None) -> list[str]:
    """Return the union of registered stocks, ETFs, quotes, and existing OHLCV tickers."""
    output_dir = output_dir or _DEFAULT_OUTPUT_DIR
    symbols: set[str] = set()

    session_factory = get_sync_session_factory()
    with session_factory() as session:
        # Stocks
        registered = session.scalars(
            select(Stock.symbol).where(Stock.is_active.is_(True))
        ).all()
        symbols.update(str(symbol).strip().upper() for symbol in registered)

        # ETFs (active)
        try:
            from app.models.etf import ETF
            etf_symbols = session.scalars(
                select(ETF.symbol).where(ETF.is_active.is_(True))
            ).all()
            symbols.update(str(symbol).strip().upper() for symbol in etf_symbols)
        except Exception as exc:
            log.debug("Could not load ETF symbols for OHLCV refresh: %s", exc)

    for cache_key in ("market:quotes", "market:quotes:last_known"):
        quotes = cache_get_sync(cache_key)
        if not isinstance(quotes, list):
            continue
        symbols.update(
            str(quote.get("symbol") or "").strip().upper()
            for quote in quotes
            if isinstance(quote, dict)
        )

    symbols.update(
        path.stem.upper()
        for path in output_dir.glob("*.parquet")
        if path.name != "all_symbols.parquet"
    )
    symbols.update(
        str(entry.get("symbol") or "").strip().upper()
        for entry in get_active_symbols()
        if isinstance(entry, dict)
    )

    return sorted(
        symbol
        for symbol in symbols
        if _SYMBOL_PATTERN.fullmatch(symbol) and not symbol.startswith("TEST")
    )


def _materialize_database_history(output_dir: Path, symbols: list[str]) -> int:
    """Seed missing per-symbol files from persisted prices before incremental refresh."""
    missing = [
        symbol
        for symbol in symbols
        if not (output_dir / f"{symbol}.parquet").is_file()
    ]
    if not missing:
        return 0

    session_factory = get_sync_session_factory()
    with session_factory() as session:
        rows = session.execute(
            select(
                Stock.symbol,
                StockPrice.date,
                StockPrice.open,
                StockPrice.high,
                StockPrice.low,
                StockPrice.close,
                StockPrice.volume,
            )
            .join(Stock, StockPrice.stock_id == Stock.id)
            .where(Stock.is_active.is_(True), Stock.symbol.in_(missing))
            .order_by(Stock.symbol, StockPrice.date)
        ).all()

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row.symbol).upper()].append(
            {
                "date": pd.Timestamp(row.date),
                "open": float(row.open) if row.open is not None else None,
                "high": float(row.high) if row.high is not None else None,
                "low": float(row.low) if row.low is not None else None,
                "close": float(row.close) if row.close is not None else None,
                "volume": int(row.volume or 0),
            }
        )

    for symbol, records in grouped.items():
        write_symbol_parquet(pd.DataFrame.from_records(records), symbol, output_dir)
    log.info(
        "Materialized persisted OHLCV history for %d/%d registered symbols missing local files",
        len(grouped),
        len(missing),
    )
    return len(grouped)


def run_after_close_scrape(
    output_dir: Path | None = None,
    *,
    batch_size: int = _BATCH_SIZE,
    pause_seconds: float = _BATCH_PAUSE_SECONDS,
    end_date=None,
) -> dict:
    """Refresh current-session daily OHLCV from Redis market quotes."""
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    symbols = get_refresh_symbols(out_dir)
    if not symbols:
        raise RuntimeError("No stock or quote symbols are available for OHLCV refresh")

    materialized = _materialize_database_history(out_dir, symbols)
    explicit_end_date = end_date is not None
    end = end_date or datetime.now(_PKT).date()
    if explicit_end_date and end.weekday() >= 5:
        raise ValueError("OHLCV refresh end_date must be a trading weekday")
    if not explicit_end_date:
        while end.weekday() >= 5:
            end -= timedelta(days=1)

    # 1. Read quotes from Redis (checking last_known fallback and active quotes)
    raw_quotes = cache_get_sync("market:quotes:last_known")
    if not raw_quotes or not isinstance(raw_quotes, list):
        raw_quotes = cache_get_sync("market:quotes")

    quotes_list = raw_quotes if isinstance(raw_quotes, list) else []
    quote_map: dict[str, dict] = {
        str(q.get("symbol") or "").strip().upper(): q
        for q in quotes_list
        if isinstance(q, dict) and q.get("symbol")
    }

    log.info(
        "Starting Redis-backed after-close OHLCV refresh for %d symbols (%d cached quotes, %d DB materialized)",
        len(symbols),
        len(quote_map),
        materialized,
    )

    results = []
    target_date = pd.Timestamp(end)

    for symbol in symbols:
        quote = quote_map.get(symbol)

        current = quote.get("current") if quote else None
        ldcp = quote.get("ldcp") if quote else None
        close_price = current if (current is not None and current > 0) else (ldcp if (ldcp is not None and ldcp > 0) else None)

        if close_price is None or close_price <= 0:
            existing_path = out_dir / f"{symbol}.parquet"
            if existing_path.is_file():
                results.append({"symbol": symbol, "status": "skipped", "reason": "no_recent_quote"})
            else:
                results.append({"symbol": symbol, "status": "no_data", "reason": "no_quote_and_no_file"})
            continue

        open_price = quote.get("open") if (quote.get("open") is not None and quote.get("open") > 0) else close_price
        high_price = quote.get("high") if (quote.get("high") is not None and quote.get("high") > 0) else max(open_price, close_price)
        low_price = quote.get("low") if (quote.get("low") is not None and quote.get("low") > 0) else min(open_price, close_price)
        volume = int(quote.get("volume") or 0)

        new_row = pd.DataFrame(
            [{
                "date": target_date,
                "open": float(open_price),
                "high": float(high_price),
                "low": float(low_price),
                "close": float(close_price),
                "volume": volume,
            }]
        )

        existing_path = out_dir / f"{symbol}.parquet"
        if existing_path.is_file():
            try:
                existing_df = pd.read_parquet(existing_path)
                if not existing_df.empty and "date" in existing_df.columns:
                    existing_df["date"] = pd.to_datetime(existing_df["date"])
                    combined_df = pd.concat([existing_df, new_row], ignore_index=True)
                    combined_df = combined_df.drop_duplicates(subset=["date"], keep="last")
                    combined_df = combined_df.sort_values("date").reset_index(drop=True)
                else:
                    combined_df = new_row
            except Exception as exc:
                log.warning("Could not read existing parquet for %s: %s", symbol, exc)
                combined_df = new_row
        else:
            combined_df = new_row

        write_symbol_parquet(combined_df, symbol, out_dir)
        results.append({
            "symbol": symbol,
            "status": "ok",
            "close": float(close_price),
            "volume": volume,
            "rows": len(combined_df),
        })

    # Rebuild combined all_symbols.parquet
    frames = {}
    for path in sorted(out_dir.glob("*.parquet")):
        if path.name == "all_symbols.parquet":
            continue
        try:
            frames[path.stem] = pd.read_parquet(path)
        except Exception as exc:
            log.warning("Could not read %s for combined parquet: %s", path.name, exc)

    if frames:
        write_combined_parquet(frames, out_dir)
        try:
            from app.data.features.run_features import run_features
            log.info("Triggering automatic feature generation from freshly updated OHLCV data...")
            run_features()
        except Exception as exc:
            log.warning("Automatic post-scrape feature generation skipped or failed: %s", exc)

    summary = {
        "mode": "redis_after_close",
        "date_range": f"{end} -> {end}",
        "session_date": str(end),
        "total_symbols": len(symbols),
        "materialized_from_database": materialized,
        "ok": sum(result.get("status") == "ok" for result in results),
        "skipped": sum(result.get("status") == "skipped" for result in results),
        "errors": sum(result.get("status") == "error" for result in results),
        "no_data": sum(result.get("status") == "no_data" for result in results),
        "rate_limited": False,
        "results": results,
    }
    _save_fetch_log(out_dir / "logs", summary)
    log.info(
        "After-close Redis OHLCV refresh finished: updated=%d skipped=%d errors=%d no_data=%d",
        summary["ok"],
        summary["skipped"],
        summary["errors"],
        summary["no_data"],
    )
    return summary
