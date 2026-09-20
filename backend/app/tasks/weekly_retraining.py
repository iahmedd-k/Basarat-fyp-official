"""Weekly Retraining — Celery task for periodic model retraining.

Implements the weekly retraining workflow:
  1. Check if enough new labeled data exists
  2. Rebuild features and sequences from latest data
  3. Train GRU candidate
  4. Train XGBoost candidate
  5. Evaluate candidates on held-out test set
  6. Compare candidates vs production models
  7. Promote if criteria are met

Production models are NEVER automatically overwritten. Candidates are
trained to separate directories and only promoted after validation.
"""

import json
import logging
import time
import uuid
from datetime import datetime
from pathlib import Path

from celery import chord, group
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery

log = logging.getLogger(__name__)


def _get_sync_session():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import get_settings
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


def _generate_version(model_type: str) -> str:
    """Generate a version string like gru_v2, xgb_v2."""
    session = _get_sync_session()
    from sqlalchemy import text
    result = session.execute(
        text("SELECT model_version FROM model_registry WHERE model_type = :type ORDER BY created_at DESC LIMIT 1"),
        {"type": model_type},
    ).fetchone()
    session.close()

    if not result:
        return f"{model_type}_v1" if model_type in ("gru", "xgboost") else f"{model_type}_v1"

    current = result[0]
    # Extract version number and increment
    parts = current.rsplit("_v", 1)
    if len(parts) == 2:
        try:
            num = int(parts[1]) + 1
            return f"{parts[0]}_v{num}"
        except ValueError:
            pass
    return f"{current}_candidate"


# ---------------------------------------------------------------------------
# Task 1: Check Training Data
# ---------------------------------------------------------------------------

@celery.task(name="app.tasks.weekly_retraining.check_training_data")
def check_training_data_task():
    """Check if enough new labeled data exists for retraining.

    Compares the count of resolved predictions since the last training
    against the configured minimum threshold.
    """
    log.info("[RETRAIN] Checking training data availability")

    from sqlalchemy import text as sql_text

    session = _get_sync_session()

    # Count resolved predictions (actual_direction is known)
    result = session.execute(
        sql_text(
            """SELECT COUNT(*), MIN(predicted_at), MAX(predicted_at)
            FROM predictions
            WHERE actual_direction IS NOT NULL"""
        )
    ).fetchone()
    session.close()

    total_resolved = result[0] if result else 0
    first_date = result[1]
    last_date = result[2]

    # Check config
    from app.core.config import get_settings
    settings = get_settings()
    min_samples = settings.TRAINING_MIN_NEW_SAMPLES

    log.info("[RETRAIN] Resolved predictions: %d (range: %s to %s)",
             total_resolved, first_date, last_date)

    if total_resolved < min_samples:
        log.info("[RETRAIN] Insufficient data (%d < %d) — skipping retraining",
                 total_resolved, min_samples)
        return {"status": "skip", "reason": "insufficient_data",
                "resolved_count": total_resolved, "min_required": min_samples}

    return {"status": "proceed", "resolved_count": total_resolved}


# ---------------------------------------------------------------------------
# Task 2: Rebuild Features
# ---------------------------------------------------------------------------

@celery.task(name="app.tasks.weekly_retraining.rebuild_features")
def rebuild_features_task():
    """Rebuild features and sequences from the latest OHLCV data."""
    log.info("[RETRAIN] Rebuilding features and sequences")

    from app.data.features.run_features import run_features

    run_features()
    log.info("[RETRAIN] Features rebuilt successfully")
    return {"status": "success"}


# ---------------------------------------------------------------------------
# Task 3: Train GRU Candidate
# ---------------------------------------------------------------------------

@celery.task(
    name="app.tasks.weekly_retraining.train_gru_candidate",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def train_gru_candidate_task(self):
    """Train a GRU candidate model and save to a candidate directory.

    Does NOT overwrite the production model. Saves to models/gru_candidate/.
    """
    log.info("[RETRAIN] Training GRU candidate")

    try:
        import numpy as np
        import pandas as pd
        import tensorflow as tf

        from app.core.config import get_settings
        from app.ml.training.data_split import time_split
        from app.ml.training.evaluate import evaluate
        from app.ml.training.model import build_model
        from app.ml.training.scaling import apply_scaler, fit_scaler, save_scaler
        from app.ml.training.train import train_model

        settings = get_settings()

        SEQUENCES_DIR = Path("data/sequences")
        FEATURES_DIR = Path("data/features")
        MODEL_DIR = Path("models/gru_candidate")
        REPORTS_DIR = Path("data/reports")

        # Load data
        data = np.load(SEQUENCES_DIR / "sequences.npz")
        X, y = data["X"], data["y"]
        meta = pd.read_parquet(SEQUENCES_DIR / "sequences_meta.parquet")
        feature_columns = json.loads((FEATURES_DIR / "feature_columns.json").read_text(encoding="utf-8"))
        label_mapping = json.loads((FEATURES_DIR / "label_mapping.json").read_text(encoding="utf-8"))

        log.info("[RETRAIN] GRU: Loaded X=%s, y=%s", X.shape, y.shape)

        # Split
        splits = time_split(X, y, meta)
        X_train, y_train = splits["train"]["X"], splits["train"]["y"]
        X_val, y_val = splits["val"]["X"], splits["val"]["y"]
        X_test, y_test = splits["test"]["X"], splits["test"]["y"]

        # Scale
        scaler = fit_scaler(X_train)
        X_train = apply_scaler(X_train, scaler)
        X_val = apply_scaler(X_val, scaler)
        X_test = apply_scaler(X_test, scaler)
        save_scaler(scaler, path=MODEL_DIR / "scaler.pkl")

        # Build and train
        input_shape = (X_train.shape[1], X_train.shape[2])
        model = build_model(input_shape, n_classes=len(label_mapping))

        model_path = MODEL_DIR / "model.keras"
        train_result = train_model(
            model, X_train, y_train, X_val, y_val,
            batch_size=32,
            max_epochs=50,
            model_save_path=model_path,
        )

        # Save metadata
        meta_path = MODEL_DIR / "metadata.json"
        saved_meta = json.loads(meta_path.read_text(encoding="utf-8"))
        saved_meta["version"] = MODEL_DIR.name
        saved_meta["feature_columns"] = feature_columns
        saved_meta["label_mapping"] = label_mapping
        saved_meta["train_samples"] = len(X_train)
        saved_meta["val_samples"] = len(X_val)
        saved_meta["test_samples"] = len(X_test)
        meta_path.write_text(json.dumps(saved_meta, indent=2), encoding="utf-8")

        # Evaluate
        eval_report = evaluate(model, X_test, y_test, y_train,
                               report_path=REPORTS_DIR / "evaluation_gru_candidate.json")

        log.info("[RETRAIN] GRU candidate: accuracy=%.4f, macro_f1=%.4f",
                 eval_report["test_accuracy"], eval_report.get("macro_f1", 0))

        # Weighted F1 (support-weighted) for backward-compatible promotion logic
        _w_f1 = sum(
            v["f1"] * v["support"]
            for v in eval_report["per_class"].values()
        ) / max(sum(v["support"] for v in eval_report["per_class"].values()), 1)

        return {
            "status": "success",
            "model_version": MODEL_DIR.name,
            "metrics": {
                "test_accuracy": eval_report["test_accuracy"],
                "macro_f1": eval_report.get("macro_f1", 0),
                "balanced_accuracy": eval_report.get("balanced_accuracy", 0),
                "per_class": eval_report["per_class"],
                "confusion_matrix": eval_report["confusion_matrix"],
                "weighted_avg_f1": _w_f1,
            },
            "model_path": str(model_path),
            "scaler_path": str(MODEL_DIR / "scaler.pkl"),
        }

    except SoftTimeLimitExceeded:
        log.error("[RETRAIN] GRU training timed out")
        raise self.retry(countdown=1200)
    except Exception as exc:
        log.exception("[RETRAIN] GRU training failed")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 4: Train XGBoost Candidate
# ---------------------------------------------------------------------------

@celery.task(
    name="app.tasks.weekly_retraining.train_xgb_candidate",
    bind=True,
    max_retries=1,
    default_retry_delay=600,
)
def train_xgb_candidate_task(self):
    """Train an XGBoost candidate model and save to a candidate directory."""
    log.info("[RETRAIN] Training XGBoost candidate")

    try:
        import numpy as np
        import pandas as pd

        from app.ml.training_xgb.feature_prep import build_xgb_features, get_feature_list
        from app.ml.training_xgb.data_split import time_split_xgb
        from app.ml.training_xgb.model import (
            build_xgb_classifier,
            compute_sample_weights,
            save_feature_importances,
            save_model_metadata,
        )
        from app.ml.training_xgb.evaluate_xgb import evaluate_xgb

        FEATURES_DIR = Path("data/features")
        MODEL_DIR = Path("models/xgb_candidate")
        REPORTS_DIR = Path("data/reports")

        # Load label mapping
        label_mapping = json.loads(
            (FEATURES_DIR / "label_mapping.json").read_text(encoding="utf-8")
        )

        # Build features
        df = build_xgb_features()

        # Split
        splits = time_split_xgb(df, label_mapping=label_mapping)
        X_train, y_train = splits["train"]["X"], splits["train"]["y"]
        X_val, y_val = splits["val"]["X"], splits["val"]["y"]
        X_test, y_test = splits["test"]["X"], splits["test"]["y"]
        feature_names = splits["train"]["feature_names"]

        log.info("[RETRAIN] XGB: Train=%d, Val=%d, Test=%d, Features=%d",
                 len(X_train), len(X_val), len(X_test), len(feature_names))

        # Train weighted variant (best performing)
        model = build_xgb_classifier()
        sample_weights = compute_sample_weights(y_train)
        model.fit(
            X=X_train,
            y=y_train,
            sample_weight=sample_weights,
            eval_set=[(X_val, y_val)],
            verbose=50,
        )

        # Save model
        model_path = MODEL_DIR / "xgb_weighted.xgb"
        MODEL_DIR.mkdir(parents=True, exist_ok=True)
        save_model_metadata(
            model=model,
            model_path=model_path,
            feature_names=feature_names,
            label_mapping=label_mapping,
            split_info={
                "train_samples": len(X_train),
                "val_samples": len(X_val),
                "test_samples": len(X_test),
            },
            variant="weighted",
        )
        save_feature_importances(model, feature_names, REPORTS_DIR / "xgb_feature_importance_candidate.json")

        # Evaluate
        eval_report = evaluate_xgb(
            model=model,
            X_test=X_test,
            y_test=y_test,
            y_train=y_train,
            label_mapping=label_mapping,
            report_path=REPORTS_DIR / "evaluation_xgb_candidate.json",
            variant="weighted",
        )

        log.info("[RETRAIN] XGB candidate: accuracy=%.4f, macro_f1=%.4f",
                 eval_report["test_accuracy"], eval_report.get("macro_f1", 0))

        # Weighted F1 (support-weighted) for backward-compatible promotion logic
        _w_f1 = sum(
            v["f1"] * v["support"]
            for v in eval_report["per_class"].values()
        ) / max(sum(v["support"] for v in eval_report["per_class"].values()), 1)

        return {
            "status": "success",
            "model_version": MODEL_DIR.name,
            "metrics": {
                "test_accuracy": eval_report["test_accuracy"],
                "macro_f1": eval_report.get("macro_f1", 0),
                "balanced_accuracy": eval_report.get("balanced_accuracy", 0),
                "per_class": eval_report["per_class"],
                "confusion_matrix": eval_report["confusion_matrix"],
                "weighted_avg_f1": _w_f1,
            },
            "model_path": str(model_path),
        }

    except SoftTimeLimitExceeded:
        log.error("[RETRAIN] XGB training timed out")
        raise self.retry(countdown=1200)
    except Exception as exc:
        log.exception("[RETRAIN] XGB training failed")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 5: Compare and Promote
# ---------------------------------------------------------------------------

@celery.task(name="app.tasks.weekly_retraining.compare_and_promote")
def compare_and_promote_task(gru_result: dict, xgb_result: dict):
    """Compare GRU and XGB candidates against production, promote if better.

    This task runs after both training tasks complete (via chord callback).
    """
    log.info("[RETRAIN] Comparing candidates vs production")

    from app.core.config import get_settings
    from app.ml.serving.model_registry import (
        get_production_model,
        promote_model,
        reject_model,
        register_model,
    )
    from app.ml.serving.promotion import compare_models

    settings = get_settings()
    session = _get_sync_session()
    run_id = str(uuid.uuid4())[:8]

    config = {
        "MIN_ACCURACY_IMPROVEMENT": settings.MIN_ACCURACY_IMPROVEMENT,
        "MIN_F1_IMPROVEMENT": settings.MIN_F1_IMPROVEMENT,
        "MAX_ABSTENTION_INCREASE": settings.MAX_ABSTENTION_INCREASE,
    }

    results = {"gru": {}, "xgb": {}}

    # --- GRU comparison ---
    if gru_result and gru_result.get("status") == "success":
        prod_gru = get_production_model(session, "gru")
        prod_metrics = prod_gru["metrics"] if prod_gru and prod_gru.get("metrics") else {
            "test_accuracy": 0, "weighted_avg_f1": 0, "abstention_rate": 0,
        }

        gru_comparison = compare_models(prod_metrics, gru_result["metrics"], config)

        # Register the candidate
        gru_version = gru_result["model_version"]
        register_model(
            session,
            model_version=gru_version,
            model_type="gru",
            status="candidate",
            training_sample_count=gru_result.get("metrics", {}).get("train_samples", 0),
            metrics=gru_result["metrics"],
            model_path=gru_result.get("model_path"),
            scaler_path=gru_result.get("scaler_path"),
        )

        if gru_comparison["decision"] == "promoted":
            promote_model(session, gru_version)
            log.info("[PROMOTION] GRU candidate %s promoted", gru_version)
        else:
            reject_model(session, gru_version, gru_comparison["reason"])
            log.info("[PROMOTION] GRU candidate %s rejected: %s", gru_version, gru_comparison["reason"])

        results["gru"] = gru_comparison

    # --- XGB comparison ---
    if xgb_result and xgb_result.get("status") == "success":
        prod_xgb = get_production_model(session, "xgboost")
        prod_metrics = prod_xgb["metrics"] if prod_xgb and prod_xgb.get("metrics") else {
            "test_accuracy": 0, "weighted_avg_f1": 0, "abstention_rate": 0,
        }

        xgb_comparison = compare_models(prod_metrics, xgb_result["metrics"], config)

        # Register the candidate
        xgb_version = xgb_result["model_version"]
        register_model(
            session,
            model_version=xgb_version,
            model_type="xgboost",
            status="candidate",
            training_sample_count=xgb_result.get("metrics", {}).get("train_samples", 0),
            metrics=xgb_result["metrics"],
            model_path=xgb_result.get("model_path"),
        )

        if xgb_comparison["decision"] == "promoted":
            promote_model(session, xgb_version)
            log.info("[PROMOTION] XGB candidate %s promoted", xgb_version)
        else:
            reject_model(session, xgb_version, xgb_comparison["reason"])
            log.info("[PROMOTION] XGB candidate %s rejected: %s", xgb_version, xgb_comparison["reason"])

        results["xgb"] = xgb_comparison

    # Save comparison report
    report = {
        "run_id": run_id,
        "timestamp": datetime.utcnow().isoformat(),
        "gru_result": results["gru"],
        "xgb_result": results["xgb"],
    }
    report_path = Path("data/reports/weekly_retraining_report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    session.close()
    log.info("[RETRAIN] Weekly retraining complete — report saved to %s", report_path)
    return report


# ---------------------------------------------------------------------------
# Weekly Pipeline Orchestrator
# ---------------------------------------------------------------------------

@celery.task(name="app.tasks.weekly_retraining.run_weekly_pipeline")
def run_weekly_pipeline():
    """Orchestrate the full weekly retraining workflow.

    1. Check training data availability
    2. Rebuild features
    3. Train GRU + XGB candidates in parallel
    4. Compare and promote
    """
    log.info("[RETRAIN] Starting weekly retraining pipeline")

    # Step 1: Check data
    check_result = check_training_data_task.apply_async().get(timeout=60)
    if check_result.get("status") == "skip":
        log.info("[RETRAIN] Skipping — %s", check_result.get("reason"))
        return check_result

    # Step 2: Rebuild features
    rebuild_features_task.apply_async().get(timeout=600)

    # Step 3: Train both models in parallel, then compare
    callback = compare_and_promote_task.s()
    job = chord(
        [train_gru_candidate_task.s(), train_xgb_candidate_task.s()],
        callback,
    )
    result = job.apply_async()

    log.info("[RETRAIN] Training pipeline dispatched — id=%s", result.id)
    return {"status": "dispatched", "job_id": result.id}
