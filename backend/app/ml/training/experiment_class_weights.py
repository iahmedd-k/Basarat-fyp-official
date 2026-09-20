"""
Controlled Experiment: GRU Class Weights vs Baseline (Task 6)
============================================================

Compares:
  - Baseline: Standard unweighted cross-entropy
  - Balanced: Inverse-frequency class weights computed strictly from y_train

Evaluated on the VALIDATION split only (never touching the test set).
Reports:
  - Accuracy
  - Macro F1
  - Weighted F1
  - Balanced accuracy
  - Per-class precision, recall, F1
"""

import json
import logging
from pathlib import Path
from typing import Dict

import numpy as np
import pandas as pd
from sklearn.utils.class_weight import compute_class_weight

from app.data.features.gru_feature_list import GRU_FEATURE_LIST
from app.ml.training.comprehensive_evaluation import compute_metrics
from app.ml.training.data_split import time_split
from app.ml.training.model import build_model
from app.ml.training.reproducibility import set_seed
from app.ml.training.scaling import apply_scaler, fit_scaler
from app.ml.training.train import train_model

log = logging.getLogger("experiment.class_weights")

SEQUENCES_DIR = Path("data/sequences")
FEATURES_DIR = Path("data/features")
REPORTS_DIR = Path("data/reports")


def run_class_weight_experiment(
    batch_size: int = 32,
    max_epochs: int = 40,
    patience: int = 5,
    seed: int = 42,
) -> Dict[str, dict]:
    """Run controlled experiment comparing unweighted vs class-weighted GRU on val set."""
    set_seed(seed)

    # 1. Load data
    data = np.load(SEQUENCES_DIR / "sequences.npz")
    X, y = data["X"], data["y"]
    meta = pd.read_parquet(SEQUENCES_DIR / "sequences_meta.parquet")
    label_mapping = json.loads((FEATURES_DIR / "label_mapping.json").read_text(encoding="utf-8"))
    label_names = {v: k for k, v in label_mapping.items()}

    # 2. Split
    splits = time_split(X, y, meta)
    X_train, y_train = splits["train"]["X"], splits["train"]["y"]
    X_val, y_val = splits["val"]["X"], splits["val"]["y"]

    # 3. Scale on train only
    scaler = fit_scaler(X_train)
    X_train = apply_scaler(X_train, scaler)
    X_val = apply_scaler(X_val, scaler)

    input_shape = (X_train.shape[1], X_train.shape[2])

    # Compute balanced class weights strictly from y_train
    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight_dict = {int(c): float(w) for c, w in zip(classes, weights)}
    log.info("Calculated class weights from y_train: %s", class_weight_dict)

    results = {}

    # Variant A: Baseline (unweighted)
    log.info("\n--- Training Variant A: Unweighted Baseline ---")
    set_seed(seed)
    model_unweighted = build_model(input_shape, n_classes=len(label_mapping))
    save_path_unweighted = Path("models/experiments/gru_unweighted.keras")
    train_model(
        model_unweighted, X_train, y_train, X_val, y_val,
        batch_size=batch_size, max_epochs=max_epochs, patience=patience,
        model_save_path=save_path_unweighted,
        metadata_path=Path("models/experiments/metadata_unweighted.json"),
    )
    val_probs_unweighted = model_unweighted.predict(X_val, verbose=0)
    val_preds_unweighted = np.argmax(val_probs_unweighted, axis=1)
    results["unweighted_baseline"] = compute_metrics(y_val, val_preds_unweighted, label_names, model_name="GRU_Unweighted_Val")

    # Variant B: Balanced Class Weights
    log.info("\n--- Training Variant B: Balanced Class Weights ---")
    set_seed(seed)
    model_weighted = build_model(input_shape, n_classes=len(label_mapping))
    save_path_weighted = Path("models/experiments/gru_weighted.keras")
    train_model(
        model_weighted, X_train, y_train, X_val, y_val,
        batch_size=batch_size, max_epochs=max_epochs, patience=patience,
        class_weight=class_weight_dict,
        model_save_path=save_path_weighted,
        metadata_path=Path("models/experiments/metadata_weighted.json"),
    )
    val_probs_weighted = model_weighted.predict(X_val, verbose=0)
    val_preds_weighted = np.argmax(val_probs_weighted, axis=1)
    results["balanced_weighted"] = compute_metrics(y_val, val_preds_weighted, label_names, model_name="GRU_Balanced_Val")

    # Save comparison report
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "experiment_class_weights.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    log.info("Class weight experiment report saved -> %s", report_path)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_class_weight_experiment()
