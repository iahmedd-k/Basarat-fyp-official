"""Backfill missing daily OHLCV rows with real PSX closing prices.

Fetches actual historical prices from PSX (dps.psx.com.pk) for symbols whose
parquet files end before the target end date, merges the new rows into the
per-symbol files, and can rebuild the combined file and feature store.

Usage::

    # Pilot: backfill only 4 stale symbols and verify
    python scripts/backfill_missing_ohlcv.py --end 2026-10-06 --limit 4

    # Specific symbols
    python scripts/backfill_missing_ohlcv.py --end 2026-10-06 --symbols 786,AABS,AAL

    # Everything that is stale, then rebuild combined + features
    python scripts/backfill_missing_ohlcv.py --end 2026-10-06 --rebuild --features
"""

import argparse
import logging
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from app.data.scraper.ohlcv import fetch_ohlcv, psx_access_denied, reset_psx_access_denied
from app.data.scraper.symbol_universe import get_active_symbols
from app.data.scraper.writers import write_combined_parquet, write_symbol_parquet

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("backfill_ohlcv")

OHLCV_DIR = Path("data/raw/ohlcv")
EXPECTED_COLUMNS = {"date", "open", "high", "low", "close", "volume"}
_PKT = ZoneInfo("Asia/Karachi")


def _last_date(path: Path) -> date | None:
    if not path.exists():
        return None
    try:
        frame = pd.read_parquet(path)
        if frame.empty or "date" not in frame.columns:
            return None
        last = pd.to_datetime(frame["date"]).max()
        return last.date() if hasattr(last, "date") else last
    except Exception as exc:
        log.warning("Could not read %s: %s", path, exc)
        return None


def _weekday_dates(start: date, end: date) -> list[date]:
    days = []
    cur = start
    while cur <= end:
        if cur.weekday() < 5:
            days.append(cur)
        cur += timedelta(days=1)
    return days


def _verify_merge(before: pd.DataFrame, after: pd.DataFrame, start: date, end: date) -> list[str]:
    """Return a list of human-readable verification findings for one symbol."""
    issues: list[str] = []
    added = after[after["date"] > pd.Timestamp(before["date"].max())]
    added_dates = {d.date() for d in added["date"]}

    expected = [d for d in _weekday_dates(start, end) if d > before["date"].max().date()]
    missing = [d for d in expected if d not in added_dates]
    if missing:
        issues.append(f"missing weekday(s): {[str(d) for d in missing]} (likely PSX holiday)")

    if not EXPECTED_COLUMNS.issubset(after.columns):
        issues.append(f"missing columns: {EXPECTED_COLUMNS - set(after.columns)}")

    if (after["close"] <= 0).any():
        issues.append("non-positive close value")
    if (after["high"] < after[["open", "close"]].max(axis=1)).any():
        issues.append("high below open/close")
    if (after["low"] > after[["open", "close"]].min(axis=1)).any():
        issues.append("low above open/close")
    if (after["volume"] < 0).any():
        issues.append("negative volume")

    recent = after.tail(12)
    day_changes = recent["close"].pct_change().abs().dropna()
    big = day_changes[day_changes > 0.20]
    if not big.empty:
        issues.append(f"day-over-day jump > 20% on {len(big)} row(s)")

    return issues


def backfill(
    end: date,
    start: date | None,
    symbols: list[str] | None,
    limit: int | None,
    delay: float,
) -> dict:
    paths = sorted(p for p in OHLCV_DIR.glob("*.parquet") if p.name != "all_symbols.parquet")
    if symbols:
        wanted = set(symbols)
        paths = [p for p in paths if p.stem in wanted]
        missing = wanted - {p.stem for p in paths}
        if missing:
            log.warning("No parquet file for: %s", ", ".join(sorted(missing)))

    stale = []
    for path in paths:
        last = _last_date(path)
        if last is None:
            log.warning("Unreadable or empty: %s", path.name)
            continue
        if last < end:
            stale.append((path, last))

    stale.sort(key=lambda item: item[1])
    if limit:
        stale = stale[:limit]

    log.info("Target end date: %s | stale symbols to backfill: %d", end, len(stale))
    reset_psx_access_denied()

    results = []
    for index, (path, last) in enumerate(stale, start=1):
        symbol = path.stem
        if psx_access_denied():
            log.error("PSX rate-limited the run; stopping after %d/%d symbols", index - 1, len(stale))
            for pending_path, pending_last in stale[index - 1 :]:
                results.append({"symbol": pending_path.stem, "status": "skipped", "reason": "source_rate_limited", "last_before": str(pending_last)})
            break

        fetch_start = start or (last + timedelta(days=1))
        if fetch_start > end:
            results.append({"symbol": symbol, "status": "skipped", "reason": "up_to_date", "last_before": str(last)})
            continue

        try:
            fresh = fetch_ohlcv(symbol, start=fetch_start, end=end)
        except Exception as exc:
            log.error("[%d/%d] %s: fetch failed — %s", index, len(stale), symbol, exc)
            results.append({"symbol": symbol, "status": "error", "error": str(exc)})
            continue

        if psx_access_denied():
            results.append({"symbol": symbol, "status": "error", "error": "psx_rate_limited"})
            break

        if fresh.empty:
            log.info("[%d/%d] %s: no data returned (%s -> %s)", index, len(stale), symbol, fetch_start, end)
            results.append({"symbol": symbol, "status": "no_data", "last_before": str(last)})
            time.sleep(delay)
            continue

        existing = pd.read_parquet(path)
        existing["date"] = pd.to_datetime(existing["date"])
        fresh["date"] = pd.to_datetime(fresh["date"])

        before_len = len(existing)
        merged = pd.concat([existing, fresh], ignore_index=True)
        merged = merged.drop_duplicates(subset=["date"], keep="last")
        merged = merged.sort_values("date").reset_index(drop=True)

        issues = _verify_merge(existing, merged, fetch_start, end)
        write_symbol_parquet(merged, symbol, OHLCV_DIR)

        added = len(merged) - before_len
        new_last = merged["date"].max().date()
        status = "ok" if not issues else "ok_with_warnings"
        log.info(
            "[%d/%d] %s: +%d rows, %s -> %s%s",
            index, len(stale), symbol, added, last, new_last,
            f" | {'; '.join(issues)}" if issues else "",
        )
        results.append(
            {
                "symbol": symbol,
                "status": status,
                "added_rows": added,
                "last_before": str(last),
                "last_after": str(new_last),
                "issues": issues,
            }
        )
        time.sleep(delay)

    summary = {
        "end": str(end),
        "stale_targets": len(stale),
        "ok": sum(r["status"].startswith("ok") for r in results),
        "warnings": sum(r["status"] == "ok_with_warnings" for r in results),
        "errors": sum(r["status"] == "error" for r in results),
        "no_data": sum(r["status"] == "no_data" for r in results),
        "skipped": sum(r["status"] == "skipped" for r in results),
        "rate_limited": psx_access_denied(),
        "results": results,
    }
    return summary


def rebuild_combined_and_features(features: bool) -> None:
    frames = {}
    for path in sorted(OHLCV_DIR.glob("*.parquet")):
        if path.name == "all_symbols.parquet":
            continue
        frames[path.stem] = pd.read_parquet(path)
    if frames:
        write_combined_parquet(frames, OHLCV_DIR)
        log.info("Rebuilt all_symbols.parquet from %d symbols", len(frames))

    if features:
        from app.data.features.run_features import run_features

        log.info("Running feature engineering pipeline...")
        run_features()
        log.info("Feature generation complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill missing OHLCV rows with real PSX closes.")
    parser.add_argument("--end", type=lambda s: date.fromisoformat(s), default=None,
                        help="Target last trading date YYYY-MM-DD (default: yesterday, Asia/Karachi).")
    parser.add_argument("--start", type=lambda s: date.fromisoformat(s), default=None,
                        help="Earliest date to fetch. Default: each symbol's last date + 1 day.")
    parser.add_argument("--symbols", type=str, default=None,
                        help="Comma-separated symbol list (default: all stale parquet files).")
    parser.add_argument("--limit", type=int, default=None, help="Only process the N most stale symbols.")
    parser.add_argument("--delay", type=float, default=2.0, help="Seconds between symbols (default 2.0).")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild all_symbols.parquet afterwards.")
    parser.add_argument("--features", action="store_true", help="Run feature generation after rebuild.")
    args = parser.parse_args()

    end = args.end or (datetime_now_pkt() - timedelta(days=1))
    if end.weekday() >= 5:
        log.warning("End date %s is a weekend; PSX has no session.", end)

    symbols = [s.strip().upper() for s in args.symbols.split(",")] if args.symbols else None
    summary = backfill(end, args.start, symbols, args.limit, args.delay)

    log.info(
        "Backfill finished: ok=%d warnings=%d errors=%d no_data=%d skipped=%d rate_limited=%s",
        summary["ok"], summary["warnings"], summary["errors"],
        summary["no_data"], summary["skipped"], summary["rate_limited"],
    )
    for result in summary["results"]:
        if result["status"] not in {"ok"}:
            log.info("  %s: %s", result["symbol"], result)

    if args.rebuild or args.features:
        rebuild_combined_and_features(args.features)

    if summary["errors"] or summary["no_data"] or summary["rate_limited"]:
        sys.exit(1)


def datetime_now_pkt() -> date:
    from datetime import datetime

    return datetime.now(_PKT).date()


if __name__ == "__main__":
    main()
