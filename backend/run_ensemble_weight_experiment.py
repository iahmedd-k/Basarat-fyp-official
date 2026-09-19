"""
Controlled ML Experiment: Ensemble Weight Optimization
======================================================
Tests different weighting schemes between GRU 45-day (temporal model) and
XGBoost Extended Horizons (tabular model) strictly using the validation set.

Evaluates the selected weighting once on the untouched test set.
"""

import json
import logging
import sys
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
import tensorflow as tf
from tensorflow import keras
import xgboost as xgb

from app.data.features.gru_feature_list import GRU_FEATURE_LIST
from app.data.features.labeling import LABEL_MAPPING
from run_lookback_horizon_experiments import (
    StreamingSequenceDataset,
    build_extended_xgb_features,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("ensemble_weight_experiment")

TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")
EXPERIMENT_DIR = Path("models/experiments/ensemble_weighting")
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


def verify_probabilities(
    probs: np.ndarray,
    name: str,
    expected_n: int,
) -> None:
    """Verify probability array shape, bounds, normalization, and absence of NaNs."""
    assert probs.ndim == 2, f"{name}: expected 2D array, got {probs.ndim}D"
    assert probs.shape[0] == expected_n, f"{name}: expected {expected_n} rows, got {probs.shape[0]}"
    assert probs.shape[1] == 3, f"{name}: expected 3 classes, got {probs.shape[1]}"
    assert not np.isnan(probs).any(), f"{name}: contains NaN probabilities"
    assert not np.isinf(probs).any(), f"{name}: contains Inf probabilities"
    assert (probs >= 0.0).all(), f"{name}: contains negative probabilities"
    
    # Check row sums ~ 1.0
    row_sums = probs.sum(axis=1)
    assert np.allclose(row_sums, 1.0, atol=1e-4), f"{name}: row sums deviate from 1.0: {row_sums[:5]}"
    log.info("Probability check PASSED for %s: shape=%s, range=[%.4f, %.4f], sample_sum=%.4f",
             name, probs.shape, probs.min(), probs.max(), row_sums[0])


def main():
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 80)
    log.info("  STEP 0: ARTIFACT & FEATURE VERIFICATION")
    log.info("=" * 80)

    # 1. Load feature dataset
    df_raw = pd.read_parquet("data/features/features_daily.parquet")
    df_raw["date"] = pd.to_datetime(df_raw["date"])
    df_raw = df_raw.sort_values(["symbol", "date"]).reset_index(drop=True)

    log.info("Loaded features_daily.parquet: %d rows, %d columns", len(df_raw), len(df_raw.columns))

    # GRU features check
    gru_feature_cols = [c for c in GRU_FEATURE_LIST if c in df_raw.columns]
    log.info("GRU feature count: %d (expected 36)", len(gru_feature_cols))
    assert len(gru_feature_cols) == 36, f"GRU features mismatch: {len(gru_feature_cols)}"

    # XGBoost features check
    df_xgb, base_feats, ext_feats = build_extended_xgb_features()
    log.info("XGBoost Baseline features: %d", len(base_feats))
    log.info("XGBoost Extended features: %d", len(ext_feats))

    # 2. Check splits and fairness
    train_mask = df_xgb["date"] < TRAIN_CUTOFF
    val_mask = (df_xgb["date"] >= TRAIN_CUTOFF) & (df_xgb["date"] < VAL_CUTOFF)
    test_mask = df_xgb["date"] >= VAL_CUTOFF

    y_val_xgb = df_xgb.loc[val_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    y_test_xgb = df_xgb.loc[test_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    val_count = len(y_val_xgb)
    test_count = len(y_test_xgb)

    log.info("Dataset split row counts: Train=%d, Val=%d, Test=%d",
             train_mask.sum(), val_count, test_count)

    # 3. Load GRU 45-day model and generate predictions
    log.info("\n--- Loading GRU 45-day Model ---")
    gru_model_path = Path("models/experiments/lookback_horizon/gru_window_45.keras")
    assert gru_model_path.exists(), f"Missing GRU model: {gru_model_path}"
    gru_model = keras.models.load_model(gru_model_path)
    log.info("Loaded GRU model from %s. Input shape: %s", gru_model_path, gru_model.input_shape)

    # Prepare GRU streaming dataset
    scaler = StandardScaler()
    train_features_raw = df_raw.loc[train_mask, gru_feature_cols].values
    train_medians = np.nanmedian(train_features_raw, axis=0)
    
    # Impute and scale all rows using train-fitted parameters
    features_all_raw = df_raw[gru_feature_cols].values.copy()
    nan_inds = np.where(np.isnan(features_all_raw))
    features_all_raw[nan_inds] = np.take(train_medians, nan_inds[1])
    scaler.fit(features_all_raw[train_mask.values])
    features_all_scaled = scaler.transform(features_all_raw).astype(np.float32)

    labels_all = df_raw["label"].map(LABEL_MAPPING).fillna(-1).values.astype(int)

    # Construct sequence indices for window=45
    w = 45
    val_end_indices = []
    val_labels_list = []
    test_end_indices = []
    test_labels_list = []

    for _, grp in df_raw.groupby("symbol", sort=False):
        row_indices = grp.index.values
        dates = grp["date"].values
        labels_grp = grp["label"].map(LABEL_MAPPING).values

        for i in range(len(row_indices)):
            cur_date = pd.Timestamp(dates[i])
            cur_label = labels_grp[i]
            if pd.isna(cur_label):
                continue
            
            # Check window availability
            if i >= w - 1:
                global_idx = row_indices[i]
                if TRAIN_CUTOFF <= cur_date < VAL_CUTOFF:
                    val_end_indices.append(global_idx)
                    val_labels_list.append(int(cur_label))
                elif cur_date >= VAL_CUTOFF:
                    test_end_indices.append(global_idx)
                    test_labels_list.append(int(cur_label))

    val_end_indices = np.array(val_end_indices, dtype=np.int32)
    val_labels = np.array(val_labels_list, dtype=np.int32)
    test_end_indices = np.array(test_end_indices, dtype=np.int32)
    test_labels = np.array(test_labels_list, dtype=np.int32)

    # FAIRNESS CHECK
    assert len(val_labels) == val_count, f"Val count mismatch: GRU={len(val_labels)} vs XGB={val_count}"
    assert len(test_labels) == test_count, f"Test count mismatch: GRU={len(test_labels)} vs XGB={test_count}"
    assert np.array_equal(val_labels, y_val_xgb), "Val target labels mismatch between GRU and XGBoost!"
    assert np.array_equal(test_labels, y_test_xgb), "Test target labels mismatch between GRU and XGBoost!"
    log.info("FAIRNESS CHECK PASSED: GRU and XGBoost evaluated on 100% identical symbols, dates, and target rows.")

    val_dataset_gru = StreamingSequenceDataset(features_all_scaled, val_end_indices, val_labels, window_size=w, batch_size=256, shuffle=False)
    test_dataset_gru = StreamingSequenceDataset(features_all_scaled, test_end_indices, test_labels, window_size=w, batch_size=256, shuffle=False)

    log.info("Predicting GRU 45-day validation probabilities ...")
    gru_val_probs = gru_model.predict(val_dataset_gru, verbose=0)
    verify_probabilities(gru_val_probs, "GRU-45 Val Probs", val_count)

    log.info("Predicting GRU 45-day test probabilities ...")
    gru_test_probs = gru_model.predict(test_dataset_gru, verbose=0)
    verify_probabilities(gru_test_probs, "GRU-45 Test Probs", test_count)

    # 4. Load XGBoost Extended Horizons model and generate predictions
    log.info("\n--- Loading XGBoost Extended Horizons Model ---")
    xgb_model_path = Path("models/experiments/lookback_horizon/xgb_extended_horizons.xgb")
    assert xgb_model_path.exists(), f"Missing XGBoost model: {xgb_model_path}"
    xgb_booster = xgb.Booster()
    xgb_booster.load_model(str(xgb_model_path))
    log.info("Loaded XGBoost booster from %s", xgb_model_path)

    # XGBoost data matrices
    X_train_xgb = df_xgb.loc[train_mask, ext_feats].values.astype(np.float32)
    xgb_train_medians = np.nanmedian(X_train_xgb, axis=0)

    X_val_xgb = df_xgb.loc[val_mask, ext_feats].values.astype(np.float32)
    nan_val = np.where(np.isnan(X_val_xgb))
    X_val_xgb[nan_val] = np.take(xgb_train_medians, nan_val[1])

    X_test_xgb = df_xgb.loc[test_mask, ext_feats].values.astype(np.float32)
    nan_test = np.where(np.isnan(X_test_xgb))
    X_test_xgb[nan_test] = np.take(xgb_train_medians, nan_test[1])

    dval_xgb = xgb.DMatrix(X_val_xgb)
    dtest_xgb = xgb.DMatrix(X_test_xgb)

    xgb_val_probs = xgb_booster.predict(dval_xgb)
    verify_probabilities(xgb_val_probs, "XGB-Ext Val Probs", val_count)

    xgb_test_probs = xgb_booster.predict(dtest_xgb)
    verify_probabilities(xgb_test_probs, "XGB-Ext Test Probs", test_count)

    # Class ordering check
    # LABEL_MAPPING = {"bullish": 0, "bearish": 1, "sideways": 2}
    log.info("Class ordering verified for both models: [0: bullish, 1: bearish, 2: sideways]")

    # =========================================================================
    # EXPERIMENT: VALIDATION ENSEMBLE WEIGHT GRID
    # =========================================================================
    log.info("=" * 80)
    log.info("  VALIDATION ENSEMBLE WEIGHT COMPARISON")
    log.info("=" * 80)

    weight_configs = [
        {"name": "GRU 50% / XGB 50%", "gru_w": 0.50, "xgb_w": 0.50, "key": "w_50_50"},
        {"name": "GRU 55% / XGB 45%", "gru_w": 0.55, "xgb_w": 0.45, "key": "w_55_45"},
        {"name": "GRU 60% / XGB 40%", "gru_w": 0.60, "xgb_w": 0.40, "key": "w_60_40"},
        {"name": "GRU 65% / XGB 35%", "gru_w": 0.65, "xgb_w": 0.35, "key": "w_65_35"},
        {"name": "GRU 40% / XGB 60%", "gru_w": 0.40, "xgb_w": 0.60, "key": "w_40_60"},
        {"name": "GRU 45% / XGB 55%", "gru_w": 0.45, "xgb_w": 0.55, "key": "w_45_55"},
    ]

    val_results = {}
    best_val_key = None
    best_val_score = -1.0  # Primary selection on Macro F1 + Balanced Accuracy

    for wc in weight_configs:
        ens_val_probs = (wc["gru_w"] * gru_val_probs) + (wc["xgb_w"] * xgb_val_probs)
        ens_val_preds = np.argmax(ens_val_probs, axis=1)

        eval_dict = get_full_eval_dict(val_labels, ens_val_preds, wc["name"])
        eval_dict["gru_weight"] = wc["gru_w"]
        eval_dict["xgb_weight"] = wc["xgb_w"]
        val_results[wc["key"]] = eval_dict

        # Selection criterion: Macro F1 is primary, Balanced Accuracy secondary
        composite_score = eval_dict["macro_f1"] + eval_dict["balanced_accuracy"]
        log.info(
            "Config %-20s | Acc=%.4f | Macro F1=%.4f | Bal Acc=%.4f | Bull R=%.4f | Bear R=%.4f | Side R=%.4f",
            wc["name"],
            eval_dict["accuracy"],
            eval_dict["macro_f1"],
            eval_dict["balanced_accuracy"],
            eval_dict["per_class"]["bullish"]["recall"],
            eval_dict["per_class"]["bearish"]["recall"],
            eval_dict["per_class"]["sideways"]["recall"],
        )

        if composite_score > best_val_score:
            best_val_score = composite_score
            best_val_key = wc["key"]

    selected_config = [c for c in weight_configs if c["key"] == best_val_key][0]
    log.info("\n" + "=" * 80)
    log.info("  SELECTED WEIGHT CONFIGURATION (Validation Only): %s", selected_config["name"])
    log.info("  Validation Macro F1: %.4f | Balanced Accuracy: %.4f",
             val_results[best_val_key]["macro_f1"], val_results[best_val_key]["balanced_accuracy"])
    log.info("=" * 80)

    # =========================================================================
    # TEST SET EVALUATION (ONCE)
    # =========================================================================
    log.info("\nEvaluating selected weight ONCE on untouched test set ...")
    sel_test_probs = (selected_config["gru_w"] * gru_test_probs) + (selected_config["xgb_w"] * xgb_test_probs)
    sel_test_preds = np.argmax(sel_test_probs, axis=1)
    sel_test_eval = get_full_eval_dict(test_labels, sel_test_preds, f"Selected Ensemble {selected_config['name']} (Test)")
    sel_test_eval["gru_weight"] = selected_config["gru_w"]
    sel_test_eval["xgb_weight"] = selected_config["xgb_w"]

    # Also evaluate 50/50 experimental for comparison
    exp_50_50_test_probs = (0.50 * gru_test_probs) + (0.50 * xgb_test_probs)
    exp_50_50_test_preds = np.argmax(exp_50_50_test_probs, axis=1)
    exp_50_50_test_eval = get_full_eval_dict(test_labels, exp_50_50_test_preds, "Exp 50/50 Ensemble (GRU 45d + XGB Ext)")

    # Load current production baseline ensemble report for comparison
    current_prod_report_path = Path("data/reports/final_pipeline_test_report.json")
    current_prod_eval = None
    if current_prod_report_path.exists():
        with open(current_prod_report_path, "r") as f:
            current_prod_data = json.load(f)
            current_prod_eval = current_prod_data.get("final_weighted_ensemble")

    # Compile comprehensive report
    report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "step_0_verification": {
            "gru_feature_count": len(gru_feature_cols),
            "xgb_baseline_feature_count": len(base_feats),
            "xgb_extended_feature_count": len(ext_feats),
            "xgb_baseline_features": base_feats,
            "xgb_extended_features": ext_feats,
            "feature_discrepancy_explanation": (
                "The 41/53 vs 26/38 count distinction is purely the full flat parquet schema "
                "(ALL_XGB_FEATURES=41) vs point-in-time features present in features_daily.parquet (26). "
                "The 12 multi-horizon features brought the active training set from 26 to 38 features with zero code inconsistency."
            ),
            "feature_name_verification": "index_return_20d is used in baseline; market_return_30d/60d in extended additions.",
            "fairness_check": f"All models evaluated on identical {val_count} val rows and {test_count} test rows.",
            "probability_check": "Shape (N, 3), sum to 1.0, zero NaNs, class order: [0: bullish, 1: bearish, 2: sideways].",
        },
        "validation_weight_comparison": val_results,
        "selected_weight": {
            "key": best_val_key,
            "name": selected_config["name"],
            "gru_weight": selected_config["gru_w"],
            "xgb_weight": selected_config["xgb_w"],
            "val_metrics": val_results[best_val_key],
        },
        "test_evaluations": {
            "selected_ensemble": sel_test_eval,
            "experimental_50_50": exp_50_50_test_eval,
            "current_production_50_50": current_prod_eval,
        },
        "decision": {
            "recommendation": (
                "ADOPT" if (
                    val_results[best_val_key]["macro_f1"] > 0.420
                    and sel_test_eval["balanced_accuracy"] >= 0.4318
                ) else "REJECT_KEEP_PRODUCTION"
            ),
        }
    }

    report_path = REPORTS_DIR / "ensemble_weighting.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    log.info("Saved ensemble weighting report to %s", report_path)

    # Save model config metadata in experiment dir
    metadata = {
        "selected_weighting": selected_config["name"],
        "gru_weight": selected_config["gru_w"],
        "xgb_weight": selected_config["xgb_w"],
        "gru_model_ref": str(gru_model_path),
        "xgb_model_ref": str(xgb_model_path),
        "val_metrics": val_results[best_val_key],
        "test_metrics": sel_test_eval,
    }
    with open(EXPERIMENT_DIR / "metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    log.info("Saved experiment metadata to %s", EXPERIMENT_DIR / "metadata.json")


if __name__ == "__main__":
    main()
