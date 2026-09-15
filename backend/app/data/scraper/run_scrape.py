"""
PSX Historical OHLCV Scraper — CLI Entrypoint
==============================================

Usage::

    # Full 5-year pull (default)
    python -m app.data.scraper.run_scrape --mode full

    # Incremental: append only new days since last fetch
    python -m app.data.scraper.run_scrape --mode incremental

    # Freeze / refresh the symbol universe (periodic manual step)
    python -m app.data.scraper.run_scrape --freeze-universe

    # Custom date range
    python -m app.data.scraper.run_scrape --mode full --start 2023-01-01 --end 2024-12-31
"""

import argparse
import json
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from app.data.scraper.ohlcv import fetch_ohlcv
from app.data.scraper.quality import check_data_quality
from app.data.scraper.symbol_universe import (
    fetch_symbol_universe,
    freeze_universe,
    load_frozen_universe,
)
from app.data.scraper.writers import write_combined_parquet, write_symbol_parquet

log = logging.getLogger("psx_scraper")

_DEFAULT_OUTPUT_DIR = Path("data/raw/ohlcv")
_DEFAULT_LOG_DIR = Path("data/raw/ohlcv")


# ---------------------------------------------------------------------------
# Fetch log helpers
# ---------------------------------------------------------------------------

def _load_fetch_log(log_dir: Path) -> dict:
    path = log_dir / "_fetch_log.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"runs": []}


def _save_fetch_log(log_dir: Path, entry: dict) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "_fetch_log.json"
    existing = _load_fetch_log(log_dir)
    existing["runs"].append(entry)
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


def _append_symbol_error(log_dir: Path, symbol: str, error: str) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "_fetch_log.json"
    existing = _load_fetch_log(log_dir)
    if "symbol_errors" not in existing:
        existing["symbol_errors"] = []
    existing["symbol_errors"].append({
        "symbol": symbol,
        "error": error,
        "timestamp": date.today().isoformat(),
    })
    path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Incremental helpers
# ---------------------------------------------------------------------------

def _load_existing_last_date(symbol: str, output_dir: Path) -> date | None:
    """Return the max date in an existing parquet file, or None."""
    path = output_dir / f"{symbol}.parquet"
    if not path.exists():
        return None
    try:
        existing = pd.read_parquet(path)
        if existing.empty or "date" not in existing.columns:
            return None
        last = pd.to_datetime(existing["date"]).max()
        return last.date() if hasattr(last, "date") else last
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Core scrape logic
# ---------------------------------------------------------------------------

def _scrape_symbol(
    symbol: str,
    start: date,
    end: date,
    output_dir: Path,
    incremental: bool,
    delay: float,
) -> dict:
    """Fetch + write one symbol. Returns a quality-check dict."""
    actual_start = start

    if incremental:
        last_date = _load_existing_last_date(symbol, output_dir)
        if last_date is not None:
            # Start from the day after the last available date
            actual_start = last_date + timedelta(days=1)
            if actual_start > end:
                log.info("  %s: already up to date (last=%s), skipping", symbol, last_date)
                return {"symbol": symbol, "status": "skipped", "reason": "up_to_date"}

    try:
        df = fetch_ohlcv(symbol, start=actual_start, end=end)
    except Exception as exc:
        log.error("  %s: fetch failed — %s", symbol, exc)
        _append_symbol_error(output_dir, symbol, str(exc))
        return {"symbol": symbol, "status": "error", "error": str(exc)}

    if df.empty:
        log.info("  %s: no data returned", symbol)
        return {"symbol": symbol, "status": "no_data"}

    # If incremental, merge with existing data
    if incremental:
        existing_path = output_dir / f"{symbol}.parquet"
        if existing_path.exists():
            try:
                existing = pd.read_parquet(existing_path)
                df = pd.concat([existing, df], ignore_index=True)
                # Deduplicate on date (keep the latest row for each date)
                df = df.drop_duplicates(subset=["date"], keep="last")
                df = df.sort_values("date").reset_index(drop=True)
            except Exception as exc:
                log.warning("  %s: could not merge with existing data — %s", symbol, exc)

    # Validate columns
    expected = {"date", "open", "high", "low", "close", "volume"}
    actual = set(df.columns)
    if not expected.issubset(actual):
        log.warning("  %s: missing columns %s (got %s)", symbol, expected - actual, actual)

    # Quality checks
    quality = check_data_quality(df, symbol)
    quality["status"] = "ok"

    # Write per-symbol parquet
    write_symbol_parquet(df, symbol, output_dir)

    time.sleep(delay)
    return quality


def run_scrape(
    mode: str = "full",
    start: date | None = None,
    end: date | None = None,
    output_dir: Path | None = None,
    delay: float = 0.5,
    freeze: bool = False,
    config_dir: Path | None = None,
) -> None:
    """Main scrape orchestrator."""
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Optionally freeze universe
    if freeze:
        log.info("=== Freezing symbol universe ===")
        universe = fetch_symbol_universe(config_dir)
        freeze_universe(universe, config_dir)
        log.info("Universe frozen. Done.")
        if not start and not end and mode == "full":
            # If only --freeze-universe was requested, exit after freezing
            return

    # Step 2: Load frozen universe
    log.info("=== Loading frozen symbol universe ===")
    try:
        universe = load_frozen_universe(config_dir)
    except FileNotFoundError as exc:
        log.error(str(exc))
        log.error("Run with --freeze-universe first to generate the symbol list.")
        sys.exit(1)

    symbols = [entry["symbol"] for entry in universe]
    log.info("Universe: %d symbols", len(symbols))

    # Step 3: Determine date range
    if end is None:
        end = date.today()
    if start is None:
        if mode == "incremental":
            # For incremental, we'll figure out per-symbol start below
            start = date(2000, 1, 1)  # fallback; overridden per symbol
        else:
            start = end - timedelta(days=5 * 365)

    log.info("Mode: %s | Range: %s -> %s", mode, start, end)

    # Step 4: Fetch each symbol
    results = []
    all_frames: dict[str, pd.DataFrame] = {}
    total = len(symbols)

    log.info("=== Starting OHLCV fetch for %d symbols ===", total)
    for i, symbol in enumerate(symbols, 1):
        log.info("[%d/%d] %s", i, total, symbol)
        result = _scrape_symbol(
            symbol=symbol,
            start=start,
            end=end,
            output_dir=out_dir,
            incremental=(mode == "incremental"),
            delay=delay,
        )
        results.append(result)

        # Accumulate for combined file (only if we actually fetched data)
        if result.get("status") == "ok":
            try:
                path = out_dir / f"{symbol}.parquet"
                if path.exists():
                    all_frames[symbol] = pd.read_parquet(path)
            except Exception:
                pass

    # Step 5: Write combined parquet
    if all_frames:
        log.info("=== Writing combined parquet ===")
        write_combined_parquet(all_frames, out_dir)

    # Step 6: Summary
    ok_count = sum(1 for r in results if r.get("status") == "ok")
    skip_count = sum(1 for r in results if r.get("status") == "skipped")
    err_count = sum(1 for r in results if r.get("status") == "error")
    no_data_count = sum(1 for r in results if r.get("status") == "no_data")

    summary = {
        "mode": mode,
        "date_range": f"{start} -> {end}",
        "total_symbols": total,
        "ok": ok_count,
        "skipped": skip_count,
        "errors": err_count,
        "no_data": no_data_count,
        "results": results,
    }

    log.info("=== Scrape Complete ===")
    log.info("  OK: %d | Skipped: %d | Errors: %d | No data: %d", ok_count, skip_count, err_count, no_data_count)

    # Save run log
    _save_fetch_log(out_dir, summary)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_scrape",
        description="Fetch PSX historical OHLCV data for the frozen symbol universe.",
    )
    parser.add_argument(
        "--mode",
        choices=["full", "incremental"],
        default="full",
        help=(
            "full = fetch 5 years of history (default).  "
            "incremental = append only new days since last fetch."
        ),
    )
    parser.add_argument(
        "--start",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="Start date (YYYY-MM-DD). Default: today - 5 years (full) or per-symbol last date (incremental).",
    )
    parser.add_argument(
        "--end",
        type=lambda s: date.fromisoformat(s),
        default=None,
        help="End date (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=_DEFAULT_OUTPUT_DIR,
        help=f"Output directory for parquet files. Default: {_DEFAULT_OUTPUT_DIR}",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.5,
        help="Seconds to sleep between symbol requests (default: 0.5).",
    )
    parser.add_argument(
        "--freeze-universe",
        action="store_true",
        help="Re-fetch index constituents and freeze the symbol universe before scraping.",
    )
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=None,
        help="Directory for symbol_universe.json. Default: data/config/",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    run_scrape(
        mode=args.mode,
        start=args.start,
        end=args.end,
        output_dir=args.output_dir,
        delay=args.delay,
        freeze=args.freeze_universe,
        config_dir=args.config_dir,
    )


if __name__ == "__main__":
    main()
