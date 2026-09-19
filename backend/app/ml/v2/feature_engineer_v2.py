"""
Feature Engineering Engine v2 for Basarat PSX Forecasting Pipeline.
Constructs 100% stationary, scale-invariant technical, market-regime, and volatility features
across all active PSX equities for the full 2020-2026 history.
"""

from pathlib import Path
import json
import logging
import numpy as np
import pandas as pd

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("feature_engineer_v2")

ROOT_DIR = Path(__file__).resolve().parents[3]
RAW_FEATURES_PATH = ROOT_DIR / "data" / "features" / "features_daily.parquet"
OUTPUT_DIR = ROOT_DIR / "data" / "processed_v2"
OUTPUT_PARQUET = OUTPUT_DIR / "features_v2.parquet"
OUTPUT_METADATA = OUTPUT_DIR / "v2_features_metadata.json"


def build_v2_features() -> pd.DataFrame:
    log.info("Loading base dataset from %s", RAW_FEATURES_PATH)
    df = pd.read_parquet(RAW_FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)
    log.info("Loaded %d rows across %d symbols from %s to %s",
             len(df), df["symbol"].nunique(), df["date"].min().strftime("%Y-%m-%d"), df["date"].max().strftime("%Y-%m-%d"))

    # 1. Stationary Scale-Invariant Price Geometries
    log.info("Engineering scale-invariant technical ratios...")
    df["dist_sma20"] = df["close"] / (df["sma_20"] + 1e-6) - 1.0
    df["dist_sma50"] = df["close"] / (df["sma_50"] + 1e-6) - 1.0
    df["dist_ema12"] = df["close"] / (df["ema_12"] + 1e-6) - 1.0
    df["dist_ema26"] = df["close"] / (df["ema_26"] + 1e-6) - 1.0

    # Bollinger Bands Position and Width
    bb_range = df["bb_upper"] - df["bb_lower"]
    df["bb_pct_b"] = np.where(bb_range > 1e-6, (df["close"] - df["bb_lower"]) / bb_range, 0.50)
    df["bb_width"] = np.where(df["bb_mid"] > 1e-6, bb_range / df["bb_mid"], 0.05)

    # Volatility and Bar Range Normalizations
    df["norm_atr14"] = df["atr_14"] / (df["close"] + 1e-6)
    df["hl_range"] = (df["high"] - df["low"]) / (df["close"] + 1e-6)
    df["co_range"] = (df["close"] - df["open"]) / (df["open"] + 1e-6)

    # Normalized Oscillators
    df["rsi_norm"] = (df["rsi_14"] - 50.0) / 50.0
    df["macd_norm"] = df["macd"] / (df["close"] + 1e-6)
    df["macd_hist_norm"] = df["macd_hist"] / (df["close"] + 1e-6)

    # Return series (log returns)
    log_ret = np.log(df["close"] / (df.groupby("symbol")["close"].shift(1) + 1e-6))
    df["log_return"] = log_ret.fillna(0.0)
    df["ret_1d"] = df["close"] / (df.groupby("symbol")["close"].shift(1) + 1e-6) - 1.0
    df["ret_2d"] = df["close"] / (df.groupby("symbol")["close"].shift(2) + 1e-6) - 1.0
    df["ret_3d"] = df["close"] / (df.groupby("symbol")["close"].shift(3) + 1e-6) - 1.0
    df["ret_5d"] = df["close"] / (df.groupby("symbol")["close"].shift(5) + 1e-6) - 1.0
    df["ret_10d"] = df["close"] / (df.groupby("symbol")["close"].shift(10) + 1e-6) - 1.0
    df["ret_20d"] = df["close"] / (df.groupby("symbol")["close"].shift(20) + 1e-6) - 1.0

    # Multi-horizon rolling volatility
    df["volatility_10d"] = df.groupby("symbol")["log_return"].transform(lambda s: s.rolling(10, min_periods=5).std()).fillna(0.02)
    df["volatility_20d"] = df.groupby("symbol")["log_return"].transform(lambda s: s.rolling(20, min_periods=10).std()).fillna(0.02)
    df["volatility_30d"] = df.groupby("symbol")["log_return"].transform(lambda s: s.rolling(30, min_periods=15).std()).fillna(0.02)
    df["volatility_60d"] = df.groupby("symbol")["log_return"].transform(lambda s: s.rolling(60, min_periods=30).std()).fillna(0.02)

    # Volume Z-score and Changes
    df["volume_zscore_20"] = np.clip(df["volume_zscore_20"].fillna(0.0), -3.0, 3.0)
    vol_shift5 = df.groupby("symbol")["volume"].shift(5)
    vol_shift10 = df.groupby("symbol")["volume"].shift(10)
    vol_shift20 = df.groupby("symbol")["volume"].shift(20)
    df["volume_change_5d"] = np.clip((df["volume"] - vol_shift5) / (vol_shift5 + 1.0), -1.0, 5.0).fillna(0.0)
    df["volume_change_10d"] = np.clip((df["volume"] - vol_shift10) / (vol_shift10 + 1.0), -1.0, 5.0).fillna(0.0)
    df["volume_change_20d"] = np.clip((df["volume"] - vol_shift20) / (vol_shift20 + 1.0), -1.0, 5.0).fillna(0.0)

    # 2. Market-Wide Breadth & Macro Context
    log.info("Computing market breadth and index regime features...")
    # Market breadth: % of stocks with close > sma_20 on each date
    df["above_sma20"] = (df["close"] > df["sma_20"]).astype(float)
    breadth = df.groupby("date")["above_sma20"].mean().rename("market_breadth_20d")
    df = df.merge(breadth, on="date", how="left")

    # Relative return vs market
    df["index_return_5d"] = df["index_return_5d"].fillna(0.0)
    df["index_return_20d"] = df["index_return_20d"].fillna(0.0)
    df["index_return_10d"] = df.groupby("symbol")["index_return_5d"].rolling(2, min_periods=1).mean().reset_index(level=0, drop=True).fillna(0.0)
    df["rel_to_index_5d"] = (df["ret_5d"] - df["index_return_5d"]).fillna(0.0)
    df["rel_to_index_10d"] = (df["ret_10d"] - df["index_return_10d"]).fillna(0.0)
    df["rel_to_index_20d"] = (df["ret_20d"] - df["index_return_20d"]).fillna(0.0)

    # Macro interest rates & FX normalized
    df["policy_rate_norm"] = (df["policy_rate"].fillna(17.5) - 15.0) / 10.0
    pkr_ret_20d = df.groupby("symbol")["pkr_usd_rate"].pct_change(20).fillna(0.0)
    df["pkr_usd_ret_20d"] = pkr_ret_20d

    # Symbol Categorical ID
    symbols = sorted(df["symbol"].unique())
    symbol_to_id = {sym: idx for idx, sym in enumerate(symbols)}
    df["symbol_id"] = df["symbol"].map(symbol_to_id)

    # 3. Forward Targets & Adaptive Volatility Bands
    log.info("Constructing forward 5-day return targets...")
    df["close_t5"] = df.groupby("symbol")["close"].shift(-5)
    df["actual_5d_return"] = (df["close_t5"] - df["close"]) / (df["close"] + 1e-6)

    # Standard fixed +-1.0% labels
    df["target_fixed_class"] = np.where(
        df["actual_5d_return"] > 0.01, 0,  # bullish
        np.where(df["actual_5d_return"] < -0.01, 1, 2)  # bearish, sideways
    )

    # Volatility-adaptive threshold: tau = clip(0.40 * norm_atr14 * sqrt(5), 0.015, 0.035)
    df["adaptive_tau"] = np.clip(0.40 * df["norm_atr14"] * np.sqrt(5), 0.015, 0.035)
    df["target_adaptive_class"] = np.where(
        df["actual_5d_return"] > df["adaptive_tau"], 0,
        np.where(df["actual_5d_return"] < -df["adaptive_tau"], 1, 2)
    )

    # Clip any residual infinities or outliers
    num_cols = [c for c in df.columns if c not in ["symbol", "date", "target_fixed_class", "target_adaptive_class", "symbol_id"]]
    df[num_cols] = df[num_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUTPUT_PARQUET, index=False)
    log.info("Saved v2 features parquet -> %s (%d rows, %d cols)", OUTPUT_PARQUET, len(df), len(df.columns))

    v2_gru_features = [
        "dist_sma20", "dist_sma50", "dist_ema12", "dist_ema26",
        "bb_pct_b", "bb_width", "norm_atr14", "hl_range", "co_range",
        "rsi_norm", "macd_norm", "macd_hist_norm",
        "log_return", "ret_1d", "ret_2d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
        "volatility_10d", "volatility_20d", "volatility_30d", "volatility_60d",
        "volume_zscore_20", "volume_change_5d", "volume_change_10d", "volume_change_20d",
        "market_breadth_20d", "rel_to_index_5d", "rel_to_index_10d", "rel_to_index_20d",
        "index_return_5d", "index_return_10d", "index_return_20d",
        "policy_rate_norm", "pkr_usd_ret_20d"
    ]

    v2_xgb_features = [
        "dist_sma20", "dist_sma50", "dist_ema12", "dist_ema26",
        "bb_pct_b", "bb_width", "norm_atr14", "hl_range", "co_range",
        "rsi_norm", "macd_norm", "macd_hist_norm",
        "ret_1d", "ret_2d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
        "volatility_10d", "volatility_20d", "volatility_30d", "volatility_60d",
        "volume_zscore_20", "volume_change_5d", "volume_change_10d", "volume_change_20d",
        "market_breadth_20d", "rel_to_index_5d", "rel_to_index_20d",
        "index_return_5d", "index_return_20d", "policy_rate_norm", "pkr_usd_ret_20d",
        "symbol_id"
    ]

    metadata = {
        "dataset_rows": len(df),
        "unique_symbols": df["symbol"].nunique(),
        "date_min": df["date"].min().strftime("%Y-%m-%d"),
        "date_max": df["date"].max().strftime("%Y-%m-%d"),
        "gru_features": v2_gru_features,
        "gru_feature_count": len(v2_gru_features),
        "xgb_features": v2_xgb_features,
        "xgb_feature_count": len(v2_xgb_features),
        "symbol_map": symbol_to_id
    }

    with open(OUTPUT_METADATA, "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("Saved v2 feature metadata -> %s", OUTPUT_METADATA)

    return df


if __name__ == "__main__":
    build_v2_features()
