"""
Data Quality Checks — run basic sanity checks on fetched OHLCV data
and return a dict of findings to be logged.

Also provides ``clean_bad_rows()`` for dropping rows with invalid prices
or negative volume.
"""

import logging
from datetime import timedelta
from typing import Any, Dict

import pandas as pd

log = logging.getLogger(__name__)


def check_data_quality(df: pd.DataFrame, symbol: str) -> Dict[str, Any]:
    """Run sanity checks on *df* and return a dict of quality metrics.

    Checks performed:
    - row count
    - date range (min / max)
    - number of gaps > 5 consecutive trading days
    - zero or negative price values (open, high, low, close)
    - zero or negative volume values
    - duplicate dates
    """
    result: Dict[str, Any] = {
        "symbol": symbol,
        "row_count": len(df),
        "date_min": None,
        "date_max": None,
        "large_gaps": 0,
        "zero_negative_prices": 0,
        "zero_negative_volume": 0,
        "duplicate_dates": 0,
    }

    if df.empty:
        return result

    df = df.sort_values("date").reset_index(drop=True)

    result["date_min"] = str(df["date"].min().date())
    result["date_max"] = str(df["date"].max().date())

    # Detect large gaps (>5 trading days apart)
    if len(df) >= 2:
        date_diffs = df["date"].diff().dropna()
        large_gap_mask = date_diffs > timedelta(days=7)
        result["large_gaps"] = int(large_gap_mask.sum())

    # Zero / negative prices
    for col in ["open", "high", "low", "close"]:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce")
            result["zero_negative_prices"] += int(((vals <= 0) & vals.notna()).sum())

    # Zero / negative volume
    if "volume" in df.columns:
        vols = pd.to_numeric(df["volume"], errors="coerce")
        result["zero_negative_volume"] = int(((vols <= 0) & vols.notna()).sum())

    # Duplicate dates
    result["duplicate_dates"] = int(df["date"].duplicated().sum())

    if result["large_gaps"] > 0:
        log.warning("  %s: %d large date gap(s) detected", symbol, result["large_gaps"])
    if result["zero_negative_prices"] > 0:
        log.warning("  %s: %d zero/negative price value(s)", symbol, result["zero_negative_prices"])
    if result["zero_negative_volume"] > 0:
        log.warning("  %s: %d zero/negative volume value(s)", symbol, result["zero_negative_volume"])
    if result["duplicate_dates"] > 0:
        log.warning("  %s: %d duplicate date(s)", symbol, result["duplicate_dates"])

    return result


def clean_bad_rows(df: pd.DataFrame, symbol: str) -> pd.DataFrame:
    """Drop rows with invalid prices or negative volume.

    Rules (applied uniformly):
    - If close <= 0 OR high <= 0 OR low <= 0 OR open <= 0: drop the row
      (invalid price data, not usable for training).
    - If volume < 0: drop the row (data error).
    - If volume == 0 but prices are valid: KEEP the row
      (zero volume on a valid trading day is legitimate for thin/illiquid stocks).

    Returns the cleaned DataFrame and logs the number of rows dropped.
    """
    if df.empty:
        return df

    before = len(df)

    price_cols = ["open", "high", "low", "close"]
    bad_mask = pd.Series(False, index=df.index)

    for col in price_cols:
        if col in df.columns:
            vals = pd.to_numeric(df[col], errors="coerce")
            bad_mask |= (vals <= 0) & vals.notna()

    if "volume" in df.columns:
        vols = pd.to_numeric(df["volume"], errors="coerce")
        bad_mask |= (vols < 0) & vols.notna()

    cleaned = df[~bad_mask].copy()
    after = len(cleaned)
    dropped = before - after

    if dropped > 0:
        log.info("  %s: dropped %d rows with invalid prices/negative volume (%d -> %d)", symbol, dropped, before, after)

    return cleaned
