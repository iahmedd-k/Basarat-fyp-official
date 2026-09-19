"""
Diagnostic Prediction-Complementarity Experiment
=================================================
Diagnoses why the GRU30 + XGB Baseline ensemble outperforms the GRU45 + XGB Extended
ensemble despite individual model metric differences.

Evaluates on BOTH Validation and Test sets using exact identical rows.
Outputs: data/reports/ensemble_complementarity.json
"""

import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
from scipy.stats import pearsonr
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
log = logging.getLogger("complementarity_diagnostic")

TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")
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


def compute_agreement(preds_a: np.ndarray, preds_b: np.ndarray) -> dict:
    agree_mask = (preds_a == preds_b)
    n = len(preds_a)
    agree_cnt = int(np.sum(agree_mask))
    disagree_cnt = n - agree_cnt
    return {
        "sample_count": n,
        "agreement_count": agree_cnt,
        "agreement_pct": round(agree_cnt / n * 100.0, 2),
        "disagreement_count": disagree_cnt,
        "disagreement_pct": round(disagree_cnt / n * 100.0, 2),
    }


def compute_complementarity(preds_a: np.ndarray, preds_b: np.ndarray, y_true: np.ndarray) -> dict:
    n = len(y_true)
    correct_a = (preds_a == y_true)
    correct_b = (preds_b == y_true)

    both_correct = int(np.sum(correct_a & correct_b))
    both_incorrect = int(np.sum((~correct_a) & (~correct_b)))
    a_corr_b_inc = int(np.sum(correct_a & (~correct_b)))
    a_inc_b_corr = int(np.sum((~correct_a) & correct_b))

    union_correct = int(np.sum(correct_a | correct_b))

    return {
        "sample_count": n,
        "both_correct_count": both_correct,
        "both_correct_pct": round(both_correct / n * 100.0, 2),
        "both_incorrect_count": both_incorrect,
        "both_incorrect_pct": round(both_incorrect / n * 100.0, 2),
        "first_correct_second_incorrect_count": a_corr_b_inc,
        "first_correct_second_incorrect_pct": round(a_corr_b_inc / n * 100.0, 2),
        "first_incorrect_second_correct_count": a_inc_b_corr,
        "first_incorrect_second_correct_pct": round(a_inc_b_corr / n * 100.0, 2),
        "oracle_union_accuracy_pct": round(union_correct / n * 100.0, 2),
        "useful_complementary_pct": round((a_corr_b_inc + a_inc_b_corr) / n * 100.0, 2),
    }


def compute_prob_correlations(probs_a: np.ndarray, probs_b: np.ndarray) -> dict:
    classes = ["bullish", "bearish", "sideways"]
    res = {}
    for i, c in enumerate(classes):
        r, p = pearsonr(probs_a[:, i], probs_b[:, i])
        res[c] = {"pearson_r": round(float(r), 4), "p_value": float(p)}
    
    # Overall correlation across all probability values flattened
    r_all, _ = pearsonr(probs_a.flatten(), probs_b.flatten())
    res["overall_pearson_r"] = round(float(r_all), 4)
    return res


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    log.info("=" * 80)
    log.info("  DIAGNOSTIC PREDICTION-COMPLEMENTARITY EXPERIMENT")
    log.info("=" * 80)

    # 1. Load Data
    df_raw = pd.read_parquet("data/features/features_daily.parquet")
    df_raw["date"] = pd.to_datetime(df_raw["date"])
    df_raw = df_raw.sort_values(["symbol", "date"]).reset_index(drop=True)

    df_xgb, base_feats, ext_feats = build_extended_xgb_features()

    train_mask = df_xgb["date"] < TRAIN_CUTOFF
    val_mask = (df_xgb["date"] >= TRAIN_CUTOFF) & (df_xgb["date"] < VAL_CUTOFF)
    test_mask = df_xgb["date"] >= VAL_CUTOFF

    y_val = df_xgb.loc[val_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    y_test = df_xgb.loc[test_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    val_n = len(y_val)
    test_n = len(y_test)

    log.info("Split counts: Train=%d, Val=%d, Test=%d", train_mask.sum(), val_n, test_n)

    # 2. Prepare GRU Datasets (both 30d and 45d)
    gru_feature_cols = [c for c in GRU_FEATURE_LIST if c in df_raw.columns]
    scaler = StandardScaler()
    train_features_raw = df_raw.loc[train_mask, gru_feature_cols].values
    train_medians = np.nanmedian(train_features_raw, axis=0)

    features_all_raw = df_raw[gru_feature_cols].values.copy()
    nan_inds = np.where(np.isnan(features_all_raw))
    features_all_raw[nan_inds] = np.take(train_medians, nan_inds[1])
    scaler.fit(features_all_raw[train_mask.values])
    features_all_scaled = scaler.transform(features_all_raw).astype(np.float32)

    def get_gru_indices(w: int):
        val_idx, val_lbl = [], []
        test_idx, test_lbl = [], []
        for _, grp in df_raw.groupby("symbol", sort=False):
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
    assert np.array_equal(v_lbl_30, y_val) and np.array_equal(t_lbl_30, y_test)

    # 3. Load Models
    log.info("\n--- Loading Model A: GRU 30-Day Production ---")
    gru30_model = keras.models.load_model("models/gru_v1/model.keras")

    log.info("--- Loading Model B: GRU 45-Day Experimental ---")
    gru45_model = keras.models.load_model("models/experiments/lookback_horizon/gru_window_45.keras")

    log.info("--- Loading Model C: XGBoost Baseline ---")
    xgb_base_booster = xgb.Booster()
    xgb_base_booster.load_model("models/experiments/lookback_horizon/xgb_baseline.xgb")

    log.info("--- Loading Model D: XGBoost Extended ---")
    xgb_ext_booster = xgb.Booster()
    xgb_ext_booster.load_model("models/experiments/lookback_horizon/xgb_extended_horizons.xgb")

    # 4. Generate Predictions for all 4 models on Val and Test
    log.info("\n--- Generating Predictions ---")
    # GRU 30
    ds_val_gru30 = StreamingSequenceDataset(features_all_scaled, v_idx_30, v_lbl_30, window_size=30, batch_size=256, shuffle=False)
    ds_test_gru30 = StreamingSequenceDataset(features_all_scaled, t_idx_30, t_lbl_30, window_size=30, batch_size=256, shuffle=False)
    probs_val_gru30 = gru30_model.predict(ds_val_gru30, verbose=0)
    probs_test_gru30 = gru30_model.predict(ds_test_gru30, verbose=0)

    # GRU 45
    ds_val_gru45 = StreamingSequenceDataset(features_all_scaled, v_idx_45, v_lbl_45, window_size=45, batch_size=256, shuffle=False)
    ds_test_gru45 = StreamingSequenceDataset(features_all_scaled, t_idx_45, t_lbl_45, window_size=45, batch_size=256, shuffle=False)
    probs_val_gru45 = gru45_model.predict(ds_val_gru45, verbose=0)
    probs_test_gru45 = gru45_model.predict(ds_test_gru45, verbose=0)

    # XGBoost Baseline
    X_train_base = df_xgb.loc[train_mask, base_feats].values.astype(np.float32)
    xgb_base_medians = np.nanmedian(X_train_base, axis=0)
    X_val_base = df_xgb.loc[val_mask, base_feats].values.astype(np.float32)
    X_val_base[np.where(np.isnan(X_val_base))] = np.take(xgb_base_medians, np.where(np.isnan(X_val_base))[1])
    X_test_base = df_xgb.loc[test_mask, base_feats].values.astype(np.float32)
    X_test_base[np.where(np.isnan(X_test_base))] = np.take(xgb_base_medians, np.where(np.isnan(X_test_base))[1])

    probs_val_xgb_base = xgb_base_booster.predict(xgb.DMatrix(X_val_base))
    probs_test_xgb_base = xgb_base_booster.predict(xgb.DMatrix(X_test_base))

    # XGBoost Extended
    X_train_ext = df_xgb.loc[train_mask, ext_feats].values.astype(np.float32)
    xgb_ext_medians = np.nanmedian(X_train_ext, axis=0)
    X_val_ext = df_xgb.loc[val_mask, ext_feats].values.astype(np.float32)
    X_val_ext[np.where(np.isnan(X_val_ext))] = np.take(xgb_ext_medians, np.where(np.isnan(X_val_ext))[1])
    X_test_ext = df_xgb.loc[test_mask, ext_feats].values.astype(np.float32)
    X_test_ext[np.where(np.isnan(X_test_ext))] = np.take(xgb_ext_medians, np.where(np.isnan(X_test_ext))[1])

    probs_val_xgb_ext = xgb_ext_booster.predict(xgb.DMatrix(X_val_ext))
    probs_test_xgb_ext = xgb_ext_booster.predict(xgb.DMatrix(X_test_ext))

    preds_val_gru30 = np.argmax(probs_val_gru30, axis=1)
    preds_test_gru30 = np.argmax(probs_test_gru30, axis=1)

    preds_val_gru45 = np.argmax(probs_val_gru45, axis=1)
    preds_test_gru45 = np.argmax(probs_test_gru45, axis=1)

    preds_val_xgb_base = np.argmax(probs_val_xgb_base, axis=1)
    preds_test_xgb_base = np.argmax(probs_test_xgb_base, axis=1)

    preds_val_xgb_ext = np.argmax(probs_val_xgb_ext, axis=1)
    preds_test_xgb_ext = np.argmax(probs_test_xgb_ext, axis=1)

    # 5. Ensembles Predictions
    # Current Prod: GRU30 + XGB Base (50/50)
    probs_val_ens_prod = 0.5 * probs_val_gru30 + 0.5 * probs_val_xgb_base
    probs_test_ens_prod = 0.5 * probs_test_gru30 + 0.5 * probs_test_xgb_base
    preds_val_ens_prod = np.argmax(probs_val_ens_prod, axis=1)
    preds_test_ens_prod = np.argmax(probs_test_ens_prod, axis=1)

    # Exp 50/50: GRU45 + XGB Ext (50/50)
    probs_val_ens_exp50 = 0.5 * probs_val_gru45 + 0.5 * probs_val_xgb_ext
    probs_test_ens_exp50 = 0.5 * probs_test_gru45 + 0.5 * probs_test_xgb_ext
    preds_val_ens_exp50 = np.argmax(probs_val_ens_exp50, axis=1)
    preds_test_ens_exp50 = np.argmax(probs_test_ens_exp50, axis=1)

    # Exp 40/60: GRU45 + XGB Ext (40/60)
    probs_val_ens_exp4060 = 0.4 * probs_val_gru45 + 0.6 * probs_val_xgb_ext
    probs_test_ens_exp4060 = 0.4 * probs_test_gru45 + 0.6 * probs_test_xgb_ext
    preds_val_ens_exp4060 = np.argmax(probs_val_ens_exp4060, axis=1)
    preds_test_ens_exp4060 = np.argmax(probs_test_ens_exp4060, axis=1)

    # 6. Build Diagnostic Suite for a split
    def build_split_diagnostic(split_name: str, y_true: np.ndarray,
                               p_g30, p_g45, p_xb, p_xe,
                               pr_g30, pr_g45, pr_xb, pr_xe,
                               pr_prod, pr_exp50, pr_exp4060):
        # A. Per-model performance
        perf = {
            "gru_30": get_full_eval_dict(y_true, pr_g30, "GRU 30-Day"),
            "gru_45": get_full_eval_dict(y_true, pr_g45, "GRU 45-Day"),
            "xgb_base": get_full_eval_dict(y_true, pr_xb, "XGBoost Baseline"),
            "xgb_ext": get_full_eval_dict(y_true, pr_xe, "XGBoost Extended"),
            "ens_prod_50_50": get_full_eval_dict(y_true, pr_prod, "Prod Ensemble (GRU30 + XGB Base 50/50)"),
            "ens_exp_50_50": get_full_eval_dict(y_true, pr_exp50, "Exp Ensemble (GRU45 + XGB Ext 50/50)"),
            "ens_exp_40_60": get_full_eval_dict(y_true, pr_exp4060, "Exp Ensemble (GRU45 + XGB Ext 40/60)"),
        }

        # B. Prediction Agreement
        agreement = {
            "gru30_vs_xgb_base": compute_agreement(pr_g30, pr_xb),
            "gru45_vs_xgb_ext": compute_agreement(pr_g45, pr_xe),
            "gru30_vs_gru45": compute_agreement(pr_g30, pr_g45),
            "xgb_base_vs_xgb_ext": compute_agreement(pr_xb, pr_xe),
        }

        # C. Correctness Complementarity
        complementarity = {
            "gru30_vs_xgb_base": compute_complementarity(pr_g30, pr_xb, y_true),
            "gru45_vs_xgb_ext": compute_complementarity(pr_g45, pr_xe, y_true),
            "gru30_vs_gru45": compute_complementarity(pr_g30, pr_g45, y_true),
            "xgb_base_vs_xgb_ext": compute_complementarity(pr_xb, pr_xe, y_true),
        }

        # D. Probability Correlations
        prob_corr = {
            "gru30_vs_xgb_base": compute_prob_correlations(p_g30, p_xb),
            "gru45_vs_xgb_ext": compute_prob_correlations(p_g45, p_xe),
            "gru30_vs_gru45": compute_prob_correlations(p_g30, p_g45),
            "xgb_base_vs_xgb_ext": compute_prob_correlations(p_xb, p_xe),
        }

        # E. Detailed Error Analysis
        # Determine for each ensemble where mistakes occur
        def analyze_ensemble_errors(preds, name):
            cm = confusion_matrix(y_true, preds, labels=[0, 1, 2])
            # cm[i, j] -> row=actual, col=pred
            total_bull = int(np.sum(y_true == 0))
            total_bear = int(np.sum(y_true == 1))
            total_side = int(np.sum(y_true == 2))

            # Directional confusion: Bull actual predicted Bear, Bear actual predicted Bull
            bull_as_bear = int(cm[0, 1])
            bear_as_bull = int(cm[1, 0])
            # Collapse to sideways
            bull_as_side = int(cm[0, 2])
            bear_as_side = int(cm[1, 2])
            # False alarms from sideways
            side_as_bull = int(cm[2, 0])
            side_as_bear = int(cm[2, 1])

            return {
                "name": name,
                "confusion_matrix": cm.tolist(),
                "directional_inversions": {
                    "actual_bull_pred_bear": bull_as_bear,
                    "actual_bull_pred_bear_pct": round(bull_as_bear / total_bull * 100.0, 2),
                    "actual_bear_pred_bull": bear_as_bull,
                    "actual_bear_pred_bull_pct": round(bear_as_bull / total_bear * 100.0, 2),
                },
                "sideways_collapses": {
                    "actual_bull_pred_side": bull_as_side,
                    "actual_bull_pred_side_pct": round(bull_as_side / total_bull * 100.0, 2),
                    "actual_bear_pred_side": bear_as_side,
                    "actual_bear_pred_side_pct": round(bear_as_side / total_bear * 100.0, 2),
                },
                "false_signals_from_sideways": {
                    "actual_side_pred_bull": side_as_bull,
                    "actual_side_pred_bull_pct": round(side_as_bull / total_side * 100.0, 2),
                    "actual_side_pred_bear": side_as_bear,
                    "actual_side_pred_bear_pct": round(side_as_bear / total_side * 100.0, 2),
                }
            }

        error_analysis = {
            "ens_prod_50_50": analyze_ensemble_errors(pr_prod, "Prod Ensemble (GRU30 + XGB Base 50/50)"),
            "ens_exp_50_50": analyze_ensemble_errors(pr_exp50, "Exp Ensemble (GRU45 + XGB Ext 50/50)"),
            "ens_exp_40_60": analyze_ensemble_errors(pr_exp4060, "Exp Ensemble (GRU45 + XGB Ext 40/60)"),
        }

        return {
            "split_name": split_name,
            "sample_count": len(y_true),
            "model_performance": perf,
            "prediction_agreement": agreement,
            "correctness_complementarity": complementarity,
            "probability_correlations": prob_corr,
            "error_analysis": error_analysis,
        }

    val_diag = build_split_diagnostic(
        "validation", y_val,
        probs_val_gru30, probs_val_gru45, probs_val_xgb_base, probs_val_xgb_ext,
        preds_val_gru30, preds_val_gru45, preds_val_xgb_base, preds_val_xgb_ext,
        preds_val_ens_prod, preds_val_ens_exp50, preds_val_ens_exp4060,
    )

    test_diag = build_split_diagnostic(
        "test", y_test,
        probs_test_gru30, probs_test_gru45, probs_test_xgb_base, probs_test_xgb_ext,
        preds_test_gru30, preds_test_gru45, preds_test_xgb_base, preds_test_xgb_ext,
        preds_test_ens_prod, preds_test_ens_exp50, preds_test_ens_exp4060,
    )

    full_report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "validation_diagnostics": val_diag,
        "test_diagnostics": test_diag,
    }

    report_path = REPORTS_DIR / "ensemble_complementarity.json"
    with open(report_path, "w") as f:
        json.dump(full_report, f, indent=2)
    log.info("\nSaved complementarity report to %s", report_path)


if __name__ == "__main__":
    main()
