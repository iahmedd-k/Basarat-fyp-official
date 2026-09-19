"""
Master Controlled ML Experiments Runner — Memory Optimized & Incremental
========================================================================
Runs the 4 specified controlled experiments using the VALIDATION set for selection:
1. GRU Baseline vs GRU Balanced Class Weights
2. XGBoost Unweighted vs XGBoost Weighted
3. Label Thresholds: 0.005, 0.010, 0.015, 0.020
4. Feature Sets: Baseline vs Normalized vs Market-Relative

At the end, identifies the best configuration(s) based on Validation Macro F1,
Balanced Accuracy, and Bullish/Bearish recall, and runs a single test set evaluation.
"""

import gc
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)
from sklearn.utils.class_weight import compute_class_weight
import tensorflow as tf
import xgboost as xgb

from app.data.features.gru_feature_list import GRU_FEATURE_LIST
from app.data.features.labeling import LABEL_MAPPING, label_from_return
from app.data.features.sequence_builder import build_sequences
from app.ml.training.comprehensive_evaluation import compute_metrics
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
log = logging.getLogger("experiments")

FEATURES_PATH = Path("data/features/features_daily.parquet")
EXPERIMENT_MODELS_DIR = Path("models/experiments")
REPORTS_DIR = Path("data/reports")
TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")
LABEL_MAPPING_INV = {0: "bullish", 1: "bearish", 2: "sideways"}


def get_full_eval_dict(y_true: np.ndarray, y_pred: np.ndarray, name: str) -> dict:
    """Standardized metric extraction."""
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


def print_experiment_result(res: dict):
    print("\n" + "-" * 75)
    print(f"  Configuration: {res['name']}")
    print("-" * 75)
    print(f"  Accuracy:          {res['accuracy']:.4f}")
    print(f"  Macro F1:          {res['macro_f1']:.4f}")
    print(f"  Weighted F1:       {res['weighted_f1']:.4f}")
    print(f"  Balanced Accuracy: {res['balanced_accuracy']:.4f}")
    print("  Per-Class Metrics:")
    for cls in ["bullish", "bearish", "sideways"]:
        p = res["per_class"][cls]
        print(f"    {cls:<10}: Precision={p['precision']:.4f} | Recall={p['recall']:.4f} | F1={p['f1']:.4f} | Support={p['support']}")
    print(f"  Confusion Matrix (rows=true, cols=pred: [bullish, bearish, sideways]):")
    for row in res["confusion_matrix"]:
        print(f"    {row}")


def save_val_reports(all_res: dict):
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    exp_report_path = REPORTS_DIR / "controlled_experiments_val_report.json"
    exp_report_path.write_text(json.dumps(all_res, indent=2), encoding="utf-8")
    log.info("Saved/Updated validation report -> %s", exp_report_path)


def run_exp1_gru_weights() -> Dict[str, dict]:
    """Exp 1: GRU baseline vs GRU with balanced class weights on Validation set."""
    log.info("\n=== EXPERIMENT 1: GRU Class Weights vs Baseline ===")
    seq_data = np.load("data/sequences/sequences.npz")
    X_all = seq_data["X"].astype(np.float32)
    y_all = seq_data["y"]
    meta_all = pd.read_parquet("data/sequences/sequences_meta.parquet")

    splits = time_split(X_all, y_all, meta_all)
    X_train, y_train = splits["train"]["X"], splits["train"]["y"]
    X_val, y_val = splits["val"]["X"], splits["val"]["y"]

    del X_all, y_all, meta_all, splits
    gc.collect()

    scaler = fit_scaler(X_train)
    X_train_s = apply_scaler(X_train, scaler)
    X_val_s = apply_scaler(X_val, scaler)
    del X_train, X_val
    gc.collect()

    input_shape = (X_train_s.shape[1], X_train_s.shape[2])

    # Unweighted
    set_seed(42)
    model_unweighted = build_model(input_shape, n_classes=3)
    train_model(
        model_unweighted, X_train_s, y_train, X_val_s, y_val,
        batch_size=32, max_epochs=40, patience=5,
        model_save_path=EXPERIMENT_MODELS_DIR / "gru_unweighted.keras",
    )
    val_probs_unw = model_unweighted.predict(X_val_s, verbose=0)
    val_preds_unw = np.argmax(val_probs_unw, axis=1)
    res_unw = get_full_eval_dict(y_val, val_preds_unw, "GRU Unweighted (Baseline)")

    # Balanced
    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight_dict = {int(c): float(w) for c, w in zip(classes, weights)}

    set_seed(42)
    model_weighted = build_model(input_shape, n_classes=3)
    train_model(
        model_weighted, X_train_s, y_train, X_val_s, y_val,
        batch_size=32, max_epochs=40, patience=5,
        class_weight=class_weight_dict,
        model_save_path=EXPERIMENT_MODELS_DIR / "gru_weighted.keras",
    )
    val_probs_wt = model_weighted.predict(X_val_s, verbose=0)
    val_preds_wt = np.argmax(val_probs_wt, axis=1)
    res_wt = get_full_eval_dict(y_val, val_preds_wt, "GRU Balanced Class Weights")

    del X_train_s, X_val_s, y_train, y_val, model_unweighted, model_weighted
    gc.collect()
    return {"unweighted": res_unw, "weighted": res_wt}


def run_exp2_xgb_weights() -> Dict[str, dict]:
    """Exp 2: XGBoost unweighted vs weighted on Validation set."""
    log.info("\n=== EXPERIMENT 2: XGBoost Unweighted vs Weighted ===")
    df_xgb = pd.read_parquet("data/processed/features_xgb.parquet")
    feature_names = [c for c in ALL_XGB_FEATURES if c in df_xgb.columns]
    dates = pd.to_datetime(df_xgb["date"])

    train_mask = dates < TRAIN_CUTOFF
    val_mask = (dates >= TRAIN_CUTOFF) & (dates < VAL_CUTOFF)

    X_train = df_xgb.loc[train_mask, feature_names].values.astype(np.float32)
    y_train = df_xgb.loc[train_mask, "label"].map(LABEL_MAPPING).values
    X_val = df_xgb.loc[val_mask, feature_names].values.astype(np.float32)
    y_val = df_xgb.loc[val_mask, "label"].map(LABEL_MAPPING).values
    del df_xgb
    gc.collect()

    # Impute using train median
    for f_idx in range(len(feature_names)):
        col = X_train[:, f_idx]
        valid = col[~np.isnan(col)]
        med = float(np.median(valid)) if len(valid) > 0 else 0.0
        X_train[np.isnan(X_train[:, f_idx]), f_idx] = med
        X_val[np.isnan(X_val[:, f_idx]), f_idx] = med

    # Unweighted XGB
    model_unw = xgb.XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        objective="multi:softprob", num_class=3,
        random_state=42, early_stopping_rounds=20,
    )
    model_unw.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
    preds_unw = model_unw.predict(X_val)
    res_unw = get_full_eval_dict(y_val, preds_unw, "XGBoost Unweighted")

    # Weighted XGB
    from app.ml.training_xgb.model import compute_sample_weights
    sample_weights = compute_sample_weights(y_train)
    model_wt = xgb.XGBClassifier(
        n_estimators=300, max_depth=6, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        objective="multi:softprob", num_class=3,
        random_state=42, early_stopping_rounds=20,
    )
    model_wt.fit(X_train, y_train, sample_weight=sample_weights, eval_set=[(X_val, y_val)], verbose=False)
    preds_wt = model_wt.predict(X_val)
    res_wt = get_full_eval_dict(y_val, preds_wt, "XGBoost Weighted")

    del X_train, y_train, X_val, y_val, model_unw, model_wt
    gc.collect()
    return {"unweighted": res_unw, "weighted": res_wt}


def run_exp3_thresholds() -> Dict[str, dict]:
    """Exp 3: Threshold sweep (0.005, 0.010, 0.015, 0.020) on Validation set."""
    log.info("\n=== EXPERIMENT 3: Label Threshold Sweep ===")
    thresholds = [0.005, 0.010, 0.015, 0.020]
    results = {}

    df_f = pd.read_parquet(FEATURES_PATH)
    df_f = df_f.sort_values(["symbol", "date"]).reset_index(drop=True)
    df_f["forward_return"] = df_f.groupby("symbol")["close"].transform(
        lambda s: s.shift(-1) / s - 1
    )
    df_f = df_f.dropna(subset=["forward_return"]).reset_index(drop=True)

    dates = pd.to_datetime(df_f["date"])
    train_mask = dates < TRAIN_CUTOFF
    val_mask = (dates >= TRAIN_CUTOFF) & (dates < VAL_CUTOFF)

    feature_names = [c for c in ALL_XGB_FEATURES if c in df_f.columns]
    X_train_raw = df_f.loc[train_mask, feature_names].values.astype(np.float32)
    X_val_raw = df_f.loc[val_mask, feature_names].values.astype(np.float32)
    fwd_ret = df_f["forward_return"].values
    del df_f
    gc.collect()

    for thresh in thresholds:
        log.info("Evaluating Threshold: %.3f ...", thresh)
        labels = np.array([
            0 if r > thresh else (1 if r < -thresh else 2)
            for r in fwd_ret
        ], dtype=np.int32)

        y_train = labels[train_mask]
        y_val = labels[val_mask]

        X_train = X_train_raw.copy()
        X_val = X_val_raw.copy()

        for f_idx in range(len(feature_names)):
            col = X_train[:, f_idx]
            valid = col[~np.isnan(col)]
            med = float(np.median(valid)) if len(valid) > 0 else 0.0
            X_train[np.isnan(X_train[:, f_idx]), f_idx] = med
            X_val[np.isnan(X_val[:, f_idx]), f_idx] = med

        model = xgb.XGBClassifier(
            n_estimators=250, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            objective="multi:softprob", num_class=3,
            random_state=42, early_stopping_rounds=20,
        )
        model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)
        preds = model.predict(X_val)

        res = get_full_eval_dict(y_val, preds, f"Threshold {thresh:.3f} (XGB Baseline)")
        train_dist = pd.Series(y_train).value_counts(normalize=True).to_dict()
        val_dist = pd.Series(y_val).value_counts(normalize=True).to_dict()
        res["threshold"] = thresh
        res["train_dist"] = {LABEL_MAPPING_INV[k]: round(v * 100, 2) for k, v in train_dist.items()}
        res["val_dist"] = {LABEL_MAPPING_INV[k]: round(v * 100, 2) for k, v in val_dist.items()}

        results[f"thresh_{int(thresh*1000):03d}"] = res
        del X_train, X_val, y_train, y_val, model
        gc.collect()

    del X_train_raw, X_val_raw, fwd_ret
    gc.collect()
    return results


def run_exp4_features(baseline_res: dict | None = None) -> Dict[str, dict]:
    """Exp 4: Baseline vs Normalized vs Market-Relative on Validation set."""
    log.info("\n=== EXPERIMENT 4: Feature Sets Comparison ===")
    df_features = pd.read_parquet(FEATURES_PATH)

    normalized_features = [
        "close_to_sma20_ratio", "close_to_sma50_ratio", "ema_cross_ratio",
        "bollinger_pos", "daily_range_pct", "volume_change_1d"
    ]
    market_features = [
        "market_return_5d", "market_return_20d", "stock_return_20d", "stock_relative_return_20d"
    ]

    feature_sets = {}
    if baseline_res is not None:
        results = {"baseline": baseline_res}
    else:
        results = {}
        feature_sets["baseline"] = GRU_FEATURE_LIST.copy()

    feature_sets["baseline_normalized"] = GRU_FEATURE_LIST + [f for f in normalized_features if f in df_features.columns]
    feature_sets["baseline_norm_market"] = GRU_FEATURE_LIST + [f for f in normalized_features + market_features if f in df_features.columns]

    for set_name, cols in feature_sets.items():
        log.info("Evaluating Feature Set '%s' with %d features ...", set_name, len(cols))
        set_seed(42)

        X, y, meta = build_sequences(df_features, cols, LABEL_MAPPING, window_size=30)
        splits = time_split(X, y, meta)

        X_train, y_train = splits["train"]["X"], splits["train"]["y"]
        X_val, y_val = splits["val"]["X"], splits["val"]["y"]
        del X, y, meta, splits
        gc.collect()

        scaler = fit_scaler(X_train)
        X_train_s = apply_scaler(X_train, scaler)
        X_val_s = apply_scaler(X_val, scaler)
        del X_train, X_val
        gc.collect()

        input_shape = (X_train_s.shape[1], X_train_s.shape[2])
        model = build_model(input_shape, n_classes=3)
        train_model(
            model, X_train_s, y_train, X_val_s, y_val,
            batch_size=32, max_epochs=35, patience=5,
            model_save_path=EXPERIMENT_MODELS_DIR / f"gru_{set_name}.keras",
        )
        val_probs = model.predict(X_val_s, verbose=0)
        val_preds = np.argmax(val_probs, axis=1)

        res = get_full_eval_dict(y_val, val_preds, f"GRU Feature Set: {set_name}")
        res["n_features"] = len(cols)
        results[set_name] = res

        del X_train_s, X_val_s, y_train, y_val, model
        gc.collect()

    del df_features
    gc.collect()
    return results


def run_selected_test_eval():
    """Evaluate ONLY top configurations identified from validation on untouched test set."""
    log.info("\n=== EVALUATING TOP CONFIGURATIONS ON UNTOUCHED TEST SET (ONCE) ===")
    test_eval_results = {}

    seq_data = np.load("data/sequences/sequences.npz")
    X_all = seq_data["X"].astype(np.float32)
    y_all = seq_data["y"]
    meta_all = pd.read_parquet("data/sequences/sequences_meta.parquet")

    splits = time_split(X_all, y_all, meta_all)
    X_train, y_train = splits["train"]["X"], splits["train"]["y"]
    X_test, y_test = splits["test"]["X"], splits["test"]["y"]
    meta_test = splits["test"]["meta"]

    scaler = fit_scaler(X_train)
    X_test_s = apply_scaler(X_test, scaler)
    del X_all, y_all, meta_all, splits, X_train
    gc.collect()

    # 1. GRU Balanced
    gru_weighted_model = tf.keras.models.load_model(EXPERIMENT_MODELS_DIR / "gru_weighted.keras")
    gru_wt_test_probs = gru_weighted_model.predict(X_test_s, verbose=0)
    gru_wt_test_preds = np.argmax(gru_wt_test_probs, axis=1)
    test_eval_results["gru_balanced_weighted"] = get_full_eval_dict(y_test, gru_wt_test_preds, "GRU Balanced Weights (Test Set)")

    # 2. XGBoost Weighted on Test Set
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
    meta_test_copy = meta_test.copy()
    meta_test_copy["date_dt"] = pd.to_datetime(meta_test_copy["date"])
    meta_test_copy["orig_idx"] = np.arange(len(meta_test_copy))
    merged = pd.merge(meta_test_copy, df_xgb_idx, on=["symbol", "date_dt"], how="left")
    X_xgb_test = merged[feature_names_xgb].values.astype(np.float32)
    for f_idx in range(len(feature_names_xgb)):
        X_xgb_test[np.isnan(X_xgb_test[:, f_idx]), f_idx] = fill_meds[f_idx]

    xgb_wt_model = xgb.XGBClassifier()
    xgb_wt_model.load_model("models/xgb_v1/xgb_v1_weighted.xgb")
    xgb_wt_test_probs = xgb_wt_model.predict_proba(X_xgb_test)

    # 3. Weighted Ensemble (GRU Balanced + XGB Weighted)
    ens_wt_probs = 0.5 * gru_wt_test_probs + 0.5 * xgb_wt_test_probs
    ens_wt_preds = np.argmax(ens_wt_probs, axis=1)
    test_eval_results["ensemble_weighted"] = get_full_eval_dict(y_test, ens_wt_preds, "Ensemble Weighted (GRU Bal + XGB Wt) (Test Set)")

    # 4. GRU with Normalized + Market-Relative Features on Test Set
    df_features = pd.read_parquet(FEATURES_PATH)
    best_feat_cols = GRU_FEATURE_LIST + [
        "close_to_sma20_ratio", "close_to_sma50_ratio", "ema_cross_ratio",
        "bollinger_pos", "daily_range_pct", "volume_change_1d",
        "market_return_5d", "market_return_20d", "stock_return_20d", "stock_relative_return_20d"
    ]
    best_feat_cols = [c for c in best_feat_cols if c in df_features.columns]
    X_bf, y_bf, meta_bf = build_sequences(df_features, best_feat_cols, LABEL_MAPPING, window_size=30)
    splits_bf = time_split(X_bf, y_bf, meta_bf)
    scaler_bf = fit_scaler(splits_bf["train"]["X"])
    X_test_bf_s = apply_scaler(splits_bf["test"]["X"], scaler_bf)

    gru_bf_model = tf.keras.models.load_model(EXPERIMENT_MODELS_DIR / "gru_baseline_norm_market.keras")
    gru_bf_test_probs = gru_bf_model.predict(X_test_bf_s, verbose=0)
    gru_bf_test_preds = np.argmax(gru_bf_test_probs, axis=1)
    test_eval_results["gru_norm_market_features"] = get_full_eval_dict(splits_bf["test"]["y"], gru_bf_test_preds, "GRU Norm+Market Features (Test Set)")

    test_report_path = REPORTS_DIR / "controlled_experiments_test_report.json"
    test_report_path.write_text(json.dumps(test_eval_results, indent=2), encoding="utf-8")
    log.info("Saved test evaluation results -> %s", test_report_path)

    print("\n" + "=" * 80)
    print("  FINAL TEST EVALUATION OF SELECTED CONFIGURATION(S)")
    print("=" * 80)
    for r in test_eval_results.values():
        print_experiment_result(r)


def main():
    EXPERIMENT_MODELS_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    all_res = {}

    # Experiment 1
    exp1 = run_exp1_gru_weights()
    all_res["exp1_gru_weights"] = exp1
    save_val_reports(all_res)
    for r in exp1.values():
        print_experiment_result(r)

    # Experiment 2
    exp2 = run_exp2_xgb_weights()
    all_res["exp2_xgb_weights"] = exp2
    save_val_reports(all_res)
    for r in exp2.values():
        print_experiment_result(r)

    # Experiment 3
    exp3 = run_exp3_thresholds()
    all_res["exp3_thresholds"] = exp3
    save_val_reports(all_res)
    for r in exp3.values():
        print_experiment_result(r)

    # Experiment 4
    exp4 = run_exp4_features(baseline_res=exp1["unweighted"])
    all_res["exp4_features"] = exp4
    save_val_reports(all_res)
    for r in exp4.values():
        print_experiment_result(r)

    # Single test evaluation for selected top configurations
    run_selected_test_eval()


if __name__ == "__main__":
    main()
