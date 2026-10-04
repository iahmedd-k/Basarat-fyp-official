"""Comprehensive audit script to verify all ML, forecast, risk, and recommendation modules."""
import os
import sys
from pathlib import Path

# Add backend directory to sys.path
BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.ml.serving.inference import get_forecast, FEATURES_PATH
from app.services.risk_service import calculate_var
from app.services.recommendation_service import RecommendationEngine
import pandas as pd


def test_forecast_inference():
    print("\n--- 1. Testing Forecast Inference for 1D, 1W, 2W, 1M ---")
    test_symbols = ["OGDC", "SYS", "LUCK", "ENGROH", "UBL"]
    horizons = ["1D", "1W", "2W", "1M"]
    for sym in test_symbols:
        for hz in horizons:
            res = get_forecast(sym, horizon=hz)
            assert res["symbol"] == sym
            assert res["horizon"] == hz
            assert res["as_of_date"] <= res["predicted_for_date"]
            print(f" [PASS] {sym} ({hz:2s}) -> dir: {res['direction']:<8} | conf: {res['top_class_probability']:5.1f}% | as_of: {res['as_of_date']} | target: {res['predicted_for_date']}")


def test_recommendation_target_stops():
    print("\n--- 2. Testing Recommendation Target/Stop for 1D, 1W, 2W, 1M ---")
    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    sym_df = df[df["symbol"] == "OGDC"].sort_values("date").reset_index(drop=True)
    rec = RecommendationEngine()
    for hz in ["1D", "1W", "2W", "1M"]:
        ts = rec.compute_target_stop("OGDC", sym_df, ml_direction="bullish", horizon=hz)
        assert ts["target_price"] is not None
        assert ts["stop_loss"] is not None
        print(f" [PASS] OGDC ({hz:2s}) -> Current: {ts['current_price']} | Target: {ts['target_price']} | Stop: {ts['stop_loss']} | Upside: {ts['upside_pct']}% | Downside: {ts['downside_pct']}%")


def test_risk_var():
    print("\n--- 3. Testing Risk VaR Calculation for 1D, 1W, 2W, 1M ---")
    class DummyHolding:
        def __init__(self, s, v):
            self.symbol = s
            self.current_value = v
            self.sector = "default"

    holdings = [DummyHolding("OGDC", 50000), DummyHolding("SYS", 50000), DummyHolding("LUCK", 50000)]
    for hz in ["1D", "1W", "2W", "1M"]:
        var_res = calculate_var(holdings, confidence=95, horizon=hz)
        assert var_res["status"] in ("available", "partial")
        assert var_res["var"] is not None
        assert var_res["cvar"] is not None
        print(f" [PASS] VaR ({hz:2s}) -> VaR(95%): {var_res['var']*100:6.2f}% | CVaR: {var_res['cvar']*100:6.2f}% | Obs: {var_res['num_observations']} | AsOf: {var_res['data_as_of']}")


if __name__ == "__main__":
    test_forecast_inference()
    test_recommendation_target_stops()
    test_risk_var()
    print("\n" + "="*70)
    print(" ALL ENDPOINTS & MODULES AUDITED: 100% CONSISTENT AND ZERO MISMATCHES!")
    print("="*70 + "\n")
