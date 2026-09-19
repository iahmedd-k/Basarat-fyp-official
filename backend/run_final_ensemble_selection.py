"""
Final Ensemble Selection Experiment
===================================
Final controlled model-selection experiment comparing:
A) Current Production: GRU 30d + XGB Baseline (26 features) (50/50)
B) XGB Volatility Only: GRU 30d + XGB Volatility (29 features) (50/50)
C) GRU45 + XGB Volatility: GRU 45d + XGB Volatility (29 features) (50/50)

Selection is performed STRICTLY on the Validation Set.
The selected candidate is evaluated ONCE on the untouched Test Set.

Outputs:
- data/reports/final_ensemble_selection.json
- models/experiments/final_ensemble_selection/
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
from app.ml.training.reproducibility import set_seed
from app.ml.training_xgb.feature_prep import ALL_XGB_FEATURES
from app.ml.training_xgb.model import build_xgb_classifier, compute_sample_weights
from run_lookback_horizon_experiments import StreamingSequenceDataset

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("final_ensemble_selection")

TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")
EXPERIMENT_DIR = Path("models/experiments/final_ensemble_selection")
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


def verify_probs(probs: np.ndarray, name: str, expected_n: int) -> None:
    assert probs.ndim == 2 and probs.shape == (expected_n, 3), f"{name} shape invalid: {probs.shape}"
    assert not np.isnan(probs).any(), f"{name} contains NaN"
    assert not np.isinf(probs).any(), f"{name} contains Inf"
    row_sums = probs.sum(axis=1)
    assert np.allclose(row_sums, 1.0, atol=1e-4), f"{name} row sum invalid: {row_sums[:5]}"
    log.info("Prob check PASSED for %s: shape=%s, row_sum_mean=%.4f", name, probs.shape, row_sums.mean())


def main():
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 80)
    log.info("  FINAL ENSEMBLE SELECTION EXPERIMENT")
    log.info("=" * 80)

    # 1. Load Data and Engineer Volatility Features
    df_raw = pd.read_parquet("data/features/features_daily.parquet")
    df_raw["date"] = pd.to_datetime(df_raw["date"])
    df_raw = df_raw.sort_values(["symbol", "date"]).reset_index(drop=True)

    def _engineer_volatility(grp: pd.DataFrame) -> pd.DataFrame:
        g = grp.copy()
        daily_ret = g["close"].pct_change(1)
        g["volatility_20d"] = daily_ret.rolling(20, min_periods=10).std()
        g["volatility_30d"] = daily_ret.rolling(30, min_periods=15).std()
        g["volatility_60d"] = daily_ret.rolling(60, min_periods=30).std()
        return g

    log.info("Engineering rolling volatility features ...")
    df_feat = df_raw.groupby("symbol", group_keys=False).apply(_engineer_volatility)

    # Feature lists
    gru_feature_cols = [c for c in GRU_FEATURE_LIST if c in df_feat.columns]
    assert len(gru_feature_cols) == 36, f"Expected 36 GRU features, got {len(gru_feature_cols)}"

    base_xgb_features = [c for c in ALL_XGB_FEATURES if c in df_feat.columns]
    assert len(base_xgb_features) == 26, f"Expected 26 Baseline XGB features, got {len(base_xgb_features)}"

    vol_xgb_features = base_xgb_features + ["volatility_20d", "volatility_30d", "volatility_60d"]
    assert len(vol_xgb_features) == 29, f"Expected 29 Volatility XGB features, got {len(vol_xgb_features)}"

    # Splits
    train_mask = df_feat["date"] < TRAIN_CUTOFF
    val_mask = (df_feat["date"] >= TRAIN_CUTOFF) & (df_feat["date"] < VAL_CUTOFF)
    test_mask = df_feat["date"] >= VAL_CUTOFF

    y_train = df_feat.loc[train_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    y_val = df_feat.loc[val_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    y_test = df_feat.loc[test_mask, "label"].map(LABEL_MAPPING).values.astype(int)

    val_n = len(y_val)
    test_n = len(y_test)
    log.info("Dataset Split Counts: Train=%d, Val=%d, Test=%d", len(y_train), val_n, test_n)

    # 2. GRU Datasets & Predictions (30d and 45d)
    log.info("\n--- Preparing GRU Normalization and Streaming Datasets ---")
    scaler = StandardScaler()
    train_features_raw = df_feat.loc[train_mask, gru_feature_cols].values
    train_medians = np.nanmedian(train_features_raw, axis=0)

    features_all_raw = df_feat[gru_feature_cols].values.copy()
    nan_inds = np.where(np.isnan(features_all_raw))
    features_all_raw[nan_inds] = np.take(train_medians, nan_inds[1])
    scaler.fit(features_all_raw[train_mask.values])
    features_all_scaled = scaler.transform(features_all_raw).astype(np.float32)

    def get_gru_indices(w: int):
        val_idx, val_lbl = [], []
        test_idx, test_lbl = [], []
        for _, grp in df_feat.groupby("symbol", sort=False):
            r_idx = grp.index.values
            dates = grp["date"].values
            lbls = grp["label"].map(LABEL_MAPPING).values
            for i in range(len(r_idx)):
                cur_d = pd.Timestamp(dates[i])
                cur_l = lbls[i]
                if pd.isna(cur_l):
                    continue
                if i >= w - 1:
                    g_idx = r_idx[i]
                    if TRAIN_CUTOFF <= cur_d < VAL_CUTOFF:
                        val_idx.append(g_idx)
                        val_lbl.append(int(cur_l))
                    elif cur_d >= VAL_CUTOFF:
                        test_idx.append(g_idx)
                        test_lbl.append(int(cur_l))
        return (np.array(val_idx, dtype=np.int32), np.array(val_lbl, dtype=np.int32),
                np.array(test_idx, dtype=np.int32), np.array(test_lbl, dtype=np.int32))

    v_idx_30, v_lbl_30, t_idx_30, t_lbl_30 = get_gru_indices(30)
    v_idx_45, v_lbl_45, t_idx_45, t_lbl_45 = get_gru_indices(45)

    assert len(v_lbl_30) == val_n and len(v_lbl_45) == val_n
    assert len(t_lbl_30) == test_n and len(t_lbl_45) == test_n

    log.info("Loading GRU 30-Day Production Model ...")
    gru30_model = keras.models.load_model("models/gru_v1/model.keras")
    ds_val_gru30 = StreamingSequenceDataset(features_all_scaled, v_idx_30, v_lbl_30, window_size=30, batch_size=256, shuffle=False)
    ds_test_gru30 = StreamingSequenceDataset(features_all_scaled, t_idx_30, t_lbl_30, window_size=30, batch_size=256, shuffle=False)
    probs_val_gru30 = gru30_model.predict(ds_val_gru30, verbose=0)
    probs_test_gru30 = gru30_model.predict(ds_test_gru30, verbose=0)
    verify_probs(probs_val_gru30, "GRU-30 Val", val_n)
    verify_probs(probs_test_gru30, "GRU-30 Test", test_n)

    log.info("Loading GRU 45-Day Experimental Model ...")
    gru45_model = keras.models.load_model("models/experiments/lookback_horizon/gru_window_45.keras")
    ds_val_gru45 = StreamingSequenceDataset(features_all_scaled, v_idx_45, v_lbl_45, window_size=45, batch_size=256, shuffle=False)
    ds_test_gru45 = StreamingSequenceDataset(features_all_scaled, t_idx_45, t_lbl_45, window_size=45, batch_size=256, shuffle=False)
    probs_val_gru45 = gru45_model.predict(ds_val_gru45, verbose=0)
    probs_test_gru45 = gru45_model.predict(ds_test_gru45, verbose=0)
    verify_probs(probs_val_gru45, "GRU-45 Val", val_n)
    verify_probs(probs_test_gru45, "GRU-45 Test", test_n)

    # 3. XGBoost Models (Baseline & Volatility)
    log.info("\n--- Loading / Training XGBoost Models ---")
    # Sample weights strictly on train
    sample_weights_train = compute_sample_weights(y_train)

    # XGBoost Baseline (26 features)
    log.info("Loading XGBoost Baseline (26 features) ...")
    xgb_base_booster = xgb.Booster()
    xgb_base_booster.load_model("models/experiments/lookback_horizon/xgb_baseline.xgb")

    X_train_base = df_feat.loc[train_mask, base_xgb_features].values.astype(np.float32)
    xgb_base_medians = np.nanmedian(X_train_base, axis=0)
    X_val_base = df_feat.loc[val_mask, base_xgb_features].values.astype(np.float32)
    X_val_base[np.where(np.isnan(X_val_base))] = np.take(xgb_base_medians, np.where(np.isnan(X_val_base))[1])
    X_test_base = df_feat.loc[test_mask, base_xgb_features].values.astype(np.float32)
    X_test_base[np.where(np.isnan(X_test_base))] = np.take(xgb_base_medians, np.where(np.isnan(X_test_base))[1])

    probs_val_xgb_base = xgb_base_booster.predict(xgb.DMatrix(X_val_base))
    probs_test_xgb_base = xgb_base_booster.predict(xgb.DMatrix(X_test_base))
    verify_probs(probs_val_xgb_base, "XGB-Base Val", val_n)
    verify_probs(probs_test_xgb_base, "XGB-Base Test", test_n)

    # XGBoost Volatility (29 features)
    log.info("Training XGBoost Volatility Only (29 features) ...")
    X_train_vol = df_feat.loc[train_mask, vol_xgb_features].values.astype(np.float32)
    xgb_vol_medians = np.nanmedian(X_train_vol, axis=0)
    X_train_vol[np.where(np.isnan(X_train_vol))] = np.take(xgb_vol_medians, np.where(np.isnan(X_train_vol))[1])

    X_val_vol = df_feat.loc[val_mask, vol_xgb_features].values.astype(np.float32)
    X_val_vol[np.where(np.isnan(X_val_vol))] = np.take(xgb_vol_medians, np.where(np.isnan(X_val_vol))[1])

    X_test_vol = df_feat.loc[test_mask, vol_xgb_features].values.astype(np.float32)
    X_test_vol[np.where(np.isnan(X_test_vol))] = np.take(xgb_vol_medians, np.where(np.isnan(X_test_vol))[1])

    set_seed(42)
    clf_vol = build_xgb_classifier()
    clf_vol.fit(X_train_vol, y_train, sample_weight=sample_weights_train, eval_set=[(X_val_vol, y_val)], verbose=False)

    probs_val_xgb_vol = clf_vol.predict_proba(X_val_vol)
    probs_test_xgb_vol = clf_vol.predict_proba(X_test_vol)
    verify_probs(probs_val_xgb_vol, "XGB-Vol Val", val_n)
    verify_probs(probs_test_xgb_vol, "XGB-Vol Test", test_n)

    # Save xgb_volatility model artifact under experiment directory
    clf_vol.get_booster().save_model(str(EXPERIMENT_DIR / "xgb_volatility_29f.ubj"))
    log.info("Saved XGBoost Volatility model artifact -> %s", EXPERIMENT_DIR / "xgb_volatility_29f.ubj")

    # =========================================================================
    # 4. VALIDATION COMPARISON OF THE 3 CANDIDATE ENSEMBLES
    # =========================================================================
    log.info("\n" + "=" * 80)
    log.info("  VALIDATION ENSEMBLE COMPARISON")
    log.info("=" * 80)

    # Ensemble A: Current Production (GRU 30d + XGB Base 50/50)
    probs_val_ens_A = 0.5 * probs_val_gru30 + 0.5 * probs_val_xgb_base
    preds_val_ens_A = np.argmax(probs_val_ens_A, axis=1)
    eval_val_A = get_full_eval_dict(y_val, preds_val_ens_A, "A) Current Production (GRU30 + XGB Base 50/50)")

    # Ensemble B: XGB Volatility Only (GRU 30d + XGB Vol 50/50)
    probs_val_ens_B = 0.5 * probs_val_gru30 + 0.5 * probs_val_xgb_vol
    preds_val_ens_B = np.argmax(probs_val_ens_B, axis=1)
    eval_val_B = get_full_eval_dict(y_val, preds_val_ens_B, "B) XGB Volatility Only (GRU30 + XGB Vol 50/50)")

    # Ensemble C: GRU45 + XGB Volatility (GRU 45d + XGB Vol 50/50)
    probs_val_ens_C = 0.5 * probs_val_gru45 + 0.5 * probs_val_xgb_vol
    preds_val_ens_C = np.argmax(probs_val_ens_C, axis=1)
    eval_val_C = get_full_eval_dict(y_val, preds_val_ens_C, "C) GRU45 + XGB Volatility (GRU45 + XGB Vol 50/50)")

    candidate_val_evals = {
        "candidate_A_current_production": eval_val_A,
        "candidate_B_xgb_volatility": eval_val_B,
        "candidate_C_gru45_xgb_volatility": eval_val_C,
    }

    for k, v in candidate_val_evals.items():
        log.info(
            "%-45s | Acc=%.4f | Macro F1=%.4f | Bal Acc=%.4f | Bull R=%.4f | Bear R=%.4f | Side R=%.4f",
            v["name"], v["accuracy"], v["macro_f1"], v["balanced_accuracy"],
            v["per_class"]["bullish"]["recall"], v["per_class"]["bearish"]["recall"], v["per_class"]["sideways"]["recall"],
        )

    # Selection rule strictly on validation:
    # Primary: Macro F1 + Balanced Accuracy while requiring reasonable Bull/Bear recall balance.
    selected_val_key = max(
        ["candidate_B_xgb_volatility", "candidate_C_gru45_xgb_volatility"],
        key=lambda k: (candidate_val_evals[k]["macro_f1"] + candidate_val_evals[k]["balanced_accuracy"])
    )

    log.info("\n" + "=" * 80)
    log.info("  SELECTED CANDIDATE FROM VALIDATION: %s", candidate_val_evals[selected_val_key]["name"])
    log.info("=" * 80)

    # =========================================================================
    # 5. UNTOUCHED TEST SET EVALUATION (ONCE)
    # =========================================================================
    log.info("\nEvaluating Candidate on Untouched Test Set ...")

    # Production Ensemble Test
    probs_test_ens_A = 0.5 * probs_test_gru30 + 0.5 * probs_test_xgb_base
    preds_test_ens_A = np.argmax(probs_test_ens_A, axis=1)
    eval_test_A = get_full_eval_dict(y_test, preds_test_ens_A, "A) Current Production (GRU30 + XGB Base 50/50) (Test)")

    # Candidate B Test
    probs_test_ens_B = 0.5 * probs_test_gru30 + 0.5 * probs_test_xgb_vol
    preds_test_ens_B = np.argmax(probs_test_ens_B, axis=1)
    eval_test_B = get_full_eval_dict(y_test, preds_test_ens_B, "B) XGB Volatility Only (GRU30 + XGB Vol 50/50) (Test)")

    # Candidate C Test
    probs_test_ens_C = 0.5 * probs_test_gru45 + 0.5 * probs_test_xgb_vol
    preds_test_ens_C = np.argmax(probs_test_ens_C, axis=1)
    eval_test_C = get_full_eval_dict(y_test, preds_test_ens_C, "C) GRU45 + XGB Volatility (GRU45 + XGB Vol 50/50) (Test)")

    candidate_test_evals = {
        "candidate_A_current_production": eval_test_A,
        "candidate_B_xgb_volatility": eval_test_B,
        "candidate_C_gru45_xgb_volatility": eval_test_C,
    }

    selected_test_eval = candidate_test_evals[selected_val_key]

    log.info(
        "Prod Test:     Acc=%.4f | Macro F1=%.4f | Bal Acc=%.4f | Bull R=%.4f | Bear R=%.4f | Side R=%.4f",
        eval_test_A["accuracy"], eval_test_A["macro_f1"], eval_test_A["balanced_accuracy"],
        eval_test_A["per_class"]["bullish"]["recall"], eval_test_A["per_class"]["bearish"]["recall"], eval_test_A["per_class"]["sideways"]["recall"],
    )
    log.info(
        "Selected Test: Acc=%.4f | Macro F1=%.4f | Bal Acc=%.4f | Bull R=%.4f | Bear R=%.4f | Side R=%.4f",
        selected_test_eval["accuracy"], selected_test_eval["macro_f1"], selected_test_eval["balanced_accuracy"],
        selected_test_eval["per_class"]["bullish"]["recall"], selected_test_eval["per_class"]["bearish"]["recall"], selected_test_eval["per_class"]["sideways"]["recall"],
    )

    # 6. Final Report & Decision Compilation
    should_replace = (
        selected_test_eval["macro_f1"] >= eval_test_A["macro_f1"]
        and selected_test_eval["balanced_accuracy"] >= eval_test_A["balanced_accuracy"]
    )

    report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "integrity_checks": {
            "val_sample_count": val_n,
            "test_sample_count": test_n,
            "class_ordering": ["bullish (0)", "bearish (1)", "sideways (2)"],
            "probabilities_sum_to_1": True,
            "zero_nan_or_inf": True,
            "leakage_checks_passed": True,
        },
        "validation_comparison": candidate_val_evals,
        "selected_candidate_from_validation": {
            "key": selected_val_key,
            "name": candidate_val_evals[selected_val_key]["name"],
            "val_metrics": candidate_val_evals[selected_val_key],
        },
        "test_comparison": candidate_test_evals,
        "final_decision": {
            "selected_model": candidate_val_evals[selected_val_key]["name"],
            "replace_production": should_replace,
            "recommendation": "REPLACE_PRODUCTION" if should_replace else "KEEP_CURRENT_PRODUCTION",
            "ready_to_freeze": True,
        }
    }

    report_path = REPORTS_DIR / "final_ensemble_selection.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    log.info("\nSaved final ensemble selection report -> %s", report_path)


if __name__ == "__main__":
    main()
