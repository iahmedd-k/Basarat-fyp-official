"""
Controlled ML Experiment: XGBoost Feature Group Ablation
========================================================
Ablation study testing individual feature groups added to the 26-feature baseline:
1. Baseline (26 features)
2. Baseline + Momentum 20/30/60
3. Baseline + Volatility 20/30/60
4. Baseline + Market Context 20/30/60
5. Baseline + Relative Performance 20/30/60

Outputs: data/reports/xgb_feature_ablation.json
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
import xgboost as xgb

from app.data.features.labeling import LABEL_MAPPING
from app.ml.training.reproducibility import set_seed
from app.ml.training_xgb.feature_prep import ALL_XGB_FEATURES
from app.ml.training_xgb.model import build_xgb_classifier, compute_sample_weights

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("xgb_feature_ablation")

TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")
REPORTS_DIR = Path("data/reports")
EXPERIMENT_DIR = Path("models/experiments/xgb_ablation")


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


def prepare_ablation_features() -> Tuple[pd.DataFrame, Dict[str, List[str]]]:
    """Engineer feature groups on top of raw daily features."""
    log.info("Loading features_daily.parquet ...")
    df = pd.read_parquet("data/features/features_daily.parquet")
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # 1. Market-wide aggregations for 20d, 30d, 60d
    df["daily_ret"] = df.groupby("symbol")["close"].pct_change(1)
    market_daily = df.groupby("date")["daily_ret"].mean().reset_index()
    market_daily = market_daily.sort_values("date").reset_index(drop=True)

    m_growth = 1.0 + market_daily["daily_ret"].fillna(0.0)
    market_daily["market_return_20d_eng"] = m_growth.rolling(20, min_periods=20).apply(np.prod, raw=True) - 1.0
    market_daily["market_return_30d"] = m_growth.rolling(30, min_periods=30).apply(np.prod, raw=True) - 1.0
    market_daily["market_return_60d"] = m_growth.rolling(60, min_periods=60).apply(np.prod, raw=True) - 1.0

    market_lookup = market_daily[["date", "market_return_20d_eng", "market_return_30d", "market_return_60d"]]
    df = pd.merge(df, market_lookup, on="date", how="left")
    df = df.drop(columns=["daily_ret"])

    # 2. Per-symbol rolling statistics
    def _engineer_groups(grp: pd.DataFrame) -> pd.DataFrame:
        g = grp.copy()
        close = g["close"]
        daily_ret = close.pct_change(1)

        # Momentum: return_20d, return_30d, return_60d
        g["return_20d_eng"] = close.pct_change(20)
        g["return_30d"] = close.pct_change(30)
        g["return_60d"] = close.pct_change(60)

        # Volatility: volatility_20d, volatility_30d, volatility_60d
        g["volatility_20d"] = daily_ret.rolling(20, min_periods=10).std()
        g["volatility_30d"] = daily_ret.rolling(30, min_periods=15).std()
        g["volatility_60d"] = daily_ret.rolling(60, min_periods=30).std()

        # Relative Performance: stock_relative_return 20d, 30d, 60d
        g["stock_relative_return_20d_eng"] = g["return_20d_eng"] - g["market_return_20d_eng"]
        g["stock_relative_return_30d"] = g["return_30d"] - g["market_return_30d"]
        g["stock_relative_return_60d"] = g["return_60d"] - g["market_return_60d"]

        return g

    log.info("Engineering per-symbol feature groups ...")
    df = df.groupby("symbol", group_keys=False).apply(_engineer_groups)

    # Base feature list (26 features)
    baseline_feats = [c for c in ALL_XGB_FEATURES if c in df.columns]

    # Define the 5 feature sets
    feature_groups = {
        "baseline": {
            "name": "Baseline (26 features)",
            "features": baseline_feats,
        },
        "baseline_plus_momentum": {
            "name": "Baseline + Momentum 20/30/60 (29 features)",
            "features": baseline_feats + ["return_20d_eng", "return_30d", "return_60d"],
        },
        "baseline_plus_volatility": {
            "name": "Baseline + Volatility 20/30/60 (29 features)",
            "features": baseline_feats + ["volatility_20d", "volatility_30d", "volatility_60d"],
        },
        "baseline_plus_market_context": {
            "name": "Baseline + Market Context 20/30/60 (29 features)",
            "features": baseline_feats + ["market_return_20d_eng", "market_return_30d", "market_return_60d"],
        },
        "baseline_plus_relative_performance": {
            "name": "Baseline + Relative Performance 20/30/60 (29 features)",
            "features": baseline_feats + ["stock_relative_return_20d_eng", "stock_relative_return_30d", "stock_relative_return_60d"],
        },
    }

    return df, feature_groups


def main():
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPERIMENT_DIR.mkdir(parents=True, exist_ok=True)

    log.info("=" * 80)
    log.info("  XGBOOST FEATURE GROUP ABLATION EXPERIMENT")
    log.info("=" * 80)

    df, feature_groups = prepare_ablation_features()

    train_mask = df["date"] < TRAIN_CUTOFF
    val_mask = (df["date"] >= TRAIN_CUTOFF) & (df["date"] < VAL_CUTOFF)
    test_mask = df["date"] >= VAL_CUTOFF

    y_train = df.loc[train_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    y_val = df.loc[val_mask, "label"].map(LABEL_MAPPING).values.astype(int)
    y_test = df.loc[test_mask, "label"].map(LABEL_MAPPING).values.astype(int)

    sample_weights_train = compute_sample_weights(y_train)

    val_results = {}
    test_results = {}
    top_features_per_group = {}

    for grp_key, grp_info in feature_groups.items():
        feat_list = grp_info["features"]
        log.info("\n--- Training %s (n=%d) ---", grp_info["name"], len(feat_list))

        # Impute missing with train median strictly on train split
        X_train_raw = df.loc[train_mask, feat_list].values.astype(np.float32)
        train_medians = np.nanmedian(X_train_raw, axis=0)

        X_train = np.copy(X_train_raw)
        X_train[np.where(np.isnan(X_train))] = np.take(train_medians, np.where(np.isnan(X_train))[1])

        X_val = df.loc[val_mask, feat_list].values.astype(np.float32)
        X_val[np.where(np.isnan(X_val))] = np.take(train_medians, np.where(np.isnan(X_val))[1])

        X_test = df.loc[test_mask, feat_list].values.astype(np.float32)
        X_test[np.where(np.isnan(X_test))] = np.take(train_medians, np.where(np.isnan(X_test))[1])

        set_seed(42)
        clf = build_xgb_classifier()
        clf.fit(
            X_train,
            y_train,
            sample_weight=sample_weights_train,
            eval_set=[(X_val, y_val)],
            verbose=False,
        )

        # Validation evaluation
        val_preds = clf.predict(X_val)
        val_eval = get_full_eval_dict(y_val, val_preds, grp_info["name"] + " (Val)")
        val_eval["feature_count"] = len(feat_list)
        val_eval["features"] = feat_list
        val_results[grp_key] = val_eval

        # Test evaluation
        test_preds = clf.predict(X_test)
        test_eval = get_full_eval_dict(y_test, test_preds, grp_info["name"] + " (Test)")
        test_eval["feature_count"] = len(feat_list)
        test_eval["features"] = feat_list
        test_results[grp_key] = test_eval

        # Feature importances
        booster = clf.get_booster()
        score_dict = booster.get_score(importance_type="gain")
        # Map f0, f1... to feature names
        mapped_scores = {}
        for k, v in score_dict.items():
            if k.startswith("f"):
                try:
                    idx = int(k[1:])
                    mapped_scores[feat_list[idx]] = round(float(v), 4)
                except (ValueError, IndexError):
                    mapped_scores[k] = round(float(v), 4)
            else:
                mapped_scores[k] = round(float(v), 4)
        top_5 = sorted(mapped_scores.items(), key=lambda x: x[1], reverse=True)[:5]
        top_features_per_group[grp_key] = dict(top_5)

        log.info(
            "Val: Acc=%.4f | Macro F1=%.4f | Bal Acc=%.4f | Bull R=%.4f | Bear R=%.4f | Side R=%.4f",
            val_eval["accuracy"], val_eval["macro_f1"], val_eval["balanced_accuracy"],
            val_eval["per_class"]["bullish"]["recall"],
            val_eval["per_class"]["bearish"]["recall"],
            val_eval["per_class"]["sideways"]["recall"],
        )
        log.info(
            "Test: Acc=%.4f | Macro F1=%.4f | Bal Acc=%.4f | Bull R=%.4f | Bear R=%.4f | Side R=%.4f",
            test_eval["accuracy"], test_eval["macro_f1"], test_eval["balanced_accuracy"],
            test_eval["per_class"]["bullish"]["recall"],
            test_eval["per_class"]["bearish"]["recall"],
            test_eval["per_class"]["sideways"]["recall"],
        )

    # Find best on validation
    best_val_key = max(val_results.keys(), key=lambda k: (val_results[k]["macro_f1"], val_results[k]["balanced_accuracy"]))

    report = {
        "timestamp": pd.Timestamp.now().isoformat(),
        "ablation_validation_comparison": val_results,
        "ablation_test_comparison": test_results,
        "top_features_per_group": top_features_per_group,
        "selected_group_on_validation": {
            "key": best_val_key,
            "name": feature_groups[best_val_key]["name"],
            "val_metrics": val_results[best_val_key],
            "test_metrics": test_results[best_val_key],
        }
    }

    report_path = REPORTS_DIR / "xgb_feature_ablation.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)
    log.info("\nSaved XGBoost feature ablation report to %s", report_path)


if __name__ == "__main__":
    main()
