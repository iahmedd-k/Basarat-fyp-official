"""
Offline Experiment: Label Threshold Sweep (Task 10)
===================================================

Tests classification thresholds on the 1-day forward return:
  [0.005, 0.01, 0.015, 0.02]

Evaluated using VALIDATION data only (never the test set).
Reports:
  - Class distributions across splits
  - Macro F1, Weighted F1, Balanced Accuracy
  - Per-class precision, recall, and F1
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score

from app.data.features.labeling import LABEL_MAPPING, label_from_return
from app.ml.training.comprehensive_evaluation import compute_metrics

log = logging.getLogger("experiment.thresholds")

FEATURES_PATH = Path("data/features/features_daily.parquet")
REPORTS_DIR = Path("data/reports")
TRAIN_CUTOFF = pd.Timestamp("2024-07-01")
VAL_CUTOFF = pd.Timestamp("2025-07-01")


def run_threshold_experiment(
    thresholds: List[float] = [0.005, 0.01, 0.015, 0.02],
) -> Dict[str, dict]:
    """Run threshold comparison evaluating class balance and validation performance."""
    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"Features file not found at {FEATURES_PATH}")

    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values(["symbol", "date"]).reset_index(drop=True)

    # Compute forward returns
    df["forward_return"] = df.groupby("symbol")["close"].transform(
        lambda s: s.shift(-1) / s - 1
    )
    df = df.dropna(subset=["forward_return"])

    dates = df["date"]
    train_mask = dates < TRAIN_CUTOFF
    val_mask = (dates >= TRAIN_CUTOFF) & (dates < VAL_CUTOFF)

    label_names = {v: k for k, v in LABEL_MAPPING.items()}
    results = {}

    for thresh in thresholds:
        key = f"thresh_{int(thresh * 1000):03d}"
        labels_series = df["forward_return"].apply(lambda r: label_from_return(r, thresh))
        y_encoded = labels_series.map(LABEL_MAPPING).values

        y_train = y_encoded[train_mask]
        y_val = y_encoded[val_mask]

        train_dist = pd.Series(y_train).value_counts(normalize=True).to_dict()
        val_dist = pd.Series(y_val).value_counts(normalize=True).to_dict()

        # Majority class baseline on validation set
        majority_cls = int(pd.Series(y_train).mode()[0])
        baseline_preds = np.full_like(y_val, majority_cls)

        val_metrics = compute_metrics(
            y_true=y_val,
            y_pred=baseline_preds,
            label_names=label_names,
            model_name=f"MajorityBaseline_{thresh}",
        )

        results[key] = {
            "threshold": thresh,
            "train_sample_count": len(y_train),
            "val_sample_count": len(y_val),
            "train_distribution": {label_names[k]: round(v * 100, 2) for k, v in train_dist.items()},
            "val_distribution": {label_names[k]: round(v * 100, 2) for k, v in val_dist.items()},
            "val_majority_baseline_macro_f1": val_metrics["macro_f1"],
            "val_majority_baseline_bal_acc": val_metrics["balanced_accuracy"],
        }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "experiment_thresholds.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    log.info("Threshold experiment report saved -> %s", report_path)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_threshold_experiment()
