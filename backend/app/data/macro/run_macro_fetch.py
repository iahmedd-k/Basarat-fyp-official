"""
PKR/USD Macro Fetch — CLI Entrypoint
=====================================

Usage::

    # Full fetch (default: 2019-01-01 to today)
    python -m app.data.macro.run_macro_fetch --mode full

    # Incremental: fetch only from last saved date to today
    python -m app.data.macro.run_macro_fetch --mode incremental

    # Custom date range
    python -m app.data.macro.run_macro_fetch --mode full --start 2020-01-01 --end 2024-12-31
"""

import argparse
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from app.data.macro.fx_fetcher import (
    fetch_pkr_usd,
    load_existing_rates,
    save_fetch_log,
    save_rates,
)

log = logging.getLogger("macro_fetch")

_DEFAULT_START = date(2019, 1, 1)


def run_macro_fetch(
    mode: str = "full",
    start: date | None = None,
    end: date | None = None,
    output_dir: Path | None = None,
) -> None:
    """Main macro fetch orchestrator."""
    today = date.today()

    if end is None:
        end = today

    if mode == "incremental":
        existing = load_existing_rates(output_dir)
        if not existing.empty:
            last_date = existing["date"].max().date()
            start = last_date + timedelta(days=1)
            if start > end:
                log.info("Already up to date (last=%s), nothing to fetch", last_date)
                save_fetch_log({
                    "mode": mode,
                    "date_range": f"{last_date} -> {end}",
                    "rows_fetched": 0,
                    "status": "up_to_date",
                }, output_dir)
                return
        else:
            start = _DEFAULT_START
    else:
        if start is None:
            start = _DEFAULT_START

    log.info("Mode: %s | Range: %s -> %s", mode, start, end)

    # Fetch new data
    new_data = fetch_pkr_usd(start, end)

    if new_data.empty:
        log.warning("No data fetched")
        save_fetch_log({
            "mode": mode,
            "date_range": f"{start} -> {end}",
            "rows_fetched": 0,
            "status": "no_data",
        }, output_dir)
        return

    # Merge with existing if incremental
    if mode == "incremental":
        existing = load_existing_rates(output_dir)
        if not existing.empty:
            combined = pd.concat([existing, new_data], ignore_index=True)
            combined = combined.drop_duplicates(subset=["date"], keep="last")
            combined = combined.sort_values("date").reset_index(drop=True)
            new_data = combined

    # Save
    save_rates(new_data, output_dir)

    # Log
    entry = {
        "mode": mode,
        "date_range": f"{start} -> {end}",
        "rows_fetched": len(new_data),
        "date_min": str(new_data["date"].min().date()),
        "date_max": str(new_data["date"].max().date()),
        "status": "ok",
    }
    save_fetch_log(entry, output_dir)
    log.info("Done. %d total rates saved.", len(new_data))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_macro_fetch",
        description="Fetch PKR/USD exchange rates from Frankfurter API (SBP provider).",
    )
    parser.add_argument(
        "--mode", choices=["full", "incremental"], default="full",
        help="full = fetch from 2019-01-01. incremental = append from last saved date.",
    )
    parser.add_argument(
        "--start", type=lambda s: date.fromisoformat(s), default=None,
        help="Start date (YYYY-MM-DD). Default: 2019-01-01 (full) or last saved date (incremental).",
    )
    parser.add_argument(
        "--end", type=lambda s: date.fromisoformat(s), default=None,
        help="End date (YYYY-MM-DD). Default: today.",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=None,
        help="Output directory. Default: data/config/macro/",
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

    run_macro_fetch(
        mode=args.mode,
        start=args.start,
        end=args.end,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
