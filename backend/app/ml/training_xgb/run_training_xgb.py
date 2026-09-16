"""
XGBoost Training Pipeline — CLI Entrypoint
===========================================

Trains both unweighted and weighted XGBoost models for the PSX
direction-classification problem, as a parallel track to the GRU pipeline.

Usage::

    python -m app.ml.training_xgb.run_training_xgb
    python -m app.ml.training_xgb.run_training_xgb --early-stopping 30

This script:
  1. Loads features_daily.parquet and engineers trailing-window features
  2. Splits using the SAME cutoff dates as GRU v1
  3. Trains XGBoost with early stopping on the validation set
  4. Saves both unweighted and weighted model variants
  5. Evaluates both on the test set using the same report format as GRU
  6. Prints a direct comparison table against GRU v1
  7. Prints top 10 feature importances
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.training_xgb.evaluate_xgb import (
    evaluate_xgb,
    load_gru_v1_report,
    print_comparison_table,
    print_top_features,
)
from app.ml.training_xgb.feature_prep import build_xgb_features, get_feature_list
from app.ml.training_xgb.data_split import time_split_xgb
from app.ml.training_xgb.train_xgb import train_xgb_variants

log = logging.getLogger("training_xgb")

FEATURES_DIR = Path("data/features")
REPORTS_DIR = Path("data/reports")


def run_training_xgb(
    early_stopping_rounds: int = 20,
) -> None:
    """Full XGBoost training pipeline."""
    log.info("=" * 70)
    log.info("  XGBoost Training Pipeline")
    log.info("  Parallel track to GRU v1 — same data, same splits, different model")
    log.info("=" * 70)

    # ── Load label mapping ───────────────────────────────────────────────
    label_mapping = json.loads(
        (FEATURES_DIR / "label_mapping.json").read_text(encoding="utf-8")
    )
    log.info("Label mapping: %s", label_mapping)

    # ── Step 1: Feature preparation ─────────────────────────────────────
    log.info("\nStep 1: Feature preparation ...")
    df = build_xgb_features()
    log.info(
        "Rows: %d (features_daily.parquet has ~150,893 — same underlying data, "
        "minor differences possible from NaN handling)",
        len(df),
    )

    # ── Step 2: Train/test split (SAME cutoffs as GRU v1) ───────────────
    log.info("\nStep 2: Time-based split (same cutoffs as GRU v1) ...")
    splits = time_split_xgb(df, label_mapping=label_mapping)

    X_train, y_train = splits["train"]["X"], splits["train"]["y"]
    X_val, y_val = splits["val"]["X"], splits["val"]["y"]
    X_test, y_test = splits["test"]["X"], splits["test"]["y"]
    feature_names = splits["train"]["feature_names"]

    log.info("Feature count: %d", len(feature_names))
    log.info(
        "Train: %d, Val: %d, Test: %d",
        len(X_train), len(X_val), len(X_test),
    )

    # ── Step 3 & 4: Train both variants ─────────────────────────────────
    log.info("\nStep 3-4: Training (unweighted + weighted) ...")
    train_results = train_xgb_variants(
        splits=splits,
        label_mapping=label_mapping,
        feature_names=feature_names,
        early_stopping_rounds=early_stopping_rounds,
    )

    # ── Step 5: Evaluate both variants ──────────────────────────────────
    log.info("\nStep 5: Evaluating on test set ...")
    eval_results = {}
    for variant in ("unweighted", "weighted"):
        log.info("-" * 40)
        log.info("Evaluating variant: %s", variant)

        report_path = REPORTS_DIR / f"evaluation_xgb_{variant}.json"
        report = evaluate_xgb(
            model=train_results[variant]["model"],
            X_test=X_test,
            y_test=y_test,
            y_train=y_train,
            label_mapping=label_mapping,
            report_path=report_path,
            variant=variant,
        )
        eval_results[variant] = report

    # ── Step 6: Direct comparison with GRU v1 ───────────────────────────
    log.info("\nStep 6: Comparison with GRU v1 ...")
    gru_report = load_gru_v1_report()
    print_comparison_table(gru_report, eval_results["unweighted"], eval_results["weighted"])

    # ── Step 7: Feature importances ─────────────────────────────────────
    log.info("\nStep 7: Feature importances ...")
    for variant in ("unweighted", "weighted"):
        importance_path = REPORTS_DIR / f"xgb_feature_importance_{variant}.json"
        print_top_features(importance_path, top_n=10, variant=variant)

    # ── Step 8: Manual sanity check (momentum stress test) ──────────────
    log.info("\nStep 8: Manual sanity check — momentum stress test ...")
    best_variant = "unweighted" if eval_results["unweighted"]["test_accuracy"] >= eval_results["weighted"]["test_accuracy"] else "weighted"
    log.info("Best variant for sanity check: %s (accuracy=%.4f)", best_variant, eval_results[best_variant]["test_accuracy"])
    _run_sanity_check(
        model=train_results[best_variant]["model"],
        feature_names=feature_names,
        label_mapping=label_mapping,
        variant=best_variant,
    )

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("  TRAINING COMPLETE")
    print("=" * 70)
    print(f"  Models saved to:  models/xgb_v1/")
    print(f"  Reports saved to: data/reports/evaluation_xgb_*.json")
    print(f"  Features saved:   data/processed/features_xgb.parquet")
    print(f"  Split report:     data/reports/split_xgb.json")
    print(f"  History:          data/reports/training_history_xgb.json")
    print("=" * 70 + "\n")


# ── Sanity check / momentum stress test ──────────────────────────────────

# Same 7 symbols as GRU's momentum_stress_test.py
SANITY_SYMBOLS = {
    "AICL": {"known_trend": "up",   "known_return": "+12.5%", "notes": "Strong upward"},
    "IBFL": {"known_trend": "up",   "known_return": "~+10%",  "notes": "Strong upward"},
    "MTL":  {"known_trend": "up",   "known_return": "~+5%",   "notes": "Gradual upward"},
    "CHCC": {"known_trend": "down", "known_return": "-13.2%", "notes": "Strong downward"},
    "UBL":  {"known_trend": "down", "known_return": "-9.3%",  "notes": "Downward"},
    "PABC": {"known_trend": "down", "known_return": "-7.5%",  "notes": "Downward"},
    "MLCF": {"known_trend": "down", "known_return": "-6.6%",  "notes": "Downward"},
}

FEATURES_PATH = Path("data/features/features_daily.parquet")
OHLCV_PATH = Path("data/raw/ohlcv/all_symbols.parquet")


def _run_sanity_check(
    model,
    feature_names: list[str],
    label_mapping: dict,
    variant: str = "unweighted",
) -> None:
    """Run momentum stress test on the same 7 symbols as GRU's test.

    This is the XGBoost equivalent of app/ml/serving/momentum_stress_test.py,
    using the same test symbols and known trends for direct comparison.
    """
    from datetime import date

    label_names = {v: k for k, v in label_mapping.items()}

    # Load features
    if not FEATURES_PATH.exists():
        log.warning("Features file not found, skipping sanity check")
        return

    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])

    # Load raw OHLCV for actual return verification
    if not OHLCV_PATH.exists():
        log.warning("OHLCV file not found, skipping sanity check")
        return

    ohlcv = pd.read_parquet(OHLCV_PATH)
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        ohlcv[col] = pd.to_numeric(ohlcv[col], errors="coerce")

    print("\n" + "=" * 90)
    print(f"  MOMENTUM STRESS TEST — XGBoost ({variant})")
    print("  Same 7 symbols as GRU v1 sanity check for direct comparison")
    print("=" * 90)

    results = []
    for symbol, info in SANITY_SYMBOLS.items():
        sym_features = df[df["symbol"] == symbol].copy()
        sym_ohlcv = ohlcv[ohlcv["symbol"] == symbol].copy()

        if sym_features.empty:
            print(f"\n  {symbol}: NO DATA — skipping")
            results.append({"symbol": symbol, "match": "NO DATA"})
            continue

        # Get the latest row (most recent date)
        sym_features = sym_features.sort_values("date").reset_index(drop=True)
        latest_row = sym_features.iloc[-1]
        latest_date = latest_row["date"]

        # Build feature vector — must match the feature_names from training
        feat_values = []
        for fname in feature_names:
            if fname in latest_row.index:
                val = latest_row[fname]
                feat_values.append(float(val) if not pd.isna(val) else 0.0)
            else:
                feat_values.append(0.0)

        X_pred = np.array([feat_values], dtype=np.float32)
        proba = model.predict_proba(X_pred)[0]
        pred_class = int(np.argmax(proba))
        direction = label_names.get(pred_class, "unknown")
        confidence = float(proba[pred_class]) * 100

        # Compute actual return over trend window (Aug 18 - Sep 15, 2026)
        from datetime import date as _date
        trend_start = _date(2026, 8, 18)
        trend_end = _date(2026, 9, 15)

        sym_ohlcv_sorted = sym_ohlcv.sort_values("date").reset_index(drop=True)
        sym_ohlcv_sorted["date_only"] = sym_ohlcv_sorted["date"].dt.date

        after_start = sym_ohlcv_sorted[sym_ohlcv_sorted["date_only"] >= trend_start]
        before_end = sym_ohlcv_sorted[sym_ohlcv_sorted["date_only"] <= trend_end]

        actual_ret = None
        actual_start = None
        actual_end = None
        if not after_start.empty and not before_end.empty:
            actual_start = after_start["date_only"].iloc[0]
            start_close = float(after_start.iloc[0]["close"])
            actual_end = before_end["date_only"].iloc[-1]
            end_close = float(before_end.iloc[-1]["close"])
            actual_ret = (end_close - start_close) / start_close

        # Match determination
        known_dir = info["known_trend"]
        if known_dir == "up" and direction == "bullish":
            match = "YES"
        elif known_dir == "down" and direction == "bearish":
            match = "YES"
        elif direction == "sideways":
            match = "PARTIAL" if actual_ret and abs(actual_ret) < 0.03 else "NO"
        else:
            match = "NO"

        actual_str = f"{actual_ret * 100:+.1f}%" if actual_ret is not None else "N/A"
        actual_range = f"({actual_start} to {actual_end})" if actual_start and actual_end else ""

        print(f"\n  {'='*70}")
        print(f"  {symbol}  |  Known: {info['notes']}  |  Actual return: {actual_str} {actual_range}")
        print(f"  {'='*70}")
        print(f"  XGBoost prediction: {direction:>8}  conf={confidence:.1f}%")
        print(f"    Probabilities: B={proba[0]*100:.1f}%  S={proba[2]*100:.1f}%  R={proba[1]*100:.1f}%")
        print(f"  Match known trend ({known_dir}): {match}")

        # Feature diagnostics
        print(f"  Key features at prediction date ({latest_date.date()}):")
        for fname in ["rsi_14", "macd_hist", "sma_20", "sma_50", "volume_zscore_20", "return_1d", "rolling_std_20d"]:
            if fname in latest_row.index:
                val = latest_row[fname]
                print(f"    {fname:<25s} = {val:.4f}" if not pd.isna(val) else f"    {fname:<25s} = N/A")

        results.append({
            "symbol": symbol,
            "known_trend": known_dir,
            "actual_ret": actual_ret,
            "match": match,
            "pred_dir": direction,
            "confidence": confidence,
        })

    # Aggregate summary
    print("\n" + "=" * 90)
    print("  AGGREGATE SUMMARY")
    print("=" * 90)
    print(f"\n  {'Symbol':<8} {'Known':>6} {'Actual Ret':>11} {'Predicted':>12} {'Match':>7} {'Conf':>6}")
    print(f"  {'-'*8} {'-'*6} {'-'*11} {'-'*12} {'-'*7} {'-'*6}")

    for r in results:
        act_s = f"{r['actual_ret']*100:+.1f}%" if r.get("actual_ret") is not None else "N/A"
        print(f"  {r['symbol']:<8} {r.get('known_trend','?'):>6} {act_s:>11} "
              f"{r.get('pred_dir','?'):>12} {r.get('match','?'):>7} "
              f"{r.get('confidence',0):>5.1f}%")

    uptrend = [r for r in results if r.get("known_trend") == "up"]
    downtrend = [r for r in results if r.get("known_trend") == "down"]

    up_correct = sum(1 for r in uptrend if r.get("match") == "YES")
    down_correct = sum(1 for r in downtrend if r.get("match") == "YES")

    print(f"\n  Uptrend stocks (AICL, IBFL, MTL):")
    print(f"    Correctly flagged BULLISH: {up_correct}/{len(uptrend)}")
    print(f"\n  Downtrend stocks (CHCC, UBL, PABC, MLCF):")
    print(f"    Correctly flagged BEARISH: {down_correct}/{len(downtrend)}")

    total_correct = up_correct + down_correct
    total = len(uptrend) + len(downtrend)
    print(f"\n  TOTAL MATCH: {total_correct}/{total} ({total_correct/total*100:.0f}%)")
    print("=" * 90 + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_training_xgb",
        description="XGBoost training pipeline for PSX direction classification.",
    )
    parser.add_argument(
        "--early-stopping", type=int, default=20,
        help="Early stopping patience in rounds (default: 20)",
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

    run_training_xgb(
        early_stopping_rounds=args.early_stopping,
    )


if __name__ == "__main__":
    main()
