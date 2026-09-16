"""
XGBoost Training — train both weighted and unweighted variants.

Trains on the training split, uses validation split for early stopping,
and saves both model variants for later comparison.

Both a weighted (inverse-frequency sample weights) and unweighted version
are trained and saved, so we can compare which is better without guessing.
"""

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from app.ml.training_xgb.model import (
    build_xgb_classifier,
    compute_sample_weights,
    save_feature_importances,
    save_model_metadata,
)

log = logging.getLogger("training_xgb.train")

MODEL_DIR = Path("models/xgb_v1")
REPORTS_DIR = Path("data/reports")


def train_xgb_variants(
    splits: dict,
    label_mapping: dict,
    feature_names: list[str],
    model_dir: Path | None = None,
    reports_dir: Path | None = None,
    early_stopping_rounds: int = 20,
) -> dict:
    """Train both unweighted and weighted XGBoost models.

    Parameters
    ----------
    splits : output of time_split_xgb() with keys train, val, test
    label_mapping : {"bullish": 0, "bearish": 1, "sideways": 2}
    feature_names : ordered list of feature column names
    model_dir : where to save models
    reports_dir : where to save reports
    early_stopping_rounds : patience for early stopping

    Returns
    -------
    dict with keys "unweighted" and "weighted", each containing
    {"model", "evals_result", "metadata_path"}.
    """
    model_dir = model_dir or MODEL_DIR
    reports_dir = reports_dir or REPORTS_DIR

    X_train = splits["train"]["X"]
    y_train = splits["train"]["y"]
    X_val = splits["val"]["X"]
    y_val = splits["val"]["y"]

    log.info("Training data: X=%s, y=%s", X_train.shape, y_train.shape)
    log.info("Validation data: X=%s, y=%s", X_val.shape, y_val.shape)

    results = {}

    for variant in ("unweighted", "weighted"):
        log.info("=" * 60)
        log.info("Training XGBoost variant: %s", variant)
        log.info("=" * 60)

        model = build_xgb_classifier()

        fit_params = {
            "X": X_train,
            "y": y_train,
            "eval_set": [(X_val, y_val)],
            "verbose": 50,
        }

        if variant == "weighted":
            sample_weights = compute_sample_weights(y_train)
            fit_params["sample_weight"] = sample_weights

        model.fit(**fit_params)

        # ── Extract training history ─────────────────────────────────────
        evals_result = model.evals_result()
        best_iter = int(model.best_iteration) if hasattr(model, "best_iteration") else -1
        best_score = None
        if "validation_0" in evals_result and "mlogloss" in evals_result["validation_0"]:
            val_losses = evals_result["validation_0"]["mlogloss"]
            best_score = float(val_losses[best_iter]) if best_iter >= 0 else float(min(val_losses))

        log.info("Best iteration: %d, best val mlogloss: %s", best_iter, best_score)

        # ── Save model ───────────────────────────────────────────────────
        model_path = model_dir / f"xgb_v1_{variant}.xgb"
        meta_path = save_model_metadata(
            model=model,
            model_path=model_path,
            feature_names=feature_names,
            label_mapping=label_mapping,
            split_info={
                "train_samples": len(X_train),
                "val_samples": len(X_val),
                "test_samples": len(splits["test"]["X"]),
            },
            variant=variant,
            extra_meta={
                "best_iteration": best_iter,
                "best_val_mlogloss": best_score,
                "early_stopping_rounds": early_stopping_rounds,
            },
        )

        # ── Save feature importances ─────────────────────────────────────
        importance_path = reports_dir / f"xgb_feature_importance_{variant}.json"
        feat_imp = save_feature_importances(model, feature_names, importance_path)

        # ── Log top 10 features ──────────────────────────────────────────
        log.info("Top 10 most important features (%s):", variant)
        for i, (fname, score) in enumerate(list(feat_imp.items())[:10]):
            log.info("  %2d. %-25s %.6f", i + 1, fname, score)

        results[variant] = {
            "model": model,
            "evals_result": evals_result,
            "meta_path": meta_path,
            "importance_path": importance_path,
            "best_iteration": best_iter,
            "best_val_mlogloss": best_score,
        }

    # ── Save training history ────────────────────────────────────────────
    history = {}
    for variant, res in results.items():
        evals = res["evals_result"]
        if "validation_0" in evals:
            history[variant] = {
                "mlogloss": evals["validation_0"]["mlogloss"],
                "best_iteration": res["best_iteration"],
                "best_val_mlogloss": res["best_val_mlogloss"],
            }

    history_path = reports_dir / "training_history_xgb.json"
    history_path.write_text(json.dumps(history, indent=2), encoding="utf-8")
    log.info("Training history saved -> %s", history_path)

    return results
