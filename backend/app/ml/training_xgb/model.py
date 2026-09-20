"""
XGBoost classifier definition for multi-class direction classification.

DESIGN NOTE — NO FEATURE SCALING
==================================
Tree-based models (XGBoost, Random Forest, etc.) are invariant to
monotonic feature transformations. Unlike the GRU pipeline which
requires StandardScaler normalization, XGBoost operates directly on
raw feature values. Split decisions are based on threshold comparisons,
so the scale of features does not affect model performance. This is a
real, correct difference from the GRU pipeline — applying scaling here
would be unnecessary and would reduce interpretability of feature
importances.
"""

import json
import logging
from pathlib import Path

import numpy as np
from xgboost import XGBClassifier

log = logging.getLogger("training_xgb.model")

# ── Default hyperparameters ────────────────────────────────────────────
DEFAULT_PARAMS = {
    "n_estimators": 300,
    "max_depth": 6,
    "learning_rate": 0.05,
    "subsample": 0.8,
    "colsample_bytree": 0.8,
    "objective": "multi:softprob",
    "num_class": 3,
    "eval_metric": "mlogloss",
    "tree_method": "hist",
    "random_state": 42,
    "n_jobs": -1,
}


def build_xgb_classifier(
    params: dict | None = None,
    use_sample_weights: bool = False,
) -> XGBClassifier:
    """Build an XGBClassifier with the specified parameters.

    Parameters
    ----------
    params : override any default hyperparameters
    use_sample_weights : if True, enables use of sample_weight in training

    Returns
    -------
    Unfitted XGBClassifier instance.
    """
    merged = {**DEFAULT_PARAMS}
    if params:
        merged.update(params)

    model = XGBClassifier(**merged)
    log.info(
        "Built XGBClassifier: n_estimators=%d, max_depth=%d, lr=%.4f",
        merged["n_estimators"], merged["max_depth"], merged["learning_rate"],
    )
    return model


def compute_sample_weights(y: np.ndarray) -> np.ndarray:
    """Compute inverse-frequency sample weights for class imbalance.

    Equivalent to sklearn's compute_class_weight('balanced', ...),
    but returns per-sample weights for XGBoost's sample_weight parameter.

    Parameters
    ----------
    y : array of integer class labels

    Returns
    -------
    Array of shape (n_samples,) with per-sample weights.
    """
    classes, counts = np.unique(y, return_counts=True)
    n_samples = len(y)
    n_classes = len(classes)

    weights = {}
    for cls, count in zip(classes, counts):
        weights[cls] = n_samples / (n_classes * count)

    sample_weights = np.array([weights[label] for label in y], dtype=np.float32)

    log.info("Sample weights computed:")
    for cls, w in sorted(weights.items()):
        log.info("  class %d: weight=%.4f", cls, w)

    return sample_weights


def save_model_metadata(
    model: XGBClassifier,
    model_path: Path,
    feature_names: list[str],
    label_mapping: dict,
    split_info: dict,
    variant: str = "unweighted",
    extra_meta: dict | None = None,
) -> Path:
    """Save model + metadata JSON for the trained XGBoost model.

    Parameters
    ----------
    model : fitted XGBClassifier
    model_path : path to save the XGBoost model JSON
    feature_names : ordered list of feature column names
    label_mapping : {"bullish": 0, "bearish": 1, "sideways": 2}
    split_info : dict with train_samples, val_samples, test_samples
    variant : "unweighted" or "weighted"
    extra_meta : additional metadata to include

    Returns
    -------
    Path to the metadata JSON file.
    """
    # Save model — use .xgb extension so it doesn't collide with metadata .json
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model.save_model(str(model_path))
    log.info("Saved model -> %s", model_path)

    # Save metadata — always .json, separate from the model file
    meta = {
        "model_type": "xgboost",
        "variant": variant,
        "n_estimators": model.n_estimators,
        "max_depth": model.max_depth,
        "learning_rate": float(model.learning_rate),
        "subsample": float(model.subsample),
        "colsample_bytree": float(model.colsample_bytree),
        "objective": "multi:softprob",
        "num_class": 3,
        "feature_names": feature_names,
        "n_features": len(feature_names),
        "label_mapping": label_mapping,
        "train_samples": split_info.get("train_samples", 0),
        "val_samples": split_info.get("val_samples", 0),
        "test_samples": split_info.get("test_samples", 0),
        "best_iteration": int(getattr(model, "best_iteration", -1)) if hasattr(model, "best_iteration") else -1,
    }
    if extra_meta:
        meta.update(extra_meta)

    meta_path = model_path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    log.info("Saved metadata -> %s", meta_path)

    return meta_path


def save_feature_importances(
    model: XGBClassifier,
    feature_names: list[str],
    output_path: Path,
) -> dict:
    """Save feature importances sorted descending.

    Parameters
    ----------
    model : fitted XGBClassifier
    feature_names : ordered list of feature names (must match model's features)
    output_path : where to save the JSON

    Returns
    -------
    dict mapping feature_name -> importance_score (sorted descending).
    """
    importances = model.feature_importances_
    feat_imp = dict(zip(feature_names, importances.tolist()))
    feat_imp_sorted = dict(sorted(feat_imp.items(), key=lambda x: x[1], reverse=True))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(feat_imp_sorted, indent=2), encoding="utf-8")
    log.info("Saved feature importances -> %s", output_path)

    return feat_imp_sorted
