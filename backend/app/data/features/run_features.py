"""
Feature Pipeline — CLI Entrypoint
==================================

Usage::

    python -m app.data.features.run_features
    python -m app.data.features.run_features --window-size 60 --label-threshold 0.015
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from app.data.features.labeling import (
    DEFAULT_THRESHOLD,
    assign_labels,
    save_label_mapping,
)
from app.data.features.macro_features import join_macro_features
from app.data.features.quality import build_feature_quality_report
from app.data.features.sequence_builder import (
    DEFAULT_WINDOW_SIZE,
    build_sequences,
    save_sequences,
)
from app.data.features.technical_indicators import compute_technical_indicators
from app.data.scraper.symbol_universe import get_active_symbols

log = logging.getLogger("features")

OHLCV_PATH = Path("data/raw/ohlcv/all_symbols.parquet")
FEATURES_DIR = Path("data/features")
SEQUENCES_DIR = Path("data/sequences")
REPORTS_DIR = Path("data/reports")


def _threshold_suffix(threshold: float) -> str:
    """Derive a file-name suffix from a label threshold.

    0.01 -> "" (default, no suffix)
    0.005 -> "thresh05"
    0.015 -> "thresh15"
    0.02 -> "thresh20"
    """
    if threshold == DEFAULT_THRESHOLD:
        return ""
    # Convert 0.005 -> "005", 0.015 -> "015", etc.
    raw = f"{threshold:.3f}".replace("0.", "").replace(".", "")
    return f"thresh{raw}"


def run_features(
    window_size: int = DEFAULT_WINDOW_SIZE,
    label_threshold: float = DEFAULT_THRESHOLD,
) -> None:
    """Full feature engineering pipeline."""
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    SEQUENCES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    suffix = _threshold_suffix(label_threshold)
    file_prefix = f"_{suffix}" if suffix else ""

    # ── Load active symbols ────────────────────────────────────────────
    active = get_active_symbols()
    active_syms = {e["symbol"] for e in active}
    log.info("Active symbols: %d", len(active_syms))

    # ── Load OHLCV ─────────────────────────────────────────────────────
    log.info("Loading OHLCV from %s ...", OHLCV_PATH)
    ohlcv = pd.read_parquet(OHLCV_PATH)
    ohlcv = ohlcv[ohlcv["symbol"].isin(active_syms)].copy()
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])

    # Ensure numeric types
    for col in ["open", "high", "low", "close", "volume"]:
        if col in ohlcv.columns:
            ohlcv[col] = pd.to_numeric(ohlcv[col], errors="coerce")

    log.info("Loaded %d rows for %d active symbols", len(ohlcv), ohlcv["symbol"].nunique())

    # ── Technical Indicators ───────────────────────────────────────────
    log.info("Step 1: Technical indicators ...")
    df = compute_technical_indicators(ohlcv)

    # ── Macro Join ─────────────────────────────────────────────────────
    log.info("Step 2: Macro features ...")
    df = join_macro_features(df)

    # ── Symbol ID ──────────────────────────────────────────────────────
    log.info("Step 3: Symbol ID mapping ...")
    symbol_ids = sorted(df["symbol"].unique())
    sym_id_map = {sym: idx for idx, sym in enumerate(symbol_ids)}
    df["symbol_id"] = df["symbol"].map(sym_id_map)

    # Save mapping
    sym_id_path = Path("data/config/symbol_id_mapping.json")
    sym_id_path.parent.mkdir(parents=True, exist_ok=True)
    sym_id_path.write_text(json.dumps(sym_id_map, indent=2), encoding="utf-8")
    log.info("Saved symbol ID mapping -> %s (%d symbols)", sym_id_path, len(sym_id_map))

    # ── Labeling ───────────────────────────────────────────────────────
    log.info("Step 4: Labeling (threshold=%.3f) ...", label_threshold)
    df, label_report = assign_labels(df, threshold=label_threshold)
    label_map_filename = f"label_mapping{file_prefix}.json" if suffix else "label_mapping.json"
    save_label_mapping(FEATURES_DIR, filename=label_map_filename)

    # ── Identify feature columns ───────────────────────────────────────
    exclude_cols = {"symbol", "date", "forward_return", "label", "symbol_id"}
    feature_columns = sorted([c for c in df.columns if c not in exclude_cols])

    # Ensure numeric
    for col in feature_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    log.info("Feature columns (%d): %s", len(feature_columns), feature_columns)

    # ── Save features parquet ──────────────────────────────────────────
    features_filename = f"features_daily{file_prefix}.parquet" if suffix else "features_daily.parquet"
    features_path = FEATURES_DIR / features_filename
    df.to_parquet(features_path, index=False)
    log.info("Saved features -> %s (%d rows, %d cols)", features_path, len(df), len(df.columns))

    # ── Feature columns ────────────────────────────────────────────────
    columns_path = FEATURES_DIR / "feature_columns.json"
    columns_path.write_text(json.dumps(feature_columns, indent=2), encoding="utf-8")
    log.info("Saved feature columns -> %s (%d features)", columns_path, len(feature_columns))

    # ── Quality Report ─────────────────────────────────────────────────
    log.info("Step 5: Quality report ...")
    quality_filename = f"feature_quality{file_prefix}.json" if suffix else "feature_quality.json"
    build_feature_quality_report(df, label_report, REPORTS_DIR, filename=quality_filename)

    # ── Build sequences ────────────────────────────────────────────────
    log.info("Step 6: Building sequences (window_size=%d) ...", window_size)
    X, y, meta = build_sequences(df, feature_columns, label_report["label_mapping"], window_size)
    save_sequences(X, y, meta, SEQUENCES_DIR, prefix=suffix)

    log.info("=" * 60)
    log.info("Pipeline complete!")
    log.info("  Features parquet: %s", features_path)
    log.info("  Sequences:        %s", SEQUENCES_DIR / f"sequences{file_prefix}.npz")
    log.info("  X shape:          %s", X.shape if X.size > 0 else "empty")
    log.info("  y shape:          %s", y.shape if y.size > 0 else "empty")
    log.info("  Label mapping:    %s", FEATURES_DIR / label_map_filename)
    log.info("  Quality report:   %s", REPORTS_DIR / quality_filename)
    log.info("=" * 60)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_features",
        description="Feature engineering + labeling pipeline for PSX OHLCV data.",
    )
    parser.add_argument(
        "--window-size", type=int, default=DEFAULT_WINDOW_SIZE,
        help=f"Sliding window size (default: {DEFAULT_WINDOW_SIZE})",
    )
    parser.add_argument(
        "--label-threshold", type=float, default=DEFAULT_THRESHOLD,
        help=f"Forward return threshold for labeling (default: {DEFAULT_THRESHOLD})",
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

    run_features(
        window_size=args.window_size,
        label_threshold=args.label_threshold,
    )


if __name__ == "__main__":
    main()
