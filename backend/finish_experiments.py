"""
Finish Experiment 4 and Run Final Test Evaluation
=================================================
"""

import gc
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
import tensorflow as tf
import xgboost as xgb

from app.data.features.gru_feature_list import GRU_FEATURE_LIST
from app.data.features.labeling import LABEL_MAPPING
from app.data.features.sequence_builder import build_sequences
from app.ml.training.data_split import time_split
from app.ml.training.model import build_model
from app.ml.training.reproducibility import set_seed
from app.ml.training.scaling import apply_scaler, fit_scaler
from app.ml.training.train import train_model
from app.ml.training_xgb.feature_prep import ALL_XGB_FEATURES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("finish_experiments")

FEATURES_PATH = Path("data/features/features_daily.parquet")
EXPERIMENT_MODELS_DIR = Path("models/experiments")
REPORTS_DIR = Path("data/reports")
TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")


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
        "accuracy": round(acc, 4),
        "macro_f1": round(macro_f1, 4),
        "weighted_f1": round(weighted_f1, 4),
        "balanced_accuracy": round(bal_acc, 4),
        "per_class": per_class,
        "confusion_matrix": cm,
    }


def main():
    val_report_path = REPORTS_DIR / "controlled_experiments_val_report.json"
    all_res = json.loads(val_report_path.read_text(encoding="utf-8"))

    df_features = pd.read_parquet(FEATURES_PATH)

    normalized_features = [
        "close_to_sma20_ratio", "close_to_sma50_ratio", "ema_cross_ratio",
        "bollinger_pos", "daily_range_pct", "volume_change_1d"
    ]
    market_features = [
        "market_return_5d", "market_return_20d", "stock_return_20d", "stock_relative_return_20d"
    ]

    exp4_res = {}
    exp4_res["baseline"] = all_res["exp1_gru_weights"]["unweighted"]

    # 1. Evaluate baseline_normalized (model already saved)
    cols_norm = GRU_FEATURE_LIST + [f for f in normalized_features if f in df_features.columns]
    X_n, y_n, meta_n = build_sequences(df_features, cols_norm, LABEL_MAPPING, window_size=30)
    splits_n = time_split(X_n, y_n, meta_n)
    scaler_n = fit_scaler(splits_n["train"]["X"])
    X_val_n_s = apply_scaler(splits_n["val"]["X"], scaler_n)

    model_norm = tf.keras.models.load_model(EXPERIMENT_MODELS_DIR / "gru_baseline_normalized.keras")
    val_probs_n = model_norm.predict(X_val_n_s, verbose=0)
    val_preds_n = np.argmax(val_probs_n, axis=1)
    res_norm = get_full_eval_dict(splits_n["val"]["y"], val_preds_n, "GRU Feature Set: baseline_normalized")
    res_norm["n_features"] = len(cols_norm)
    exp4_res["baseline_normalized"] = res_norm

    del X_n, y_n, meta_n, splits_n, X_val_n_s, model_norm
    gc.collect()

    # 2. Train & Evaluate baseline_norm_market
    cols_mkt = GRU_FEATURE_LIST + [f for f in normalized_features + market_features if f in df_features.columns]
    X_m, y_m, meta_m = build_sequences(df_features, cols_mkt, LABEL_MAPPING, window_size=30)
    splits_m = time_split(X_m, y_m, meta_m)
    X_train_m, y_train_m = splits_m["train"]["X"], splits_m["train"]["y"]
    X_val_m, y_val_m = splits_m["val"]["X"], splits_m["val"]["y"]
    X_test_m, y_test_m = splits_m["test"]["X"], splits_m["test"]["y"]
    del X_m, y_m, meta_m, splits_m
    gc.collect()

    scaler_m = fit_scaler(X_train_m)
    X_train_m_s = apply_scaler(X_train_m, scaler_m)
    X_val_m_s = apply_scaler(X_val_m, scaler_m)
    X_test_m_s = apply_scaler(X_test_m, scaler_m)
    del X_train_m, X_val_m, X_test_m
    gc.collect()

    set_seed(42)
    input_shape = (X_train_m_s.shape[1], X_train_m_s.shape[2])
    model_mkt = build_model(input_shape, n_classes=3)
    train_model(
        model_mkt, X_train_m_s, y_train_m, X_val_m_s, y_val_m,
        batch_size=32, max_epochs=35, patience=5,
        model_save_path=EXPERIMENT_MODELS_DIR / "gru_baseline_norm_market.keras",
    )
    val_probs_m = model_mkt.predict(X_val_m_s, verbose=0)
    val_preds_m = np.argmax(val_probs_m, axis=1)
    res_mkt = get_full_eval_dict(y_val_m, val_preds_m, "GRU Feature Set: baseline_norm_market")
    res_mkt["n_features"] = len(cols_mkt)
    exp4_res["baseline_norm_market"] = res_mkt

    all_res["exp4_features"] = exp4_res
    val_report_path.write_text(json.dumps(all_res, indent=2), encoding="utf-8")
    log.info("Full validation experiment report updated -> %s", val_report_path)

    # 3. Final Test Evaluation on Untouched Test Set for selected configurations
    log.info("\n=== RUNNING TEST SET EVALUATION ===")
    test_eval_results = {}

    # Load baseline test set
    seq_data = np.load("data/sequences/sequences.npz")
    splits_base = time_split(seq_data["X"].astype(np.float32), seq_data["y"], pd.read_parquet("data/sequences/sequences_meta.parquet"))
    scaler_base = fit_scaler(splits_base["train"]["X"])
    X_test_base_s = apply_scaler(splits_base["test"]["X"], scaler_base)
    y_test_base = splits_base["test"]["y"]
    meta_test_base = splits_base["test"]["meta"]

    # GRU Balanced model on test
    gru_weighted_model = tf.keras.models.load_model(EXPERIMENT_MODELS_DIR / "gru_weighted.keras")
    gru_wt_test_probs = gru_weighted_model.predict(X_test_base_s, verbose=0)
    gru_wt_test_preds = np.argmax(gru_wt_test_probs, axis=1)
    test_eval_results["gru_balanced_weighted"] = get_full_eval_dict(y_test_base, gru_wt_test_preds, "GRU Balanced Weights (Test Set)")

    # GRU Norm+Market on test
    gru_mkt_test_probs = model_mkt.predict(X_test_m_s, verbose=0)
    gru_mkt_test_preds = np.argmax(gru_mkt_test_probs, axis=1)
    test_eval_results["gru_norm_market_features"] = get_full_eval_dict(y_test_m, gru_mkt_test_preds, "GRU Norm+Market Features (Test Set)")

    # XGBoost Weighted on test
    df_xgb = pd.read_parquet("data/processed/features_xgb.parquet")
    feature_names_xgb = [c for c in ALL_XGB_FEATURES if c in df_xgb.columns]
    train_mask_xgb = pd.to_datetime(df_xgb["date"]) < TRAIN_CUTOFF
    X_xgb_train = df_xgb.loc[train_mask_xgb, feature_names_xgb].values.astype(np.float32)
    fill_meds = np.zeros(len(feature_names_xgb), dtype=np.float32)
    for f_idx in range(len(feature_names_xgb)):
        col = X_xgb_train[:, f_idx]
        valid = col[~np.isnan(col)]
        fill_meds[f_idx] = float(np.median(valid)) if len(valid) > 0 else 0.0

    df_xgb_idx = df_xgb.copy()
    df_xgb_idx["date_dt"] = pd.to_datetime(df_xgb_idx["date"])
    meta_test_copy = meta_test_base.copy()
    meta_test_copy["date_dt"] = pd.to_datetime(meta_test_copy["date"])
    merged = pd.merge(meta_test_copy, df_xgb_idx, on=["symbol", "date_dt"], how="left")
    X_xgb_test = merged[feature_names_xgb].values.astype(np.float32)
    for f_idx in range(len(feature_names_xgb)):
        X_xgb_test[np.isnan(X_xgb_test[:, f_idx]), f_idx] = fill_meds[f_idx]

    xgb_wt_model = xgb.XGBClassifier()
    xgb_wt_model.load_model("models/xgb_v1/xgb_v1_weighted.xgb")
    xgb_wt_test_probs = xgb_wt_model.predict_proba(X_xgb_test)
    xgb_wt_test_preds = np.argmax(xgb_wt_test_probs, axis=1)
    test_eval_results["xgboost_weighted"] = get_full_eval_dict(y_test_base, xgb_wt_test_preds, "XGBoost Weighted (Test Set)")

    # Weighted Ensemble test: 50% GRU Balanced + 50% XGB Weighted
    ens_wt_probs = 0.5 * gru_wt_test_probs + 0.5 * xgb_wt_test_probs
    ens_wt_preds = np.argmax(ens_wt_probs, axis=1)
    test_eval_results["ensemble_weighted"] = get_full_eval_dict(y_test_base, ens_wt_preds, "Ensemble Weighted (GRU Bal + XGB Wt) (Test Set)")

    test_report_path = REPORTS_DIR / "controlled_experiments_test_report.json"
    test_report_path.write_text(json.dumps(test_eval_results, indent=2), encoding="utf-8")
    log.info("Saved final test evaluation results -> %s", test_report_path)


if __name__ == "__main__":
    main()
