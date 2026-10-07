"""Paced daily OHLCV refresh using the existing per-symbol scraper."""

import logging
import re
import time
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
    _scrape_symbol,
)
from app.models.stock import Stock, StockPrice

log = logging.getLogger(__name__)

_BATCH_SIZE = 50
_BATCH_PAUSE_SECONDS = 15
_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{1,20}$")
_PKT = ZoneInfo("Asia/Karachi")


def get_refresh_symbols(output_dir: Path | None = None) -> list[str]:
    """Return the union of registered stocks, quotes, and existing OHLCV tickers."""
    output_dir = output_dir or _DEFAULT_OUTPUT_DIR
    symbols: set[str] = set()

    session_factory = get_sync_session_factory()
    with session_factory() as session:
        registered = session.scalars(
            select(Stock.symbol).where(Stock.is_active.is_(True))
        ).all()
        symbols.update(str(symbol).strip().upper() for symbol in registered)

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
    """Refresh current-session closes, pausing after each batch of symbols."""
    if batch_size < 1:
        raise ValueError("batch_size must be at least 1")
    if pause_seconds < 0:
        raise ValueError("pause_seconds cannot be negative")

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
    start = end - timedelta(days=5 * 365)
    results = []
    reset_psx_access_denied()

    log.info(
        "Starting paced after-close OHLCV refresh for %d symbols (%d database histories materialized)",
        len(symbols),
        materialized,
    )
    for index, symbol in enumerate(symbols, start=1):
        if psx_access_denied():
            log.error("Stopping OHLCV refresh after PSX HTTP 403/429")
            results.extend(
                {
                    "symbol": pending,
                    "status": "skipped",
                    "reason": "source_rate_limited",
                }
                for pending in symbols[index - 1 :]
            )
            break

        result = _scrape_symbol(
            symbol=symbol,
            start=start,
            end=end,
            output_dir=out_dir,
            incremental=True,
            delay=0,
            initial_lookback_days=365,
        )
        results.append(result)
        if index % batch_size == 0 and index < len(symbols) and not psx_access_denied():
            log.info(
                "Completed %d/%d symbols; pausing %.0f seconds",
                index,
                len(symbols),
                pause_seconds,
            )
            time.sleep(pause_seconds)

    # Rebuild the combined model-input file from all per-symbol files, including
    # symbols skipped because they already had a current-session record.
    frames = {}
    for path in sorted(out_dir.glob("*.parquet")):
        if path.name == "all_symbols.parquet":
            continue
        frames[path.stem] = pd.read_parquet(path)
    if frames:
        write_combined_parquet(frames, out_dir)
        try:
            from app.data.features.run_features import run_features
            log.info("Triggering automatic feature generation from freshly scraped OHLCV data...")
            run_features()
        except Exception as exc:
            log.warning("Automatic post-scrape feature generation skipped or failed: %s", exc)

    summary = {
        "mode": "incremental_after_close",
        "date_range": f"{start} -> {end}",
        "total_symbols": len(symbols),
        "materialized_from_database": materialized,
        "ok": sum(result.get("status") == "ok" for result in results),
        "skipped": sum(result.get("status") == "skipped" for result in results),
        "errors": sum(result.get("status") == "error" for result in results),
        "no_data": sum(result.get("status") == "no_data" for result in results),
        "rate_limited": psx_access_denied(),
        "results": results,
    }
    _save_fetch_log(out_dir / "logs", summary)
    log.info(
        "After-close OHLCV refresh finished: updated=%d skipped=%d errors=%d no_data=%d",
        summary["ok"],
        summary["skipped"],
        summary["errors"],
        summary["no_data"],
    )
    return summary
