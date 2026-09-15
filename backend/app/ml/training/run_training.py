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

log = logging.getLogger("training")

DATA_DIR = Path("data/processed")
MODELS_DIR = Path("models")

# Sample symbols for sanity-check inference
SANITY_SYMBOLS = ["OGDC", "LUCK", "ABL"]


def run_training(
    batch_size: int = 32,
    max_epochs: int = 50,
    train_cutoff: str = "2024-07-01",
    val_cutoff: str = "2025-07-01",
) -> None:
    """Full training pipeline: split → scale → train → evaluate → sanity check."""
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

    # ── Scale ───────────────────────────────────────────────────────────
    log.info("Step 2: Feature scaling ...")
    scaler = fit_scaler(X_train)
    X_train = apply_scaler(X_train, scaler)
    X_val = apply_scaler(X_val, scaler)
    X_test = apply_scaler(X_test, scaler)
    save_scaler(scaler)

    # ── Build model ─────────────────────────────────────────────────────
    log.info("Step 3: Building model ...")
    input_shape = (X_train.shape[1], X_train.shape[2])
    model = build_model(input_shape, n_classes=len(label_mapping))

    # ── Train ───────────────────────────────────────────────────────────
    log.info("Step 4: Training ...")
    model_path = MODELS_DIR / "gru_v1.keras"
    train_result = train_model(
        model, X_train, y_train, X_val, y_val,
        batch_size=batch_size,
        max_epochs=max_epochs,
        model_save_path=model_path,
    )

    # Update metadata with split info and feature columns
    meta_path = model_path.parent / "metadata.json"
    saved_meta = json.loads(meta_path.read_text(encoding="utf-8"))
    saved_meta["train_cutoff"] = train_cutoff
    saved_meta["val_cutoff"] = val_cutoff
    saved_meta["window_size"] = int(X_train.shape[1])
    saved_meta["n_features"] = int(X_train.shape[2])
    saved_meta["feature_columns"] = feature_columns
    saved_meta["label_mapping"] = label_mapping
    saved_meta["train_samples"] = len(X_train)
    saved_meta["val_samples"] = len(X_val)
    saved_meta["test_samples"] = len(X_test)
    meta_path.write_text(json.dumps(saved_meta, indent=2), encoding="utf-8")

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
    macro_path = DATA_DIR / "features_daily.parquet"
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
        confidence = float(proba[pred_class])

        last_date = sym_df["date"].iloc[-1].strftime("%Y-%m-%d")

        print(f"\n  {sym} (as of {last_date}):")
        print(f"    Prediction:  {reverse_labels[pred_class].upper()}")
        print(f"    Confidence:  {confidence:.1%}")
        print(f"    Probabilities:")
        for cls_id in sorted(label_mapping.values()):
            cls_name = reverse_labels[cls_id]
            bar_len = int(proba[cls_id] * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)
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
