"""
Controlled Feature Experiment (Tasks 11 & 12)
==============================================

Evaluates feature sets using the VALIDATION set only:
  Set 1: Baseline GRU features (27 features)
  Set 2: Baseline + Normalized price features (close/SMA20, close/SMA50, EMA12/EMA26, Bollinger position, range/close, volume change)
  Set 3: Baseline + Normalized price features + Market-relative features (index return 5D/20D, stock return 20D, stock-relative return 20D)

Ensures point-in-time calculation with zero future leakage.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from app.data.features.gru_feature_list import GRU_FEATURE_LIST
from app.data.features.sequence_builder import build_sequences
from app.ml.training.comprehensive_evaluation import compute_metrics
from app.ml.training.data_split import time_split
from app.ml.training.model import build_model
from app.ml.training.reproducibility import set_seed
from app.ml.training.scaling import apply_scaler, fit_scaler
from app.ml.training.train import train_model

log = logging.getLogger("experiment.features")

FEATURES_PATH = Path("data/features/features_daily.parquet")
REPORTS_DIR = Path("data/reports")


# Feature set definitions
NORMALIZED_PRICE_FEATURES = [
    "close_to_sma20_ratio",
    "close_to_sma50_ratio",
    "ema_cross_ratio",
    "bollinger_pos",
    "daily_range_pct",
    "volume_change_1d",
]

MARKET_RELATIVE_FEATURES = [
    "market_return_5d",
    "market_return_20d",
    "stock_return_20d",
    "stock_relative_return_20d",
]


def run_feature_experiment(
    batch_size: int = 32,
    max_epochs: int = 30,
    patience: int = 4,
    seed: int = 42,
) -> Dict[str, dict]:
    """Run controlled feature experiment on the validation set."""
    set_seed(seed)

    if not FEATURES_PATH.exists():
        raise FileNotFoundError(f"Features file not found at {FEATURES_PATH}")

    df = pd.read_parquet(FEATURES_PATH)
    label_mapping = json.loads((Path("data/features/label_mapping.json")).read_text(encoding="utf-8"))
    label_names = {v: k for k, v in label_mapping.items()}

    feature_sets = {
        "baseline_v1": GRU_FEATURE_LIST.copy(),
        "baseline_plus_normalized": GRU_FEATURE_LIST + [f for f in NORMALIZED_PRICE_FEATURES if f in df.columns],
        "baseline_plus_norm_and_market": GRU_FEATURE_LIST + [f for f in NORMALIZED_PRICE_FEATURES + MARKET_RELATIVE_FEATURES if f in df.columns],
    }

    results = {}

    for set_name, feature_cols in feature_sets.items():
        log.info("\n=== Evaluating Feature Set: %s (%d features) ===", set_name, len(feature_cols))
        set_seed(seed)

        X, y, meta = build_sequences(df, feature_cols, label_mapping, window_size=30)
        splits = time_split(X, y, meta)

        X_train, y_train = splits["train"]["X"], splits["train"]["y"]
        X_val, y_val = splits["val"]["X"], splits["val"]["y"]

        scaler = fit_scaler(X_train)
        X_train_scaled = apply_scaler(X_train, scaler)
        X_val_scaled = apply_scaler(X_val, scaler)

        input_shape = (X_train_scaled.shape[1], X_train_scaled.shape[2])
        model = build_model(input_shape, n_classes=len(label_mapping))

        model_path = Path(f"models/experiments/gru_{set_name}.keras")
        train_model(
            model, X_train_scaled, y_train, X_val_scaled, y_val,
            batch_size=batch_size, max_epochs=max_epochs, patience=patience,
            model_save_path=model_path,
            metadata_path=Path(f"models/experiments/metadata_{set_name}.json"),
        )

        val_probs = model.predict(X_val_scaled, verbose=0)
        val_preds = np.argmax(val_probs, axis=1)

        metrics = compute_metrics(y_val, val_preds, label_names, model_name=f"GRU_{set_name}")
        results[set_name] = {
            "n_features": len(feature_cols),
            "feature_columns": feature_cols,
            "accuracy": metrics["accuracy"],
            "balanced_accuracy": metrics["balanced_accuracy"],
            "macro_f1": metrics["macro_f1"],
            "weighted_f1": metrics["weighted_f1"],
            "per_class": metrics["per_class"],
        }

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    report_path = REPORTS_DIR / "experiment_features.json"
    report_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    log.info("Feature experiment report saved -> %s", report_path)

    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_feature_experiment()
