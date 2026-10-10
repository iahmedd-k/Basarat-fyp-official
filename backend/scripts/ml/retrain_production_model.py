"""Train an experimental binary cross-sectional Buy/Avoid ranking model.

This experiment is exported separately from the three-class final_v3 serving
artifacts created by ``run_ml_pipeline.py``.
"""

from pathlib import Path
import json
import logging
from datetime import datetime
import numpy as np
import pandas as pd
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("production_retraining")

ROOT_DIR = Path(__file__).resolve().parents[1]
RAW_DATA_PATH = ROOT_DIR / "data" / "features" / "features_daily.parquet"
MODEL_DIR = ROOT_DIR / "models" / "experiments" / "alpha_rank_binary_v1"
REPORTS_DIR = ROOT_DIR / "data" / "reports" / "experiments"


def retrain_and_export_production_model():
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Loading raw dataset from %s", RAW_DATA_PATH)
    raw_df = pd.read_parquet(RAW_DATA_PATH)
    raw_df["date"] = pd.to_datetime(raw_df["date"])
    raw_df = raw_df.sort_values(["symbol", "date"]).reset_index(drop=True)

    min_date = str(raw_df["date"].min())[:10]
    max_date = str(raw_df["date"].max())[:10]
    total_symbols = raw_df["symbol"].nunique()
    log.info("Dataset span: %s to %s (%d rows across %d symbols)", min_date, max_date, len(raw_df), total_symbols)

    # 1. Market Calendar
    date_counts = raw_df.groupby("date")["symbol"].nunique()
    market_dates = date_counts[date_counts >= (total_symbols * 0.50)].index.sort_values()
    log.info("Total market calendar trading days: %d", len(market_dates))

    market_date_map = {market_dates[i]: market_dates[i + 5] for i in range(len(market_dates) - 5)}
    raw_df["target_t5_date"] = raw_df["date"].map(market_date_map)

    price_dict = raw_df.set_index(["symbol", "date"])[["open", "close", "volume"]].to_dict("index")

    t5_closes = []
    for row in raw_df.itertuples():
        t5_dt = getattr(row, "target_t5_date")
        sym = getattr(row, "symbol")
        if pd.notna(t5_dt) and (sym, t5_dt) in price_dict:
            t5_closes.append(price_dict[(sym, t5_dt)]["close"])
        else:
            t5_closes.append(np.nan)

    raw_df["close_t5"] = t5_closes
    raw_df["actual_5d_return"] = (raw_df["close_t5"] - raw_df["close"]) / (raw_df["close"] + 1e-6)

    # 2. Liquidity Filter (Lagged 60-Day Median Traded Value)
    raw_df["daily_ret"] = raw_df.groupby("symbol")["close"].pct_change()
    raw_df["traded_val"] = raw_df["close"] * raw_df["volume"]
    raw_df["liq_60d"] = raw_df.groupby("symbol")["traded_val"].transform(lambda s: s.rolling(60, min_periods=20).median())
    raw_df["lagged_liq_60d"] = raw_df.groupby("symbol")["liq_60d"].shift(1)
    raw_df["is_primary_universe"] = raw_df.groupby("date")["lagged_liq_60d"].transform(lambda s: s >= s.median()).fillna(False)

    # 3. 30 Clean Normalized Features
    df = raw_df.copy()
    df["index_return_5d"] = df["index_return_5d"].fillna(0.0)
    df["excess_5d_return"] = df["actual_5d_return"] - df["index_return_5d"]

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
    df.drop(columns=["tr_temp"], inplace=True)

    sma20 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    sma50 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(50, min_periods=20).mean())
    ema12 = df.groupby("symbol")["close"].transform(lambda s: s.ewm(span=12, adjust=False).mean())
    ema26 = df.groupby("symbol")["close"].transform(lambda s: s.ewm(span=26, adjust=False).mean())

    df["dist_sma20"] = np.clip((df["close"] - sma20) / (sma20 + 1e-6), -0.50, 0.50).fillna(0.0)
    df["dist_sma50"] = np.clip((df["close"] - sma50) / (sma50 + 1e-6), -0.50, 0.50).fillna(0.0)
    df["dist_ema12"] = np.clip((df["close"] - ema12) / (ema12 + 1e-6), -0.50, 0.50).fillna(0.0)
    df["dist_ema26"] = np.clip((df["close"] - ema26) / (ema26 + 1e-6), -0.50, 0.50).fillna(0.0)

    bb_std20 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(20, min_periods=10).std()).fillna(1e-4)
    df["bb_pct_b"] = np.clip((df["close"] - (sma20 - 2 * bb_std20)) / (4 * bb_std20 + 1e-6), -0.50, 1.50).fillna(0.50)
    df["bb_width"] = np.clip((4 * bb_std20) / (sma20 + 1e-6), 0.0, 1.0).fillna(0.05)

    delta = df.groupby("symbol")["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.groupby(df["symbol"]).transform(lambda s: s.rolling(14, min_periods=5).mean())
    avg_loss = loss.groupby(df["symbol"]).transform(lambda s: s.rolling(14, min_periods=5).mean())
    rs = avg_gain / (avg_loss + 1e-6)
    rsi14 = 100 - (100 / (1 + rs))
    df["rsi_norm"] = (rsi14.fillna(50.0) - 50.0) / 50.0

    macd_line = ema12 - ema26
    macd_signal = macd_line.groupby(df["symbol"]).transform(lambda s: s.ewm(span=9, adjust=False).mean())
    df["macd_norm"] = np.clip(macd_line / (df["close"] + 1e-6), -0.10, 0.10).fillna(0.0)
    df["macd_hist_norm"] = np.clip((macd_line - macd_signal) / (df["close"] + 1e-6), -0.05, 0.05).fillna(0.0)

    vol_mean20 = df.groupby("symbol")["volume"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    vol_std20 = df.groupby("symbol")["volume"].transform(lambda s: s.rolling(20, min_periods=10).std()).fillna(1.0)
    df["volume_zscore_20"] = np.clip((df["volume"] - vol_mean20) / (vol_std20 + 1.0), -3.0, 5.0).fillna(0.0)
    
    vol_shift5 = df.groupby("symbol")["volume"].shift(5)
    vol_shift20 = df.groupby("symbol")["volume"].shift(20)
    df["vol_growth_5d"] = np.clip((df["volume"] - vol_shift5) / (vol_shift5 + 1.0), -1.0, 5.0).fillna(0.0)
    df["vol_growth_20d"] = np.clip((df["volume"] - vol_shift20) / (vol_shift20 + 1.0), -1.0, 5.0).fillna(0.0)

    df["rel_to_index_5d"] = (df["ret_5d"] - df["index_return_5d"]).fillna(0.0)
    df["rel_to_index_20d"] = (df["ret_20d"] - df["index_return_20d"].fillna(0.0)).fillna(0.0)
    df["pkr_usd_ret_20d"] = df.groupby("symbol")["pkr_usd_rate"].pct_change(20).fillna(0.0)

    clean_feature_names = [
        "dist_52w_high", "mom_12m_1m", "ret_1d", "ret_3d", "ret_5d", "ret_10d", "ret_20d",
        "amihud_illiquidity", "is_lower_circuit",
        "volatility_10d", "volatility_20d", "volatility_60d", "norm_atr14", "hl_range", "co_range",
        "dist_sma20", "dist_sma50", "dist_ema12", "dist_ema26", "bb_pct_b", "bb_width",
        "rsi_norm", "macd_norm", "macd_hist_norm", "volume_zscore_20", "vol_growth_5d", "vol_growth_20d",
        "rel_to_index_5d", "rel_to_index_20d", "pkr_usd_ret_20d"
    ]

    features_30 = []
    for fn in clean_feature_names:
        rank_fn = f"{fn}_csrank"
        df[rank_fn] = df.groupby("date")[fn].rank(pct=True).fillna(0.50)
        features_30.append(rank_fn)

    # Cross-Sectional Targets
    valid_mask = df["actual_5d_return"].notna()
    df["excess_5d_rank"] = df[valid_mask].groupby("date")["excess_5d_return"].rank(pct=True)

    df["target_cs_class"] = np.nan
    df.loc[valid_mask & (df["excess_5d_rank"] >= 0.70), "target_cs_class"] = 0 # Buy
    df.loc[valid_mask & (df["excess_5d_rank"] <= 0.30), "target_cs_class"] = 1 # Avoid
    df.loc[valid_mask & (df["excess_5d_rank"] > 0.30) & (df["excess_5d_rank"] < 0.70), "target_cs_class"] = 2 # Neutral

    # Filter training data on extreme 60% with full historical window
    train_data = df[df["target_cs_class"].isin([0, 1])].copy()
    X_train = train_data[features_30].values
    y_train = train_data["target_cs_class"].values.astype(int)

    log.info("Training Final Production XGBoost on %d extreme samples...", len(train_data))

    final_model = xgb.XGBClassifier(
        n_estimators=150,
        learning_rate=0.03,
        max_depth=4,
        min_child_weight=100,
        subsample=0.8,
        colsample_bytree=0.6,
        reg_alpha=1.0,
        reg_lambda=10.0,
        random_state=42,
        n_jobs=4,
        eval_metric="logloss"
    )
    final_model.fit(X_train, y_train)

    # Export Model Artifacts
    model_path_ubj = MODEL_DIR / "xgb_model.ubj"
    final_model.save_model(str(model_path_ubj))
    log.info("Saved experimental binary model -> %s", model_path_ubj)

    features_json_path = MODEL_DIR / "xgb_features.json"
    with open(features_json_path, "w") as f:
        json.dump(features_30, f, indent=2)
    log.info("Saved experimental feature list -> %s", features_json_path)

    manifest = {
        "model_version": "alpha_rank_binary_v1",
        "model_name": "Basarat_PSX_Production_Alpha_XGBoost_v3",
        "trained_date": datetime.now().isoformat(),
        "data_start": min_date,
        "data_end": max_date,
        "total_training_rows": len(train_data),
        "features_count": len(features_30),
        "features": features_30,
        "classes": ["Buy", "Avoid"],
        "label_mapping": {"buy": 0, "avoid": 1},
        "probabilities_calibrated": False,
        "parameters": {
            "n_estimators": 150,
            "learning_rate": 0.03,
            "max_depth": 4,
            "min_child_weight": 100,
            "subsample": 0.8,
            "colsample_bytree": 0.6,
            "reg_lambda": 10.0,
        }
    }
    with open(MODEL_DIR / "model_manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    # 4. Generate Fresh Production Recommendations for Latest Market Date
    latest_dt = df["date"].max()
    latest_df = df[df["date"] == latest_dt].copy()
    log.info("Generating live recommendations for latest date: %s (%d stocks)...", str(latest_dt)[:10], len(latest_df))

    latest_X = latest_df[features_30].values
    latest_df["ai_buy_prob"] = final_model.predict_proba(latest_X)[:, 0] # Class 0 = Buy
    latest_df["basarat_score"] = (latest_df["ai_buy_prob"].rank(pct=True) * 100).round(1)

    recommendations = []
    for r in latest_df.sort_values("basarat_score", ascending=False).itertuples():
        sym = getattr(r, "symbol")
        score = getattr(r, "basarat_score")
        p_close = getattr(r, "close")
        vol = getattr(r, "volume")
        is_liq = getattr(r, "is_primary_universe")
        
        if score >= 80.0:
            rating = "Strong Buy"
            recommendation_type = "BULLISH"
        elif score <= 20.0:
            rating = "Avoid"
            recommendation_type = "BEARISH"
        else:
            rating = "Hold"
            recommendation_type = "NEUTRAL"

        recommendations.append({
            "symbol": sym,
            "date": str(latest_dt)[:10],
            "close_price": round(float(p_close), 2),
            "volume": int(vol),
            "basarat_score": float(score),
            "rating": rating,
            "signal": recommendation_type,
            "is_liquid_universe": bool(is_liq)
        })

    recs_output_path = REPORTS_DIR / "latest_stock_recommendations.json"
    with open(recs_output_path, "w") as f:
        json.dump({
            "as_of_date": str(latest_dt)[:10],
            "generated_at": datetime.now().isoformat(),
            "total_stocks_analyzed": len(recommendations),
            "top_bullish_picks": [r for r in recommendations if r["rating"] == "Strong Buy" and r["is_liquid_universe"]][:10],
            "top_avoid_stocks": [r for r in recommendations if r["rating"] == "Avoid"][:10],
            "all_stock_rankings": recommendations
        }, f, indent=2)

    log.info("Saved experimental stock ranking -> %s", recs_output_path)
    return recs_output_path


if __name__ == "__main__":
    retrain_and_export_production_model()
