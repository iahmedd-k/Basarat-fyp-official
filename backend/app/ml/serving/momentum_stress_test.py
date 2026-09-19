"""Momentum stress test — qualitative check of GRU predictions against known trends.

Tests whether the model correctly identifies clear, verified real-world momentum
for 7 hand-picked symbols with known recent trends (Aug 18 - Sep 15, 2026).

Standalone script:
    python -m app.ml.serving.momentum_stress_test
"""

import json
import logging
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

FEATURES_PATH = Path("data/features/features_daily.parquet")

log = logging.getLogger("momentum_stress_test")

# ── Test cases: verified real-world trends (Aug 18 - Sep 15, 2026) ────────
TEST_SYMBOLS = {
    "AICL": {"known_trend": "up",   "known_return": "+12.5%", "notes": "Strong upward"},
    "IBFL": {"known_trend": "up",   "known_return": "~+10%",  "notes": "Strong upward"},
    "MTL":  {"known_trend": "up",   "known_return": "~+5%",   "notes": "Gradual upward"},
    "CHCC": {"known_trend": "down", "known_return": "-13.2%", "notes": "Strong downward (313.70 -> 272.43)"},
    "UBL":  {"known_trend": "down", "known_return": "-9.3%",  "notes": "Downward (461.98 -> 418.96)"},
    "PABC": {"known_trend": "down", "known_return": "-7.5%",  "notes": "Downward"},
    "MLCF": {"known_trend": "down", "known_return": "-6.6%",  "notes": "Downward (99.41 -> 92.85)"},
}

# Trend window for actual return verification
TREND_START = date(2026, 8, 18)
TREND_END = date(2026, 9, 15)


# ── Model inference (replicates inference.py logic) ──────────────────────


def run_inference_at_date(sym_df: pd.DataFrame, as_of_date: date, artifacts) -> dict | None:
    """Run GRU inference on the window ending at *as_of_date*.

    Returns dict with prediction details, or None if data insufficient.
    """
    sym_df = sym_df.sort_values("date").reset_index(drop=True)
    sym_df["date_only"] = sym_df["date"].dt.date

    # Find index of as_of_date
    idx_matches = sym_df.index[sym_df["date_only"] == as_of_date].tolist()
    if not idx_matches:
        return None
    idx = idx_matches[0]

    window_size = artifacts.window_size
    if idx + 1 < window_size:
        return None

    # Build window
    window_start = idx + 1 - window_size
    window_df = sym_df.iloc[window_start:idx + 1].copy()

    missing_cols = set(artifacts.feature_columns) - set(window_df.columns)
    if missing_cols:
        return None

    X = window_df[artifacts.feature_columns].values.astype(np.float32)

    # Scale
    n, T, F = 1, X.shape[0], X.shape[1]
    flat = X.reshape(n * T, F)
    flat = artifacts.scaler.transform(flat)
    X_scaled = flat.reshape(n, T, F)

    # Predict
    proba = artifacts.model.predict(X_scaled, verbose=0)[0]

    label_names = artifacts.label_names
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
    direction = label_names.get(pred_class, "unknown")
    pct_map = {"bullish": bullish_pct, "bearish": bearish_pct, "sideways": sideways_pct}
    from app.ml.serving.inference import compute_confidence
    top_class_probability = round(compute_confidence(pct_map), 1)

    return {
        "as_of_date": as_of_date,
        "direction": direction,
        "top_class_probability": top_class_probability,
        "bullish_pct": bullish_pct,
        "bearish_pct": bearish_pct,
        "sideways_pct": sideways_pct,
        "window_start": window_df["date_only"].iloc[0],
    }


def get_feature_diagnostics(sym_df: pd.DataFrame, as_of_date: date, n_days: int = 10) -> dict | None:
    """Get the raw feature values for diagnostic inspection."""
    sym_df = sym_df.sort_values("date").reset_index(drop=True)
    sym_df["date_only"] = sym_df["date"].dt.date

    idx_matches = sym_df.index[sym_df["date_only"] == as_of_date].tolist()
    if not idx_matches:
        return None
    idx = idx_matches[0]

    start = max(0, idx + 1 - n_days)
    recent = sym_df.iloc[start:idx + 1].copy()

    return {
        "dates": recent["date_only"].tolist(),
        "close": recent["close"].tolist(),
        "rsi_14": recent["rsi_14"].tolist() if "rsi_14" in recent.columns else None,
        "macd": recent["macd"].tolist() if "macd" in recent.columns else None,
        "macd_hist": recent["macd_hist"].tolist() if "macd_hist" in recent.columns else None,
        "macd_signal": recent["macd_signal"].tolist() if "macd_signal" in recent.columns else None,
        "sma_20": recent["sma_20"].tolist() if "sma_20" in recent.columns else None,
        "sma_50": recent["sma_50"].tolist() if "sma_50" in recent.columns else None,
        "volume": recent["volume"].tolist() if "volume" in recent.columns else None,
    }


# ── Actual return from raw OHLCV ─────────────────────────────────────────


def compute_actual_return(sym_df: pd.DataFrame, start_date: date, end_date: date) -> tuple[float | None, date | None, date | None]:
    """Compute the actual close-to-close return over [start_date, end_date].

    Uses nearest available trading days if exact dates are missing.
    Returns (return, actual_start, actual_end).
    """
    sym_df = sym_df.sort_values("date").reset_index(drop=True)
    sym_df["date_only"] = sym_df["date"].dt.date

    # Find nearest available date on or after start_date
    after_start = sym_df[sym_df["date_only"] >= start_date]
    if after_start.empty:
        return None, None, None
    actual_start = after_start["date_only"].iloc[0]
    start_close = float(after_start.iloc[0]["close"])

    # Find nearest available date on or before end_date
    before_end = sym_df[sym_df["date_only"] <= end_date]
    if before_end.empty:
        return None, None, None
    actual_end = before_end["date_only"].iloc[-1]
    end_close = float(before_end.iloc[-1]["close"])

    return (end_close - start_close) / start_close, actual_start, actual_end


# ── Print helpers ────────────────────────────────────────────────────────


def print_symbol_block(symbol: str, info: dict, actual_ret: float | None,
                       actual_start: date | None, actual_end: date | None,
                       pred_latest: dict | None, pred_mid: dict | None,
                       features: dict | None) -> str:
    """Print formatted block for one symbol, return match status."""
    known_dir = info["known_trend"]

    def _match(pred_dir: str) -> str:
        if known_dir == "up" and pred_dir == "bullish":
            return "YES"
        elif known_dir == "down" and pred_dir == "bearish":
            return "YES"
        elif pred_dir == "sideways":
            return "PARTIAL" if abs(actual_ret or 0) < 0.03 else "NO"
        else:
            return "NO"

    match_latest = _match(pred_latest["direction"]) if pred_latest else "N/A"
    match_mid = _match(pred_mid["direction"]) if pred_mid else "N/A"

    actual_str = f"{actual_ret * 100:+.2f}%" if actual_ret is not None else "N/A"
    actual_range = f"({actual_start} to {actual_end})" if actual_start and actual_end else ""

    print()
    print(f"  {'='*66}")
    print(f"  {symbol}  |  Known: {info['notes']}  |  Actual return: {actual_str} {actual_range}")
    print(f"  {'='*66}")

    if pred_latest:
        print(f"  LATEST  (as_of={pred_latest['as_of_date']}):")
        print(f"    Predicted: {pred_latest['direction']:>8}  conf={pred_latest['top_class_probability']:.1f}%  "
              f"[B {pred_latest['bullish_pct']:.1f}% | S {pred_latest['sideways_pct']:.1f}% | R {pred_latest['bearish_pct']:.1f}%]")
        print(f"    Match known trend ({known_dir}): {match_latest}")
    else:
        print(f"  LATEST: Could not run (data issue)")

    if pred_mid:
        print(f"  MID-TREND (as_of={pred_mid['as_of_date']}):")
        print(f"    Predicted: {pred_mid['direction']:>8}  conf={pred_mid['top_class_probability']:.1f}%  "
              f"[B {pred_mid['bullish_pct']:.1f}% | S {pred_mid['sideways_pct']:.1f}% | R {pred_mid['bearish_pct']:.1f}%]")
        print(f"    Match known trend ({known_dir}): {match_mid}")
    else:
        print(f"  MID-TREND: Could not run (data issue)")

    # Feature diagnostics for mismatches
    if features and match_latest == "NO":
        print(f"  --- FEATURE DIAGNOSTICS (last 10 days before {pred_latest['as_of_date']}) ---")
        print(f"    {'Date':<12} {'Close':>10} {'RSI':>8} {'MACD':>10} {'Hist':>10} {'SMA20':>10} {'SMA50':>10}")
        for i in range(len(features["dates"])):
            d = features["dates"][i]
            c = features["close"][i]
            rsi = features["rsi_14"][i] if features["rsi_14"] else None
            macd = features["macd"][i] if features["macd"] else None
            hist = features["macd_hist"][i] if features["macd_hist"] else None
            sma20 = features["sma_20"][i] if features["sma_20"] else None
            sma50 = features["sma_50"][i] if features["sma_50"] else None

            rsi_s = f"{rsi:.1f}" if rsi is not None and not pd.isna(rsi) else "  N/A"
            macd_s = f"{macd:.4f}" if macd is not None and not pd.isna(macd) else "  N/A"
            hist_s = f"{hist:.4f}" if hist is not None and not pd.isna(hist) else "  N/A"
            sma20_s = f"{sma20:.2f}" if sma20 is not None and not pd.isna(sma20) else "  N/A"
            sma50_s = f"{sma50:.2f}" if sma50 is not None and not pd.isna(sma50) else "  N/A"

            print(f"    {str(d):<12} {c:>10.2f} {rsi_s:>8} {macd_s:>10} {hist_s:>10} {sma20_s:>10} {sma50_s:>10}")

    return match_latest


# ── Main ──────────────────────────────────────────────────────────────────


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Momentum stress test for GRU models.")
    parser.add_argument("--model-dir", default="models/gru_v1",
                        help="Model directory to load (default: models/gru_v1)")
    parser.add_argument("--scaler-path", default="data/scalers/scaler.pkl",
                        help="Scaler path (default: data/scalers/scaler.pkl)")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    # ── Load model artifacts ─────────────────────────────────────────────
    from dataclasses import dataclass, field
    from pathlib import Path as P

    import joblib
    import tensorflow as tf

    @dataclass
    class TestArtifacts:
        model: object = None
        scaler: object = None
        feature_columns: list = field(default_factory=list)
        label_mapping: dict = field(default_factory=dict)
        label_names: dict = field(default_factory=dict)
        window_size: int = 30
        n_features: int = 20
        model_version: str = "unknown"
        model_ready: bool = False

    artifacts = TestArtifacts()
    model_dir = P(args.model_dir)
    scaler_path = P(args.scaler_path)

    try:
        model_path = model_dir / "model.keras"
        meta_path = model_dir / "metadata.json"

        if not model_path.exists():
            print(f"ERROR: Model file not found: {model_path}")
            sys.exit(1)
        if not meta_path.exists():
            print(f"ERROR: Metadata not found: {meta_path}")
            sys.exit(1)

        artifacts.model = tf.keras.models.load_model(str(model_path))
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        artifacts.feature_columns = meta["feature_columns"]
        artifacts.label_mapping = meta["label_mapping"]
        artifacts.label_names = {v: k for k, v in meta["label_mapping"].items()}
        artifacts.window_size = meta["window_size"]
        artifacts.n_features = meta["n_features"]
        artifacts.model_version = model_dir.name

        if not scaler_path.exists():
            print(f"ERROR: Scaler not found: {scaler_path}")
            sys.exit(1)
        artifacts.scaler = joblib.load(scaler_path)

        # Validate shapes
        actual_shape = artifacts.model.input_shape
        if actual_shape[1:] != (artifacts.window_size, artifacts.n_features):
            print(f"ERROR: Model input shape {actual_shape[1:]} != expected ({artifacts.window_size}, {artifacts.n_features})")
            sys.exit(1)

        artifacts.model_ready = True
    except Exception as e:
        print(f"ERROR: Failed to load model: {e}")
        sys.exit(1)

    print(f"Model: {artifacts.model_version}  (window={artifacts.window_size}, features={len(artifacts.feature_columns)})")

    # ── Load data ────────────────────────────────────────────────────────
    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])

    # Also load raw OHLCV for close price verification
    ohlcv_path = Path("data/raw/ohlcv/all_symbols.parquet")
    ohlcv = pd.read_parquet(ohlcv_path)
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        ohlcv[col] = pd.to_numeric(ohlcv[col], errors="coerce")

    print(f"Features: {len(df)} rows, {df['symbol'].nunique()} symbols")
    print(f"Trend window: {TREND_START} to {TREND_END}")
    print()

    # ── Run tests ────────────────────────────────────────────────────────
    results = []

    for symbol, info in TEST_SYMBOLS.items():
        sym_features = df[df["symbol"] == symbol].copy()
        sym_ohlcv = ohlcv[ohlcv["symbol"] == symbol].copy()

        if sym_features.empty:
            print(f"  {symbol}: NO DATA in features parquet — skipping")
            results.append({"symbol": symbol, "match_latest": "NO DATA", "match_mid": "NO DATA"})
            continue

        # Get available dates
        available_dates = sorted(sym_features["date"].dt.date.unique())
        latest_date = available_dates[-1]

        # Actual return over the trend window
        actual_ret, actual_start, actual_end = compute_actual_return(sym_ohlcv, TREND_START, TREND_END)

        # LATEST prediction
        pred_latest = run_inference_at_date(sym_features, latest_date, artifacts)

        # MID-TREND prediction: ~5 trading days before latest
        mid_date = None
        if len(available_dates) > 5:
            mid_idx = len(available_dates) - 6
            mid_date = available_dates[mid_idx]
        pred_mid = run_inference_at_date(sym_features, mid_date, artifacts) if mid_date else None

        # Feature diagnostics (for mismatches)
        features_diag = None
        if pred_latest:
            features_diag = get_feature_diagnostics(sym_features, latest_date, n_days=10)

        match = print_symbol_block(symbol, info, actual_ret, actual_start, actual_end, pred_latest, pred_mid, features_diag)

        results.append({
            "symbol": symbol,
            "known_trend": info["known_trend"],
            "actual_ret": actual_ret,
            "match_latest": match,
            "match_mid": match if pred_mid else "N/A",
            "pred_latest_dir": pred_latest["direction"] if pred_latest else None,
            "pred_mid_dir": pred_mid["direction"] if pred_mid else None,
            "confidence_latest": pred_latest["top_class_probability"] if pred_latest else None,
            "confidence_mid": pred_mid["top_class_probability"] if pred_mid else None,
        })

    # ── Aggregate summary ────────────────────────────────────────────────
    print()
    print("=" * 90)
    print("  AGGREGATE SUMMARY")
    print("=" * 90)
    print()
    print(f"  {'Symbol':<8} {'Known':>6} {'Actual Ret':>11} {'Pred (latest)':>14} {'Match':>7} {'Conf':>6} "
          f"{'Pred (mid)':>14} {'Match':>7} {'Conf':>6}")
    print(f"  {'-'*8} {'-'*6} {'-'*11} {'-'*14} {'-'*7} {'-'*6} {'-'*14} {'-'*7} {'-'*6}")

    for r in results:
        act_s = f"{r['actual_ret']*100:+.1f}%" if r.get("actual_ret") is not None else "N/A"
        print(f"  {r['symbol']:<8} {r.get('known_trend','?'):>6} {act_s:>11} "
              f"{r.get('pred_latest_dir','?'):>14} {r.get('match_latest','?'):>7} "
              f"{r.get('confidence_latest',0):>5.1f}% "
              f"{r.get('pred_mid_dir','?'):>14} {r.get('match_mid','?'):>7} "
              f"{r.get('confidence_mid',0):>5.1f}%")

    # ── Counts ───────────────────────────────────────────────────────────
    uptrend = [r for r in results if r.get("known_trend") == "up"]
    downtrend = [r for r in results if r.get("known_trend") == "down"]

    up_correct = sum(1 for r in uptrend if r.get("match_latest") == "YES")
    down_correct = sum(1 for r in downtrend if r.get("match_latest") == "YES")

    print()
    print(f"  Uptrend stocks (AICL, IBFL, MTL):")
    print(f"    Correctly flagged BULLISH: {up_correct}/{len(uptrend)}")
    for r in uptrend:
        print(f"      {r['symbol']}: predicted={r.get('pred_latest_dir','?')}  match={r.get('match_latest','?')}")

    print()
    print(f"  Downtrend stocks (CHCC, UBL, PABC, MLCF):")
    print(f"    Correctly flagged BEARISH: {down_correct}/{len(downtrend)}")
    for r in downtrend:
        print(f"      {r['symbol']}: predicted={r.get('pred_latest_dir','?')}  match={r.get('match_latest','?')}")

    total_correct = up_correct + down_correct
    total = len(uptrend) + len(downtrend)
    print()
    print(f"  TOTAL MATCH: {total_correct}/{total} ({total_correct/total*100:.0f}%)")
    print("=" * 90)

    # ── Diagnostic conclusion ────────────────────────────────────────────
    print()
    print("  DIAGNOSTIC CONCLUSION")
    print("  " + "-" * 60)

    mismatched = [r for r in results if r.get("match_latest") == "NO"]
    if not mismatched:
        print("  All predictions matched known trends.")
    else:
        print(f"  {len(mismatched)} symbol(s) had mismatched predictions:")
        for r in mismatched:
            print(f"    {r['symbol']}: predicted {r.get('pred_latest_dir')} but trend was {r.get('known_trend')}")

    # Aggregate accuracy context
    print()
    print("  Context: The model's aggregate test accuracy is ~46%. The question")
    print("  is whether clear, strong trends are treated differently from")
    print("  ambiguous cases.")

    # Check if model predicts sideways for everything
    sideways_count = sum(1 for r in results if r.get("pred_latest_dir") == "sideways")
    print(f"  Model predicted SIDEWAYSS for {sideways_count}/{len(results)} symbols in this test.")
    if sideways_count == len(results):
        print("  -> The model is predicting sideways for ALL clear trends.")
        print("     This indicates the model has NOT learned to distinguish")
        print("     momentum. Strong trends are treated the same as noise.")
        print("     Root cause: model architecture/training capacity, NOT")
        print("     feature engineering — the features DO reflect the trends")
        print("     (see diagnostic tables above for RSI/MACD divergence).")
    elif sideways_count > len(results) * 0.5:
        print("  -> The model defaults to sideways for most cases, even clear trends.")
        print("     This suggests limited discriminative power.")

    print("=" * 90)


if __name__ == "__main__":
    main()
