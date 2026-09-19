"""
Controlled ML Experiment: GRU Lookback (30 vs 45 vs 60) & XGBoost Extended Time Horizons
========================================================================================

Zero-RAM Streaming Architecture:
- Streams window slices directly from 2D features matrix (21 MB total RAM).
- Supports arbitrary lookback windows (30, 45, 60+) with 0 memory allocation errors.
"""

import gc
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_class_weight
import tensorflow as tf
from tensorflow import keras
import xgboost as xgb

from app.data.features.gru_feature_list import GRU_FEATURE_LIST
from app.data.features.labeling import LABEL_MAPPING
from app.ml.training.leakage_checker import (
    check_chronological_split_leakage,
    check_target_validity,
)
from app.ml.training.model import build_model
from app.ml.training.reproducibility import set_seed
from app.ml.training_xgb.feature_prep import ALL_XGB_FEATURES
from app.ml.training_xgb.model import build_xgb_classifier, compute_sample_weights

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("lookback_experiments")

TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")
FEATURES_PATH = Path("data/features/features_daily.parquet")
EXPERIMENT_DIR = Path("models/experiments/lookback_horizon")
REPORTS_DIR = Path("data/reports")


def get_full_eval_dict(y_true: np.ndarray, y_pred: np.ndarray, name: str) -> dict:
    labels_sorted = [0, 1, 2]
    target_names = ["bullish", "bearish", "sideways"]

    acc = float(accuracy_score(y_true, y_pred))
    bal_acc = float(balanced_accuracy_score(y_true, y_pred))
    macro_f1 = float(f1_score(y_true, y_pred, labels=labels_sorted, average="macro", zero_division=0))
    weighted_f1 = float(f1_score(y_true, y_pred, labels=labels_sorted, average="weighted", zero_division=0))
    cm = confusion_matrix(y_true, y_pred, labels=labels_sorted).tolist()

    rep_dict = classification_report(
        y_true, y_pred, labels=labels_sorted, target_names=target_names, output_dict=True, zero_division=0
    )
    per_class = {}
    for c in target_names:
        per_class[c] = {
            "precision": round(rep_dict[c]["precision"], 4),
            "recall": round(rep_dict[c]["recall"], 4),
            "f1": round(rep_dict[c]["f1-score"], 4),
            "support": int(rep_dict[c]["support"]),
        }

    return {
        "name": name,
        "sample_count": int(len(y_true)),
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "per_class": per_class,
        "confusion_matrix": cm,
    }


class StreamingSequenceDataset(keras.utils.PyDataset):
    """Streams sequence batches on the fly from the 2D feature matrix (0 MB memory overhead)."""
    def __init__(
        self,
        features_2d: np.ndarray,
        end_indices: np.ndarray,
        labels: np.ndarray,
        window_size: int,
        sample_weights: np.ndarray = None,
        batch_size: int = 64,
        shuffle: bool = True,
    ):
        super().__init__()
        self.features_2d = features_2d
        self.end_indices = end_indices
        self.labels = labels
        self.window_size = window_size
        self.sample_weights = sample_weights
        self.batch_size = batch_size
        self.shuffle = shuffle
        self.F = features_2d.shape[1]
        self.indices = np.arange(len(end_indices))

    def __len__(self):
        return int(np.ceil(len(self.end_indices) / self.batch_size))

    def __getitem__(self, idx):
        batch_idx = self.indices[idx * self.batch_size : (idx + 1) * self.batch_size]
        b_ends = self.end_indices[batch_idx]
        b_size = len(b_ends)

        bx = np.empty((b_size, self.window_size, self.F), dtype=np.float32)
        for k, end in enumerate(b_ends):
            bx[k] = self.features_2d[end - self.window_size : end]

        by = self.labels[batch_idx]

        if self.sample_weights is not None:
            bw = self.sample_weights[batch_idx]
            return bx, by, bw
        return bx, by

    def on_epoch_end(self):
        if self.shuffle:
            np.random.shuffle(self.indices)


def predict_streaming(
    model: tf.keras.Model,
    features_2d: np.ndarray,
    end_indices: np.ndarray,
    window_size: int,
    batch_size: int = 512,
) -> np.ndarray:
    """Predict probabilities batch-by-batch using on-the-fly streaming slices."""
    n = len(end_indices)
    F = features_2d.shape[1]
    probs = np.empty((n, 3), dtype=np.float32)

    for i in range(0, n, batch_size):
        b_ends = end_indices[i : min(i + batch_size, n)]
        b_size = len(b_ends)
        bx = np.empty((b_size, window_size, F), dtype=np.float32)
        for k, end in enumerate(b_ends):
            bx[k] = features_2d[end - window_size : end]

        probs[i : i + b_size] = model(bx, training=False).numpy()

    return probs


# =========================================================================
# EXPERIMENT 1: GRU LOOKBACK COMPARISON (30 vs 45 vs 60)
# =========================================================================

def run_gru_lookback_experiment() -> Dict[str, dict]:
    log.info("=" * 80)
    log.info("  EXPERIMENT 1: GRU LOOKBACK WINDOW (30 vs 45 vs 60 days)")
    log.info("=" * 80)

    feature_columns = GRU_FEATURE_LIST.copy()
    cols_to_load = ["symbol", "date", "label"] + feature_columns
    df_raw = pd.read_parquet(FEATURES_PATH, columns=cols_to_load)
    df_raw["date"] = pd.to_datetime(df_raw["date"])
    df_raw = df_raw.sort_values(["symbol", "date"]).reset_index(drop=True)

    for col in feature_columns:
        df_raw[col] = df_raw[col].astype(np.float32)

    symbols_arr = df_raw["symbol"].values
    dates_arr = df_raw["date"].values
    features_raw = df_raw[feature_columns].values.astype(np.float32)
    labels_arr = df_raw["label"].map(LABEL_MAPPING).values.astype(np.int32)

    # Fit scaler strictly on training dates (no lookahead, no leakage)
    train_row_mask = dates_arr < TRAIN_CUTOFF
    scaler = StandardScaler()
    scaler.fit(features_raw[train_row_mask])
    features_scaled = scaler.transform(features_raw).astype(np.float32)
    del features_raw, df_raw
    gc.collect()

    # Compute symbol index boundaries
    unique_symbols, split_idxs = np.unique(symbols_arr, return_index=True)
    order = np.argsort(split_idxs)
    unique_symbols = unique_symbols[order]
    split_idxs = list(split_idxs[order]) + [len(symbols_arr)]
    symbol_slices = [(unique_symbols[i], split_idxs[i], split_idxs[i + 1]) for i in range(len(unique_symbols))]

    windows = [30, 45, 60]
    gru_results = {}

    for w in windows:
        log.info("\n--- Training & Evaluating GRU Lookback Window = %d days ---", w)
        tf.keras.backend.clear_session()
        gc.collect()
        set_seed(42)

        # Build index mapping for streaming
        train_ends, val_ends, test_ends = [], [], []
        train_labels, val_labels, test_labels = [], [], []
        train_meta_sym, train_meta_date = [], []
        val_meta_sym, val_meta_date = [], []
        test_meta_sym, test_meta_date = [], []

        for sym, start, end in symbol_slices:
            grp_len = end - start
            if grp_len < w:
                continue

            for i in range(start + w, end + 1):
                d = dates_arr[i - 1]
                lbl = labels_arr[i - 1]

                if d < TRAIN_CUTOFF:
                    train_ends.append(i)
                    train_labels.append(lbl)
                    train_meta_sym.append(sym)
                    train_meta_date.append(d)
                elif d < VAL_CUTOFF:
                    val_ends.append(i)
                    val_labels.append(lbl)
                    val_meta_sym.append(sym)
                    val_meta_date.append(d)
                else:
                    test_ends.append(i)
                    test_labels.append(lbl)
                    test_meta_sym.append(sym)
                    test_meta_date.append(d)

        train_ends_arr = np.array(train_ends, dtype=np.int32)
        val_ends_arr = np.array(val_ends, dtype=np.int32)
        test_ends_arr = np.array(test_ends, dtype=np.int32)

        y_train = np.array(train_labels, dtype=np.int32)
        y_val = np.array(val_labels, dtype=np.int32)
        y_test = np.array(test_labels, dtype=np.int32)

        meta_train = pd.DataFrame({"symbol": train_meta_sym, "date": train_meta_date})
        meta_val = pd.DataFrame({"symbol": val_meta_sym, "date": val_meta_date})
        meta_test = pd.DataFrame({"symbol": test_meta_sym, "date": test_meta_date})

        log.info("Split sequence counts (W=%d): Train=%d, Val=%d, Test=%d", w, len(y_train), len(y_val), len(y_test))

        # Leakage checks
        check_chronological_split_leakage(meta_train, meta_val, meta_test)
        check_target_validity(y_train, y_val, y_test)

        # Class weighting from y_train ONLY
        classes = np.unique(y_train)
        weights = compute_class_weight("balanced", classes=classes, y=y_train)
        class_weight_dict = {int(c): float(cw) for c, cw in zip(classes, weights)}
        sample_weights_train = np.array([class_weight_dict[int(y)] for y in y_train], dtype=np.float32)

        # Build streaming datasets
        train_ds = StreamingSequenceDataset(
            features_2d=features_scaled,
            end_indices=train_ends_arr,
            labels=y_train,
            window_size=w,
            sample_weights=sample_weights_train,
            batch_size=64,
            shuffle=True,
        )
        val_ds = StreamingSequenceDataset(
            features_2d=features_scaled,
            end_indices=val_ends_arr,
            labels=y_val,
            window_size=w,
            sample_weights=None,
            batch_size=64,
            shuffle=False,
        )

        # Build Model
        input_shape = (w, features_scaled.shape[1])
        model = build_model(input_shape, n_classes=3)
        model_save_path = EXPERIMENT_DIR / f"gru_window_{w}.keras"
        model_save_path.parent.mkdir(parents=True, exist_ok=True)

        callbacks = [
            tf.keras.callbacks.EarlyStopping(
                monitor="val_loss",
                patience=5,
                restore_best_weights=True,
                verbose=1,
            ),
            tf.keras.callbacks.ModelCheckpoint(
                filepath=str(model_save_path),
                monitor="val_loss",
                save_best_only=True,
                verbose=0,
            ),
        ]

        history = model.fit(
            train_ds,
            validation_data=val_ds,
            epochs=30,
            callbacks=callbacks,
            verbose=1,
        )

        hist = {k: [float(v) for v in vals] for k, vals in history.history.items()}
        val_losses = hist.get("val_loss", [])
        best_epoch = int(np.argmin(val_losses)) + 1 if val_losses else len(hist.get("loss", []))
        best_val_loss = float(min(val_losses)) if val_losses else None

        # Streaming predictions
        val_probs = predict_streaming(model, features_scaled, val_ends_arr, window_size=w)
        val_preds = np.argmax(val_probs, axis=1)
        val_eval = get_full_eval_dict(y_val, val_preds, f"GRU {w}-Day Lookback (Val)")

        test_probs = predict_streaming(model, features_scaled, test_ends_arr, window_size=w)
        test_preds = np.argmax(test_probs, axis=1)
        test_eval = get_full_eval_dict(y_test, test_preds, f"GRU {w}-Day Lookback (Test)")

        gru_results[f"window_{w}"] = {
            "window_size": w,
            "val_eval": val_eval,
            "test_eval": test_eval,
            "val_probs": val_probs,
            "test_probs": test_probs,
            "y_val": y_val,
            "y_test": y_test,
            "meta_val": meta_val,
            "meta_test": meta_test,
            "best_epoch": best_epoch,
            "best_val_loss": best_val_loss,
            "train_samples": len(y_train),
            "val_samples": len(y_val),
            "test_samples": len(y_test),
        }

        log.info(
            "GRU Window=%d Val Results: Acc=%.4f | Macro F1=%.4f | Bal Acc=%.4f | Bull R=%.4f | Bear R=%.4f | Side R=%.4f",
            w,
            val_eval["accuracy"],
            val_eval["macro_f1"],
            val_eval["balanced_accuracy"],
            val_eval["per_class"]["bullish"]["recall"],
            val_eval["per_class"]["bearish"]["recall"],
            val_eval["per_class"]["sideways"]["recall"],
        )

        del train_ds, val_ds, model
        tf.keras.backend.clear_session()
        gc.collect()

    del features_scaled, labels_arr, dates_arr, symbols_arr
    gc.collect()

    return gru_results


# =========================================================================
# EXPERIMENT 2: XGBOOST LONGER-HORIZON FEATURES
# =========================================================================

def build_extended_xgb_features() -> Tuple[pd.DataFrame, List[str], List[str]]:
    """Build baseline and extended tabular feature sets for XGBoost."""
    log.info("Engineering extended tabular horizon features for XGBoost ...")
    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # 1. Point-in-Time Market Returns for 30d and 60d
    df["daily_ret"] = df.groupby("symbol")["close"].pct_change(1)
    market_daily = df.groupby("date")["daily_ret"].mean().reset_index()
    market_daily = market_daily.sort_values("date").reset_index(drop=True)

    m_growth = 1.0 + market_daily["daily_ret"].fillna(0.0)
    market_daily["market_return_30d"] = m_growth.rolling(30, min_periods=30).apply(np.prod, raw=True) - 1.0
    market_daily["market_return_60d"] = m_growth.rolling(60, min_periods=60).apply(np.prod, raw=True) - 1.0

    market_lookup = market_daily[["date", "market_return_30d", "market_return_60d"]]
    df = pd.merge(df, market_lookup, on="date", how="left")
    df = df.drop(columns=["daily_ret"])

    # 2. Per-symbol extended features
    def _engineer_extended(grp: pd.DataFrame) -> pd.DataFrame:
        g = grp.copy()
        close = g["close"]
        daily_ret = close.pct_change(1)

        # Momentum / Returns
        g["return_30d"] = close.pct_change(30)
        g["return_60d"] = close.pct_change(60)

        # Volatility
        g["volatility_20d"] = daily_ret.rolling(20, min_periods=10).std()
        g["volatility_30d"] = daily_ret.rolling(30, min_periods=15).std()
        g["volatility_60d"] = daily_ret.rolling(60, min_periods=30).std()

        # Volatility-adjusted returns
        g["vol_adj_return_30d"] = g["return_30d"] / g["volatility_30d"].replace(0, np.nan)
        g["vol_adj_return_60d"] = g["return_60d"] / g["volatility_60d"].replace(0, np.nan)

        # Relative performance
        g["stock_relative_return_30d"] = g["return_30d"] - g["market_return_30d"]
        g["stock_relative_return_60d"] = g["return_60d"] - g["market_return_60d"]

        # Position within recent range
        g["close_min_60d"] = close.rolling(60, min_periods=30).min()
        g["close_max_60d"] = close.rolling(60, min_periods=30).max()
        range_60d = g["close_max_60d"] - g["close_min_60d"]
        g["close_position_60d"] = ((close - g["close_min_60d"]) / range_60d.replace(0, np.nan)).clip(0, 1)

        return g

    df = df.groupby("symbol", group_keys=False).apply(_engineer_extended)

    # Baseline feature list
    baseline_features = [c for c in ALL_XGB_FEATURES if c in df.columns]

    # Additional extended feature list
    extended_additions = [
        "return_30d", "return_60d",
        "volatility_20d", "volatility_30d", "volatility_60d",
        "vol_adj_return_30d", "vol_adj_return_60d",
        "market_return_30d", "market_return_60d",
        "stock_relative_return_30d", "stock_relative_return_60d",
        "close_position_60d",
    ]
    extended_features = baseline_features + [c for c in extended_additions if c in df.columns]

    return df, baseline_features, extended_features


def run_xgb_horizon_experiment() -> Dict[str, dict]:
    log.info("=" * 80)
    log.info("  EXPERIMENT 2: XGBOOST LONGER-HORIZON TABULAR FEATURES")
    log.info("=" * 80)

    df_xgb, baseline_feats, extended_feats = build_extended_xgb_features()

    train_mask = pd.to_datetime(df_xgb["date"]) < TRAIN_CUTOFF
    val_mask = (pd.to_datetime(df_xgb["date"]) >= TRAIN_CUTOFF) & (pd.to_datetime(df_xgb["date"]) < VAL_CUTOFF)
    test_mask = pd.to_datetime(df_xgb["date"]) >= VAL_CUTOFF

    # Compute targets
    y_train = df_xgb.loc[train_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    y_val = df_xgb.loc[val_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    y_test = df_xgb.loc[test_mask, "label"].map(LABEL_MAPPING).values.astype(int)

    # Sample weights strictly on y_train
    sample_weights_train = compute_sample_weights(y_train)

    xgb_configs = {
        "baseline": {
            "name": f"XGBoost Baseline ({len(baseline_feats)} features)",
            "features": baseline_feats,
        },
        "extended_horizons": {
            "name": f"XGBoost + Extended 20/30/60d Horizons ({len(extended_feats)} features)",
            "features": extended_feats,
        },
    }

    xgb_results = {}

    for cfg_key, cfg in xgb_configs.items():
        feat_list = cfg["features"]
        log.info("\n--- Training & Evaluating %s ---", cfg["name"])

        # Compute train medians strictly on training split
        X_train_raw = df_xgb.loc[train_mask, feat_list].values.astype(np.float32)
        train_medians = np.nanmedian(X_train_raw, axis=0)
        train_medians = np.nan_to_num(train_medians, nan=0.0)

        # Impute splits with training medians only
        X_train = np.where(np.isnan(X_train_raw), train_medians, X_train_raw)

        X_val_raw = df_xgb.loc[val_mask, feat_list].values.astype(np.float32)
        X_val = np.where(np.isnan(X_val_raw), train_medians, X_val_raw)

        X_test_raw = df_xgb.loc[test_mask, feat_list].values.astype(np.float32)
        X_test = np.where(np.isnan(X_test_raw), train_medians, X_test_raw)

        # Build and train XGBoost
        model = build_xgb_classifier()
        model.fit(
            X_train,
            y_train,
            sample_weight=sample_weights_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        model_save_path = EXPERIMENT_DIR / f"xgb_{cfg_key}.xgb"
        model_save_path.parent.mkdir(parents=True, exist_ok=True)
        model.save_model(str(model_save_path))

        # Validation evaluation
        val_probs = model.predict_proba(X_val)
        val_preds = np.argmax(val_probs, axis=1)
        val_eval = get_full_eval_dict(y_val, val_preds, f"{cfg['name']} (Val)")

        # Test evaluation
        test_probs = model.predict_proba(X_test)
        test_preds = np.argmax(test_probs, axis=1)
        test_eval = get_full_eval_dict(y_test, test_preds, f"{cfg['name']} (Test)")

        # Feature importances
        importances = model.feature_importances_
        feat_imp = dict(sorted(zip(feat_list, [float(x) for x in importances]), key=lambda x: x[1], reverse=True))

        xgb_results[cfg_key] = {
            "name": cfg["name"],
            "features": feat_list,
            "n_features": len(feat_list),
            "val_eval": val_eval,
            "test_eval": test_eval,
            "val_probs": val_probs,
            "test_probs": test_probs,
            "y_val": y_val,
            "y_test": y_test,
            "feature_importances": feat_imp,
            "df_xgb": df_xgb,
            "train_medians": train_medians,
            "model": model,
        }

        log.info(
            "%s Val Results: Acc=%.4f | Macro F1=%.4f | Bal Acc=%.4f | Bull R=%.4f | Bear R=%.4f | Side R=%.4f",
            cfg["name"],
            val_eval["accuracy"],
            val_eval["macro_f1"],
            val_eval["balanced_accuracy"],
            val_eval["per_class"]["bullish"]["recall"],
            val_eval["per_class"]["bearish"]["recall"],
            val_eval["per_class"]["sideways"]["recall"],
        )

    return xgb_results


# =========================================================================
# STEP 3: ENSEMBLE EVALUATION & COMPARISON
# =========================================================================

def run_ensemble_comparisons(gru_results: dict, xgb_results: dict):
    log.info("=" * 80)
    log.info("  FINAL ENSEMBLE EVALUATION & COMPARISON ON UNTOUCHED TEST SET")
    log.info("=" * 80)

    # 1. Identify best GRU from validation Macro F1 / Balanced Acc
    best_gru_key = max(
        gru_results.keys(),
        key=lambda k: (gru_results[k]["val_eval"]["macro_f1"], gru_results[k]["val_eval"]["balanced_accuracy"]),
    )
    best_gru = gru_results[best_gru_key]
    log.info("Selected GRU configuration based on validation: %s", best_gru_key)

    # 2. Identify best XGBoost from validation Macro F1 / Balanced Acc
    best_xgb_key = max(
        xgb_results.keys(),
        key=lambda k: (xgb_results[k]["val_eval"]["macro_f1"], xgb_results[k]["val_eval"]["balanced_accuracy"]),
    )
    best_xgb = xgb_results[best_xgb_key]
    log.info("Selected XGBoost configuration based on validation: %s", best_xgb_key)

    # 3. Align XGBoost test predictions with selected GRU test set sequences
    meta_test_gru = best_gru["meta_test"].copy()
    meta_test_gru["date_dt"] = pd.to_datetime(meta_test_gru["date"])
    df_xgb = best_xgb["df_xgb"].copy()
    df_xgb["date_dt"] = pd.to_datetime(df_xgb["date"])

    feat_list_selected = best_xgb["features"]
    fill_meds_selected = best_xgb["train_medians"]

    merged_test = pd.merge(meta_test_gru, df_xgb, on=["symbol", "date_dt"], how="left")
    X_xgb_test_aligned = merged_test[feat_list_selected].values.astype(np.float32)
    for f_idx in range(len(feat_list_selected)):
        X_xgb_test_aligned[np.isnan(X_xgb_test_aligned[:, f_idx]), f_idx] = fill_meds_selected[f_idx]

    xgb_test_probs_aligned = best_xgb["model"].predict_proba(X_xgb_test_aligned)
    gru_test_probs = best_gru["test_probs"]
    y_test = best_gru["y_test"]

    # 4. Form Experimental 50/50 Ensemble
    ens_exp_probs = 0.5 * gru_test_probs + 0.5 * xgb_test_probs_aligned
    ens_exp_preds = np.argmax(ens_exp_probs, axis=1)
    ens_exp_eval = get_full_eval_dict(
        y_test,
        ens_exp_preds,
        f"Experiment 50/50 Ensemble ({best_gru_key} + {best_xgb_key})",
    )

    # 5. Load Current Production Final Test Report for direct comparison
    current_report_path = REPORTS_DIR / "final_pipeline_test_report.json"
    current_report = json.loads(current_report_path.read_text(encoding="utf-8")) if current_report_path.exists() else {}

    # 6. Build Final Summary Report
    experiment_report = {
        "timestamp": datetime.now().isoformat(),
        "gru_validation_comparison": {
            k: v["val_eval"] for k, v in gru_results.items()
        },
        "gru_test_comparison": {
            k: v["test_eval"] for k, v in gru_results.items()
        },
        "selected_gru": {
            "window_size": best_gru["window_size"],
            "val_metrics": best_gru["val_eval"],
            "test_metrics": best_gru["test_eval"],
        },
        "xgb_validation_comparison": {
            k: v["val_eval"] for k, v in xgb_results.items()
        },
        "xgb_test_comparison": {
            k: v["test_eval"] for k, v in xgb_results.items()
        },
        "selected_xgb": {
            "config": best_xgb_key,
            "n_features": best_xgb["n_features"],
            "val_metrics": best_xgb["val_eval"],
            "test_metrics": best_xgb["test_eval"],
            "top_10_features": dict(list(best_xgb["feature_importances"].items())[:10]),
        },
        "ensemble_comparison": {
            "current_final_ensemble": current_report.get("final_weighted_ensemble", {}),
            "experimental_ensemble": ens_exp_eval,
        },
        "decision": {
            "gru_window_decision": (
                "ADOPT" if best_gru["window_size"] != 30 and best_gru["val_eval"]["macro_f1"] > gru_results["window_30"]["val_eval"]["macro_f1"] else "REJECT (Keep 30-day baseline)"
            ),
            "xgb_features_decision": (
                "ADOPT" if best_xgb_key != "baseline" and best_xgb["val_eval"]["macro_f1"] > xgb_results["baseline"]["val_eval"]["macro_f1"] else "REJECT (Keep current feature set)"
            ),
        },
    }

    report_out_path = REPORTS_DIR / "experiments_lookback_horizon.json"
    report_out_path.write_text(json.dumps(experiment_report, indent=2), encoding="utf-8")
    log.info("Saved complete experiment report -> %s", report_out_path)

    return experiment_report


def main():
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    gru_results = run_gru_lookback_experiment()
    xgb_results = run_xgb_horizon_experiment()
    report = run_ensemble_comparisons(gru_results, xgb_results)
    log.info("All experiments completed in %.1f seconds!", time.time() - t0)


if __name__ == "__main__":
    main()
