"""
Labeling — assign directional labels based on 1-day forward return.

Labels:
    bullish  — forward_return > threshold
    bearish  — forward_return < -threshold
    sideways — otherwise (abs return <= threshold)

The threshold is configurable (default 0.01 = 1%).
Last row per symbol is dropped (no forward return available).
"""

import json
import logging
import warnings
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

log = logging.getLogger(__name__)

DEFAULT_THRESHOLD = 0.01

LABEL_MAPPING = {"bullish": 0, "bearish": 1, "sideways": 2}


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

    # Assign label
    def _label(ret: float) -> str:
        if pd.isna(ret):
            return "sideways"
        if ret > threshold:
            return "bullish"
        elif ret < -threshold:
            return "bearish"
        return "sideways"

    df["label"] = df["forward_return"].apply(_label)

    # Drop last row per symbol (no forward return)
    before = len(df)
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=FutureWarning)
        df = df.groupby("symbol", group_keys=False).apply(
            lambda g: g.iloc[:-1] if len(g) > 1 else g
        )
    after = len(df)
    log.info("Dropped %d last-row-per-symbol rows (%d -> %d)", before - after, before, after)

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
    out_dir = output_dir or Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(json.dumps(LABEL_MAPPING, indent=2), encoding="utf-8")
    log.info("Saved label mapping -> %s", path)
    return path
