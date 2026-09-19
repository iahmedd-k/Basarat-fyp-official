"""
Labeling — assign directional labels based on 1-day forward return.

Labels:
    bullish  — forward_return > threshold
    bearish  — forward_return < -threshold
    sideways — otherwise (abs return <= threshold)

The threshold is configurable (default 0.01 = 1%).
Rows with missing forward_return (e.g. last row per symbol, data gaps) are
explicitly dropped before labeling.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.01

LABEL_MAPPING = {"bullish": 0, "bearish": 1, "sideways": 2}


def label_from_return(future_return: float, threshold: float = DEFAULT_THRESHOLD) -> str:
    """Map a future return to a directional label.

    Parameters
    ----------
    future_return : float
        The forward return (e.g. close[t+1]/close[t] - 1).
    threshold : float
        Symmetric dead-zone half-width.  Values above +threshold are
        bullish, below -threshold are bearish, everything else sideways.

    Returns
    -------
    str : "bullish", "bearish", or "sideways"

    Raises
    ------
    ValueError
        If future_return is NaN.  Missing forward returns should be dropped
        before calling this function.
    """
    if pd.isna(future_return):
        raise ValueError("future_return is NaN; missing forward returns must be dropped before labeling")
    if future_return > threshold:
        return "bullish"
    elif future_return < -threshold:
        return "bearish"
    return "sideways"


def assign_labels(
    df: pd.DataFrame,
    threshold: float = DEFAULT_THRESHOLD,
) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Add forward_return and label columns to *df*.

    Returns (df_with_labels, quality_report) where quality_report contains
    class distributions overall and per symbol.
    """
    if df.empty:
        return df, {}

    df = df.copy()
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Forward return = (close[t+1] - close[t]) / close[t]
    df["forward_return"] = df.groupby("symbol")["close"].transform(
        lambda s: s.shift(-1) / s - 1
    )

    # Drop rows with missing forward_return (last row per symbol, or any gaps)
    before = len(df)
    df = df.dropna(subset=["forward_return"])
    after = len(df)
    log.info("Dropped %d rows with missing forward_return (%d -> %d)", before - after, before, after)

    # Explicit assertion: never proceed with NaN forward returns
    if df["forward_return"].isna().any():
        raise AssertionError("forward_return contains NaN values after dropna; missing targets must be eliminated")

    # Assign label using the canonical function
    df["label"] = df["forward_return"].apply(lambda r: label_from_return(r, threshold))

    # Explicit assertion: every remaining row must have a valid label
    if df["label"].isna().any():
        raise AssertionError("label column contains NaN values; all samples must have a valid class label")

    # Build quality report
    report: Dict[str, Any] = {
        "threshold": threshold,
        "label_mapping": LABEL_MAPPING,
        "total_rows": len(df),
        "overall_distribution": {},
        "per_symbol_distribution": {},
        "per_symbol_row_count": {},
    }

    # Overall distribution
    dist = df["label"].value_counts()
    for label_name in LABEL_MAPPING:
        count = int(dist.get(label_name, 0))
        report["overall_distribution"][label_name] = {
            "count": count,
            "pct": round(count / len(df) * 100, 2) if len(df) > 0 else 0,
        }

    # Per symbol
    for sym, grp in df.groupby("symbol"):
        sym_dist = grp["label"].value_counts()
        report["per_symbol_row_count"][sym] = len(grp)
        report["per_symbol_distribution"][sym] = {}
        for label_name in LABEL_MAPPING:
            count = int(sym_dist.get(label_name, 0))
            report["per_symbol_distribution"][sym][label_name] = {
                "count": count,
                "pct": round(count / len(grp) * 100, 2) if len(grp) > 0 else 0,
            }

    log.info("Label distribution (threshold=%.3f):", threshold)
    for label_name, info in report["overall_distribution"].items():
        log.info("  %s: %d (%.1f%%)", label_name, info["count"], info["pct"])

    return df, report


def save_label_mapping(
    output_dir: Optional[Path] = None,
    filename: str = "label_mapping.json",
) -> Path:
    """Write label_mapping.json to disk."""
    out_dir = output_dir or Path("data/features")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(json.dumps(LABEL_MAPPING, indent=2), encoding="utf-8")
    log.info("Saved label mapping -> %s", path)
    return path
