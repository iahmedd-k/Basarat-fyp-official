"""
Macro Features — join PKR/USD and SBP policy rate onto the daily OHLCV timeline.

Uses ``pandas.merge_asof`` (forward-fill) per-symbol so each symbol's daily
timeline gets the most recent known macro value.  Missing coverage is filled
with NaN and logged.

IMPORTANT: merge_asof is always scoped to a single symbol at a time to avoid
silent row duplication / incorrect matches on multi-symbol data.
"""

import logging
import warnings
from pathlib import Path
from typing import Optional

import pandas as pd

log = logging.getLogger(__name__)

_MACRO_DIR = Path("data/config/macro")


def _load_pkr_usd(macro_dir: Optional[Path] = None) -> pd.DataFrame:
    path = (macro_dir or _MACRO_DIR) / "pkr_usd.csv"
    if not path.exists():
        log.warning("PKR/USD file not found at %s — macro features will have NaN for pkr_usd_rate", path)
        return pd.DataFrame(columns=["date", "pkr_usd_rate"])
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.rename(columns={"rate": "pkr_usd_rate"})
    return df.sort_values("date").reset_index(drop=True)


def _load_sbp_rate(macro_dir: Optional[Path] = None) -> pd.DataFrame:
    path = (macro_dir or _MACRO_DIR) / "sbp_rate.csv"
    if not path.exists():
        log.warning("SBP rate file not found at %s — macro features will have NaN for policy_rate", path)
        return pd.DataFrame(columns=["date", "policy_rate"])
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["effective_date"])
    df = df.drop(columns=["effective_date"])
    return df.sort_values("date").reset_index(drop=True)


def _log_coverage(df: pd.DataFrame, col: str, name: str) -> None:
    """Log macro coverage stats for a given column."""
    total = len(df)
    non_null = df[col].notna().sum()
    pct = non_null / total * 100 if total > 0 else 0
    log.info("  %s: %d/%d rows have data (%.1f%%)", name, non_null, total, pct)
    if non_null == 0:
        log.warning("  %s: NO coverage — all NaN", name)
    elif pct < 50:
        log.warning("  %s: LOW coverage — only %.1f%%", name, pct)


def join_macro_features(
    ohlcv_df: pd.DataFrame,
    macro_dir: Optional[Path] = None,
) -> pd.DataFrame:
    """Merge macro features onto the OHLCV DataFrame using forward-fill asof join.

    Adds columns: pkr_usd_rate, policy_rate.

    merge_asof is applied per-symbol to prevent silent row duplication.
    """
    if ohlcv_df.empty:
        return ohlcv_df

    df = ohlcv_df.copy()
    df["date"] = pd.to_datetime(df["date"])

    # Load macro data once (date-level, not symbol-level)
    pkr = _load_pkr_usd(macro_dir)
    sbp = _load_sbp_rate(macro_dir)

    # Coverage check against the full OHLCV date range
    ohlcv_min = df["date"].min()
    ohlcv_max = df["date"].max()
    if not pkr.empty:
        pkr_min, pkr_max = pkr["date"].min(), pkr["date"].max()
        if pkr_min > ohlcv_min:
            log.warning("PKR/USD missing for %s to %s (before first available rate)",
                        ohlcv_min.date(), (pkr_min - pd.Timedelta(days=1)).date())
        if pkr_max < ohlcv_max:
            log.warning("PKR/USD missing for %s to %s (after last available rate)",
                        (pkr_max + pd.Timedelta(days=1)).date(), ohlcv_max.date())

    # Build a date-level lookup via merge_asof on the unique-date timeline,
    # then left-join back. This avoids running merge_asof on multi-symbol data.
    all_dates = df[["date"]].drop_duplicates().sort_values("date").reset_index(drop=True)

    # Note on publication timing (Task 9):
    # Daily interbank FX rates and monetary policy announcements published after
    # market close on date t must not leak into trading day t if predicting before close.
    # merge_asof with direction="backward" ensures each trading day t matches the latest
    # officially published macro record with publication date <= date t.
    if not pkr.empty:
        all_dates = pd.merge_asof(all_dates, pkr, on="date", direction="backward")
        _log_coverage(all_dates, "pkr_usd_rate", "PKR/USD")
    else:
        all_dates["pkr_usd_rate"] = float("nan")

    if not sbp.empty:
        all_dates = pd.merge_asof(all_dates, sbp, on="date", direction="backward")
        _log_coverage(all_dates, "policy_rate", "SBP Policy Rate")
    else:
        all_dates["policy_rate"] = float("nan")

    # Verify no duplicates in the date-level lookup (would indicate a bug)
    assert not all_dates["date"].duplicated().any(), (
        "BUG: all_dates has duplicate dates after merge_asof — this would "
        "cause row multiplication in the final join"
    )

    # Left-join back onto the multi-symbol dataframe (many-to-one on date)
    df = pd.merge(df, all_dates, on="date", how="left", suffixes=("", "_macro"))
    for col in list(df.columns):
        if col.endswith("_macro"):
            df = df.drop(columns=[col])

    # Final safety check
    dupes = df.duplicated(subset=["symbol", "date"]).sum()
    assert dupes == 0, f"BUG: {dupes} duplicate (symbol, date) pairs after macro join"

    return df
