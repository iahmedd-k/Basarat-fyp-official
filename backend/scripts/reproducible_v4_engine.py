"""
Reproducible PSX Forecasting & Alpha Engine (v4).
==================================================
Clean forward-date masking, multi-horizon alpha calculations, and exact metrics.
"""

from pathlib import Path
import gc
import hashlib
import argparse
import json
import logging
import os
import random
import numpy as np
import pandas as pd
import scipy.stats as stats
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    log_loss,
    roc_auc_score,
)
import joblib

SEED = 42
os.environ["PYTHONHASHSEED"] = str(SEED)
random.seed(SEED)
np.random.seed(SEED)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(message)s")
log = logging.getLogger("reproducible_v4")

ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_PATH = ROOT_DIR / "data" / "features" / "features_daily.parquet"
SPLITS_DIR = ROOT_DIR / "data" / "splits"
SPLITS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR = ROOT_DIR / "models" / "experiments" / "v4_secondary_pipeline"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

CONFIRMED_ACTIONS = {
    ("MARI", "2024-09-16"): 9.00,
    ("SYS", "2022-03-31"): 2.00,
    ("SYS", "2025-06-02"): 5.00,
    ("LUCK", "2025-04-28"): 5.00,
    ("UBL", "2025-06-23"): 2.00,
    ("LCI", "2025-07-21"): 5.00,
    ("KOHC", "2025-08-25"): 5.00,
    ("KTML", "2025-09-15"): 5.00,
    ("SRVI", "2021-04-20"): 2.00,
    ("SRVI", "2026-08-24"): 10.00,
    ("BAFL", "2026-04-20"): 2.00,
    ("AHCL", "2025-03-27"): 9.50,
    ("COLG", "2023-02-10"): 1.35,
    ("COLG", "2023-06-14"): 1.90,
    ("MTL", "2022-03-07"): 1.25,
    ("MTL", "2023-06-22"): 1.45,
    ("MTL", "2026-06-22"): 2.00,
    ("APL", "2022-09-12"): 1.3333,
    ("ILP", "2023-06-15"): 1.50,
    ("GHGL", "2021-01-14"): 1.35,
    ("MEHT", "2023-06-23"): 1.50,
    ("NATF", "2021-10-06"): 1.25,
    ("NPL", "2024-10-15"): 1.30,
    ("PRL", "2020-03-03"): 1.25,
    ("SAZEW", "2020-02-26"): 1.50,
    ("SEARL", "2021-10-29"): 1.30,
    ("TGL", "2020-03-20"): 1.40,
    ("TGL", "2022-10-19"): 1.25,
    ("YOUW", "2026-03-02"): 1.25,
}

BASE_FEATURES = [
    "dist_52w_high_csrank", "mom_12m_1m_csrank", "ret_1d_csrank", "ret_3d_csrank",
    "ret_5d_csrank", "ret_10d_csrank", "ret_20d_csrank", "amihud_illiquidity_csrank",
    "is_lower_circuit_csrank", "volatility_10d_csrank", "volatility_20d_csrank",
    "volatility_60d_csrank", "norm_atr14_csrank", "hl_range_csrank", "co_range_csrank",
    "dist_sma20_csrank", "dist_sma50_csrank", "dist_ema12_csrank", "dist_ema26_csrank",
    "bb_pct_b_csrank", "bb_width_csrank", "rsi_norm_csrank", "macd_norm_csrank",
    "macd_hist_norm_csrank", "volume_zscore_20_csrank", "vol_growth_5d_csrank",
    "vol_growth_20d_csrank", "rel_to_index_5d_csrank", "rel_to_index_20d_csrank",
    "pkr_usd_ret_20d_csrank",
]
REGIME_FEATURES = ["mkt_trend_60d", "mkt_trend_120d", "mkt_volatility_30d", "mkt_regime_state"]


def metric_summary(y_true, predictions, feature_hash: str) -> dict:
    report = classification_report(
        y_true, predictions, labels=[0, 1, 2],
        target_names=["Bearish", "Bullish", "Sideways"], output_dict=True, zero_division=0,
    )
    recalls = {name: report[name]["recall"] for name in ("Bearish", "Bullish", "Sideways")}
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "macro_f1": float(f1_score(y_true, predictions, labels=[0, 1, 2], average="macro", zero_division=0)),
        "class_recall": recalls,
        "min_class_recall": float(min(recalls.values())),
        "feature_matrix_sha256": feature_hash,
    }


def build_model(params: dict, early_stopping: bool = False) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        **params, random_state=SEED, eval_metric="mlogloss", n_jobs=1, tree_method="hist",
        **({"early_stopping_rounds": 40} if early_stopping else {}),
    )


def audit_corporate_actions(raw_df: pd.DataFrame, adjusted_df: pd.DataFrame) -> dict:
    records = []
    for (symbol, date_text), ratio in CONFIRMED_ACTIONS.items():
        action_date = pd.Timestamp(date_text)
        event = {"symbol": symbol, "action_date": date_text, "ratio": ratio}
        for label, frame in (("raw", raw_df), ("adjusted", adjusted_df)):
            group = frame[frame["symbol"] == symbol].sort_values("date")
            positions = np.flatnonzero(group["date"].to_numpy() >= action_date.to_datetime64())
            if len(positions) == 0 or positions[0] == 0:
                event[f"{label}_event_present"] = False
                continue
            pos = int(positions[0])
            previous = float(group.iloc[pos - 1]["close"])
            current = float(group.iloc[pos]["close"])
            event[f"{label}_event_present"] = True
            event[f"{label}_event_date"] = str(group.iloc[pos]["date"].date())
            event[f"{label}_change_pct"] = (current / previous - 1.0) * 100.0 if previous else None
        records.append(event)

    returns = adjusted_df.sort_values(["symbol", "date"]).groupby("symbol")["close"].pct_change()
    suspicious_mask = returns.abs() > 0.20
    suspicious = adjusted_df.loc[suspicious_mask, ["symbol", "date"]].copy()
    suspicious["change_pct"] = returns.loc[suspicious_mask].to_numpy() * 100.0
    known_events = {(symbol, pd.Timestamp(date)) for symbol, date in CONFIRMED_ACTIONS}
    suspicious = suspicious[
        ~suspicious.apply(lambda row: (row["symbol"], pd.Timestamp(row["date"])) in known_events, axis=1)
    ]
    return {
        "confirmed_action_count": len(CONFIRMED_ACTIONS),
        "events": records,
        "remaining_gt_20pct_moves_count": len(suspicious),
        "remaining_gt_20pct_moves_sample": [
            {"symbol": row.symbol, "date": str(row.date.date()), "change_pct": round(float(row.change_pct), 3)}
            for row in suspicious.head(50).itertuples(index=False)
        ],
    }


def load_and_clean_data():
    raw_df = pd.read_parquet(DATA_PATH, columns=["symbol", "date", "open", "high", "low", "close", "volume"])
    raw_df["date"] = pd.to_datetime(raw_df["date"])
    raw_df = raw_df.sort_values(["symbol", "date"]).reset_index(drop=True)
    
    # 1. Back-adjust confirmed corporate actions
    adjusted_dfs = []
    for sym, g in raw_df.groupby("symbol", as_index=False):
        g = g.sort_values("date").reset_index(drop=True)
        for (action_sym, action_date_str), ratio in CONFIRMED_ACTIONS.items():
            if sym == action_sym:
                action_date = pd.Timestamp(action_date_str)
                idx_matches = g.index[g["date"] >= action_date]
                if len(idx_matches) > 0:
                    first_post_idx = idx_matches[0]
                    if first_post_idx > 0:
                        factor = 1.0 / ratio
                        g.loc[:first_post_idx - 1, "open"] *= factor
                        g.loc[:first_post_idx - 1, "high"] *= factor
                        g.loc[:first_post_idx - 1, "low"] *= factor
                        g.loc[:first_post_idx - 1, "close"] *= factor
                        g.loc[:first_post_idx - 1, "volume"] = (g.loc[:first_post_idx - 1, "volume"] / factor).round()
        adjusted_dfs.append(g)
        
    df = pd.concat(adjusted_dfs, ignore_index=True)
    action_audit = audit_corporate_actions(raw_df, df)
    del raw_df, adjusted_dfs
    gc.collect()
    
    # 2. Market Calendar & Time-Series Forward Returns
    date_counts = df.groupby("date")["symbol"].nunique()
    market_dates = date_counts[date_counts >= 30].index.sort_values()
    price_dict = df.set_index(["symbol", "date"])["close"].to_dict()
    
    df["daily_ret"] = df.groupby("symbol")["close"].pct_change().fillna(0.0).astype(np.float32)
    daily_mkt_ret = df.groupby("date")["daily_ret"].mean().sort_index().fillna(0.0)
    # Point-in-time market returns. Every window ends on its row date; the
    # forward return columns below are targets/benchmarks and must not enter X.
    mkt_trailing_5d = daily_mkt_ret.add(1.0).rolling(5, min_periods=5).apply(np.prod, raw=True).sub(1.0).fillna(0.0)
    mkt_trailing_20d = daily_mkt_ret.add(1.0).rolling(20, min_periods=20).apply(np.prod, raw=True).sub(1.0).fillna(0.0)

    for h in [5, 10, 20, 60]:
        date_map = {market_dates[i]: market_dates[i + h] for i in range(len(market_dates) - h)}
        target_dates = df["date"].map(date_map)
        
        t_closes = [price_dict.get((row.symbol, target_dates.iloc[idx]), np.nan) for idx, row in enumerate(df.itertuples())]
        df[f"actual_{h}d_return"] = ((pd.Series(t_closes) - df["close"]) / (df["close"] + 1e-6)).astype(np.float32)
        
        mkt_h = {}
        for i in range(len(market_dates) - h):
            d_start = market_dates[i]
            d_end = market_dates[i + h]
            cum_ret = (1.0 + daily_mkt_ret.loc[d_start:d_end].iloc[1:]).prod() - 1.0
            mkt_h[d_start] = float(cum_ret)
        df[f"index_forward_{h}d"] = df["date"].map(mkt_h).fillna(0.0).astype(np.float32)
        df[f"excess_{h}d_return"] = (df[f"actual_{h}d_return"] - df[f"index_forward_{h}d"]).astype(np.float32)
        df[f"excess_{h}d_rank"] = df.groupby("date")[f"excess_{h}d_return"].rank(pct=True).fillna(0.50).astype(np.float32)

    # 3-Class Target: 0: Bearish (<-1.5%), 1: Bullish (>+1.5%), 2: Sideways
    df["target_3class"] = np.where(
        df["actual_5d_return"].isna(), 2,
        np.where(df["actual_5d_return"] > 0.015, 1,
        np.where(df["actual_5d_return"] < -0.015, 0, 2))
    ).astype(np.int8)

    # 3. Factor Construction
    feat_dict = {}
    
    rolling_52w = df.groupby("symbol")["high"].transform(lambda s: s.rolling(252, min_periods=50).max())
    feat_dict["dist_52w_high"] = np.clip((df["close"] / (rolling_52w + 1e-6)) - 1.0, -0.90, 0.0).astype(np.float32)
    
    ret_12m = df["close"] / (df.groupby("symbol")["close"].shift(252) + 1e-6) - 1.0
    ret_1m = df["close"] / (df.groupby("symbol")["close"].shift(21) + 1e-6) - 1.0
    feat_dict["mom_12m_1m"] = np.clip(ret_12m - ret_1m, -1.0, 3.0).fillna(0.0).astype(np.float32)
    
    for lag in [1, 3, 5, 10, 20]:
        feat_dict[f"ret_{lag}d"] = (df["close"] / (df.groupby("symbol")["close"].shift(lag) + 1e-6) - 1.0).fillna(0.0).astype(np.float32)
        
    traded_val = df["close"] * df["volume"]
    feat_dict["amihud_illiquidity"] = np.clip(
        df["daily_ret"].abs().groupby(df["symbol"]).transform(lambda s: s.rolling(20, min_periods=5).mean()) /
        (traded_val.groupby(df["symbol"]).transform(lambda s: s.rolling(20, min_periods=5).mean()) + 1e-4),
        0.0, 0.10
    ).fillna(0.0).astype(np.float32)
    
    feat_dict["is_lower_circuit"] = (df["daily_ret"] <= -0.074).astype(np.float32)
    
    for vol_w in [10, 20, 60]:
        feat_dict[f"volatility_{vol_w}d"] = df["daily_ret"].groupby(df["symbol"]).transform(lambda s: s.rolling(vol_w, min_periods=5).std()).fillna(0.02).astype(np.float32)
        
    prev_close = df.groupby("symbol")["close"].shift(1)
    tr = np.maximum(df["high"] - df["low"], np.maximum((df["high"] - prev_close).abs(), (df["low"] - prev_close).abs()))
    feat_dict["norm_atr14"] = np.clip(tr.groupby(df["symbol"]).transform(lambda s: s.rolling(14, min_periods=5).mean()) / (df["close"] + 1e-6), 0.0, 0.20).fillna(0.02).astype(np.float32)
    feat_dict["hl_range"] = ((df["high"] - df["low"]) / (df["close"] + 1e-6)).astype(np.float32)
    feat_dict["co_range"] = ((df["close"] - df["open"]) / (df["open"] + 1e-6)).astype(np.float32)
    
    sma20 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    sma50 = df.groupby("symbol")["close"].transform(lambda s: s.rolling(50, min_periods=20).mean())
    ema12 = df.groupby("symbol")["close"].transform(lambda s: s.ewm(span=12, adjust=False).mean())
    ema26 = df.groupby("symbol")["close"].transform(lambda s: s.ewm(span=26, adjust=False).mean())
    
    feat_dict["dist_sma20"] = np.clip((df["close"] - sma20) / (sma20 + 1e-6), -0.50, 0.50).fillna(0.0).astype(np.float32)
    feat_dict["dist_sma50"] = np.clip((df["close"] - sma50) / (sma50 + 1e-6), -0.50, 0.50).fillna(0.0).astype(np.float32)
    feat_dict["dist_ema12"] = np.clip((df["close"] - ema12) / (ema12 + 1e-6), -0.50, 0.50).fillna(0.0).astype(np.float32)
    feat_dict["dist_ema26"] = np.clip((df["close"] - ema26) / (ema26 + 1e-6), -0.50, 0.50).fillna(0.0).astype(np.float32)
    
    bb_std = df.groupby("symbol")["close"].transform(lambda s: s.rolling(20, min_periods=10).std()).fillna(1e-4)
    feat_dict["bb_pct_b"] = np.clip((df["close"] - (sma20 - 2 * bb_std)) / (4 * bb_std + 1e-6), -0.50, 1.50).fillna(0.50).astype(np.float32)
    feat_dict["bb_width"] = np.clip((4 * bb_std) / (sma20 + 1e-6), 0.0, 1.0).fillna(0.05).astype(np.float32)
    
    delta = df.groupby("symbol")["close"].diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_g = gain.groupby(df["symbol"]).transform(lambda s: s.rolling(14, min_periods=5).mean())
    avg_l = loss.groupby(df["symbol"]).transform(lambda s: s.rolling(14, min_periods=5).mean())
    rs = avg_g / (avg_l + 1e-6)
    feat_dict["rsi_norm"] = (((100 - (100 / (1 + rs))).fillna(50.0) - 50.0) / 50.0).astype(np.float32)
    
    macd_line = (ema12 - ema26) / (df["close"] + 1e-6)
    macd_sig = macd_line.groupby(df["symbol"]).transform(lambda s: s.ewm(span=9, adjust=False).mean())
    feat_dict["macd_norm"] = np.clip(macd_line, -0.10, 0.10).fillna(0.0).astype(np.float32)
    feat_dict["macd_hist_norm"] = np.clip(macd_line - macd_sig, -0.05, 0.05).fillna(0.0).astype(np.float32)
    
    vol_mean = df.groupby("symbol")["volume"].transform(lambda s: s.rolling(20, min_periods=10).mean())
    vol_std = df.groupby("symbol")["volume"].transform(lambda s: s.rolling(20, min_periods=10).std()).fillna(1.0)
    feat_dict["volume_zscore_20"] = np.clip((df["volume"] - vol_mean) / (vol_std + 1.0), -3.0, 5.0).fillna(0.0).astype(np.float32)
    
    vol_shift5 = df.groupby("symbol")["volume"].shift(5)
    vol_shift20 = df.groupby("symbol")["volume"].shift(20)
    feat_dict["vol_growth_5d"] = np.clip((df["volume"] - vol_shift5) / (vol_shift5 + 1.0), -1.0, 5.0).fillna(0.0).astype(np.float32)
    feat_dict["vol_growth_20d"] = np.clip((df["volume"] - vol_shift20) / (vol_shift20 + 1.0), -1.0, 5.0).fillna(0.0).astype(np.float32)
    feat_dict["rel_to_index_5d"] = (feat_dict["ret_5d"] - df["date"].map(mkt_trailing_5d)).fillna(0.0).astype(np.float32)
    feat_dict["rel_to_index_20d"] = (feat_dict["ret_20d"] - df["date"].map(mkt_trailing_20d)).fillna(0.0).astype(np.float32)
    feat_dict["pkr_usd_ret_20d"] = np.full(len(df), 0.002, dtype=np.float32)
    
    # Regime Signals
    mkt_cum60 = daily_mkt_ret.rolling(60, min_periods=20).sum().fillna(0.0)
    feat_dict["mkt_trend_60d"] = df["date"].map(mkt_cum60).fillna(0.0).astype(np.float32)
    mkt_cum120 = daily_mkt_ret.rolling(120, min_periods=40).sum().fillna(0.0)
    feat_dict["mkt_trend_120d"] = df["date"].map(mkt_cum120).fillna(0.0).astype(np.float32)
    mkt_vol30 = daily_mkt_ret.rolling(30, min_periods=10).std().fillna(0.01)
    feat_dict["mkt_volatility_30d"] = df["date"].map(mkt_vol30).fillna(0.01).astype(np.float32)
    feat_dict["mkt_regime_state"] = np.where(feat_dict["mkt_trend_60d"] > 0.05, 1.0, np.where(feat_dict["mkt_trend_60d"] < -0.05, -1.0, 0.0)).astype(np.float32)

    # Cross-Sectional Ranking
    raw_feature_cols = list(feat_dict.keys())
    raw_df_feats = pd.DataFrame(feat_dict)
    raw_df_feats["date"] = df["date"]
    regime_features = ["mkt_trend_60d", "mkt_trend_120d", "mkt_volatility_30d", "mkt_regime_state"]
    ranked_feature_cols = [c for c in raw_feature_cols if c not in regime_features]
    csrank_df = raw_df_feats.groupby("date")[ranked_feature_cols].rank(pct=True).fillna(0.50).astype(np.float32)
    feature_cols = [f"{c}_csrank" for c in ranked_feature_cols]
    csrank_df.columns = feature_cols

    # Market-wide regime signals are constant across symbols on a date, so
    # cross-sectional ranking collapses them to a near-constant. Preserve
    # their point-in-time raw values as temporal features instead.
    for column in regime_features:
        csrank_df[column] = feat_dict[column]
        feature_cols.append(column)
    
    csrank_df["symbol"] = df["symbol"]
    csrank_df["date"] = df["date"]
    csrank_df["close"] = df["close"]
    csrank_df["amihud_illiquidity"] = feat_dict["amihud_illiquidity"]
    csrank_df["target_3class"] = df["target_3class"]
    for h in [5, 10, 20, 60]:
        csrank_df[f"actual_{h}d_return"] = df[f"actual_{h}d_return"]
        csrank_df[f"excess_{h}d_return"] = df[f"excess_{h}d_return"]
        csrank_df[f"excess_{h}d_rank"] = df[f"excess_{h}d_rank"]
        csrank_df[f"index_forward_{h}d"] = df[f"index_forward_{h}d"]

    del df, feat_dict, raw_df_feats
    gc.collect()
    
    return csrank_df, feature_cols, action_audit


def dataframe_sha256(frame: pd.DataFrame, columns: list[str]) -> str:
    """Hash ordered schema and every value in the selected dataframe columns."""
    matrix = frame.loc[:, columns]
    digest = hashlib.sha256()
    digest.update(json.dumps(
        [(str(column), str(matrix[column].dtype)) for column in matrix.columns],
        separators=(",", ":"),
    ).encode("utf-8"))
    # pandas hashes values row by row and has stable handling for NaN and strings.
    digest.update(pd.util.hash_pandas_object(matrix, index=False, categorize=True).values.tobytes())
    return digest.hexdigest()


def trading_day_embargo_cutoff(dates: pd.Series, boundary: pd.Timestamp, sessions: int = 5) -> pd.Timestamp:
    """Return the first excluded session so `sessions` market days precede boundary."""
    market_dates = pd.DatetimeIndex(dates.drop_duplicates().sort_values())
    boundary_pos = market_dates.searchsorted(boundary, side="left")
    if boundary_pos < sessions:
        raise ValueError(f"Not enough history to apply {sessions}-session embargo before {boundary.date()}")
    return market_dates[boundary_pos - sessions]


def run_ablation_study(train_df, val_df, test_df, y_test, full_feature_cols, e_model, e_hash):
    original_params = {
        "n_estimators": 150, "max_depth": 4, "learning_rate": 0.03,
        "min_child_weight": 100, "subsample": 0.8, "colsample_bytree": 0.6,
        "reg_lambda": 10.0, "reg_alpha": 1.0,
    }
    tuned_params = {
        "n_estimators": 180, "max_depth": 4, "learning_rate": 0.03,
        "min_child_weight": 80, "subsample": 0.85, "colsample_bytree": 0.85,
        "reg_lambda": 8.0, "reg_alpha": 2.0,
    }
    specs = {
        "A — Baseline": (BASE_FEATURES, original_params, None, False),
        "B — Sideways reweighting only": (BASE_FEATURES, original_params, "sideways", False),
        "C — Regime features only": (BASE_FEATURES + REGIME_FEATURES, original_params, None, False),
        "D — Hyperparameters only": (BASE_FEATURES, tuned_params, None, False),
    }
    results = {}
    y_train = train_df["target_3class"].astype(int).to_numpy()
    y_val = val_df["target_3class"].astype(int).to_numpy()
    for name, (features, params, weighting, use_early_stopping) in specs.items():
        if any(column not in train_df.columns for column in features):
            raise RuntimeError(f"Ablation {name} is missing one or more features")
        model = build_model(params, early_stopping=use_early_stopping)
        weights = np.where(y_train == 2, 1.15, 1.0) if weighting == "sideways" else None
        fit_args = {"sample_weight": weights} if weights is not None else {}
        if use_early_stopping:
            fit_args["eval_set"] = [(val_df[features].to_numpy(), y_val)]
            fit_args["verbose"] = False
        model.fit(train_df[features].to_numpy(), y_train, **fit_args)
        feature_hash = dataframe_sha256(test_df, features)
        results[name] = metric_summary(y_test, model.predict(test_df[features].to_numpy()), feature_hash)

    full_counts = np.bincount(y_train, minlength=3)
    full_weights_by_class = len(y_train) / (3.0 * full_counts)
    full_weights_by_class[2] *= 1.15
    results["E — All combined"] = metric_summary(
        y_test, e_model.predict(test_df[full_feature_cols].to_numpy()), e_hash,
    )
    return results


def run_v3_binary_baseline(train_df, val_df, test_df):
    """Re-evaluate v3's actual Buy/Avoid target on its matching extreme-only task."""
    y_col = "excess_5d_rank"
    train_mask = train_df[y_col].ge(0.70) | train_df[y_col].le(0.30)
    val_mask = val_df[y_col].ge(0.70) | val_df[y_col].le(0.30)
    test_mask = test_df[y_col].ge(0.70) | test_df[y_col].le(0.30)
    train = train_df.loc[train_mask]
    validation = val_df.loc[val_mask]
    testing = test_df.loc[test_mask]
    to_binary = lambda ranks: np.where(ranks.to_numpy() >= 0.70, 0, 1)
    features = BASE_FEATURES
    params = {
        "n_estimators": 150, "max_depth": 4, "learning_rate": 0.03,
        "min_child_weight": 100, "subsample": 0.8, "colsample_bytree": 0.6,
        "reg_lambda": 10.0, "reg_alpha": 1.0,
    }
    model = build_model(params)
    model.set_params(eval_metric="logloss")
    model.fit(train[features].to_numpy(), to_binary(train[y_col]))
    test_hash = dataframe_sha256(testing, features)
    y_true = to_binary(testing[y_col])
    predictions = model.predict(testing[features].to_numpy())
    report = classification_report(y_true, predictions, labels=[0, 1], output_dict=True, zero_division=0)
    return {
        "accuracy": float(accuracy_score(y_true, predictions)),
        "macro_f1": float(f1_score(y_true, predictions, labels=[0, 1], average="macro", zero_division=0)),
        "buy_recall": report["0"]["recall"],
        "avoid_recall": report["1"]["recall"],
        "min_class_recall": min(report["0"]["recall"], report["1"]["recall"]),
        "test_rows": len(testing),
        "feature_matrix_sha256": test_hash,
    }


def run_part7_diagnostics():
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    full_df, feature_cols, _ = load_and_clean_data()
    valid_mask = full_df["actual_5d_return"].notna()
    val_start, test_start = pd.Timestamp("2024-07-01"), pd.Timestamp("2025-07-01")
    val_cutoff = trading_day_embargo_cutoff(full_df["date"], val_start)
    test_cutoff = trading_day_embargo_cutoff(full_df["date"], test_start)
    train = full_df[valid_mask & (full_df["date"] < val_cutoff)].copy()
    validation = full_df[valid_mask & (full_df["date"] >= val_start) & (full_df["date"] < test_cutoff)].copy()
    test = full_df[valid_mask & (full_df["date"] >= test_start)].copy()

    frozen = pd.read_parquet(SPLITS_DIR / "test_set_v4_frozen.parquet")
    hash_path = SPLITS_DIR / "test_set_v4_frozen.hash.txt"
    expected = dict(line.split() for line in hash_path.read_text(encoding="utf-8").splitlines())
    test_hash = dataframe_sha256(test, feature_cols)
    if (test_hash != expected["feature_matrix_sha256"]
            or dataframe_sha256(frozen, feature_cols) != expected["feature_matrix_sha256"]):
        raise RuntimeError("Part 7 diagnostics refused: frozen test feature hash mismatch")

    y_train = train["target_3class"].astype(int).to_numpy()
    y_test = test["target_3class"].astype(int).to_numpy()
    linear = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000, random_state=SEED))
    linear.fit(train[BASE_FEATURES].to_numpy(), y_train)
    linear_result = metric_summary(
        y_test, linear.predict(test[BASE_FEATURES].to_numpy()), dataframe_sha256(test, BASE_FEATURES),
    )

    # Alternative point-in-time label: sideways band is half of trailing
    # 20-session volatility scaled to the five-session forecast horizon.
    sorted_df = full_df.sort_values(["symbol", "date"]).copy()
    daily_ret = sorted_df.groupby("symbol")["close"].pct_change()
    sigma5 = daily_ret.groupby(sorted_df["symbol"]).transform(
        lambda values: values.rolling(20, min_periods=10).std()
    ) * np.sqrt(5.0)
    alt_labels = np.where(
        sorted_df["actual_5d_return"] > 0.5 * sigma5, 1,
        np.where(sorted_df["actual_5d_return"] < -0.5 * sigma5, 0, 2),
    ).astype(np.int8)
    label_by_index = pd.Series(alt_labels, index=sorted_df.index)
    train_labels = label_by_index.loc[train.index].to_numpy()
    test_labels = label_by_index.loc[test.index].to_numpy()
    class_counts = np.bincount(train_labels, minlength=3)
    class_weights = len(train_labels) / (3.0 * class_counts)
    class_weights[2] *= 1.15
    sample_weights = np.asarray([class_weights[label] for label in train_labels])
    vol_model = build_model({
        "n_estimators": 180, "max_depth": 4, "learning_rate": 0.03,
        "min_child_weight": 80, "subsample": 0.85, "colsample_bytree": 0.85,
        "reg_lambda": 8.0, "reg_alpha": 2.0,
    })
    vol_model.fit(train[feature_cols].to_numpy(), train_labels, sample_weight=sample_weights)
    vol_test_hash = dataframe_sha256(test, feature_cols)
    vol_result = metric_summary(test_labels, vol_model.predict(test[feature_cols].to_numpy()), vol_test_hash)
    label_frame = pd.DataFrame({"target_volatility_band": test_labels}, index=test.index)
    vol_result["label_matrix_sha256"] = dataframe_sha256(label_frame, ["target_volatility_band"])
    vol_result["label_definition"] = "Sideways if |5-session return| <= 0.5 * trailing 20-session daily volatility * sqrt(5); otherwise directional"
    vol_result["train_class_counts"] = class_counts.tolist()
    vol_result["test_class_counts"] = np.bincount(test_labels, minlength=3).tolist()

    return {
        "frozen_test_feature_matrix_sha256": test_hash,
        "logistic_regression_3class": linear_result,
        "volatility_band_label_xgboost": vol_result,
        "sector_relative_momentum": {
            "status": "not_run",
            "reason": "The historical OHLCV source contains only date, OHLCV, and symbol; the local frozen symbol-universe file contains index membership but no point-in-time sector history.",
        },
        "earnings_announcement_proximity": {
            "status": "not_run",
            "reason": "No historical per-symbol earnings-announcement date series is present in the local data assets; deriving this from current announcements would introduce look-ahead bias.",
        },
        "lightgbm_catboost": {
            "status": "not_run",
            "reason": "Neither optional model package is installed in the project environment; no dependency was installed.",
        },
    }


def run_walk_forward(full_df, feature_cols, periods):
    valid = full_df["actual_5d_return"].notna()
    results = {}
    weights_params = {
        "n_estimators": 180, "max_depth": 4, "learning_rate": 0.03,
        "min_child_weight": 80, "subsample": 0.85, "colsample_bytree": 0.85,
        "reg_lambda": 8.0, "reg_alpha": 2.0,
    }
    for name, start, end in periods:
        start_ts = pd.Timestamp(start)
        end_ts = pd.Timestamp(end) if end else full_df["date"].max() + pd.Timedelta(days=1)
        cutoff = trading_day_embargo_cutoff(full_df["date"], start_ts)
        training = full_df[valid & (full_df["date"] < cutoff)]
        testing = full_df[valid & (full_df["date"] >= start_ts) & (full_df["date"] < end_ts)]
        if training.empty or testing.empty:
            raise RuntimeError(f"Walk-forward period {name} has an empty train or test set")
        y_train = training["target_3class"].astype(int).to_numpy()
        counts = np.bincount(y_train, minlength=3)
        weights_by_class = len(y_train) / (3.0 * counts)
        weights_by_class[2] *= 1.15
        sample_weights = np.asarray([weights_by_class[label] for label in y_train])
        model = build_model(weights_params)
        model.fit(training[feature_cols].to_numpy(), y_train, sample_weight=sample_weights)
        test_hash = dataframe_sha256(testing, feature_cols)
        record = metric_summary(
            testing["target_3class"].astype(int).to_numpy(),
            model.predict(testing[feature_cols].to_numpy()), test_hash,
        )
        record.update({"train_rows": len(training), "test_rows": len(testing),
                       "train_end": str(training["date"].max().date()),
                       "test_start": str(testing["date"].min().date()),
                       "test_end": str(testing["date"].max().date())})
        results[name] = record
    return results


def run_reproducible_evaluation(
    initialize_frozen_hash: bool = False,
    hash_only: bool = False,
    refreeze_frozen: bool = False,
):
    full_df, feature_cols, action_audit = load_and_clean_data()
    
    # Freeze canonical splits
    valid_mask = full_df["actual_5d_return"].notna()
    val_split_date = pd.Timestamp("2024-07-01")
    test_split_date = pd.Timestamp("2025-07-01")
    val_embargo_cutoff = trading_day_embargo_cutoff(full_df["date"], val_split_date)
    test_embargo_cutoff = trading_day_embargo_cutoff(full_df["date"], test_split_date)

    train_df = full_df[valid_mask & (full_df["date"] < val_embargo_cutoff)].copy()
    val_df = full_df[valid_mask & (full_df["date"] >= val_split_date) & (full_df["date"] < test_embargo_cutoff)].copy()
    test_df = full_df[valid_mask & (full_df["date"] >= test_split_date)].copy()
    
    test_path = SPLITS_DIR / "test_set_v4_frozen.parquet"
    test_hash_path = SPLITS_DIR / "test_set_v4_frozen.hash.txt"

    # Freezing is explicit; normal runs only verify and never rewrite this file.
    if not test_path.is_file() and not refreeze_frozen:
        raise FileNotFoundError(f"Frozen test split is missing: {test_path}")
    test_hash = dataframe_sha256(test_df, feature_cols)
    test_dataset_hash = dataframe_sha256(test_df, list(test_df.columns))
    if refreeze_frozen:
        # A clean checkout may omit the large Parquet while retaining its
        # tracked sidecar. Recreate that file only if it matches the recorded
        # dataset; changing an existing freeze requires the explicit refreeze
        # operation against the existing file.
        if not test_path.is_file() and test_hash_path.is_file():
            expected = dict(line.split() for line in test_hash_path.read_text(encoding="utf-8").splitlines())
            if (test_hash != expected.get("feature_matrix_sha256")
                    or test_dataset_hash != expected.get("dataset_sha256")):
                raise RuntimeError("Rebuilt test set does not match the checked-in frozen hash sidecar")
            test_df.to_parquet(test_path, index=False)
            log.info("Recreated missing frozen test Parquet from the checked-in hashes")
            return {"initialized_hash": test_hash}
        test_df.to_parquet(test_path, index=False)
        test_hash_path.write_text(
            f"dataset_sha256 {test_dataset_hash}\nfeature_matrix_sha256 {test_hash}\n",
            encoding="utf-8",
        )
        log.info("Re-froze test split and integrity hashes: %s", test_hash_path)
        return {"initialized_hash": test_hash}
    frozen_test_df = pd.read_parquet(test_path)
    frozen_hash = dataframe_sha256(frozen_test_df, feature_cols)
    frozen_dataset_hash = dataframe_sha256(frozen_test_df, list(test_df.columns))
    if not test_hash_path.is_file():
        if not initialize_frozen_hash:
            raise RuntimeError(
                f"Frozen test hash guard is missing: {test_hash_path}. "
                "Review the current frozen split, then run once with "
                "--initialize-frozen-test-hash to create its feature-matrix SHA-256 sidecar."
            )
        if frozen_hash != test_hash:
            raise RuntimeError(
                f"Cannot initialize guard: current source matrix {test_hash} differs "
                f"from existing frozen file {frozen_hash}"
            )
        test_hash_path.write_text(
            f"dataset_sha256 {test_dataset_hash}\nfeature_matrix_sha256 {test_hash}\n",
            encoding="utf-8",
        )
        log.info("Initialized frozen test dataset and feature-matrix guards: %s", test_hash_path)
        return {"initialized_hash": test_hash}
    if initialize_frozen_hash:
        raise RuntimeError(f"Refusing to replace existing frozen hash guard: {test_hash_path}")
    expected_hashes = {}
    for line in test_hash_path.read_text(encoding="utf-8").splitlines():
        key, value = line.split()
        expected_hashes[key] = value
    if frozen_dataset_hash != expected_hashes.get("dataset_sha256"):
        raise RuntimeError(
            f"Frozen test dataset changed: expected {expected_hashes.get('dataset_sha256')}, found {frozen_dataset_hash}"
        )
    if frozen_hash != expected_hashes.get("feature_matrix_sha256"):
        raise RuntimeError(
            f"Frozen test feature matrix changed: expected {expected_hashes.get('feature_matrix_sha256')}, found {frozen_hash}"
        )
    if test_dataset_hash != expected_hashes.get("dataset_sha256"):
        raise RuntimeError(
            f"Current source produces a different test dataset: frozen={expected_hashes.get('dataset_sha256')}, current={test_dataset_hash}"
        )
    if test_hash != expected_hashes.get("feature_matrix_sha256"):
        raise RuntimeError(
            f"Current source produces a different test matrix: frozen={expected_hashes.get('feature_matrix_sha256')}, current={test_hash}"
        )
    test_df = frozen_test_df
    log.info("Feature matrix SHA-256 | train=%s val=%s test=%s",
             dataframe_sha256(train_df, feature_cols),
             dataframe_sha256(val_df, feature_cols), test_hash)
    log.info("Frozen test feature-matrix SHA-256: %s | rows=%d", test_hash, len(test_df))
    if hash_only:
        return {
            "train_feature_matrix_sha256": dataframe_sha256(train_df, feature_cols),
            "val_feature_matrix_sha256": dataframe_sha256(val_df, feature_cols),
            "test_feature_matrix_sha256": test_hash,
            "test_rows": len(test_df),
            "corporate_action_audit": action_audit,
        }
    
    X_train = train_df[feature_cols].values
    y_train_3c = train_df["target_3class"].values
    
    X_val = val_df[feature_cols].values
    y_val_3c = val_df["target_3class"].values
    
    X_test = test_df[feature_cols].values
    y_test_3c = test_df["target_3class"].values

    # Train 3-Class XGBoost with Sideways class weighting
    class_counts = np.bincount(y_train_3c, minlength=3)
    base_weights = len(y_train_3c) / (3.0 * class_counts)
    base_weights[2] *= 1.15
    sample_weights_train = np.array([base_weights[y] for y in y_train_3c])
    
    tuned_params = {
        "n_estimators": 180, "max_depth": 4, "learning_rate": 0.03,
        "subsample": 0.85, "colsample_bytree": 0.85, "min_child_weight": 80,
        "reg_lambda": 8.0, "reg_alpha": 2.0,
    }
    model_3c = build_model(tuned_params)
    model_3c.fit(X_train, y_train_3c, sample_weight=sample_weights_train)
    
    preds = model_3c.predict(X_test)
    acc_3c = accuracy_score(y_test_3c, preds)
    rep_3c = classification_report(y_test_3c, preds, target_names=["Bearish", "Bullish", "Sideways"], output_dict=True)
    cm_3c = confusion_matrix(y_test_3c, preds, labels=[0, 1, 2])
    
    # Feature Importances (Gain)
    booster = model_3c.get_booster()
    importance_gain = booster.get_score(importance_type="gain")
    mapped_gain = {feature_cols[int(k[1:])]: round(float(v), 2) for k, v in importance_gain.items() if k.startswith("f")}
    sorted_features = sorted(mapped_gain.items(), key=lambda x: x[1], reverse=True)
    
    # Multi-Horizon Backtests
    test_df["rt_cost"] = 0.0035 + np.clip(test_df["amihud_illiquidity"] * 5.0, 0.0005, 0.0025) * 2
    horizon_results = []
    
    for h in [5, 10, 20, 60]:
        valid_tr_h = train_df[f"actual_{h}d_return"].notna()
        tr_h_sub = train_df[valid_tr_h].copy()
        
        tr_h_sub["target_bin"] = np.nan
        tr_h_sub.loc[tr_h_sub[f"excess_{h}d_rank"] >= 0.70, "target_bin"] = 0
        tr_h_sub.loc[tr_h_sub[f"excess_{h}d_rank"] <= 0.30, "target_bin"] = 1
        
        tr_extreme = tr_h_sub[tr_h_sub["target_bin"].isin([0, 1])]
        
        rank_model = xgb.XGBClassifier(
            n_estimators=140, max_depth=3, learning_rate=0.03, subsample=0.85, colsample_bytree=0.85,
            min_child_weight=80, reg_lambda=8.0, random_state=SEED, eval_metric="logloss",
            n_jobs=1, tree_method="hist"
        )
        rank_model.fit(tr_extreme[feature_cols].values, tr_extreme["target_bin"].values)
        
        test_df[f"p_top_{h}d"] = rank_model.predict_proba(test_df[feature_cols].values)[:, 0]
        test_df[f"ml_rank_{h}d"] = test_df.groupby("date")[f"p_top_{h}d"].rank(pct=True)
        
        # Only evaluate on step dates where forward returns are notna
        valid_dates = test_df[test_df[f"actual_{h}d_return"].notna()]["date"].drop_duplicates().sort_values().tolist()
        step_dates = valid_dates[::h]
        
        gross_spreads, net_spreads, lo_rets, idx_rets = [], [], [], []
        top_picks_cnt = 0
        prev_portfolio = set()
        
        for d in step_dates:
            sub = test_df[(test_df["date"] == d) & test_df[f"actual_{h}d_return"].notna()]
            if len(sub) < 20: continue
            
            top10 = sub[sub[f"ml_rank_{h}d"] >= 0.90]
            bot10 = sub[sub[f"ml_rank_{h}d"] <= 0.10]
            
            if len(top10) > 0 and len(bot10) > 0:
                top_picks_cnt += len(top10)
                curr_syms = set(top10["symbol"].tolist())
                turnover_fraction = len(curr_syms - prev_portfolio) / max(1, len(curr_syms))
                prev_portfolio = curr_syms
                
                top_g = float(top10[f"actual_{h}d_return"].mean())
                bot_g = float(bot10[f"actual_{h}d_return"].mean())
                top_cost = float(top10["rt_cost"].mean() * turnover_fraction)
                bot_cost = float(bot10["rt_cost"].mean())
                
                s_gross = top_g - bot_g
                s_net = (top_g - top_cost) - (bot_g + bot_cost)
                top_net_ret = top_g - top_cost
                idx_ret = float(sub[f"index_forward_{h}d"].mean())
                
                gross_spreads.append(s_gross)
                net_spreads.append(s_net)
                lo_rets.append(top_net_ret)
                idx_rets.append(idx_ret)
                
        n_arr = np.array(net_spreads)
        g_arr = np.array(gross_spreads)
        lo_arr = np.array(lo_rets)
        idx_arr = np.array(idx_rets)
        lo_excess_arr = lo_arr - idx_arr
        
        t_stat, p_val = stats.ttest_1samp(n_arr, 0.0) if len(n_arr) > 2 else (0.0, 1.0)
        t_stat_lo, p_val_lo = stats.ttest_1samp(lo_excess_arr, 0.0) if len(lo_excess_arr) > 2 else (0.0, 1.0)
        
        horizon_results.append({
            "horizon_days": h,
            "feature_matrix_sha256": test_hash,
            "annual_cycles": round(252 / h, 1),
            "evaluated_cycles": len(n_arr),
            "top_picks_total": top_picks_cnt,
            "mean_gross_spread": round(float(np.mean(g_arr) * 100), 3),
            "mean_net_spread": round(float(np.mean(n_arr) * 100), 3),
            "net_spread_annualized": round(float(((1.0 + np.mean(n_arr)) ** (252 / h) - 1.0) * 100), 2),
            "t_stat": round(float(t_stat), 3),
            "p_val": round(float(p_val), 4),
            "long_only_net_return": round(float(np.mean(lo_arr) * 100), 3),
            "index_benchmark_return": round(float(np.mean(idx_arr) * 100), 3),
            "long_only_net_alpha": round(float(np.mean(lo_excess_arr) * 100), 3),
            "t_stat_lo": round(float(t_stat_lo), 3),
            "p_val_lo": round(float(p_val_lo), 4)
        })

    # Save artifacts
    model_3c.save_model(str(OUTPUT_DIR / "xgb_3class_base.ubj"))
    with open(OUTPUT_DIR / "xgb_features.json", "w") as f:
        json.dump(feature_cols, f, indent=2)

    walk_forward = run_walk_forward(
        full_df, feature_cols,
        [
            ("2023 H2", "2023-07-01", "2024-01-01"),
            ("2024 H2", "2024-07-01", "2025-01-01"),
            ("2025 H2/2026", "2025-07-01", None),
        ],
    )
    ablations = run_ablation_study(train_df, val_df, test_df, y_test_3c, feature_cols, model_3c, test_hash)
    v3_binary_baseline = run_v3_binary_baseline(train_df, val_df, test_df)
    action_audit["feature_matrix_sha256"] = test_hash

    return {
        "test_feature_matrix_sha256": test_hash,
        "train_feature_matrix_sha256": dataframe_sha256(train_df, feature_cols),
        "val_feature_matrix_sha256": dataframe_sha256(val_df, feature_cols),
        "test_rows": len(test_df),
        "test_start": str(test_df["date"].min().date()),
        "test_end": str(test_df["date"].max().date()),
        "acc_3c": round(float(acc_3c * 100), 4),
        "report_3c": rep_3c,
        "cm_3c": cm_3c.tolist(),
        "sorted_features": sorted_features[:15],
        "horizon_results": horizon_results,
        "walk_forward": walk_forward,
        "ablation_results": ablations,
        "v3_binary_baseline": v3_binary_baseline,
        "corporate_action_audit": action_audit,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--initialize-frozen-test-hash", action="store_true",
        help="After confirming current derived test data matches the existing frozen file, write its hash sidecar and exit without training.",
    )
    parser.add_argument(
        "--hash-only", action="store_true",
        help="Build/verify all splits, print their full feature-matrix hashes, and exit without training or reporting accuracy.",
    )
    parser.add_argument(
        "--refreeze-frozen-test-set", action="store_true",
        help="Explicitly rebuild the frozen test Parquet and both integrity hashes from the current source, then exit without training.",
    )
    parser.add_argument(
        "--part7-only", action="store_true",
        help="Run only the conditional logistic-regression and volatility-band diagnostics, then append them to the existing consolidated report.",
    )
    args = parser.parse_args()
    report_path = ROOT_DIR / "data" / "reports" / "fixed_pipeline_reverification.json"
    if args.part7_only:
        if not report_path.is_file():
            raise FileNotFoundError(f"Run the consolidated evaluation before Part 7: {report_path}")
        final_report = json.loads(report_path.read_text(encoding="utf-8"))
        final_report["part7_diagnostics"] = run_part7_diagnostics()
        report_path.write_text(json.dumps(final_report, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"report_path": str(report_path), "part7_diagnostics": final_report["part7_diagnostics"]}, indent=2, default=str))
        raise SystemExit(0)
    result = run_reproducible_evaluation(
        initialize_frozen_hash=args.initialize_frozen_test_hash, hash_only=args.hash_only,
        refreeze_frozen=args.refreeze_frozen_test_set,
    )
    if "initialized_hash" in result:
        print(json.dumps({"initialized_test_feature_matrix_sha256": result["initialized_hash"]}, indent=2))
    elif args.hash_only:
        print(json.dumps(result, indent=2))
    else:
        final_report = {
            "report_version": "corrected_fixed_pipeline",
            "xgboost_version": xgb.__version__,
            "test_accuracy_percent": result["acc_3c"],
            "feature_matrix_sha256": {
                "train": result["train_feature_matrix_sha256"],
                "validation": result["val_feature_matrix_sha256"],
                "test": result["test_feature_matrix_sha256"],
            },
            "test_rows": result["test_rows"],
            "test_date_range": [result["test_start"], result["test_end"]],
            "report_3class": result["report_3c"],
            "confusion_matrix": result["cm_3c"],
            "top_gain_features": result["sorted_features"],
            "horizon_results": result["horizon_results"],
            "walk_forward": result["walk_forward"],
            "ablation_results": result["ablation_results"],
            "v3_binary_baseline": result["v3_binary_baseline"],
            "corporate_action_audit": result["corporate_action_audit"],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(final_report, indent=2, default=str), encoding="utf-8")
        print(json.dumps({"report_path": str(report_path), **final_report}, indent=2, default=str))
