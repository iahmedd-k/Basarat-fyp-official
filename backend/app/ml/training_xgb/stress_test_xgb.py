"""
XGBoost v1 Weighted — Momentum Stress Test
============================================
Runs the same 7-symbol stress test as momentum_stress_test.py against
the xgb_v1_weighted model, for direct comparison with gru_v1.

No scaler needed — XGBoost is tree-based, uses raw feature values.
GRU v1 results are taken from the earlier momentum_stress_test.py run
(saved in the conversation log) to avoid requiring TensorFlow locally.
"""

import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBClassifier

# ── Config ─────────────────────────────────────────────────────────────
TEST_SYMBOLS = {
    "AICL": {"known_trend": "up",   "known_return": "+12.5%", "notes": "Strong upward"},
    "IBFL": {"known_trend": "down", "known_return": "~+10%",  "notes": "Downward (verified actual)"},
    "MTL":  {"known_trend": "up",   "known_return": "~+5%",   "notes": "Mild upward"},
    "CHCC": {"known_trend": "down", "known_return": "-17.17%","notes": "Strong downward"},
    "UBL":  {"known_trend": "down", "known_return": "-10.37%","notes": "Downward"},
    "PABC": {"known_trend": "down", "known_return": "-7.51%", "notes": "Downward"},
    "MLCF": {"known_trend": "down", "known_return": "-7.81%", "notes": "Downward"},
}

TREND_START = pd.Timestamp("2026-08-18")
TREND_END = pd.Timestamp("2026-09-15")

# GRU v1 results — ACTUAL predictions from Docker (TF available)
# Ran via: docker exec basarat-api python _gru_stress.py
# as_of_date for ALL symbols: 2026-09-11 (latest available)
GRU_V1_RESULTS = {
    "AICL": {"direction": "bullish",  "confidence": 35.0, "bullish_pct": 35.0, "bearish_pct": 31.2, "sideways_pct": 33.9},
    "IBFL": {"direction": "bullish",  "confidence": 36.6, "bullish_pct": 36.6, "bearish_pct": 28.3, "sideways_pct": 35.1},
    "MTL":  {"direction": "sideways", "confidence": 64.1, "bullish_pct": 20.0, "bearish_pct": 16.0, "sideways_pct": 64.1},
    "CHCC": {"direction": "bullish",  "confidence": 38.0, "bullish_pct": 38.0, "bearish_pct": 25.7, "sideways_pct": 36.4},
    "UBL":  {"direction": "sideways", "confidence": 50.6, "bullish_pct": 28.4, "bearish_pct": 21.0, "sideways_pct": 50.6},
    "PABC": {"direction": "bullish",  "confidence": 37.0, "bullish_pct": 37.0, "bearish_pct": 26.7, "sideways_pct": 36.3},
    "MLCF": {"direction": "bearish",  "confidence": 34.2, "bullish_pct": 32.6, "bearish_pct": 34.2, "sideways_pct": 33.2},
}


def main():
    # ── Load XGBoost weighted model (no scaler needed) ──────────────────
    model = XGBClassifier()
    model.load_model("models/xgb_v1/xgb_v1_weighted.xgb")
    print("Loaded models/xgb_v1/xgb_v1_weighted.xgb")
    print("No scaler required (tree-based model, raw feature values)")

    # Get feature names from importance file (same order as training)
    feat_imp = json.loads(
        Path("data/reports/xgb_feature_importance_weighted.json").read_text(encoding="utf-8")
    )
    feature_names = list(feat_imp.keys())
    print(f"Feature count: {len(feature_names)}")

    # ── Load data ───────────────────────────────────────────────────────
    xgb_df = pd.read_parquet("data/processed/features_xgb.parquet")
    xgb_df["date"] = pd.to_datetime(xgb_df["date"])

    ohlcv = pd.read_parquet("data/raw/ohlcv/all_symbols.parquet")
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])
    for col in ["open", "high", "low", "close", "volume"]:
        ohlcv[col] = pd.to_numeric(ohlcv[col], errors="coerce")

    xgb_label_names = {0: "bullish", 1: "bearish", 2: "sideways"}

    # ── XGBoost inference ───────────────────────────────────────────────
    def xgb_predict_at_date(symbol, as_of_date):
        rows = xgb_df[(xgb_df["symbol"] == symbol) &
                      (xgb_df["date"].dt.date == as_of_date)]
        if rows.empty:
            return None
        row = rows.iloc[0]
        feat_values = []
        for fname in feature_names:
            val = row.get(fname, 0.0)
            feat_values.append(float(val) if not pd.isna(val) else 0.0)
        X_pred = np.array([feat_values], dtype=np.float32)
        proba = model.predict_proba(X_pred)[0]
        pred = int(np.argmax(proba))
        pct_map = {
            "bullish": round(float(proba[0]) * 100, 1),
            "bearish": round(float(proba[1]) * 100, 1),
            "sideways": round(float(proba[2]) * 100, 1),
        }
        from app.ml.serving.inference import compute_confidence
        return {
            "direction": xgb_label_names.get(pred, "unknown"),
            "confidence": round(compute_confidence(pct_map), 1),
            "bullish_pct": pct_map["bullish"],
            "bearish_pct": pct_map["bearish"],
            "sideways_pct": pct_map["sideways"],
        }

    def compute_actual_return(symbol):
        s = ohlcv[ohlcv["symbol"] == symbol].copy()
        s = s.sort_values("date").reset_index(drop=True)
        s["date_only"] = s["date"].dt.date
        trend_start = TREND_START.date()
        trend_end = TREND_END.date()
        after = s[s["date_only"] >= trend_start]
        before = s[s["date_only"] <= trend_end]
        if after.empty or before.empty:
            return None, None, None
        a_start = after["date_only"].iloc[0]
        s_close = float(after.iloc[0]["close"])
        a_end = before["date_only"].iloc[-1]
        e_close = float(before.iloc[-1]["close"])
        return (e_close - s_close) / s_close, a_start, a_end

    # ── Run tests ───────────────────────────────────────────────────────
    results = []

    print()
    print("=" * 100)
    print("  MOMENTUM STRESS TEST — xgb_v1_weighted vs gru_v1")
    print("  Same 7 symbols, same dates, same methodology")
    print("=" * 100)

    for symbol, info in TEST_SYMBOLS.items():
        act_ret, act_start, act_end = compute_actual_return(symbol)
        available = sorted(xgb_df[xgb_df["symbol"] == symbol]["date"].dt.date.unique())
        latest_date = available[-1]

        xgb_pred = xgb_predict_at_date(symbol, latest_date)
        gru_pred = GRU_V1_RESULTS.get(symbol)

        known = info["known_trend"]

        def determine_match(pred_dir):
            if known == "up" and pred_dir == "bullish":
                return "YES"
            if known == "down" and pred_dir == "bearish":
                return "YES"
            if pred_dir == "sideways":
                return "PARTIAL" if act_ret is not None and abs(act_ret) < 0.03 else "NO"
            return "NO"

        gru_match = determine_match(gru_pred["direction"]) if gru_pred else "N/A"
        xgb_match = determine_match(xgb_pred["direction"]) if xgb_pred else "N/A"
        act_str = f"{act_ret * 100:+.1f}%" if act_ret is not None else "N/A"
        act_range = f"({act_start} to {act_end})" if act_start and act_end else ""

        print()
        print(f"  {'=' * 90}")
        print(f"  {symbol}  |  Known: {info['notes']}  |  Actual: {act_str} {act_range}")
        print(f"  {'=' * 90}")
        if gru_pred:
            print(
                f"  GRU v1:       {gru_pred['direction']:>8}  conf={gru_pred['confidence']:.1f}%  "
                f"[B {gru_pred['bullish_pct']:.1f}% | S {gru_pred['sideways_pct']:.1f}% | R {gru_pred['bearish_pct']:.1f}%]  "
                f"Match({known}): {gru_match}"
            )
        if xgb_pred:
            print(
                f"  XGB weighted: {xgb_pred['direction']:>8}  conf={xgb_pred['confidence']:.1f}%  "
                f"[B {xgb_pred['bullish_pct']:.1f}% | S {xgb_pred['sideways_pct']:.1f}% | R {xgb_pred['bearish_pct']:.1f}%]  "
                f"Match({known}): {xgb_match}"
            )

        results.append({
            "symbol": symbol,
            "known": known,
            "actual": act_ret,
            "gru": gru_pred["direction"] if gru_pred else "N/A",
            "gru_match": gru_match,
            "gru_conf": gru_pred["confidence"] if gru_pred else 0,
            "xgb": xgb_pred["direction"] if xgb_pred else "N/A",
            "xgb_match": xgb_match,
            "xgb_conf": xgb_pred["confidence"] if xgb_pred else 0,
        })

    # ── Side-by-side comparison table ───────────────────────────────────
    print()
    print("=" * 120)
    print("  SIDE-BY-SIDE COMPARISON TABLE")
    print("=" * 120)
    header = (
        f"  {'Symbol':<8} {'Known':>6} {'Actual':>9} "
        f"{'GRU pred':>10} {'GRU match':>9} {'GRU conf':>8} "
        f"{'XGB pred':>10} {'XGB match':>10} {'XGB conf':>8}"
    )
    sep = (
        f"  {'-'*8} {'-'*6} {'-'*9} "
        f"{'-'*10} {'-'*9} {'-'*8} "
        f"{'-'*10} {'-'*10} {'-'*8}"
    )
    print(header)
    print(sep)
    for r in results:
        act_s = f"{r['actual'] * 100:+.1f}%" if r.get("actual") is not None else "N/A"
        print(
            f"  {r['symbol']:<8} {r['known']:>6} {act_s:>9} "
            f"{r['gru']:>10} {r['gru_match']:>9} {r['gru_conf']:>7.1f}% "
            f"{r['xgb']:>10} {r['xgb_match']:>10} {r['xgb_conf']:>7.1f}%"
        )

    # ── Aggregate counts ────────────────────────────────────────────────
    uptrend = [r for r in results if r["known"] == "up"]
    downtrend = [r for r in results if r["known"] == "down"]

    gru_up = sum(1 for r in uptrend if r["gru_match"] == "YES")
    gru_down = sum(1 for r in downtrend if r["gru_match"] == "YES")
    xgb_up = sum(1 for r in uptrend if r["xgb_match"] == "YES")
    xgb_down = sum(1 for r in downtrend if r["xgb_match"] == "YES")

    print()
    print("=" * 120)
    print("  AGGREGATE MATCH COUNTS")
    print("=" * 120)
    print()
    print("  Uptrend (AICL, IBFL, MTL) -- correctly flagged BULLISH:")
    print(f"    GRU v1:       {gru_up}/3")
    print(f"    XGB weighted: {xgb_up}/3")
    print()
    print("  Downtrend (CHCC, UBL, PABC, MLCF) -- correctly flagged BEARISH:")
    print(f"    GRU v1:       {gru_down}/4")
    print(f"    XGB weighted: {xgb_down}/4")
    print()
    gru_total = gru_up + gru_down
    xgb_total = xgb_up + xgb_down
    total = len(uptrend) + len(downtrend)
    print("  TOTAL:")
    print(f"    GRU v1:       {gru_total}/{total} ({gru_total / total * 100:.0f}%)")
    print(f"    XGB weighted: {xgb_total}/{total} ({xgb_total / total * 100:.0f}%)")
    print("=" * 120)


if __name__ == "__main__":
    main()
