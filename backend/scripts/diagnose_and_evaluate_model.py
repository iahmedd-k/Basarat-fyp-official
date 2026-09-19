import json
from pathlib import Path
import numpy as np
import pandas as pd
import xgboost as xgb

# 1. Load Data and Model
ROOT = Path("backend")
DATA_PATH = ROOT / "data" / "features" / "features_daily.parquet"
MODEL_PATH = ROOT / "models" / "final" / "final_v3" / "xgb_model.ubj"
FEAT_PATH = ROOT / "models" / "final" / "final_v3" / "xgb_features.json"

model = xgb.XGBClassifier()
model.load_model(str(MODEL_PATH))
features_list = json.loads(FEAT_PATH.read_text())

print("Model classes:", model.classes_)
print("Features expected:", len(features_list))

# Test with all 0.50
p_dummy = model.predict_proba(np.array([[0.50] * len(features_list)], dtype=np.float32))[0]
print(f"Prediction when feature vector is all 0.50 (median): Bullish={p_dummy[0]*100:.1f}%, Bearish={p_dummy[1]*100:.1f}%\n")

# 2. Compute full cross-sectional feature set for all 98 stocks up to Sep 17, 2026
df = pd.read_parquet(DATA_PATH)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

# 5-day Forward Target for evaluation
total_symbols = df["symbol"].nunique()
date_counts = df.groupby("date")["symbol"].nunique()
market_dates = date_counts[date_counts >= (total_symbols * 0.50)].index.sort_values()
market_date_map = {market_dates[i]: market_dates[i + 5] for i in range(len(market_dates) - 5)}
df["target_t5_date"] = df["date"].map(market_date_map)

price_dict = df.set_index(["symbol", "date"])[["close"]].to_dict("index")
t5_closes = [price_dict.get((s, dt), {}).get("close", np.nan) for s, dt in zip(df["symbol"], df["target_t5_date"])]
df["close_t5"] = t5_closes
df["actual_5d_return"] = (df["close_t5"] - df["close"]) / (df["close"] + 1e-6)

# Compute the 30 clean normalized features
df["daily_ret"] = df.groupby("symbol")["close"].pct_change()
df["traded_val"] = df["close"] * df["volume"]

rolling_52w = df.groupby("symbol")["high"].transform(lambda s: s.rolling(252, min_periods=50).max())
df["dist_52w_high"] = np.clip((df["close"] / (rolling_52w + 1e-6)) - 1.0, -0.90, 0.0)

ret_12m = df["close"] / (df.groupby("symbol")["close"].shift(252) + 1e-6) - 1.0
ret_1m = df["close"] / (df.groupby("symbol")["close"].shift(21) + 1e-6) - 1.0
df["mom_12m_1m"] = np.clip(ret_12m - ret_1m, -1.0, 3.0).fillna(0.0)

df["ret_1d"] = df["close"] / (df.groupby("symbol")["close"].shift(1) + 1e-6) - 1.0
df["ret_3d"] = df["close"] / (df.groupby("symbol")["close"].shift(3) + 1e-6) - 1.0
df["ret_5d"] = df["close"] / (df.groupby("symbol")["close"].shift(5) + 1e-6) - 1.0
df["ret_10d"] = df["close"] / (df.groupby("symbol")["close"].shift(10) + 1e-6) - 1.0
df["ret_20d"] = df["close"] / (df.groupby("symbol")["close"].shift(20) + 1e-6) - 1.0

df["amihud_illiquidity"] = np.clip(
    df.groupby("symbol")["daily_ret"].transform(lambda s: s.abs()).rolling(20, min_periods=5).mean() /
    (df.groupby("symbol")["traded_val"].transform(lambda s: s.rolling(20, min_periods=5).mean()) + 1e-4),
    0.0, 0.10
).fillna(0.0)

df["is_lower_circuit"] = (df["daily_ret"] <= -0.074).astype(np.float32)

df["volatility_10d"] = df.groupby("symbol")["daily_ret"].transform(lambda s: s.rolling(10, min_periods=5).std()).fillna(0.02)
df["volatility_20d"] = df.groupby("symbol")["daily_ret"].transform(lambda s: s.rolling(20, min_periods=10).std()).fillna(0.02)
df["volatility_60d"] = df.groupby("symbol")["daily_ret"].transform(lambda s: s.rolling(60, min_periods=20).std()).fillna(0.02)

prev_close = df.groupby("symbol")["close"].shift(1)
df["tr_temp"] = np.maximum(df["high"] - df["low"], np.maximum((df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()))
df["norm_atr14"] = np.clip(df.groupby("symbol")["tr_temp"].transform(lambda s: s.rolling(14, min_periods=5).mean()) / (df["close"] + 1e-6), 0.0, 0.20).fillna(0.02)
df["hl_range"] = (df["high"] - df["low"]) / (df["close"] + 1e-6)
df["co_range"] = (df["close"] - df["open"]) / (df["open"] + 1e-6)

sma20 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(20, min_periods=10).mean())
sma50 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(50, min_periods=20).mean())
df["dist_sma20"] = np.clip((df["close"] - sma20) / (sma20 + 1e-6), -0.50, 0.50)
df["dist_sma50"] = np.clip((df["close"] - sma50) / (sma50 + 1e-6), -0.50, 0.50)

ema12 = df.groupby("symbol")["close"].transform(lambda s: s.ewm(span=12, adjust=False).mean())
ema26 = df.groupby("symbol")["close"].transform(lambda s: s.ewm(span=26, adjust=False).mean())
df["dist_ema12"] = np.clip((df["close"] - ema12) / (ema12 + 1e-6), -0.50, 0.50)
df["dist_ema26"] = np.clip((df["close"] - ema26) / (ema26 + 1e-6), -0.50, 0.50)

std20 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(20, min_periods=10).std())
upper_bb = sma20 + 2 * std20
lower_bb = sma20 - 2 * std20
df["bb_pct_b"] = np.clip((df["close"] - lower_bb) / (upper_bb - lower_bb + 1e-6), -0.50, 1.50)
df["bb_width"] = np.clip((upper_bb - lower_bb) / (sma20 + 1e-6), 0.0, 1.0)

delta = df.groupby("symbol")["close"].diff()
df["gain_temp"] = delta.clip(lower=0)
df["loss_temp"] = -delta.clip(upper=0)
avg_gain = df.groupby("symbol")["gain_temp"].transform(lambda s: s.rolling(14, min_periods=5).mean())
avg_loss = df.groupby("symbol")["loss_temp"].transform(lambda s: s.rolling(14, min_periods=5).mean())
rs = avg_gain / (avg_loss + 1e-6)
rsi = 100 - (100 / (1 + rs))
df["rsi_norm"] = np.clip((rsi - 50.0) / 50.0, -1.0, 1.0)

macd_raw = ema12 - ema26
df["macd_raw_temp"] = macd_raw
macd_sig = df.groupby("symbol")["macd_raw_temp"].transform(lambda s: s.ewm(span=9, adjust=False).mean())
macd_hist_raw = macd_raw - macd_sig
df["macd_norm"] = np.clip(macd_raw / (df["close"] + 1e-6), -0.10, 0.10)
df["macd_hist_norm"] = np.clip(macd_hist_raw / (df["close"] + 1e-6), -0.05, 0.05)

vol_mean20 = df.groupby("symbol")["volume"].transform(lambda s: s.rolling(20, min_periods=5).mean())
vol_std20 = df.groupby("symbol")["volume"].transform(lambda s: s.rolling(20, min_periods=5).std())
df["volume_zscore_20"] = np.clip((df["volume"] - vol_mean20) / (vol_std20 + 1e-6), -3.0, 3.0)

df["vol_growth_5d"] = np.clip(df["volume"] / (df.groupby("symbol")["volume"].shift(5) + 1.0) - 1.0, -1.0, 5.0)
df["vol_growth_20d"] = np.clip(df["volume"] / (df.groupby("symbol")["volume"].shift(20) + 1.0) - 1.0, -1.0, 5.0)

df["rel_to_index_5d"] = np.clip(df["ret_5d"] - df["index_return_5d"].fillna(0.0), -0.50, 0.50)
df["rel_to_index_20d"] = np.clip(df["ret_20d"] - df["index_return_20d"].fillna(0.0), -0.50, 0.50)

if "pkr_usd_rate" in df.columns:
    df["pkr_usd_ret_20d"] = df["pkr_usd_rate"].pct_change(20).fillna(0.0)
else:
    df["pkr_usd_ret_20d"] = 0.0

# Cross-sectional ranking per day across all active stocks
raw_base_cols = [f.replace("_csrank", "") for f in features_list]
for col in raw_base_cols:
    df[f"{col}_csrank"] = df.groupby("date")[col].rank(pct=True).fillna(0.50)

# Save the enriched precalculated features so inference is instant & accurate!
df.to_parquet(ROOT / "data" / "features" / "features_daily.parquet", index=False)
print("Updated features_daily.parquet with all 30 precalculated cross-sectional ranks.\n")

# 3. Test on 17 Sep 2026 for the sampled stocks:
latest_date = df["date"].max()
latest_df = df[df["date"] == latest_date]
print(f"=== Model Predictions on {str(latest_date)[:10]} with Real Cross-Sectional Features ===")
sample_stocks = ["AGP", "SYS", "DGKC", "MLCF", "SSGC", "HBL", "EFERT", "LCI", "OGDC", "FFC", "PPL", "MARI", "GAL", "BAHL", "NBP", "POL", "SAZEW"]

for sym in sample_stocks:
    sym_rows = latest_df[latest_df["symbol"] == sym]
    if sym_rows.empty:
        print(f"Stock: {sym:6s} | Not found on {str(latest_date)[:10]}")
        continue
    r = sym_rows.iloc[0]
    vec = np.array([[r[f] for f in features_list]], dtype=np.float32)
    proba = model.predict_proba(vec)[0]
    p_buy = proba[0]
    p_sell = proba[1]
    bias = "STRONG BULLISH" if p_buy > 0.58 else "BULLISH" if p_buy > 0.52 else "STRONG BEARISH" if p_sell > 0.58 else "BEARISH" if p_sell > 0.52 else "NEUTRAL"
    print(f"Stock: {sym:6s} | Buy Prob: {p_buy*100:5.1f}% | Sell Prob: {p_sell*100:5.1f}% | Spread: {(p_buy-p_sell)*100:+5.1f}% | Bias: {bias}")
