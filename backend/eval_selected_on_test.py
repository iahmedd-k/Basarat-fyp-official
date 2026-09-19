"""
Evaluate Selected Configurations on Untouched Test Set — Ultra Lean
===================================================================
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
from sklearn.preprocessing import StandardScaler
import tensorflow as tf
import xgboost as xgb

from app.data.features.gru_feature_list import GRU_FEATURE_LIST
from app.data.features.labeling import LABEL_MAPPING
from app.data.features.sequence_builder import build_sequences
from app.ml.training.scaling import apply_scaler, fit_scaler
from app.ml.training_xgb.feature_prep import ALL_XGB_FEATURES

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("eval_selected_test")

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
    test_eval_results = {}

    # 1. Load baseline test split for GRU
    seq_data = np.load("data/sequences/sequences.npz")
    meta_df = pd.read_parquet("data/sequences/sequences_meta.parquet")
    dates = pd.to_datetime(meta_df["date"])
    train_mask = dates < TRAIN_CUTOFF
    test_mask = dates >= VAL_CUTOFF

    X_train_base = np.ascontiguousarray(seq_data["X"][train_mask], dtype=np.float32)
    X_test_base = np.ascontiguousarray(seq_data["X"][test_mask], dtype=np.float32)
    y_test_base = seq_data["y"][test_mask]
    meta_test_base = meta_df.loc[test_mask].reset_index(drop=True)
    del seq_data, meta_df
    gc.collect()

    scaler_base = fit_scaler(X_train_base)
    X_test_base_s = apply_scaler(X_test_base, scaler_base)
    del X_train_base, X_test_base
    gc.collect()

    # Model 1: GRU Balanced Weights on Test Set
    log.info("Evaluating GRU Balanced Weights on Test Set ...")
    gru_weighted_model = tf.keras.models.load_model(EXPERIMENT_MODELS_DIR / "gru_weighted.keras")
    gru_wt_test_probs = gru_weighted_model.predict(X_test_base_s, verbose=0)
    gru_wt_test_preds = np.argmax(gru_wt_test_probs, axis=1)
    test_eval_results["gru_balanced_weighted"] = get_full_eval_dict(
        y_test_base, gru_wt_test_preds, "GRU Balanced Class Weights (Test Set)"
    )

    # Model 2: XGBoost Weighted on Test Set
    log.info("Evaluating XGBoost Weighted on Test Set ...")
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
    test_eval_results["xgboost_weighted"] = get_full_eval_dict(
        y_test_base, xgb_wt_test_preds, "XGBoost Weighted (Test Set)"
    )

    # Model 3: Weighted Ensemble (GRU Balanced + XGB Weighted) on Test Set
    log.info("Evaluating Weighted Ensemble on Test Set ...")
    ens_wt_probs = 0.5 * gru_wt_test_probs + 0.5 * xgb_wt_test_probs
    ens_wt_preds = np.argmax(ens_wt_probs, axis=1)
    test_eval_results["ensemble_weighted"] = get_full_eval_dict(
        y_test_base, ens_wt_preds, "Ensemble Weighted (GRU Bal + XGB Wt) (Test Set)"
    )

    del X_test_base_s, gru_weighted_model, df_xgb, df_xgb_idx, merged, X_xgb_test, xgb_wt_model
    gc.collect()

    # Model 4: GRU with Normalized + Market-Relative Features on Test Set
    log.info("Evaluating GRU Norm+Market Features on Test Set ...")
    df_features = pd.read_parquet(FEATURES_PATH)
    normalized_features = [
        "close_to_sma20_ratio", "close_to_sma50_ratio", "ema_cross_ratio",
        "bollinger_pos", "daily_range_pct", "volume_change_1d"
    ]
    market_features = [
        "market_return_5d", "market_return_20d", "stock_return_20d", "stock_relative_return_20d"
    ]
    best_feat_cols = GRU_FEATURE_LIST + [
        f for f in normalized_features + market_features if f in df_features.columns
    ]

    # Fit 2D scaler directly on training rows
    train_mask_f = pd.to_datetime(df_features["date"]) < TRAIN_CUTOFF
    scaler_bf = StandardScaler()
    scaler_bf.fit(df_features.loc[train_mask_f, best_feat_cols].values.astype(np.float32))

    # Scale feature dataframe directly in-place
    df_scaled = df_features.copy()
    df_scaled[best_feat_cols] = scaler_bf.transform(df_features[best_feat_cols].values.astype(np.float32))
    del df_features
    gc.collect()

    # Build sequences
    X_bf, y_bf, meta_bf = build_sequences(df_scaled, best_feat_cols, LABEL_MAPPING, window_size=30)
    del df_scaled
    gc.collect()

    test_mask_bf = pd.to_datetime(meta_bf["date"]) >= VAL_CUTOFF
    X_test_bf = np.ascontiguousarray(X_bf[test_mask_bf], dtype=np.float32)
    y_test_bf = y_bf[test_mask_bf]
    del X_bf, y_bf, meta_bf
    gc.collect()

    gru_bf_model = tf.keras.models.load_model(EXPERIMENT_MODELS_DIR / "gru_baseline_norm_market.keras")
    gru_bf_test_probs = gru_bf_model.predict(X_test_bf, verbose=0)
    gru_bf_test_preds = np.argmax(gru_bf_test_probs, axis=1)
    test_eval_results["gru_norm_market_features"] = get_full_eval_dict(
        y_test_bf, gru_bf_test_preds, "GRU Norm+Market Features (Test Set)"
    )

    # Save report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = REPORTS_DIR / "controlled_experiments_test_report.json"
    out_path.write_text(json.dumps(test_eval_results, indent=2), encoding="utf-8")
    log.info("Saved final test evaluation results -> %s", out_path)

    # Print clean summary table
    print("\n" + "=" * 95)
    print(f"{'Selected Configuration (Test Set)':<45} {'Accuracy':>10} {'Macro F1':>10} {'Weighted F1':>12} {'Bal Acc':>10}")
    print("-" * 95)
    for k, m in test_eval_results.items():
        print(f"{m['name']:<45} {m['accuracy']:>10.4f} {m['macro_f1']:>10.4f} {m['weighted_f1']:>12.4f} {m['balanced_accuracy']:>10.4f}")
    print("=" * 95)


if __name__ == "__main__":
    main()
