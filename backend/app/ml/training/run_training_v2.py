"""
GRU Training Pipeline v2 — Class-Weighted
==========================================

Identical to run_training.py except:
  - Computes class_weight='balanced' from training-set distribution
  - Saves model as gru_v2.keras (does not overwrite v1)
  - Writes separate metadata_v2.json and _evaluation_report_v2.json

Usage::

    python -m app.ml.training.run_training_v2
"""

import argparse
import json
import logging
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.utils.class_weight import compute_class_weight

log = logging.getLogger("training_v2")

DATA_DIR = Path("data/processed")
MODELS_DIR = Path("models")

SANITY_SYMBOLS = ["OGDC", "LUCK", "ABL"]


def run_training(
    batch_size: int = 32,
    max_epochs: int = 50,
    train_cutoff: str = "2024-07-01",
    val_cutoff: str = "2025-07-01",
) -> None:
    """Full training pipeline with class weighting: split → scale → train → evaluate → sanity check."""
    import tensorflow as tf

    from app.ml.training.data_split import time_split
    from app.ml.training.evaluate import evaluate
    from app.ml.training.model import build_model
    from app.ml.training.scaling import apply_scaler, fit_scaler, save_scaler
    from app.ml.training.train import train_model

    log.info("TensorFlow version: %s", tf.__version__)

    # ── Load data ───────────────────────────────────────────────────────
    log.info("Loading sequences from %s ...", DATA_DIR / "sequences.npz")
    data = np.load(DATA_DIR / "sequences.npz")
    X, y = data["X"], data["y"]
    meta = pd.read_parquet(DATA_DIR / "sequences_meta.parquet")
    feature_columns = json.loads((DATA_DIR / "feature_columns.json").read_text(encoding="utf-8"))
    label_mapping = json.loads((DATA_DIR / "label_mapping.json").read_text(encoding="utf-8"))

    log.info("Loaded X=%s  y=%s  meta=%d rows", X.shape, y.shape, len(meta))

    # ── Split ───────────────────────────────────────────────────────────
    log.info("Step 1: Time-based split ...")
    splits = time_split(
        X, y, meta,
        train_cutoff=pd.Timestamp(train_cutoff),
        val_cutoff=pd.Timestamp(val_cutoff),
    )

    X_train, y_train = splits["train"]["X"], splits["train"]["y"]
    X_val, y_val = splits["val"]["X"], splits["val"]["y"]
    X_test, y_test = splits["test"]["X"], splits["test"]["y"]

    # ── Scale ───────────────────────────────────────────────────────────
    log.info("Step 2: Feature scaling ...")
    scaler = fit_scaler(X_train)
    X_train = apply_scaler(X_train, scaler)
    X_val = apply_scaler(X_val, scaler)
    X_test = apply_scaler(X_test, scaler)
    save_scaler(scaler)

    # ── Compute class weights ───────────────────────────────────────────
    log.info("Step 3: Computing class weights (balanced) ...")
    classes = np.array(sorted(label_mapping.values()))
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight = dict(zip(classes.astype(int), weights.tolist()))
    log.info("Class weights: %s", {k: round(v, 4) for k, v in class_weight.items()})
    reverse_labels = {v: k for k, v in label_mapping.items()}
    for cls_id, w in class_weight.items():
        log.info("  class %d (%s): weight=%.4f", cls_id, reverse_labels.get(cls_id, "?"), w)

    # ── Build model ─────────────────────────────────────────────────────
    log.info("Step 4: Building model ...")
    input_shape = (X_train.shape[1], X_train.shape[2])
    model = build_model(input_shape, n_classes=len(label_mapping))

    # ── Train ───────────────────────────────────────────────────────────
    log.info("Step 5: Training (with class weights) ...")
    model_path = MODELS_DIR / "gru_v2.keras"
    history_path = DATA_DIR / "_training_history_v2.json"
    metadata_path = MODELS_DIR / "metadata_v2.json"
    train_result = train_model(
        model, X_train, y_train, X_val, y_val,
        batch_size=batch_size,
        max_epochs=max_epochs,
        model_save_path=model_path,
        history_path=history_path,
        class_weight=class_weight,
        metadata_path=metadata_path,
    )

    # Update metadata with split info and feature columns
    saved_meta = json.loads(metadata_path.read_text(encoding="utf-8"))
    saved_meta["train_cutoff"] = train_cutoff
    saved_meta["val_cutoff"] = val_cutoff
    saved_meta["window_size"] = int(X_train.shape[1])
    saved_meta["n_features"] = int(X_train.shape[2])
    saved_meta["feature_columns"] = feature_columns
    saved_meta["label_mapping"] = label_mapping
    saved_meta["train_samples"] = len(X_train)
    saved_meta["val_samples"] = len(X_val)
    saved_meta["test_samples"] = len(X_test)
    saved_meta["class_weight"] = {str(k): round(v, 4) for k, v in class_weight.items()}
    metadata_path.write_text(json.dumps(saved_meta, indent=2), encoding="utf-8")

    # ── Evaluate ────────────────────────────────────────────────────────
    log.info("Step 6: Evaluating on test set ...")
    v2_report_path = DATA_DIR / "_evaluation_report_v2.json"
    evaluate(model, X_test, y_test, y_train, report_path=v2_report_path)

    # ── Sanity check ────────────────────────────────────────────────────
    log.info("Step 7: Sanity check — manual predictions ...")
    from app.ml.training.run_training import _sanity_check
    _sanity_check(model, scaler, feature_columns, label_mapping)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_training_v2",
        description="GRU training pipeline v2 — class-weighted for balanced recall.",
    )
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-epochs", type=int, default=50)
    parser.add_argument("--train-cutoff", type=str, default="2024-07-01")
    parser.add_argument("--val-cutoff", type=str, default="2025-07-01")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    run_training(
        batch_size=args.batch_size,
        max_epochs=args.max_epochs,
        train_cutoff=args.train_cutoff,
        val_cutoff=args.val_cutoff,
    )


if __name__ == "__main__":
    main()
