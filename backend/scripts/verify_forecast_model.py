import sys
from pathlib import Path
sys.path.insert(0, str(Path.cwd() / "backend"))

from app.ml.serving.model_loader import load_artifacts, artifacts
from app.ml.serving.inference import get_forecast

print("--- Loading Artifacts ---")
load_artifacts()
print(f"GRU ready: {artifacts.model_ready}")
print(f"XGB ready: {artifacts.xgb_ready}")
print(f"XGB model version: {artifacts.xgb_model_version}")
print(f"XGB features count: {len(artifacts.xgb_feature_names)}")

print("\n--- Running Forecast Endpoint Live Inference ---")
for sym in ["OGDC", "FFC", "PPL", "MARI", "SYS", "PSO", "DGKC", "LUCK", "HUBC", "ENGROH"]:
    try:
        res = get_forecast(sym)
        d = res["direction"]
        top_p = res["top_class_probability"]
        bull = res["bullish_pct"]
        bear = res["bearish_pct"]
        side = res["sideways_pct"]
        mv = res["model_version"]
        gate = res.get("gate_reason", "")
        print(f"Stock: {sym:6s} | Direction: {d:10s} | Conf: {top_p:4.1f}% | Bullish: {bull:4.1f}% | Bearish: {bear:4.1f}% | Sideways: {side:4.1f}% | Model: {mv} | Gate: {gate}")
    except Exception as e:
        print(f"Stock: {sym:6s} | Error: {e}")
