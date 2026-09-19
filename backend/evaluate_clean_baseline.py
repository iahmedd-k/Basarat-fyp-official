"""
Clean Baseline Evaluation Script
Evaluates GRU, XGBoost, and Ensemble on the untouched test set,
along with the Naive majority-class baseline.
"""

import json
from pathlib import Path
import numpy as np
import pandas as pd
import joblib
import tensorflow as tf
import xgboost as xgb
from sklearn.metrics import (
    accuracy_score,
    balanced_accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
)

from app.data.features.gru_feature_list import GRU_FEATURE_LIST, GRU_FEATURE_VERSION
from app.ml.training.data_split import time_split
from app.ml.training.scaling import apply_scaler
from app.ml.training_xgb.feature_prep import ALL_XGB_FEATURES

def run_evaluation():
    # Load label mapping
    label_mapping = json.loads(Path("data/features/label_mapping.json").read_text(encoding="utf-8"))
    label_names = {v: k for k, v in label_mapping.items()}
    labels_sorted = sorted(label_names.keys())
    target_names = [label_names[i] for i in labels_sorted]

    # Load GRU data
    seq_data = np.load("data/sequences/sequences.npz")
    X_gru_all = seq_data["X"]
    y_gru_all = seq_data["y"]
    meta_gru_all = pd.read_parquet("data/sequences/sequences_meta.parquet")

    # GRU time split
    gru_splits = time_split(
        X_gru_all, y_gru_all, meta_gru_all,
        train_cutoff=pd.Timestamp("2024-07-01"),
        val_cutoff=pd.Timestamp("2025-07-01"),
    )

    X_train_gru, y_train_gru = gru_splits["train"]["X"], gru_splits["train"]["y"]
    X_val_gru, y_val_gru = gru_splits["val"]["X"], gru_splits["val"]["y"]
    X_test_gru, y_test_gru = gru_splits["test"]["X"], gru_splits["test"]["y"]
    meta_test_gru = gru_splits["test"]["meta"]

    # Load GRU model and scaler
    gru_model = tf.keras.models.load_model("models/gru_v1/model.keras")
    scaler = joblib.load("data/scalers/scaler.pkl")

    # Scale GRU test data
    X_test_gru_scaled = apply_scaler(X_test_gru, scaler)
    gru_proba = gru_model.predict(X_test_gru_scaled, verbose=0)
    gru_pred = np.argmax(gru_proba, axis=1)

    # Load XGBoost features and model
    df_xgb = pd.read_parquet("data/processed/features_xgb.parquet")
    dates_xgb = pd.to_datetime(df_xgb["date"])
    train_mask = dates_xgb < pd.Timestamp("2024-07-01")
    val_mask = (dates_xgb >= pd.Timestamp("2024-07-01")) & (dates_xgb < pd.Timestamp("2025-07-01"))
    test_mask = dates_xgb >= pd.Timestamp("2025-07-01")

    feature_names = [c for c in ALL_XGB_FEATURES if c in df_xgb.columns]
    X_xgb_train = df_xgb.loc[train_mask, feature_names].values.astype(np.float32)

    # Impute using train median
    fill_medians = np.zeros(len(feature_names), dtype=np.float32)
    for f_idx in range(len(feature_names)):
        col_train = X_xgb_train[:, f_idx]
        valid = col_train[~np.isnan(col_train)]
        fill_medians[f_idx] = float(np.median(valid)) if len(valid) > 0 else 0.0

    # Match test rows exactly with GRU test set (symbol, date)
    # Merge meta_test_gru with df_xgb
    df_xgb_indexed = df_xgb.copy()
    df_xgb_indexed["date_dt"] = pd.to_datetime(df_xgb_indexed["date"])
    meta_test_gru_copy = meta_test_gru.copy()
    meta_test_gru_copy["date_dt"] = pd.to_datetime(meta_test_gru_copy["date"])
    meta_test_gru_copy["orig_idx"] = np.arange(len(meta_test_gru_copy))

    merged = pd.merge(
        meta_test_gru_copy,
        df_xgb_indexed,
        on=["symbol", "date_dt"],
        how="left"
    )

    X_xgb_aligned = merged[feature_names].values.astype(np.float32)
    for f_idx in range(len(feature_names)):
        mask_nan = np.isnan(X_xgb_aligned[:, f_idx])
        X_xgb_aligned[mask_nan, f_idx] = fill_medians[f_idx]

    # Load XGBoost unweighted model
    xgb_unweighted = xgb.XGBClassifier()
    xgb_unweighted.load_model("models/xgb_v1/xgb_v1_unweighted.xgb")
    xgb_proba = xgb_unweighted.predict_proba(X_xgb_aligned)
    xgb_pred = np.argmax(xgb_proba, axis=1)

    # Load XGBoost weighted model
    xgb_weighted = xgb.XGBClassifier()
    xgb_weighted.load_model("models/xgb_v1/xgb_v1_weighted.xgb")
    xgb_weighted_proba = xgb_weighted.predict_proba(X_xgb_aligned)
    xgb_weighted_pred = np.argmax(xgb_weighted_proba, axis=1)

    # Ensemble (50/50 GRU + XGBoost unweighted)
    ensemble_proba = 0.5 * gru_proba + 0.5 * xgb_proba
    ensemble_pred = np.argmax(ensemble_proba, axis=1)

    # Ensemble with weighted XGBoost (50/50 GRU + XGBoost weighted)
    ensemble_wt_proba = 0.5 * gru_proba + 0.5 * xgb_weighted_proba
    ensemble_wt_pred = np.argmax(ensemble_wt_proba, axis=1)

    # Naive majority-class baseline on test set
    # Majority class in training set:
    train_counts = pd.Series(y_train_gru).value_counts()
    majority_class = train_counts.index[0] # sideways = 2
    naive_pred = np.full_like(y_test_gru, majority_class)

    y_true = y_test_gru

    # Calculate metrics function
    def get_metrics_dict(y_t, y_p, name):
        acc = float(accuracy_score(y_t, y_p))
        bal_acc = float(balanced_accuracy_score(y_t, y_p))
        macro_f1 = float(f1_score(y_t, y_p, labels=labels_sorted, average="macro", zero_division=0))
        weighted_f1 = float(f1_score(y_t, y_p, labels=labels_sorted, average="weighted", zero_division=0))
        cm = confusion_matrix(y_t, y_p, labels=labels_sorted).tolist()
        
        rep_dict = classification_report(
            y_t, y_p, labels=labels_sorted, target_names=target_names, output_dict=True, zero_division=0
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

    m_naive = get_metrics_dict(y_true, naive_pred, "Naive Majority-Class")
    m_gru = get_metrics_dict(y_true, gru_pred, "GRU Baseline")
    m_xgb = get_metrics_dict(y_true, xgb_pred, "XGBoost Baseline (Unweighted)")
    m_xgb_wt = get_metrics_dict(y_true, xgb_weighted_pred, "XGBoost Baseline (Weighted)")
    m_ens = get_metrics_dict(y_true, ensemble_pred, "Ensemble (GRU + XGB Unweighted)")
    m_ens_wt = get_metrics_dict(y_true, ensemble_wt_pred, "Ensemble (GRU + XGB Weighted)")

    all_models = [m_naive, m_gru, m_xgb, m_xgb_wt, m_ens, m_ens_wt]

    # Compute improvements over naive
    for m in all_models[1:]:
        m["diff_vs_naive"] = {
            "accuracy": round(m["accuracy"] - m_naive["accuracy"], 4),
            "macro_f1": round(m["macro_f1"] - m_naive["macro_f1"], 4),
            "weighted_f1": round(m["weighted_f1"] - m_naive["weighted_f1"], 4),
            "balanced_accuracy": round(m["balanced_accuracy"] - m_naive["balanced_accuracy"], 4),
        }

    # Split info
    split_info = {
        "train": {
            "start_date": str(gru_splits["train"]["meta"]["date"].min().date()),
            "end_date": str(gru_splits["train"]["meta"]["date"].max().date()),
            "samples": len(y_train_gru),
            "class_distribution": {label_names[k]: int(v) for k, v in pd.Series(y_train_gru).value_counts().to_dict().items()},
            "class_distribution_pct": {label_names[k]: round(float(v) / len(y_train_gru) * 100, 2) for k, v in pd.Series(y_train_gru).value_counts().to_dict().items()},
        },
        "val": {
            "start_date": str(gru_splits["val"]["meta"]["date"].min().date()),
            "end_date": str(gru_splits["val"]["meta"]["date"].max().date()),
            "samples": len(y_val_gru),
            "class_distribution": {label_names[k]: int(v) for k, v in pd.Series(y_val_gru).value_counts().to_dict().items()},
            "class_distribution_pct": {label_names[k]: round(float(v) / len(y_val_gru) * 100, 2) for k, v in pd.Series(y_val_gru).value_counts().to_dict().items()},
        },
        "test": {
            "start_date": str(meta_test_gru["date"].min().date()),
            "end_date": str(meta_test_gru["date"].max().date()),
            "samples": len(y_test_gru),
            "class_distribution": {label_names[k]: int(v) for k, v in pd.Series(y_test_gru).value_counts().to_dict().items()},
            "class_distribution_pct": {label_names[k]: round(float(v) / len(y_test_gru) * 100, 2) for k, v in pd.Series(y_test_gru).value_counts().to_dict().items()},
        },
    }

    full_output = {
        "split_info": split_info,
        "gru_features": {
            "version": GRU_FEATURE_VERSION,
            "count": len(GRU_FEATURE_LIST),
            "features": GRU_FEATURE_LIST,
        },
        "models": {
            "naive": m_naive,
            "gru": m_gru,
            "xgboost": m_xgb,
            "xgboost_weighted": m_xgb_wt,
            "ensemble": m_ens,
            "ensemble_weighted": m_ens_wt,
        }
    }

    Path("data/reports/clean_baseline_evaluation.json").write_text(
        json.dumps(full_output, indent=2), encoding="utf-8"
    )
    print("Baseline evaluation written to data/reports/clean_baseline_evaluation.json")

    # Print summary table
    print("\n" + "=" * 100)
    print(f"{'Model':<35} {'Accuracy':>10} {'Macro F1':>10} {'Weighted F1':>12} {'Bal Acc':>10} {'Acc Diff':>10} {'F1 Diff':>10}")
    print("-" * 100)
    for m in all_models:
        acc_diff = f"{m.get('diff_vs_naive', {}).get('accuracy', 0.0):>+10.4f}" if "diff_vs_naive" in m else f"{'--':>10}"
        f1_diff = f"{m.get('diff_vs_naive', {}).get('macro_f1', 0.0):>+10.4f}" if "diff_vs_naive" in m else f"{'--':>10}"
        print(f"{m['name']:<35} {m['accuracy']:>10.4f} {m['macro_f1']:>10.4f} {m['weighted_f1']:>12.4f} {m['balanced_accuracy']:>10.4f} {acc_diff} {f1_diff}")
    print("=" * 100)

if __name__ == "__main__":
    run_evaluation()
