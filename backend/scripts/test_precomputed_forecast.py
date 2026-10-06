import os
import sys
import time
import json
from datetime import date
from dotenv import load_dotenv

sys.stdout.reconfigure(encoding='utf-8')
load_dotenv("backend/.env")
os.environ.setdefault("SECRET_KEY", "a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6q7r8s9t0u1v2w3x4y5z6")
sys.path.insert(0, "backend")

from app.core.redis import get_sync_redis_client
from app.services.stock_service import StockService

print("=" * 80)
print("🚀 TESTING PRE-COMPUTED FORECAST & REDIS CACHE LATENCY VERIFICATION")
print("=" * 80)

redis_client = get_sync_redis_client()
stock_service = StockService()

# 1. Sample pre-computed forecast payload for KSE-100 symbol (e.g. TRG, SYS, OGDC)
test_sym = "TRG"
live_quote = stock_service.get_quote(test_sym) or {}
curr_price = float(live_quote.get("current") or live_quote.get("ldcp") or 95.0)

sample_forecast_payload = {
    "symbol": test_sym,
    "horizon": "1W",
    "horizon_label": "1-Week (5 Trading Days)",
    "trading_days": 5,
    "direction": "bullish",
    "confidence": 0.645,
    "probabilities": {"bullish": 64.5, "bearish": 20.5, "sideways": 15.0},
    "as_of_date": date.today().isoformat(),
    "as_of_label": date.today().strftime("%a, %b %d, %Y"),
    "target_date": (date.today()).isoformat(),
    "target_label": "Target by next week",
    "market_status": "open",
    "current_price": curr_price,
    "target_price": round(curr_price * 1.08, 2),
    "expected_range": {"low": round(curr_price * 0.96, 2), "high": round(curr_price * 1.08, 2), "method": "atr_band"},
    "stop_loss": round(curr_price * 0.96, 2),
    "signal_rating": "Strong Buy",
    "upside_pct": 8.0,
    "downside_pct": -4.0,
    "risk_reward_ratio": 2.0,
    "price_target_rationale": "Target price and stop-loss pre-computed via dual-model ensemble (Attention-BiGRU + XGBoost).",
    "model_version": "ensemble",
    "gate_reason": "consensus_agree(bullish)",
    "models": {
        "gru": {"direction": "bullish", "bullish_pct": 66.0, "bearish_pct": 19.0, "sideways_pct": 15.0, "gap_pp": 47.0},
        "xgb": {"direction": "bullish", "bullish_pct": 63.0, "bearish_pct": 22.0, "sideways_pct": 15.0, "gap_pp": 41.0},
    }
}

# 2. Write pre-computed forecast to Redis with 24h TTL
key = f"forecast:stock:v2:{test_sym}:1W"
redis_client.set(key, json.dumps(sample_forecast_payload), ex=86400)
print(f"✅ Stored pre-computed forecast for {test_sym} in Redis: key '{key}' (TTL: 86,400s)")

# 3. Benchmark cache-hit retrieval latency
t0 = time.perf_counter()
raw = redis_client.get(key)
lat_redis = (time.perf_counter() - t0) * 1000.0
cached_data = json.loads(raw)

# 4. Simulate real-time dynamic quote overlay (e.g. price ticks during market hours)
live_tick_price = round(curr_price * 1.015, 2)
cached_data["current_price"] = live_tick_price
tp = cached_data["target_price"]
sl = cached_data["stop_loss"]
cached_data["upside_pct"] = round((tp - live_tick_price) / live_tick_price * 100, 2)
cached_data["downside_pct"] = round((sl - live_tick_price) / live_tick_price * 100, 2)

print(f"\n[CACHE HIT TEST] {test_sym} retrieved in: {lat_redis:.2f} ms")
print(f"  • Pre-computed Model Signal:  {cached_data['direction'].upper()} ({cached_data['signal_rating']})")
print(f"  • Confidence:                 {cached_data['confidence']*100:.1f}%")
print(f"  • Pre-computed Target Price:  PKR {cached_data['target_price']}")
print(f"  • Real-time Live Price:       PKR {cached_data['current_price']}")
print(f"  • Dynamic Live Upside:        {cached_data['upside_pct']:+.2f}%")
print(f"  • Dynamic Live Downside:      {cached_data['downside_pct']:+.2f}%")

# 5. Check fundamentals and technicals Redis cache latency
t0 = time.perf_counter()
fund_raw = redis_client.get(f"fund:v23:{test_sym}") or redis_client.get(f"stocks:{test_sym}:fundamentals")
lat_fund = (time.perf_counter() - t0) * 1000.0

t0 = time.perf_counter()
tech_raw = redis_client.get(f"tech:v1:{test_sym}") or redis_client.get(f"stocks:{test_sym}:technicals")
lat_tech = (time.perf_counter() - t0) * 1000.0

print(f"\n[BENCHMARK VERIFICATION]")
print(f"  • Fundamentals Redis Latency: {lat_fund:.2f} ms (Found: {bool(fund_raw)})")
print(f"  • Technicals Redis Latency:   {lat_tech:.2f} ms (Found: {bool(tech_raw)})")
print(f"  • Pre-computed Forecast:      {lat_redis:.2f} ms (Found: {bool(raw)})")
print("=" * 80)
