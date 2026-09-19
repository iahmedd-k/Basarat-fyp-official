"""
Standalone diagnostic: check classifier direction vs ATR target_price consistency.

Prints 5 sample rows showing:
  - Current price
  - ATR target price (from recommendation_service)
  - Computed % move from ATR target
  - ML classifier label for that date
  - Whether they agree directionally

Run:
    python diagnostic_consistency.py
    python diagnostic_consistency.py --symbol OGDC
    python diagnostic_consistency.py --threshold 0.02
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from app.data.features.labeling import label_from_return

FEATURES_PATH = Path("data/features/features_daily.parquet")
MODEL_DIR = Path("models/gru_v1")
SCALER_PATH = Path("data/scalers/scaler.pkl")
SEQUENCES_DIR = Path("data/sequences")

LABEL_MAPPING = {"bullish": 0, "bearish": 1, "sideways": 2}
REVERSE_LABELS = {v: k for k, v in LABEL_MAPPING.items()}


def load_artifacts():
    import joblib
    import tensorflow as tf

    model = tf.keras.models.load_model(str(MODEL_DIR / "model.keras"))
    scaler = joblib.load(SCALER_PATH)
    meta = json.loads((MODEL_DIR / "metadata.json").read_text(encoding="utf-8"))
    return model, scaler, meta


def run_diagnostic(symbol: str | None, threshold: float, n_samples: int = 5):
    print("=" * 80)
    print("  DIAGNOSTIC: Classifier direction vs ATR target_price consistency")
    print("=" * 80)
    print(f"  Threshold: {threshold*100:.1f}%  |  Samples: {n_samples}")
    print()

    model, scaler, meta = load_artifacts()
    feature_columns = meta["feature_columns"]
    window_size = meta["window_size"]

    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])

    if symbol:
        df = df[df["symbol"] == symbol.upper()].copy()
        if df.empty:
            print(f"  ERROR: No data for symbol '{symbol}'")
            sys.exit(1)

    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # We need window_size + 1 rows (window for ML + 1 for forward_return check)
    # and we skip the first window_size rows per symbol

    # Compute ATR-based target_price inline (same logic as recommendation_service.py)
    RISK_MULT = 3.0  # moderate

    results = []

    for sym, grp in df.groupby("symbol"):
        grp = grp.sort_values("date").reset_index(drop=True)
        if len(grp) < window_size + 2:
            continue

        # Iterate over candidate rows (skip first window_size rows, skip last row)
        for i in range(window_size, len(grp) - 1):
            row = grp.iloc[i]
            current_price = float(row.get("close", 0))
            atr = float(row.get("atr_14", 0))

            if current_price <= 0 or atr <= 0 or pd.isna(atr):
                continue

            # ATR target price (same as recommendation_service.compute_target_stop)
            atr_target_price = round(current_price + (atr * RISK_MULT), 2)
            atr_pct_move = (atr_target_price - current_price) / current_price * 100

            # ML classifier prediction: build window
            window_start = i + 1 - window_size
            window_df = grp.iloc[window_start:i + 1]

            missing = set(feature_columns) - set(window_df.columns)
            if missing:
                continue

            X = window_df[feature_columns].values.astype(np.float32)
            n, T, F = 1, X.shape[0], X.shape[1]
            flat = X.reshape(n * T, F)
            flat = scaler.transform(flat)
            X_scaled = flat.reshape(n, T, F)

            proba = model.predict(X_scaled, verbose=0)[0]
            pred_class = int(np.argmax(proba))
            ml_label = REVERSE_LABELS.get(pred_class, "unknown")
            pct_map = {REVERSE_LABELS[i]: float(proba[i]) * 100 for i in range(len(proba))}
            from app.ml.serving.inference import compute_confidence
            confidence = compute_confidence(pct_map)

            # Forward return (actual next-day move)
            next_row = grp.iloc[i + 1]
            next_price = float(next_row.get("close", 0))
            fwd_return_pct = (next_price - current_price) / current_price * 100

            # Classification of forward return
            actual_label = label_from_return(fwd_return_pct / 100, threshold)

            # Direction agreement check
            atr_direction = "bullish" if atr_pct_move > 0 else "bearish" if atr_pct_move < 0 else "sideways"
            ml_vs_atr_agree = (ml_label == atr_direction) or (
                ml_label in ("bullish", "bearish") and atr_direction == "bullish"
            )

            # Flag contradictions
            contradiction = (ml_label == "bearish" and atr_pct_move > threshold * 100) or \
                           (ml_label == "bullish" and atr_pct_move < -threshold * 100)

            results.append({
                "symbol": sym,
                "date": row["date"].strftime("%Y-%m-%d"),
                "current_price": current_price,
                "atr_14": atr,
                "atr_target_price": atr_target_price,
                "atr_pct_move": atr_pct_move,
                "ml_label": ml_label,
                "confidence": confidence,
                "actual_next_day_pct": fwd_return_pct,
                "actual_label": actual_label,
                "contradiction": contradiction,
            })

    if not results:
        print("  No valid results found.")
        return

    # Sort: contradictions first, then by absolute pct move (worst contradictions on top)
    results.sort(key=lambda r: (not r["contradiction"], -abs(r["atr_pct_move"])))

    # Show top N
    display = results[:n_samples]

    print("-" * 80)
    print(f"  {'Symbol':<8} {'Date':<12} {'CurPrice':>9} {'ATR Target':>11} {'ATR %Move':>10} "
          f"{'ML Label':>10} {'Conf%':>6} {'Actual%':>8} {'Actual':>9} {'Contradiction'}")
    print("-" * 80)

    for r in display:
        flag = " <<< BUG" if r["contradiction"] else ""
        print(f"  {r['symbol']:<8} {r['date']:<12} {r['current_price']:>9.2f} "
              f"{r['atr_target_price']:>11.2f} {r['atr_pct_move']:>+9.1f}% "
              f"{r['ml_label']:>10} {r['confidence']:>5.1f}% "
              f"{r['actual_next_day_pct']:>+7.2f}% {r['actual_label']:>9}{flag}")

    print("-" * 80)

    # Summary stats
    total = len(results)
    contradictions = sum(1 for r in results if r["contradiction"])
    bearish_with_up_target = sum(1 for r in results
                                  if r["ml_label"] == "bearish" and r["atr_pct_move"] > 1.0)

    print()
    print("  SUMMARY:")
    print(f"    Total samples analyzed:         {total}")
    print(f"    Direction contradictions:        {contradictions} ({contradictions/total*100:.1f}%)")
    print(f"    Bearish classifier + upward ATR: {bearish_with_up_target} ({bearish_with_up_target/total*100:.1f}%)")
    print()
    print("  ROOT CAUSE:")
    print("    ATR target_price = current_price + (ATR_14 * 3.0)")
    print("    This ALWAYS projects upward, regardless of classifier direction.")
    print("    The target_price and classifier are computed by independent code paths.")
    print()
    print("  FIX: The target_price should be conditioned on classifier direction:")
    print("    - bullish: target = current + ATR * mult")
    print("    - bearish: target = current - ATR * mult  (or show current as target)")
    print("    - sideways: target = current_price (no directional target)")
    print("=" * 80)


def main():
    parser = argparse.ArgumentParser(description="Diagnostic: classifier vs ATR target consistency")
    parser.add_argument("--symbol", type=str, default=None, help="Filter to one symbol")
    parser.add_argument("--threshold", type=float, default=0.01, help="Label threshold (default: 0.01 = 1%%)")
    parser.add_argument("--n-samples", type=int, default=5, help="Number of rows to display")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    run_diagnostic(args.symbol, args.threshold, args.n_samples)


if __name__ == "__main__":
    main()
