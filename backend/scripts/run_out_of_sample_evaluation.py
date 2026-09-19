import json
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import spearmanr
import xgboost as xgb

ROOT = Path("backend")
DATA_PATH = ROOT / "data" / "features" / "features_daily.parquet"
MODEL_PATH = ROOT / "models" / "final" / "final_v3" / "xgb_model.ubj"
FEAT_PATH = ROOT / "models" / "final" / "final_v3" / "xgb_features.json"

print("--- Loading Out-of-Sample Historical Data & Model ---")
model = xgb.XGBClassifier()
model.load_model(str(MODEL_PATH))
features_list = json.loads(FEAT_PATH.read_text())

df = pd.read_parquet(DATA_PATH)
df["date"] = pd.to_datetime(df["date"])
df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

# Filter for test period: July 2025 to September 2026 (Out-of-Sample)
test_df = df[df["date"] >= "2025-07-01"].copy().reset_index(drop=True)
test_df = test_df.dropna(subset=["actual_5d_return"] + features_list)

print(f"Test Period: {str(test_df['date'].min())[:10]} to {str(test_df['date'].max())[:10]}")
print(f"Total Test Observations: {len(test_df)} across {test_df['symbol'].nunique()} stocks")

# Predict on all test observations
X_test = test_df[features_list].values.astype(np.float32)
probs = model.predict_proba(X_test)
test_df["pred_score"] = probs[:, 0]  # P(Buy / Top Quintile)

# 1. Daily Cross-Sectional Information Coefficient (Rank IC)
daily_ics = []
for d, grp in test_df.groupby("date"):
    if len(grp) >= 15:
        ic, _ = spearmanr(grp["pred_score"], grp["actual_5d_return"])
        if not np.isnan(ic):
            daily_ics.append(ic)

mean_ic = np.mean(daily_ics)
ic_std = np.std(daily_ics)
ir = mean_ic / (ic_std + 1e-6) * np.sqrt(52)  # Annualized IR
hit_rate_ic = np.mean([1 for x in daily_ics if x > 0]) * 100.0

print(f"\n--- Cross-Sectional Ranking Metrics (5-Day Horizon) ---")
print(f"Mean Rank IC:            {mean_ic*100:+.2f}%")
print(f"Information Ratio (IR):  {ir:+.2f}")
print(f"Positive IC Days %:      {hit_rate_ic:.1f}%")

# 2. Quintile Portfolio Spread Analysis
# Top 20% (Long) vs Bottom 20% (Short) per day
top_returns = []
bot_returns = []
market_returns = []

for d, grp in test_df.groupby("date"):
    if len(grp) >= 20:
        q_high = grp["pred_score"].quantile(0.80)
        q_low = grp["pred_score"].quantile(0.20)
        top_picks = grp[grp["pred_score"] >= q_high]
        bot_picks = grp[grp["pred_score"] <= q_low]
        top_returns.append(top_picks["actual_5d_return"].mean())
        bot_returns.append(bot_picks["actual_5d_return"].mean())
        market_returns.append(grp["actual_5d_return"].mean())

avg_top = np.mean(top_returns) * 100
avg_bot = np.mean(bot_returns) * 100
avg_mkt = np.mean(market_returns) * 100
spread = avg_top - avg_bot
win_rate_spread = np.mean([1 for t, b in zip(top_returns, bot_returns) if t > b]) * 100

print(f"\n--- Quintile Portfolio Performance ---")
print(f"Top Quintile (Model Long):   {avg_top:+.2f}% avg 5-day return")
print(f"Market Average Benchmark:    {avg_mkt:+.2f}% avg 5-day return")
print(f"Bottom Quintile (Model Avoid):{avg_bot:+.2f}% avg 5-day return")
print(f"Long-Short Alpha Spread:     {spread:+.2f}% per 5-day holding period")
print(f"Alpha Win Rate (Top > Bottom): {win_rate_spread:.1f}%\n")
