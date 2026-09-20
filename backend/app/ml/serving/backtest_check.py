"""Backtest inspector — sanity-check GRU predictions against historical outcomes.

Standalone script (no Celery, no API):
    python -m app.ml.serving.backtest_check --symbol OGDC --date 2026-08-01
    python -m app.ml.serving.backtest_check --symbol OGDC --last-n-days 60
    python -m app.ml.serving.backtest_check --symbol OGDC --last-n-days 60 --threshold 0.02

For a given as_of_date, the script:
  1. Builds the 30-day window ending at that date (same as inference.py).
  2. Runs it through the loaded gru_v1 model to get predicted direction + percentages.
  3. Looks up what ACTUALLY happened on the next trading day (real forward return + label).
  4. Prints a side-by-side comparison.

Batch mode (--last-n-days) runs this for every trading day in the range and prints
a running accuracy tally broken down by predicted class.
"""

import argparse
import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

FEATURES_PATH = Path("data/features/features_daily.parquet")

log = logging.getLogger("backtest_check")


# ── Helpers ──────────────────────────────────────────────────────────────


def _next_trading_day(d: date) -> date:
    """Return the next business day after *d* (skip weekends)."""
    nxt = d + timedelta(days=1)
    while nxt.weekday() >= 5:
        nxt += timedelta(days=1)
    return nxt


def _classify_return(forward_return: float, threshold: float) -> str:
    """Classify a forward return into bullish / bearish / sideways."""
    if forward_return > threshold:
        return "bullish"
    elif forward_return < -threshold:
        return "bearish"
    return "sideways"


def _get_trading_days(sym_df: pd.DataFrame) -> list[date]:
    """Return sorted list of trading days for *symbol*."""
    dates = sym_df["date"].dt.date.unique()
    return sorted(dates)


# ── Single-day backtest ──────────────────────────────────────────────────


def run_single(
    sym_df: pd.DataFrame,
    as_of_date: date,
    model,
    scaler,
    feature_columns: list[str],
    window_size: int,
    threshold: float,
) -> dict | None:
    """Run one backtest for a single as_of_date.

    Returns a dict with prediction + actual outcome, or None if the date
    or its successor is outside the dataset.
    """
    sym_df = sym_df.sort_values("date").reset_index(drop=True)
    sym_df["date_only"] = sym_df["date"].dt.date

    # Find the index of as_of_date
    idx_matches = sym_df.index[sym_df["date_only"] == as_of_date].tolist()
    if not idx_matches:
        return None
    idx = idx_matches[0]

    # Need at least window_size rows up to and including as_of_date
    if idx + 1 < window_size:
        return None

    # Need a next trading day to check the actual outcome
    next_day = _next_trading_day(as_of_date)
    next_matches = sym_df.index[sym_df["date_only"] == next_day].tolist()
    if not next_matches:
        return None
    next_idx = next_matches[0]

    # ── Build window (same as inference.py) ──────────────────────────────
    window_start = idx + 1 - window_size
    window_df = sym_df.iloc[window_start:idx + 1].copy()

    missing_cols = set(feature_columns) - set(window_df.columns)
    if missing_cols:
        log.warning("Missing columns %s for %s on %s, skipping", missing_cols, sym_df["symbol"].iloc[0], as_of_date)
        return None

    X = window_df[feature_columns].values.astype(np.float32)

    # ── Scale ────────────────────────────────────────────────────────────
    n, T, F = 1, X.shape[0], X.shape[1]
    flat = X.reshape(n * T, F)
    flat = scaler.transform(flat)
    X_scaled = flat.reshape(n, T, F)

    # ── Predict ──────────────────────────────────────────────────────────
    proba = model.predict(X_scaled, verbose=0)[0]

    label_names = {0: "bullish", 1: "bearish", 2: "sideways"}
    bullish_pct = round(float(proba[0]) * 100, 1)
    bearish_pct = round(float(proba[1]) * 100, 1)
    sideways_pct = round(float(proba[2]) * 100, 1)

    total = bullish_pct + bearish_pct + sideways_pct
    if abs(total - 100.0) > 0.5:
        factor = 100.0 / total
        bullish_pct = round(bullish_pct * factor, 1)
        bearish_pct = round(bearish_pct * factor, 1)
        sideways_pct = round(sideways_pct * factor, 1)

    pred_class = int(np.argmax(proba))
    predicted_direction = label_names.get(pred_class, "unknown")
    pct_map = {"bullish": bullish_pct, "bearish": bearish_pct, "sideways": sideways_pct}
    from app.ml.serving.inference import compute_confidence
    confidence = round(compute_confidence(pct_map), 1)

    # ── Actual outcome ───────────────────────────────────────────────────
    as_of_price = float(sym_df.iloc[idx]["close"])
    target_price = float(sym_df.iloc[next_idx]["close"])
    forward_return = (target_price - as_of_price) / as_of_price
    actual_direction = _classify_return(forward_return, threshold)
    matched = predicted_direction == actual_direction

    return {
        "as_of_date": as_of_date,
        "target_date": next_day,
        "predicted_direction": predicted_direction,
        "top_class_probability": confidence,
        "bullish_pct": bullish_pct,
        "bearish_pct": bearish_pct,
        "sideways_pct": sideways_pct,
        "actual_direction": actual_direction,
        "forward_return_pct": round(forward_return * 100, 3),
        "matched": matched,
    }


# ── Print helpers ────────────────────────────────────────────────────────


def print_single(result: dict) -> None:
    """Print a formatted side-by-side for one backtest result."""
    check = "CORRECT" if result["matched"] else "WRONG"
    emoji = "+" if result["matched"] else "X"

    print()
    print(f"  Date:    {result['as_of_date']}  ->  {result['target_date']}")
    print(f"  Predict: {result['predicted_direction']:>8}  ({result['confidence']:.1f}% conf)  "
          f"  [B {result['bullish_pct']:.1f}% | S {result['sideways_pct']:.1f}% | R {result['bearish_pct']:.1f}%]")
    print(f"  Actual:  {result['actual_direction']:>8}  (return {result['forward_return_pct']:+.3f}%)")
    print(f"  Result:  [{emoji}] {check}")


def print_batch_summary(results: list[dict]) -> None:
    """Print running tally and per-class breakdown."""
    total = len(results)
    correct = sum(1 for r in results if r["matched"])

    print()
    print("=" * 70)
    print(f"  BATCH SUMMARY  ({total} trading days)")
    print("=" * 70)
    print(f"  Overall accuracy:  {correct} / {total}  ({correct / total * 100:.1f}%)" if total else "  No results.")

    # Per predicted-class breakdown
    by_pred = defaultdict(lambda: {"count": 0, "correct": 0, "actual_dist": defaultdict(int)})
    for r in results:
        pred = r["predicted_direction"]
        by_pred[pred]["count"] += 1
        if r["matched"]:
            by_pred[pred]["correct"] += 1
        by_pred[pred]["actual_dist"][r["actual_direction"]] += 1

    print()
    print(f"  {'Predicted':<12} {'Count':>6} {'Correct':>8} {'Accuracy':>10}   Actual distribution")
    print(f"  {'-'*12} {'-'*6} {'-'*8} {'-'*10}   {'-'*30}")
    for pred_class in ["bullish", "bearish", "sideways"]:
        info = by_pred.get(pred_class)
        if not info:
            continue
        acc = info["correct"] / info["count"] * 100 if info["count"] else 0
        dist_str = ", ".join(f"{k}:{v}" for k, v in sorted(info["actual_dist"].items()))
        print(f"  {pred_class:<12} {info['count']:>6} {info['correct']:>8} {acc:>9.1f}%   {dist_str}")

    # Per actual-class recall
    by_act = defaultdict(lambda: {"count": 0, "correct": 0})
    for r in results:
        act = r["actual_direction"]
        by_act[act]["count"] += 1
        if r["matched"]:
            by_act[act]["correct"] += 1

    print()
    print(f"  {'Actual':<12} {'Count':>6} {'Recalled':>8} {'Recall':>10}")
    print(f"  {'-'*12} {'-'*6} {'-'*8} {'-'*10}")
    for actual_class in ["bullish", "bearish", "sideways"]:
        info = by_act.get(actual_class)
        if not info:
            continue
        recall = info["correct"] / info["count"] * 100 if info["count"] else 0
        print(f"  {actual_class:<12} {info['count']:>6} {info['correct']:>8} {recall:>9.1f}%")

    print("=" * 70)


# ── CLI ──────────────────────────────────────────────────────────────────


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Backtest GRU predictions against historical outcomes."
    )
    parser.add_argument("--symbol", required=True, help="PSX stock symbol (e.g. OGDC)")
    parser.add_argument("--date", help="Single as-of date (YYYY-MM-DD)")
    parser.add_argument("--last-n-days", type=int, help="Run batch backtest over the last N trading days")
    parser.add_argument(
        "--threshold", type=float, default=0.01,
        help="Forward-return threshold for label classification (default: 0.01 = 1%%)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.WARNING,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    # ── Load model artifacts ─────────────────────────────────────────────
    from app.ml.serving.model_loader import artifacts, load_artifacts

    if not artifacts.model_ready:
        log.info("Loading model artifacts...")
        load_artifacts()
    if not artifacts.model_ready:
        print("ERROR: Model artifacts failed to load. Check models/gru_v1/ and data/scalers/.")
        sys.exit(1)

    model = artifacts.model
    scaler = artifacts.scaler
    feature_columns = artifacts.feature_columns
    window_size = artifacts.window_size

    print(f"Model loaded: {artifacts.model_version}  (window={window_size}, features={len(feature_columns)})")

    # ── Load feature data ────────────────────────────────────────────────
    symbol = args.symbol.upper()
    df = pd.read_parquet(FEATURES_PATH)
    sym_df = df[df["symbol"] == symbol].copy()
    if sym_df.empty:
        print(f"ERROR: No data found for symbol '{symbol}' in {FEATURES_PATH}")
        sys.exit(1)

    sym_df["date"] = pd.to_datetime(sym_df["date"])
    trading_days = _get_trading_days(sym_df)
    print(f"Symbol: {symbol}  |  {len(trading_days)} trading days in dataset  |  "
          f"range {trading_days[0]} to {trading_days[-1]}")
    print(f"Threshold: {args.threshold * 100:.1f}%")

    # ── Single-day mode ──────────────────────────────────────────────────
    if args.date:
        as_of = datetime.strptime(args.date, "%Y-%m-%d").date()
        print(f"\n--- Single-day backtest: as_of_date={as_of} ---")

        result = run_single(sym_df, as_of, model, scaler, feature_columns, window_size, args.threshold)
        if result is None:
            print(f"  Could not run backtest for {as_of}: date not in dataset or insufficient history.")
            sys.exit(1)

        print_single(result)
        print()
        sys.exit(0)

    # ── Batch mode ───────────────────────────────────────────────────────
    if args.last_n_days:
        n = args.last_n_days
        # Exclude the last day (no next-day outcome possible) and
        # exclude the first window_size days (insufficient history)
        earliest = trading_days[window_size]
        candidates = [d for d in trading_days if d >= earliest]
        # Take the last N from the candidates, excluding the very last day
        batch_dates = candidates[-(n + 1):-1] if len(candidates) > n else candidates[:-1]

        if not batch_dates:
            print(f"ERROR: Not enough trading days to run batch mode with last_n_days={n}")
            sys.exit(1)

        print(f"\n--- Batch backtest: {len(batch_dates)} trading days ---")
        print(f"  Range: {batch_dates[0]} to {batch_dates[-1]}")

        results = []
        for i, as_of in enumerate(batch_dates, 1):
            result = run_single(sym_df, as_of, model, scaler, feature_columns, window_size, args.threshold)
            if result is None:
                continue
            results.append(result)
            # Progress: print each result
            tag = "+" if result["matched"] else "X"
            print(f"  [{i:>3}/{len(batch_dates)}] {result['as_of_date']}  "
                  f"pred={result['predicted_direction']:>8} ({result['confidence']:.1f}%)  "
                  f"actual={result['actual_direction']:>8} ({result['forward_return_pct']:+.3f}%)  [{tag}]")

        if results:
            print_batch_summary(results)
        else:
            print("  No valid results produced.")

        sys.exit(0)

    # Neither --date nor --last-n-days provided
    print("ERROR: Provide either --date YYYY-MM-DD or --last-n-days N")
    parser.print_help()
    sys.exit(1)


if __name__ == "__main__":
    main()
