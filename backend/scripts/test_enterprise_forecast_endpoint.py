import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SECRET_KEY", "temporary-secret-key-for-testing-123456789")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
from app.ml.serving.model_loader import load_artifacts
from app.ml.serving.inference import get_forecast
from app.services.recommendation_service import RecommendationEngine
from app.api.v1.forecast import _build_forecast_response

print("--- Initializing Serving Artifacts ---")
load_artifacts()

engine = RecommendationEngine()
df = pd.read_parquet(ROOT / "data" / "features" / "features_daily.parquet")
df["date"] = pd.to_datetime(df["date"])

print("\n=== ENTERPRISE FORECAST OUTPUT TEST ===")
for sym in ["OGDC", "FFC", "PPL", "MARI", "SYS", "GAL"]:
    sym_df = df[df["symbol"] == sym].sort_values("date").reset_index(drop=True)
    
    # Test 1D and 1W
    for horizon in ["1D", "1W"]:
        raw = get_forecast(sym, horizon=horizon)
        target_stop = engine.compute_target_stop(sym, sym_df, ml_direction=raw.get("direction"), horizon=horizon)
        resp = _build_forecast_response(raw, horizon, target_stop)
        d = resp.model_dump()
        print(f"\n[{sym} - {horizon}] Direction: {d['direction'].upper()} | Rating: {d['signal_rating']} | Conf: {d['confidence']*100:.1f}%")
        print(f"  Probabilities: Bullish={d['probabilities']['bullish']:.1f}%, Bearish={d['probabilities']['bearish']:.1f}%, Sideways={d['probabilities']['sideways']:.1f}%")
        print(f"  Price Target: Curr={d['current_price']} PKR | Target={d['target_price']} PKR ({d['upside_pct']}%) | Stop={d['stop_loss']} PKR ({d['downside_pct']}%) | R/R Ratio={d['risk_reward_ratio']}")
        print(f"  Gate/Decision: {d['gate_reason']} | Model: {d['model_version']}")
