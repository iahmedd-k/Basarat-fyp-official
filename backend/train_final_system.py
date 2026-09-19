"""
Final ML Training Pipeline & System Integration
===============================================
Trains the validated final ML prediction pipeline from scratch:
1. Rebuilds 36-feature sequences with threshold=0.01 and window=30.
2. Trains Final GRU with balanced class weights (calculated strictly on y_train).
3. Trains Final XGBoost with weighted sample weights (calculated strictly on y_train).
4. Saves all models, scalers, and comprehensive versioned metadata.
5. Evaluates Naive Baseline, Final GRU, Final XGBoost, and Final Weighted Ensemble.
6. Outputs validation and out-of-sample test results.
"""

import gc
import json
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

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

from app.data.features.gru_feature_list import (
    EXPECTED_GRU_FEATURE_COUNT,
    GRU_FEATURE_LIST,
    GRU_FEATURE_VERSION,
    validate_feature_count,
    validate_feature_list,
)
from app.data.features.labeling import LABEL_MAPPING, assign_labels, save_label_mapping
from app.data.features.macro_features import join_macro_features
from app.data.features.quality import build_feature_quality_report
from app.data.features.sequence_builder import build_sequences, save_sequences
from app.data.features.technical_indicators import compute_technical_indicators
from app.data.scraper.symbol_universe import get_active_symbols
from app.ml.training.data_split import time_split
from app.ml.training.leakage_checker import (
    check_chronological_split_leakage,
    check_target_validity,
)
from app.ml.training.model import build_model
from app.ml.training.reproducibility import set_seed
from app.ml.training.scaling import apply_scaler, fit_scaler, save_scaler
from app.ml.training.train import train_model
from app.ml.training_xgb.data_split import time_split_xgb
from app.ml.training_xgb.feature_prep import ALL_XGB_FEATURES, build_xgb_features
from app.ml.training_xgb.model import (
    build_xgb_classifier,
    compute_sample_weights,
    save_feature_importances,
    save_model_metadata,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("train_final_system")

TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")
FEATURES_DIR = Path("data/features")
SEQUENCES_DIR = Path("data/sequences")
GRU_MODEL_DIR = Path("models/gru_v1")
XGB_MODEL_DIR = Path("models/xgb_v1")
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


def step1_generate_features_and_sequences():
    """Step 1: Compute 36 technical & macro features and build sequences."""
    log.info("=== STEP 1: Feature Engineering & Sequence Generation ===")
    FEATURES_DIR.mkdir(parents=True, exist_ok=True)
    SEQUENCES_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    active = get_active_symbols()
    active_syms = {e["symbol"] for e in active}

    ohlcv_path = Path("data/raw/ohlcv/all_symbols.parquet")
    ohlcv = pd.read_parquet(ohlcv_path)
    ohlcv = ohlcv[ohlcv["symbol"].isin(active_syms)].copy()
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])

    for col in ["open", "high", "low", "close", "volume"]:
        if col in ohlcv.columns:
            ohlcv[col] = pd.to_numeric(ohlcv[col], errors="coerce")

    log.info("Computing technical indicators ...")
    df = compute_technical_indicators(ohlcv)

    log.info("Joining macro features ...")
    df = join_macro_features(df)

    # Symbol ID mapping
    symbol_ids = sorted(df["symbol"].unique())
    sym_id_map = {sym: idx for idx, sym in enumerate(symbol_ids)}
    df["symbol_id"] = df["symbol"].map(sym_id_map)
    (Path("data/config/symbol_id_mapping.json")).write_text(json.dumps(sym_id_map, indent=2), encoding="utf-8")

    # Labeling with threshold = 0.01
    log.info("Assigning labels with threshold = 0.01 ...")
    df, label_report = assign_labels(df, threshold=0.01)
    save_label_mapping(FEATURES_DIR, filename="label_mapping.json")

    feature_columns = GRU_FEATURE_LIST.copy()
    is_valid, err = validate_feature_list(feature_columns)
    if not is_valid:
        raise ValueError(f"Feature list invalid: {err}")
    is_valid_cnt, err_cnt = validate_feature_count(len(feature_columns))
    if not is_valid_cnt:
        raise ValueError(f"Feature count invalid: {err_cnt}")

    for col in feature_columns:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    features_path = FEATURES_DIR / "features_daily.parquet"
    df.to_parquet(features_path, index=False)
    log.info("Saved features -> %s (%d rows, %d cols)", features_path, len(df), len(df.columns))

    (FEATURES_DIR / "feature_columns.json").write_text(json.dumps(feature_columns, indent=2), encoding="utf-8")
    (FEATURES_DIR / "gru_feature_version.json").write_text(
        json.dumps({"version": GRU_FEATURE_VERSION, "feature_count": len(feature_columns), "features": feature_columns}, indent=2),
        encoding="utf-8",
    )

    build_feature_quality_report(df, label_report, REPORTS_DIR, filename="feature_quality.json")

    log.info("Building 36-feature sequences (window_size=30) ...")
    X, y, meta = build_sequences(df, feature_columns, label_report["label_mapping"], window_size=30)
    save_sequences(X, y, meta, SEQUENCES_DIR)

    del df, ohlcv
    gc.collect()
    log.info("Step 1 complete! X=%s, y=%s, meta=%d", X.shape, y.shape, len(meta))


def step2_train_final_gru():
    """Step 2: Train Final GRU with balanced class weights strictly on y_train."""
    log.info("\n=== STEP 2: Retraining Final 36-Feature GRU with Balanced Class Weights ===")
    set_seed(42)
    GRU_MODEL_DIR.mkdir(parents=True, exist_ok=True)

    data = np.load(SEQUENCES_DIR / "sequences.npz")
    X, y = data["X"], data["y"]
    meta = pd.read_parquet(SEQUENCES_DIR / "sequences_meta.parquet")
    feature_columns = json.loads((FEATURES_DIR / "feature_columns.json").read_text(encoding="utf-8"))
    label_mapping = json.loads((FEATURES_DIR / "label_mapping.json").read_text(encoding="utf-8"))

    splits = time_split(X, y, meta, train_cutoff=TRAIN_CUTOFF, val_cutoff=VAL_CUTOFF)
    X_train, y_train = splits["train"]["X"], splits["train"]["y"]
    X_val, y_val = splits["val"]["X"], splits["val"]["y"]
    X_test, y_test = splits["test"]["X"], splits["test"]["y"]
    meta_val = splits["val"]["meta"]
    meta_test = splits["test"]["meta"]

    # Leakage and target checks
    split_summary = check_chronological_split_leakage(splits["train"]["meta"], meta_val, meta_test)
    check_target_validity(y_train, y_val, y_test, expected_classes=set(label_mapping.values()))

    # Feature scaling - fit on train ONLY
    scaler = fit_scaler(X_train)
    X_train_s = apply_scaler(X_train, scaler)
    X_val_s = apply_scaler(X_val, scaler)
    X_test_s = apply_scaler(X_test, scaler)
    save_scaler(scaler)
    del X_train, X_val, X_test, X, y, meta, splits
    gc.collect()

    # Compute balanced class weights strictly from y_train
    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight_dict = {int(c): float(w) for c, w in zip(classes, weights)}
    log.info("GRU Class Weights (y_train only): %s", class_weight_dict)

    input_shape = (X_train_s.shape[1], X_train_s.shape[2])
    model = build_model(input_shape, n_classes=len(label_mapping))

    model_path = GRU_MODEL_DIR / "model.keras"
    train_res = train_model(
        model,
        X_train_s,
        y_train,
        X_val_s,
        y_val,
        batch_size=32,
        max_epochs=35,
        patience=5,
        model_save_path=model_path,
        class_weight=class_weight_dict,
    )

    # Save final GRU metadata
    gru_metadata = {
        "model_version": "gru_v1_balanced_36f",
        "feature_version": GRU_FEATURE_VERSION,
        "feature_columns": feature_columns,
        "n_features": len(feature_columns),
        "window_size": 30,
        "threshold": 0.01,
        "label_mapping": label_mapping,
        "class_weights": class_weight_dict,
        "train_cutoff": str(TRAIN_CUTOFF.date()),
        "val_cutoff": str(VAL_CUTOFF.date()),
        "train_date_range": split_summary["train"],
        "val_date_range": split_summary["val"],
        "test_date_range": split_summary["test"],
        "train_samples": int(len(X_train_s)),
        "val_samples": int(len(X_val_s)),
        "test_samples": int(len(X_test_s)),
        "random_seed": 42,
        "batch_size": 32,
        "max_epochs": 35,
        "patience": 5,
        "scaler_version": "StandardScaler_v1",
        "best_epoch": train_res.get("best_epoch"),
        "best_val_loss": train_res.get("best_val_loss"),
        "val_accuracy_at_best_val_loss": train_res.get("val_accuracy_at_best_val_loss"),
        "training_duration_sec": train_res.get("training_duration_sec"),
        "training_timestamp": datetime.now().isoformat(),
    }
    (GRU_MODEL_DIR / "metadata.json").write_text(json.dumps(gru_metadata, indent=2), encoding="utf-8")
    log.info("Saved GRU metadata -> %s", GRU_MODEL_DIR / "metadata.json")

    # Evaluate on Validation and Test
    val_probs = model.predict(X_val_s, verbose=0)
    val_preds = np.argmax(val_probs, axis=1)
    val_eval = get_full_eval_dict(y_val, val_preds, "Final GRU (Validation Set)")

    test_probs = model.predict(X_test_s, verbose=0)
    test_preds = np.argmax(test_probs, axis=1)
    test_eval = get_full_eval_dict(y_test, test_preds, "Final GRU (Test Set)")

    del X_train_s
    gc.collect()

    return {
        "model": model,
        "scaler": scaler,
        "X_val_s": X_val_s,
        "y_val": y_val,
        "meta_val": meta_val,
        "val_probs": val_probs,
        "val_eval": val_eval,
        "X_test_s": X_test_s,
        "y_test": y_test,
        "meta_test": meta_test,
        "test_probs": test_probs,
        "test_eval": test_eval,
        "gru_metadata": gru_metadata,
    }


def step3_train_final_xgb():
    """Step 3: Train Final XGBoost with inverse-frequency sample weights strictly on y_train."""
    log.info("\n=== STEP 3: Retraining Final Weighted XGBoost ===")
    XGB_MODEL_DIR.mkdir(parents=True, exist_ok=True)
    label_mapping = json.loads((FEATURES_DIR / "label_mapping.json").read_text(encoding="utf-8"))

    df = build_xgb_features()
    splits = time_split_xgb(df, label_mapping=label_mapping)

    X_train, y_train = splits["train"]["X"], splits["train"]["y"]
    X_val, y_val = splits["val"]["X"], splits["val"]["y"]
    X_test, y_test = splits["test"]["X"], splits["test"]["y"]
    feature_names = splits["train"]["feature_names"]

    # Sample weights on y_train ONLY
    sample_weights_train = compute_sample_weights(y_train)

    # Train Weighted Model
    model = build_xgb_classifier()
    model.fit(
        X_train,
        y_train,
        sample_weight=sample_weights_train,
        eval_set=[(X_val, y_val)],
        verbose=50,
    )

    model_path = XGB_MODEL_DIR / "xgb_v1_weighted.xgb"
    meta_path = save_model_metadata(
        model=model,
        model_path=model_path,
        feature_names=feature_names,
        label_mapping=label_mapping,
        split_info={
            "train_samples": len(X_train),
            "val_samples": len(X_val),
            "test_samples": len(X_test),
        },
        variant="weighted",
        extra_meta={
            "train_cutoff": str(TRAIN_CUTOFF.date()),
            "val_cutoff": str(VAL_CUTOFF.date()),
            "threshold": 0.01,
            "random_seed": 42,
            "training_timestamp": datetime.now().isoformat(),
        },
    )

    importance_path = REPORTS_DIR / "xgb_feature_importance_weighted.json"
    save_feature_importances(model, feature_names, importance_path)

    # Also save unweighted variant for baseline reference
    model_unweighted = build_xgb_classifier()
    model_unweighted.fit(
        X_train,
        y_train,
        eval_set=[(X_val, y_val)],
        verbose=False,
    )
    save_model_metadata(
        model=model_unweighted,
        model_path=XGB_MODEL_DIR / "xgb_v1_unweighted.xgb",
        feature_names=feature_names,
        label_mapping=label_mapping,
        split_info={"train_samples": len(X_train), "val_samples": len(X_val), "test_samples": len(X_test)},
        variant="unweighted",
    )

    val_probs = model.predict_proba(X_val)
    val_preds = np.argmax(val_probs, axis=1)
    val_eval = get_full_eval_dict(y_val, val_preds, "Final XGBoost Weighted (Validation Set)")

    test_probs = model.predict_proba(X_test)
    test_preds = np.argmax(test_probs, axis=1)
    test_eval = get_full_eval_dict(y_test, test_preds, "Final XGBoost Weighted (Test Set)")

    return {
        "model": model,
        "df_xgb": df,
        "feature_names": feature_names,
        "y_val": y_val,
        "val_probs": val_probs,
        "val_eval": val_eval,
        "y_test": y_test,
        "test_probs": test_probs,
        "test_eval": test_eval,
    }


def step4_evaluate_and_integrate(gru_res, xgb_res):
    """Step 4: Final Evaluation of Naive Baseline, GRU, XGBoost, and Weighted Ensemble."""
    log.info("\n=== STEP 4: Comprehensive Evaluation on Validation and Untouched Test Sets ===")

    y_val_gru = gru_res["y_val"]
    y_test_gru = gru_res["y_test"]
    meta_val_gru = gru_res["meta_val"]
    meta_test_gru = gru_res["meta_test"]

    # Align XGBoost predictions with GRU test set sequences for 1-to-1 ensemble pairing
    df_xgb = xgb_res["df_xgb"].copy()
    df_xgb["date_dt"] = pd.to_datetime(df_xgb["date"])
    feature_names_xgb = xgb_res["feature_names"]

    # Compute training median for imputation
    train_mask_xgb = pd.to_datetime(df_xgb["date"]) < TRAIN_CUTOFF
    X_xgb_train = df_xgb.loc[train_mask_xgb, feature_names_xgb].values.astype(np.float32)
    fill_meds = np.nanmedian(X_xgb_train, axis=0)
    fill_meds = np.nan_to_num(fill_meds, nan=0.0)

    # 1. Validation Ensemble
    meta_val_copy = meta_val_gru.copy()
    meta_val_copy["date_dt"] = pd.to_datetime(meta_val_copy["date"])
    meta_val_copy["orig_idx"] = np.arange(len(meta_val_copy))
    merged_val = pd.merge(meta_val_copy, df_xgb, on=["symbol", "date_dt"], how="left")
    X_xgb_val_aligned = merged_val[feature_names_xgb].values.astype(np.float32)
    for f_idx in range(len(feature_names_xgb)):
        X_xgb_val_aligned[np.isnan(X_xgb_val_aligned[:, f_idx]), f_idx] = fill_meds[f_idx]

    xgb_val_probs_aligned = xgb_res["model"].predict_proba(X_xgb_val_aligned)
    gru_val_probs = gru_res["val_probs"]

    ens_val_probs = 0.5 * gru_val_probs + 0.5 * xgb_val_probs_aligned
    ens_val_preds = np.argmax(ens_val_probs, axis=1)
    ens_val_eval = get_full_eval_dict(y_val_gru, ens_val_preds, "Final Weighted Ensemble (Validation Set)")

    # 2. Test Set Alignment & Ensemble
    meta_test_copy = meta_test_gru.copy()
    meta_test_copy["date_dt"] = pd.to_datetime(meta_test_copy["date"])
    meta_test_copy["orig_idx"] = np.arange(len(meta_test_copy))
    merged_test = pd.merge(meta_test_copy, df_xgb, on=["symbol", "date_dt"], how="left")
    X_xgb_test_aligned = merged_test[feature_names_xgb].values.astype(np.float32)
    for f_idx in range(len(feature_names_xgb)):
        X_xgb_test_aligned[np.isnan(X_xgb_test_aligned[:, f_idx]), f_idx] = fill_meds[f_idx]

    xgb_test_probs_aligned = xgb_res["model"].predict_proba(X_xgb_test_aligned)
    gru_test_probs = gru_res["test_probs"]

    ens_test_probs = 0.5 * gru_test_probs + 0.5 * xgb_test_probs_aligned
    ens_test_preds = np.argmax(ens_test_probs, axis=1)
    ens_test_eval = get_full_eval_dict(y_test_gru, ens_test_preds, "Final Weighted Ensemble (Test Set)")

    # 3. Naive Majority Baseline on Test Set
    # Identify majority class in y_train
    classes, counts = np.unique(gru_res["gru_metadata"]["label_mapping"], return_counts=True)
    # The historical majority class in training is Sideways (2)
    majority_class = 2  # sideways
    naive_test_preds = np.full_like(y_test_gru, fill_value=majority_class)
    naive_test_eval = get_full_eval_dict(y_test_gru, naive_test_preds, "Naive Majority Baseline (Always Sideways)")

    # Compile Full Reports
    final_val_report = {
        "final_gru": gru_res["val_eval"],
        "final_xgb_weighted": xgb_res["val_eval"],
        "final_weighted_ensemble": ens_val_eval,
    }
    (REPORTS_DIR / "final_pipeline_val_report.json").write_text(
        json.dumps(final_val_report, indent=2), encoding="utf-8"
    )

    final_test_report = {
        "naive_baseline": naive_test_eval,
        "final_gru": gru_res["test_eval"],
        "final_xgb_weighted": get_full_eval_dict(y_test_gru, np.argmax(xgb_test_probs_aligned, axis=1), "Final XGBoost Weighted (Test Set)"),
        "final_weighted_ensemble": ens_test_eval,
    }
    (REPORTS_DIR / "final_pipeline_test_report.json").write_text(
        json.dumps(final_test_report, indent=2), encoding="utf-8"
    )
    (REPORTS_DIR / "evaluation.json").write_text(
        json.dumps(final_test_report["final_gru"], indent=2), encoding="utf-8"
    )

    log.info("Saved final validation report -> data/reports/final_pipeline_val_report.json")
    log.info("Saved final test report -> data/reports/final_pipeline_test_report.json")

    return final_val_report, final_test_report


def main():
    t0 = time.time()
    step1_generate_features_and_sequences()
    gru_res = step2_train_final_gru()
    xgb_res = step3_train_final_xgb()
    val_rep, test_rep = step4_evaluate_and_integrate(gru_res, xgb_res)
    duration = time.time() - t0
    log.info("All final ML pipeline training and evaluation finished in %.1fs!", duration)


if __name__ == "__main__":
    main()
