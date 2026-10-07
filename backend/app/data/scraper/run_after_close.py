"""Paced daily OHLCV refresh using the existing per-symbol scraper."""

import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from app.data.scraper.ohlcv import psx_access_denied, reset_psx_access_denied
from app.data.scraper.run_scrape import (
    _DEFAULT_OUTPUT_DIR,
    _save_fetch_log,
    _scrape_symbol,
)
from app.data.scraper.symbol_universe import get_active_symbols
from app.data.scraper.writers import write_combined_parquet

log = logging.getLogger(__name__)

_BATCH_SIZE = 10
_BATCH_PAUSE_SECONDS = 150
_PKT = ZoneInfo("Asia/Karachi")


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
    symbols = [entry["symbol"] for entry in get_active_symbols()]
    if not symbols:
        raise RuntimeError("No active KSE-100 symbols are configured for OHLCV refresh")
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

    log.info("Starting paced after-close OHLCV refresh for %d symbols", len(symbols))
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
