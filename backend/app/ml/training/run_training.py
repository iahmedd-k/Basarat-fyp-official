"""
GRU Training Pipeline — CLI Entrypoint
=======================================

Usage::

    python -m app.ml.training.run_training
    python -m app.ml.training.run_training --batch-size 64 --max-epochs 30
    python -m app.ml.training.run_training --train-cutoff 2024-06-01 --val-cutoff 2025-06-01
"""

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from app.data.features.gru_feature_list import GRU_FEATURE_VERSION

log = logging.getLogger("training")

SEQUENCES_DIR = Path("data/sequences")
FEATURES_DIR = Path("data/features")
MODEL_DIR = Path("models/gru_v1")

# Sample symbols for sanity-check inference
SANITY_SYMBOLS = ["OGDC", "LUCK", "ABL"]


def run_training(
    batch_size: int = 32,
    max_epochs: int = 50,
    train_cutoff: str = "2024-07-01",
    val_cutoff: str = "2025-07-01",
    seed: int = 42,
) -> None:
    """Full training pipeline: split → scale → train → evaluate → sanity check."""
    import tensorflow as tf

    from app.data.features.gru_feature_list import GRU_FEATURE_VERSION
    from app.ml.training.data_split import time_split
    from app.ml.training.evaluate import evaluate
    from app.ml.training.leakage_checker import check_chronological_split_leakage, check_target_validity
    from app.ml.training.model import build_model
    from app.ml.training.reproducibility import set_seed
    from app.ml.training.scaling import apply_scaler, fit_scaler, save_scaler
    from app.ml.training.train import train_model

    # ── Set deterministic seed (Task 20) ─────────────────────────────────
    seed_info = set_seed(seed)
    log.info("TensorFlow version: %s (seed=%d)", tf.__version__, seed)

    # ── Load data ───────────────────────────────────────────────────────
    log.info("Loading sequences from %s ...", SEQUENCES_DIR / "sequences.npz")
    data = np.load(SEQUENCES_DIR / "sequences.npz")
    X, y = data["X"], data["y"]
    meta = pd.read_parquet(SEQUENCES_DIR / "sequences_meta.parquet")
    feature_columns = json.loads((FEATURES_DIR / "feature_columns.json").read_text(encoding="utf-8"))
    label_mapping = json.loads((FEATURES_DIR / "label_mapping.json").read_text(encoding="utf-8"))

    log.info("Loaded X=%s  y=%s  meta=%d rows", X.shape, y.shape, len(meta))
    log.info("Features (%d): %s", len(feature_columns), feature_columns)
    log.info("Label mapping: %s", label_mapping)

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

    # ── Leakage checks (Task 8 & Task 1) ────────────────────────────────
    log.info("Running automated leakage and target validation checks ...")
    split_summary = check_chronological_split_leakage(
        splits["train"]["meta"], splits["val"]["meta"], splits["test"]["meta"]
    )
    check_target_validity(y_train, y_val, y_test, expected_classes=set(label_mapping.values()))

    # ── Scale ───────────────────────────────────────────────────────────
    log.info("Step 2: Feature scaling (fitted on train split only) ...")
    scaler = fit_scaler(X_train)
    X_train = apply_scaler(X_train, scaler)
    X_val = apply_scaler(X_val, scaler)
    X_test = apply_scaler(X_test, scaler)
    save_scaler(scaler)

    # ── Build model ─────────────────────────────────────────────────────
    log.info("Step 3: Building model ...")
    input_shape = (X_train.shape[1], X_train.shape[2])
    model = build_model(input_shape, n_classes=len(label_mapping))

    # ── Compute balanced class weights strictly from y_train ────────────
    from sklearn.utils.class_weight import compute_class_weight

    classes = np.unique(y_train)
    weights = compute_class_weight("balanced", classes=classes, y=y_train)
    class_weight_dict = {int(c): float(w) for c, w in zip(classes, weights)}
    log.info("Computed balanced class weights from y_train only: %s", class_weight_dict)

    # ── Train ───────────────────────────────────────────────────────────
    log.info("Step 4: Training with balanced class weights ...")
    model_path = MODEL_DIR / "model.keras"
    train_result = train_model(
        model, X_train, y_train, X_val, y_val,
        batch_size=batch_size,
        max_epochs=max_epochs,
        model_save_path=model_path,
        class_weight=class_weight_dict,
    )

    # Update metadata with comprehensive details
    meta_path = model_path.parent / "metadata.json"
    saved_meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    saved_meta["model_version"] = MODEL_DIR.name
    saved_meta["feature_version"] = GRU_FEATURE_VERSION
    saved_meta["feature_columns"] = feature_columns
    saved_meta["n_features"] = int(X_train.shape[2])
    saved_meta["window_size"] = int(X_train.shape[1])
    saved_meta["threshold"] = 0.01
    saved_meta["label_mapping"] = label_mapping
    saved_meta["class_weights"] = class_weight_dict
    saved_meta["train_cutoff"] = train_cutoff
    saved_meta["val_cutoff"] = val_cutoff
    saved_meta["train_date_range"] = split_summary["train"]
    saved_meta["val_date_range"] = split_summary["val"]
    saved_meta["test_date_range"] = split_summary["test"]
    saved_meta["train_samples"] = len(X_train)
    saved_meta["val_samples"] = len(X_val)
    saved_meta["test_samples"] = len(X_test)
    saved_meta["random_seed"] = seed
    saved_meta["batch_size"] = batch_size
    saved_meta["max_epochs"] = max_epochs
    saved_meta["scaler_version"] = "StandardScaler_v1"
    saved_meta["best_epoch"] = train_result.get("best_epoch")
    saved_meta["best_val_loss"] = train_result.get("best_val_loss")
    meta_path.write_text(json.dumps(saved_meta, indent=2), encoding="utf-8")
    log.info("Saved final GRU metadata -> %s", meta_path)

    # ── Evaluate ────────────────────────────────────────────────────────
    log.info("Step 5: Evaluating on test set ...")
    evaluate(model, X_test, y_test, y_train)

    # ── Sanity check: manual predictions ────────────────────────────────
    log.info("Step 6: Sanity check — manual predictions ...")
    _sanity_check(model, scaler, feature_columns, label_mapping)


def _sanity_check(model, scaler, feature_columns, label_mapping):
    """Load latest 30-day windows for sample symbols and print predictions."""
    from app.ml.training.scaling import apply_scaler

    ohlcv_path = Path("data/raw/ohlcv/all_symbols.parquet")
    if not ohlcv_path.exists():
        log.warning("OHLCV file not found, skipping sanity check")
        return

    ohlcv = pd.read_parquet(ohlcv_path)
    ohlcv["date"] = pd.to_datetime(ohlcv["date"])

    # Need macro features for pkr_usd_rate and policy_rate
    macro_path = FEATURES_DIR / "features_daily.parquet"
    if not macro_path.exists():
        log.warning("Features parquet not found, skipping sanity check")
        return

    features_df = pd.read_parquet(macro_path)
    features_df["date"] = pd.to_datetime(features_df["date"])

    reverse_labels = {v: k for k, v in label_mapping.items()}
    window_size = int(model.input_shape[1])

    print("\n" + "=" * 70)
    print("  SANITY CHECK — Latest predictions for sample symbols")
    print("=" * 70)

    for sym in SANITY_SYMBOLS:
        sym_df = features_df[features_df["symbol"] == sym].copy()
        sym_df = sym_df.sort_values("date").reset_index(drop=True)

        if len(sym_df) < window_size:
            print(f"\n  {sym}: not enough data ({len(sym_df)} rows < {window_size})")
            continue

        window = sym_df[feature_columns].values[-window_size:]
        window = window.reshape(1, window_size, -1)
        window = apply_scaler(window, scaler)

        proba = model.predict(window, verbose=0)[0]
        pred_class = int(np.argmax(proba))
        pct_map = {reverse_labels[i]: float(proba[i]) for i in range(len(proba))}
        from app.ml.serving.inference import compute_confidence
        confidence = compute_confidence(pct_map)

        last_date = sym_df["date"].iloc[-1].strftime("%Y-%m-%d")

        print(f"\n  {sym} (as of {last_date}):")
        print(f"    Prediction:  {reverse_labels[pred_class].upper()}")
        print(f"    Confidence:  {confidence:.1%}")
        print(f"    Probabilities:")
        for cls_id in sorted(label_mapping.values()):
            cls_name = reverse_labels[cls_id]
            bar_len = int(proba[cls_id] * 30)
            bar = "#" * bar_len + "-" * (30 - bar_len)
            print(f"      {cls_name:>10s}  {proba[cls_id]:6.1%}  {bar}")

    print("\n" + "=" * 70 + "\n")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_training",
        description="GRU training pipeline for PSX sequence data.",
    )
    parser.add_argument(
        "--batch-size", type=int, default=32,
        help="Training batch size (default: 32)",
    )
    parser.add_argument(
        "--max-epochs", type=int, default=50,
        help="Maximum training epochs (default: 50)",
    )
    parser.add_argument(
        "--train-cutoff", type=str, default="2024-07-01",
        help="Train/val split date (default: 2024-07-01)",
    )
    parser.add_argument(
        "--val-cutoff", type=str, default="2025-07-01",
        help="Val/test split date (default: 2025-07-01)",
    )
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
