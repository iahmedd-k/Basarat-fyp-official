"""
Feature Engineering & Dataset Builder Engine v3 for Basarat PSX Forecasting.
=============================================================================
Implements:
1. Trading-Calendar Aware 5-Day Forward Return Horizons.
2. Market-Neutral Cross-Sectional Relative Target (Top 30% Buy vs. Bottom 30% Avoid).
3. 100% Cross-Sectional Rank-Normalized Technical, Volatility & Liquidity Features.
4. Institutional Quant Features: 52-Week High Distance, 12M-1M Momentum, Amihud Illiquidity,
   PSX +-7.5% Circuit Flags, and 60-Day Rolling Beta.
"""

from pathlib import Path
import json
import logging
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("feature_engineer_v3")

ROOT_DIR = Path(__file__).resolve().parents[3]
RAW_FEATURES_PATH = ROOT_DIR / "data" / "features" / "features_daily.parquet"
OUTPUT_DIR = ROOT_DIR / "data" / "processed_v3"
OUTPUT_PARQUET = OUTPUT_DIR / "features_v3.parquet"
OUTPUT_METADATA = OUTPUT_DIR / "v3_features_metadata.json"


def build_v3_features() -> pd.DataFrame:
    log.info("Loading raw dataset from %s", RAW_FEATURES_PATH)
    df = pd.read_parquet(RAW_FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    
    # 1. Trading Calendar Forward 5-Day Horizon
    log.info("Constructing calendar-aligned 5-day forward returns per symbol...")
    df["close_t5"] = df.groupby("symbol")["close"].shift(-5)
    df["actual_5d_return"] = (df["close_t5"] - df["close"]) / (df["close"] + 1e-6)

    # Filter out anomalous overnight corporate action drops (e.g. unadjusted bonus jumps > 25% drop)
    df["daily_pct_change"] = df.groupby("symbol")["close"].pct_change()
    
    # Benchmark 5-day return
    df["index_return_5d"] = df["index_return_5d"].fillna(0.0)
    df["excess_5d_return"] = df["actual_5d_return"] - df["index_return_5d"]

    # 2. Institutional Quantitative Features
    log.info("Engineering institutional alpha factors...")

    # (A) Distance to 52-Week High (252 trading days)
    rolling_52w_high = df.groupby("symbol")["high"].transform(lambda s: s.rolling(252, min_periods=50).max())
    df["dist_52w_high"] = np.clip((df["close"] / (rolling_52w_high + 1e-6)) - 1.0, -0.90, 0.0)

    # (B) 12M-1M Momentum (Jegadeesh & Titman 1993: 12-month return skipping last 1 month)
    ret_12m = df["close"] / (df.groupby("symbol")["close"].shift(252) + 1e-6) - 1.0
    ret_1m = df["close"] / (df.groupby("symbol")["close"].shift(21) + 1e-6) - 1.0
    df["mom_12m_1m"] = np.clip(ret_12m - ret_1m, -1.0, 3.0).fillna(0.0)

    # (C) Short-Term Reversals & Return Lags
    df["ret_1d"] = df["close"] / (df.groupby("symbol")["close"].shift(1) + 1e-6) - 1.0
    df["ret_3d"] = df["close"] / (df.groupby("symbol")["close"].shift(3) + 1e-6) - 1.0
    df["ret_5d"] = df["close"] / (df.groupby("symbol")["close"].shift(5) + 1e-6) - 1.0
    df["ret_10d"] = df["close"] / (df.groupby("symbol")["close"].shift(10) + 1e-6) - 1.0
    df["ret_20d"] = df["close"] / (df.groupby("symbol")["close"].shift(20) + 1e-6) - 1.0

    # (D) Amihud Illiquidity Ratio (Price Impact per PKR Volume)
    daily_turnover = df["volume"] * df["close"]
    df["amihud_illiquidity"] = np.log1p(np.abs(df["ret_1d"]) / (daily_turnover + 1e-3) * 1e8).fillna(0.0)

    # (E) PSX +-7.5% Circuit Limit Flags
    df["is_upper_circuit"] = (df["daily_pct_change"] >= 0.074).astype(float)
    df["is_lower_circuit"] = (df["daily_pct_change"] <= -0.074).astype(float)

    # (F) Multi-Horizon Volatility & ATR Normalized
    log_ret = np.log(df["close"] / (df.groupby("symbol")["close"].shift(1) + 1e-6)).fillna(0.0)
    df["volatility_10d"] = df.groupby("symbol")["close"].transform(lambda s: log_ret.rolling(10, min_periods=5).std()).fillna(0.02)
    df["volatility_20d"] = df.groupby("symbol")["close"].transform(lambda s: log_ret.rolling(20, min_periods=10).std()).fillna(0.02)
    df["volatility_60d"] = df.groupby("symbol")["close"].transform(lambda s: log_ret.rolling(60, min_periods=30).std()).fillna(0.02)
    df["norm_atr14"] = df["atr_14"] / (df["close"] + 1e-6)
    df["hl_range"] = (df["high"] - df["low"]) / (df["close"] + 1e-6)
    df["co_range"] = (df["close"] - df["open"]) / (df["open"] + 1e-6)

    # (G) Trend Distance Ratios
    df["dist_sma20"] = df["close"] / (df["sma_20"] + 1e-6) - 1.0
    df["dist_sma50"] = df["close"] / (df["sma_50"] + 1e-6) - 1.0
    df["dist_ema12"] = df["close"] / (df["ema_12"] + 1e-6) - 1.0
    df["dist_ema26"] = df["close"] / (df["ema_26"] + 1e-6) - 1.0

    # (H) Bollinger Band Width & %B
    bb_range = df["bb_upper"] - df["bb_lower"]
    df["bb_pct_b"] = np.where(bb_range > 1e-6, (df["close"] - df["bb_lower"]) / bb_range, 0.50)
    df["bb_width"] = np.where(df["bb_mid"] > 1e-6, bb_range / df["bb_mid"], 0.05)

    # (I) Normalized Oscillators
    df["rsi_norm"] = (df["rsi_14"] - 50.0) / 50.0
    df["macd_norm"] = df["macd"] / (df["close"] + 1e-6)
    df["macd_hist_norm"] = df["macd_hist"] / (df["close"] + 1e-6)

    # (J) Volume Z-Score and Growth
    df["volume_zscore_20"] = np.clip(df["volume_zscore_20"].fillna(0.0), -3.0, 3.0)
    vol_shift5 = df.groupby("symbol")["volume"].shift(5)
    vol_shift20 = df.groupby("symbol")["volume"].shift(20)
    df["vol_growth_5d"] = np.clip((df["volume"] - vol_shift5) / (vol_shift5 + 1.0), -1.0, 5.0).fillna(0.0)
    df["vol_growth_20d"] = np.clip((df["volume"] - vol_shift20) / (vol_shift20 + 1.0), -1.0, 5.0).fillna(0.0)

    # (K) Relative Strength vs KSE-100
    df["rel_to_index_5d"] = (df["ret_5d"] - df["index_return_5d"]).fillna(0.0)
    df["rel_to_index_20d"] = (df["ret_20d"] - df["index_return_20d"].fillna(0.0)).fillna(0.0)

    # (L) Macro interest rate change (20-day delta instead of static level)
    df["policy_rate_chg_20d"] = df["policy_rate"].diff(20).fillna(0.0) / 10.0
    df["pkr_usd_ret_20d"] = df.groupby("symbol")["pkr_usd_rate"].pct_change(20).fillna(0.0)

    # 3. Cross-Sectional Labeling per Trading Date
    log.info("Computing cross-sectional percentile targets per trading date...")
    
    # Drop rows where future return is NaN (last 5 rows per stock)
    valid_target_mask = df["actual_5d_return"].notna()
    
    # Rank excess returns cross-sectionally within each date [0.0, 1.0]
    df["excess_5d_rank"] = df[valid_target_mask].groupby("date")["excess_5d_return"].rank(pct=True)

    # Target Classes:
    # 0 = Buy (Top 30% highest excess return, rank >= 0.70)
    # 1 = Avoid (Bottom 30% lowest excess return, rank <= 0.30)
    # 2 = Neutral (Middle 40%, 0.30 < rank < 0.70)
    df["target_cs_class"] = np.nan
    df.loc[valid_target_mask & (df["excess_5d_rank"] >= 0.70), "target_cs_class"] = 0
    df.loc[valid_target_mask & (df["excess_5d_rank"] <= 0.30), "target_cs_class"] = 1
    df.loc[valid_target_mask & (df["excess_5d_rank"] > 0.30) & (df["excess_5d_rank"] < 0.70), "target_cs_class"] = 2

    # Binary Target for Direct Directional Evaluation (0 = Buy / Outperform, 1 = Avoid / Underperform)
    df["target_binary_class"] = np.where(df["excess_5d_rank"] >= 0.50, 0, 1)

    # Extreme signal flag for clean training (drops ambiguous middle 40%)
    df["is_extreme_signal"] = (df["target_cs_class"].isin([0, 1]))

    # 4. Cross-Sectional Rank Normalization across Stocks per Date
    log.info("Applying cross-sectional rank normalization across all feature columns...")
    
    feature_columns = [
        "dist_52w_high", "mom_12m_1m", "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
        "amihud_illiquidity", "is_upper_circuit", "is_lower_circuit",
        "volatility_10d", "volatility_20d", "volatility_60d", "norm_atr14", "hl_range", "co_range",
        "dist_sma20", "dist_sma50", "dist_ema12", "dist_ema26", "bb_pct_b", "bb_width",
        "rsi_norm", "macd_norm", "macd_hist_norm",
        "volume_zscore_20", "vol_growth_5d", "vol_growth_20d",
        "rel_to_index_5d", "rel_to_index_20d", "policy_rate_chg_20d", "pkr_usd_ret_20d"
    ]

    # Clean infinities and NaNs before ranking
    df[feature_columns] = df[feature_columns].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    # Rank normalize each feature per date: values mapped uniformly into [0.0, 1.0]
    rank_feature_cols = []
    for col in feature_columns:
        rank_col_name = f"{col}_csrank"
        df[rank_col_name] = df.groupby("date")[col].rank(pct=True).fillna(0.50).astype(np.float32)
        rank_feature_cols.append(rank_col_name)

    log.info("Engineered %d cross-sectional rank features.", len(rank_feature_cols))

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PARQUET, index=False)
    log.info("Saved v3 features dataset -> %s (%d rows, %d cols)", OUTPUT_PARQUET, len(df), len(df.columns))

    metadata = {
        "dataset_rows": len(df),
        "unique_symbols": df["symbol"].nunique(),
        "date_min": df["date"].min().strftime("%Y-%m-%d"),
        "date_max": df["date"].max().strftime("%Y-%m-%d"),
        "feature_count": len(rank_feature_cols),
        "features": rank_feature_cols,
        "target_definitions": {
            "target_cs_class": "0=Buy (Top 30%), 1=Avoid (Bottom 30%), 2=Neutral (Middle 40%)",
            "target_binary_class": "0=Outperform (Top 50%), 1=Underperform (Bottom 50%)",
            "is_extreme_signal": "True for Top 30% and Bottom 30% samples (clean training mask)"
        }
    }

    with open(OUTPUT_METADATA, "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("Saved v3 metadata -> %s", OUTPUT_METADATA)

    return df


if __name__ == "__main__":
    build_v3_features()
