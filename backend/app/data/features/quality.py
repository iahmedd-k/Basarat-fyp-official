"""
Feature Quality Report — validate the feature DataFrame and produce a
comprehensive quality report for downstream consumers.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

from app.data.scraper.symbol_universe import get_active_symbols

log = logging.getLogger(__name__)

EXPECTED_SYMBOL_COUNT = 98


def build_feature_quality_report(
    df: pd.DataFrame,
    label_report: Dict[str, Any],
    output_dir: Optional[Path] = None,
    filename: str = "_feature_quality_report.json",
) -> Dict[str, Any]:
    """Build and save the feature quality report.

    Checks:
    - Exactly 98 unique symbols (error loudly if not)
    - NaN stats before/after drop
    - Macro coverage
    - Per-symbol row counts
    - Any symbols dropped entirely and why
    """
    report: Dict[str, Any] = {
        "total_symbols": int(df["symbol"].nunique()),
        "total_rows_before_nan_drop": len(df),
    }

    # Validate symbol count
    active = get_active_symbols()
    active_syms = set(e["symbol"] for e in active)
    parquet_syms = set(df["symbol"].unique())

    if len(parquet_syms) != EXPECTED_SYMBOL_COUNT:
        log.error(
            "Expected %d symbols but found %d — CHECK INPUT",
            EXPECTED_SYMBOL_COUNT, len(parquet_syms),
        )

    missing = active_syms - parquet_syms
    extra = parquet_syms - active_syms
    report["missing_symbols"] = sorted(missing) if missing else []
    report["extra_symbols"] = sorted(extra) if extra else []

    # NaN stats
    numeric_cols = df.select_dtypes(include="number").columns.tolist()
    nan_before = int(df[numeric_cols].isna().sum().sum()) if numeric_cols else 0
    report["nan_count_before_drop"] = nan_before

    df_dropped = df.dropna(subset=numeric_cols) if numeric_cols else df
    report["total_rows_after_nan_drop"] = len(df_dropped)
    report["rows_dropped_for_nan"] = report["total_rows_before_nan_drop"] - report["total_rows_after_nan_drop"]

    # Macro coverage
    for col in ["pkr_usd_rate", "policy_rate"]:
        if col in df.columns:
            non_null = int(df[col].notna().sum())
            total = len(df)
            report[f"{col}_coverage_pct"] = round(non_null / total * 100, 2) if total > 0 else 0
        else:
            report[f"{col}_coverage_pct"] = 0

    # Per-symbol row counts
    per_sym = df.groupby("symbol").size().to_dict()
    report["per_symbol_row_count"] = {k: int(v) for k, v in per_sym.items()}

    # Symbols with zero rows after dropping (if any dropped entirely)
    symbols_with_rows = set(per_sym.keys())
    dropped_entirely = active_syms - symbols_with_rows
    report["symbols_dropped_entirely"] = sorted(dropped_entirely) if dropped_entirely else []

    # Label report merge
    report["label_report"] = label_report

    # Save
    out_dir = output_dir or Path("data/processed")
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    log.info("Saved feature quality report -> %s", path)

    log.info("=== Feature Quality Report ===")
    log.info("  Symbols: %d", report["total_symbols"])
    log.info("  Total rows: %d", report["total_rows_before_nan_drop"])
    log.info("  Rows after NaN drop: %d", report["total_rows_after_nan_drop"])
    log.info("  Rows dropped for NaN: %d", report["rows_dropped_for_nan"])
    log.info("  PKR/USD coverage: %.1f%%", report.get("pkr_usd_rate_coverage_pct", 0))
    log.info("  Policy rate coverage: %.1f%%", report.get("policy_rate_coverage_pct", 0))

    return report
