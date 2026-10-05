"""
Train and Evaluate Institutional Multi-Horizon XGBoost Models (5D, 10D, 20D).
=============================================================================
Computes:
  - Directional accuracy across full test set
  - Actionable accuracy at confidence rejection thresholds (tau = 0.50 to 0.60)
  - Long/Short alpha spread and Spearman Rank IC
  - Production model artifacts saved to models/production/v3/
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.metrics import accuracy_score, classification_report, f1_score, roc_auc_score
import xgboost as xgb

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("train_all_horizons")

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
DATA_PATH = ROOT_DIR / "data" / "processed_v3" / "features_v3.parquet"
OUTPUT_DIR = ROOT_DIR / "models" / "production" / "v3"


def get_v3_feature_columns(df: pd.DataFrame) -> list:
    """Return all cross-sectional rank feature columns."""
    cs_features = [c for c in df.columns if c.endswith("_csrank")]
    return sorted(cs_features)


def build_xgb_classifier(
    n_estimators: int = 1500,
    learning_rate: float = 0.02,
    max_depth: int = 4,
    min_child_weight: int = 100,
    subsample: float = 0.8,
    colsample_bytree: float = 0.6,
    reg_lambda: float = 10.0,
    reg_alpha: float = 1.0,
    random_state: int = 42,
) -> xgb.XGBClassifier:
    return xgb.XGBClassifier(
        n_estimators=n_estimators,
        learning_rate=learning_rate,
        max_depth=max_depth,
        min_child_weight=min_child_weight,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        reg_lambda=reg_lambda,
        reg_alpha=reg_alpha,
        eval_metric="logloss",
        early_stopping_rounds=40,
        random_state=random_state,
        tree_method="hist",
        n_jobs=-1,
    )


def compute_rejection_metrics(y_true: np.ndarray, y_prob_buy: np.ndarray, excess_returns: np.ndarray | None = None) -> Dict[str, Any]:
    """Compute actionable accuracy and coverage across confidence thresholds."""
    thresholds = [0.50, 0.52, 0.54, 0.55, 0.56, 0.58, 0.60]
    results = {}

    total_samples = len(y_true)
    for tau in thresholds:
        buy_mask = y_prob_buy >= tau
        avoid_mask = y_prob_buy <= (1.0 - tau)
        action_mask = buy_mask | avoid_mask
        signals_count = int(np.sum(action_mask))

        if signals_count == 0:
            results[f"threshold_{tau:.2f}"] = {
                "threshold": tau,
                "actionable_accuracy": 0.0,
                "coverage_pct": 0.0,
                "signals_generated_count": 0,
                "no_signal_count": total_samples,
            }
            continue

        pred_action = np.where(buy_mask[action_mask], 0, 1)
        true_action = y_true[action_mask]
        acc = float(accuracy_score(true_action, pred_action))

        # Alpha spread
        long_alpha = 0.0
        short_alpha = 0.0
        if excess_returns is not None:
            if np.sum(buy_mask) > 0:
                long_alpha = float(np.mean(excess_returns[buy_mask]))
            if np.sum(avoid_mask) > 0:
                short_alpha = float(np.mean(excess_returns[avoid_mask]))

        results[f"threshold_{tau:.2f}"] = {
            "threshold": tau,
            "actionable_accuracy": round(acc, 4),
            "actionable_accuracy_pct": f"{acc * 100:.2f}%",
            "coverage_pct": round(signals_count / total_samples * 100, 2),
            "signals_generated_count": signals_count,
            "no_signal_count": total_samples - signals_count,
            "mean_buy_excess_return": round(long_alpha, 5),
            "long_short_alpha_spread": round(long_alpha - short_alpha, 5),
        }
    return results


def train_horizon(
    horizon: str,
    target_col: str,
    extreme_mask_col: str,
    excess_ret_col: str,
    df: pd.DataFrame,
    feature_cols: list,
    val_split_date: str = "2024-07-01",
    test_split_date: str = "2025-07-01",
) -> Dict[str, Any]:
    log.info("=" * 70)
    log.info(" TRAINING %s HORIZON MODEL (Target: %s)", horizon, target_col)
    log.info("=" * 70)

    # Filter extreme signals
    train_mask = (df["date"] < val_split_date) & (df[extreme_mask_col] == True)
    val_mask = (df["date"] >= val_split_date) & (df["date"] < test_split_date) & (df[extreme_mask_col] == True)
    test_mask = (df["date"] >= test_split_date) & (df[extreme_mask_col] == True)

    X_train = df.loc[train_mask, feature_cols].fillna(0.5).astype(np.float32)
    y_train = df.loc[train_mask, target_col].astype(int)

    X_val = df.loc[val_mask, feature_cols].fillna(0.5).astype(np.float32)
    y_val = df.loc[val_mask, target_col].astype(int)

    X_test = df.loc[test_mask, feature_cols].fillna(0.5).astype(np.float32)
    y_test = df.loc[test_mask, target_col].astype(int)
    test_excess = df.loc[test_mask, excess_ret_col].values

    log.info("Samples: Train=%d | Val=%d | Sealed Test=%d", len(X_train), len(X_val), len(X_test))

    clf = build_xgb_classifier()
    clf.fit(
        X_train,
        y_train,
        eval_set=[(X_train, y_train), (X_val, y_val)],
        verbose=100,
    )

    # Predict probabilities (prob of class 0 = Buy/Outperform)
    test_prob_buy = clf.predict_proba(X_test)[:, 0]
    test_preds = np.where(test_prob_buy >= 0.50, 0, 1)

    test_acc = accuracy_score(y_test, test_preds)
    test_f1 = f1_score(y_test, test_preds, average="macro")
    test_auc = roc_auc_score((y_test == 0).astype(int), test_prob_buy)

    rejection_metrics = compute_rejection_metrics(y_test.values, test_prob_buy, test_excess)

    # Spearman rank IC
    ic, _ = spearmanr(test_prob_buy, test_excess)

    log.info("--- %s SEALED TEST RESULTS ---", horizon)
    log.info("Baseline Accuracy (tau=0.50): %.2f%%", test_acc * 100)
    log.info("Macro F1: %.4f | ROC-AUC: %.4f | Spearman Rank IC: %.4f", test_f1, test_auc, ic)
    for k, v in rejection_metrics.items():
        if "actionable_accuracy_pct" in v:
            log.info("  %s -> Acc: %s (Coverage: %.1f%%, Signals: %d)", k, v["actionable_accuracy_pct"], v["coverage_pct"], v["signals_generated_count"])

    # Feature importances
    importances = pd.Series(clf.feature_importances_, index=feature_cols).sort_values(ascending=False)

    # Save artifacts
    suffix = f"_{horizon.lower()}" if horizon != "5D" else ""
    model_file = f"xgb_model{suffix}.ubj"
    features_file = f"xgb_features{suffix}.json"
    metrics_file = f"xgb_metrics{suffix}.json"

    clf.save_model(str(OUTPUT_DIR / model_file))
    with open(OUTPUT_DIR / features_file, "w") as f:
        json.dump(feature_cols, f, indent=2)

    metrics_payload = {
        "horizon": horizon,
        "model_type": f"XGBoost v3 ({horizon} Cross-Sectional Alpha)",
        "test_samples": len(X_test),
        "baseline_accuracy": float(test_acc),
        "macro_f1": float(test_f1),
        "roc_auc": float(test_auc),
        "spearman_rank_ic": float(ic),
        "rejection_decision_layer": rejection_metrics,
        "best_iteration": int(clf.best_iteration),
        "top_features": importances.head(15).to_dict(),
    }

    with open(OUTPUT_DIR / metrics_file, "w") as f:
        json.dump(metrics_payload, f, indent=2)

    return metrics_payload


def run_all():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    log.info("Loading features dataset from %s", DATA_PATH)
    df = pd.read_parquet(DATA_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)

    feature_cols = get_v3_feature_columns(df)
    log.info("Found %d cross-sectional rank feature columns.", len(feature_cols))

    horizons_config = [
        ("5D", "target_5d_cs_class", "is_extreme_5d", "excess_5d_return"),
        ("10D", "target_10d_cs_class", "is_extreme_10d", "excess_10d_return"),
        ("20D", "target_20d_cs_class", "is_extreme_20d", "excess_20d_return"),
    ]

    all_results = {}
    for hz, target_col, extreme_col, excess_col in horizons_config:
        res = train_horizon(hz, target_col, extreme_col, excess_col, df, feature_cols)
        all_results[hz] = res

    # Write summary manifest
    summary_path = OUTPUT_DIR / "multi_horizon_summary.json"
    with open(summary_path, "w") as f:
        json.dump(all_results, f, indent=2)
    log.info("Saved Multi-Horizon Summary -> %s", summary_path)


if __name__ == "__main__":
    run_all()
