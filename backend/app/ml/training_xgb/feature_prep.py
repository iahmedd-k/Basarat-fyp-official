"""
Feature Preparation for XGBoost — flat tabular feature engineering.

WHY THIS IS DIFFERENT FROM THE GRU APPROACH
============================================
XGBoost doesn't consume 30-day sequences directly — it works on flat
tabular rows. Rather than raw price/indicator values at 30 timesteps,
this module engineers a fixed-width feature row summarizing recent
history for each (symbol, date) observation.

Design decisions:
  1. All 20 of gru_v1's original point-in-time features at date t are
     reused directly from features_daily.parquet (no recomputation).
  2. Summary statistics over the trailing 30-day window ending at t give
     XGBoost equivalent sequence context without needing raw sequences.
  3. Lag features (RSI, MACD at t-5, t-10) provide temporal signal that
     a single-point-in-time snapshot lacks.
  4. symbol_id is included as a numeric feature — XGBoost handles
     ordinal integers natively, no embeddings needed.
  5. No feature scaling is applied — tree-based models are invariant to
     monotonic feature transformations, unlike the GRU which requires
     StandardScaler normalization.

Output: data/processed/features_xgb.parquet — one row per (symbol, date).
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

log = logging.getLogger("training_xgb.feature_prep")

FEATURES_DIR = Path("data/features")
OUTPUT_DIR = Path("data/processed")

# The 20 original GRU v1 features (point-in-time, no windowing needed)
GRU_V1_FEATURES = [
    "rsi_14", "macd", "macd_hist", "macd_signal",
    "atr_14", "sma_20", "sma_50", "ema_12", "ema_26",
    "bb_upper", "bb_mid", "bb_lower",
    "close", "open", "high", "low", "volume",
    "volume_zscore_20", "pkr_usd_rate", "policy_rate",
    # KSE-100 index-level context (computed across all active PSX symbols)
    "index_return_5d", "index_return_20d", "stock_relative_return_20d",
]

# Engineered features computed over trailing windows
ENGINEERED_FEATURES = [
    # Cumulative returns over trailing windows
    "return_1d", "return_5d_eng", "return_10d_eng", "return_20d",
    # Volatility
    "rolling_std_5d", "rolling_std_20d",
    # Volatility-adjusted returns (return / rolling_std over same window)
    # Captures signal-to-noise: a 5% return in a 2% vol regime is more
    # meaningful than the same return in a 5% vol regime.
    "vol_adj_return_1d", "vol_adj_return_5d", "vol_adj_return_10d",
    # Lag features (temporal signal)
    "rsi_14_lag5", "rsi_14_lag10", "macd_hist_lag5",
    # Consecutive direction days
    "consecutive_up_days", "consecutive_down_days",
    # Position within recent range
    "close_min_20d", "close_max_20d", "close_position_20d",
]

ALL_XGB_FEATURES = GRU_V1_FEATURES + ENGINEERED_FEATURES + ["symbol_id"]


def build_xgb_features(
    features_path: Path | None = None,
    output_path: Path | None = None,
) -> pd.DataFrame:
    """Build flat tabular features for XGBoost from features_daily.parquet.

    Reads the pre-computed features, engineers trailing-window summary
    statistics, and outputs a single flat table with one row per
    (symbol, date).

    Parameters
    ----------
    features_path : path to features_daily.parquet
    output_path : where to save the output parquet

    Returns
    -------
    DataFrame with all engineered features, one row per (symbol, date).
    """
    features_path = features_path or (FEATURES_DIR / "features_daily.parquet")
    output_path = output_path or (OUTPUT_DIR / "features_xgb.parquet")

    log.info("Loading features from %s ...", features_path)
    df = pd.read_parquet(features_path)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    log.info("Loaded %d rows, %d columns", len(df), len(df.columns))

    # ── Verify required columns exist ───────────────────────────────────
    missing_gru = set(GRU_V1_FEATURES) - set(df.columns)
    if missing_gru:
        raise ValueError(f"Missing GRU v1 features in parquet: {missing_gru}")

    # ── Engineer trailing-window features per symbol ─────────────────────
    log.info("Engineering trailing-window features ...")

    eng_parts = []
    for sym, grp in df.groupby("symbol"):
        eng_parts.append(_engineer_symbol(grp))
    engineered = pd.concat(eng_parts, ignore_index=False)

    # Merge engineered features back
    eng_cols = [c for c in engineered.columns if c not in df.columns]
    if eng_cols:
        df = pd.concat(
            [df.reset_index(drop=True), engineered[eng_cols].reset_index(drop=True)],
            axis=1,
        )

    # NOTE: NaN in engineered features is intentionally NOT filled here.
    # Filling with the global median (across all dates) would leak future
    # data into early training rows.  Instead, NaN fill is deferred to
    # time_split_xgb() which computes the fill median from the training
    # split only.

    # ── Verify output (Task 13: Fail fast if any declared feature is missing) ─
    missing = set(ALL_XGB_FEATURES) - set(df.columns)
    if missing:
        raise ValueError(
            f"Missing required XGBoost features: {sorted(missing)}. "
            f"All declared features in ALL_XGB_FEATURES must be generated before training."
        )

    output_features = [c for c in ALL_XGB_FEATURES if c in df.columns]

    log.info(
        "Final feature set: %d features, %d rows",
        len(output_features), len(df),
    )

    # ── Save ─────────────────────────────────────────────────────────────
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(output_path, index=False)
    log.info("Saved XGBoost features -> %s (%d rows)", output_path, len(df))

    return df


def _engineer_symbol(grp: pd.DataFrame) -> pd.DataFrame:
    """Compute engineered features for a single symbol's data.

    Expects the input to be sorted by date ascending.
    """
    g = grp.copy()
    close = g["close"]
    rsi = g["rsi_14"]
    macd_hist = g["macd_hist"]

    # ── Cumulative returns over trailing windows ─────────────────────────
    g["return_1d"] = close.pct_change(1)
    # return_5d and return_10d already exist in features_daily.parquet as
    # pct_change(5) and pct_change(10). We alias them for clarity but
    # also recompute to ensure consistency.
    g["return_5d_eng"] = close.pct_change(5)
    g["return_10d_eng"] = close.pct_change(10)
    g["return_20d"] = close.pct_change(20)

    # ── Rolling volatility ───────────────────────────────────────────────
    daily_ret = close.pct_change(1)
    g["rolling_std_5d"] = daily_ret.rolling(5, min_periods=3).std()
    g["rolling_std_20d"] = daily_ret.rolling(20, min_periods=10).std()

    # ── Volatility-adjusted returns ──────────────────────────────────────
    # return_Nd / rolling_std_Nd: signal-to-noise ratio. A large return in
    # a low-vol regime is more informative than the same return in a high-vol
    # regime. This is the key feature that lets the model distinguish
    # "meaningful" moves from noise.
    g["vol_adj_return_1d"] = daily_ret / g["rolling_std_5d"].replace(0, np.nan)
    g["vol_adj_return_5d"] = g["return_5d_eng"] / g["rolling_std_5d"].replace(0, np.nan)
    g["vol_adj_return_10d"] = g["return_10d_eng"] / g["rolling_std_20d"].replace(0, np.nan)

    # ── Lag features (temporal signal) ───────────────────────────────────
    g["rsi_14_lag5"] = rsi.shift(5)
    g["rsi_14_lag10"] = rsi.shift(10)
    g["macd_hist_lag5"] = macd_hist.shift(5)

    # ── Position within recent range ─────────────────────────────────────
    g["close_min_20d"] = close.rolling(20, min_periods=10).min()
    g["close_max_20d"] = close.rolling(20, min_periods=10).max()
    # position = (close - min) / (max - min), clamped to [0, 1]
    range_20d = g["close_max_20d"] - g["close_min_20d"]
    g["close_position_20d"] = ((close - g["close_min_20d"]) / range_20d.replace(0, np.nan)).clip(0, 1)

    return g


def get_feature_list() -> list[str]:
    """Return the ordered list of feature columns for XGBoost."""
    return [c for c in ALL_XGB_FEATURES if c != "symbol_id"] + ["symbol_id"]


def get_gru_v1_features() -> list[str]:
    """Return the 20 original GRU v1 feature names."""
    return list(GRU_V1_FEATURES)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )
    df = build_xgb_features()
    print(f"\nOutput shape: {df.shape}")
    print(f"Features: {len(ALL_XGB_FEATURES)}")
    print(f"Row count: {len(df)}")
