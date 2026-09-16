"""Model Monitoring — periodic performance tracking and drift detection.

Monitors model performance over sliding windows (7d, 30d, 60d) and
detects significant degradation. Also tracks feature distributions
for simple data drift detection.
"""

import json
import logging
from datetime import date, datetime, timedelta
from pathlib import Path

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


def _compute_metrics(rows: list) -> dict:
    """Compute classification metrics from a list of (predicted, actual) tuples."""
    if not rows:
        return {"accuracy": 0, "f1": 0, "precision": 0, "recall": 0, "count": 0}

    total = len(rows)
    correct = sum(1 for p, a in rows if p == a)
    accuracy = correct / total if total else 0

    # Per-class metrics
    classes = ["bullish", "bearish", "sideways"]
    per_class = {}
    for cls in classes:
        tp = sum(1 for p, a in rows if p == cls and a == cls)
        fp = sum(1 for p, a in rows if p == cls and a != cls)
        fn = sum(1 for p, a in rows if p != cls and a == cls)
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        per_class[cls] = {"precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4)}

    # Weighted F1
    weighted_f1 = 0
    for cls in classes:
        cls_count = sum(1 for _, a in rows if a == cls)
        weighted_f1 += per_class[cls]["f1"] * cls_count
    weighted_f1 /= total if total else 1

    # Confusion matrix
    cm = {true: {pred: 0 for pred in classes} for true in classes}
    for pred, actual in rows:
        cm[actual][pred] += 1

    return {
        "accuracy": round(accuracy, 4),
        "weighted_f1": round(weighted_f1, 4),
        "per_class": per_class,
        "confusion_matrix": cm,
        "count": total,
    }


def _compute_abstention_rate(rows: list) -> float:
    """Compute the abstention rate (fraction of 'uncertain' predictions)."""
    if not rows:
        return 0
    uncertain = sum(1 for p, _ in rows if p == "uncertain")
    return round(uncertain / len(rows), 4)


@celery.task(name="app.tasks.model_monitoring.monitor_performance")
def monitor_model_performance_task():
    """Monitor model performance over sliding windows.

    Computes metrics for the last 7, 30, and 60 days where enough
    labeled outcomes exist. Detects significant degradation.
    """
    log.info("[MONITOR] Starting model performance monitoring")

    try:
        import pandas as pd
        from sqlalchemy import text as sql_text

        session = _get_sync_session()
        today = date.today()

        # Load all resolved predictions
        result = session.execute(
            sql_text(
                """SELECT symbol, horizon, predicted_direction, actual_direction,
                          was_correct, as_of_date, target_date, model_version
                FROM predictions
                WHERE actual_direction IS NOT NULL
                ORDER BY target_date DESC"""
            )
        ).fetchall()
        session.close()

        if not result:
            log.info("[MONITOR] No resolved predictions to analyze")
            return {"status": "no_data"}

        # Convert to DataFrame
        df = pd.DataFrame(result, columns=[
            "symbol", "horizon", "predicted_direction", "actual_direction",
            "was_correct", "as_of_date", "target_date", "model_version",
        ])
        df["target_date"] = pd.to_datetime(df["target_date"]).dt.date

        # Compute metrics for each window
        windows = {
            "7d": 7,
            "30d": 30,
            "60d": 60,
        }

        monitoring = {}
        for window_name, days in windows.items():
            cutoff = today - timedelta(days=days)
            window_df = df[df["target_date"] >= cutoff]

            if len(window_df) < 10:
                monitoring[window_name] = {"status": "insufficient_data", "count": len(window_df)}
                continue

            rows = list(zip(window_df["predicted_direction"], window_df["actual_direction"]))
            metrics = _compute_metrics(rows)
            abstention = _compute_abstention_rate(rows)

            monitoring[window_name] = {
                "status": "ok",
                "metrics": metrics,
                "abstention_rate": abstention,
                "sample_count": len(window_df),
                "date_range": f"{cutoff} to {today}",
            }

            log.info("[MONITOR] %s: accuracy=%.4f, f1=%.4f, abstention=%.4f, n=%d",
                     window_name, metrics["accuracy"], metrics["weighted_f1"],
                     abstention, len(window_df))

        # Detect degradation (compare 7d vs 30d)
        degradation = None
        if "7d" in monitoring and "30d" in monitoring:
            m7 = monitoring["7d"].get("metrics", {})
            m30 = monitoring["30d"].get("metrics", {})
            if m7 and m30:
                acc_diff = m7.get("accuracy", 0) - m30.get("accuracy", 0)
                f1_diff = m7.get("weighted_f1", 0) - m30.get("weighted_f1", 0)
                if acc_diff < -0.05 or f1_diff < -0.05:
                    degradation = {
                        "type": "performance_drop",
                        "accuracy_change": round(acc_diff, 4),
                        "f1_change": round(f1_diff, 4),
                        "severity": "warning" if max(abs(acc_diff), abs(f1_diff)) < 0.1 else "critical",
                    }
                    log.warning("[MONITOR] Performance degradation detected: %s", degradation)

        # Save report
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "windows": monitoring,
            "degradation": degradation,
        }
        report_path = Path("data/reports/daily_model_monitoring.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

        log.info("[MONITOR] Monitoring report saved to %s", report_path)
        return {
            "status": "success",
            "degradation": degradation,
            "report_path": str(report_path),
        }

    except SoftTimeLimitExceeded:
        log.error("[MONITOR] Monitoring task timed out")
        return {"status": "timeout"}
    except Exception:
        log.exception("[MONITOR] Monitoring task failed")
        return {"status": "error"}


@celery.task(name="app.tasks.model_monitoring.detect_drift")
def detect_drift_task():
    """Simple data drift detection by comparing recent feature distributions
    against the training reference period.
    """
    log.info("[DRIFT] Starting drift detection")

    try:
        import numpy as np
        import pandas as pd

        features_path = Path("data/features/features_daily.parquet")
        if not features_path.exists():
            return {"status": "no_features"}

        df = pd.read_parquet(features_path)
        df["date"] = pd.to_datetime(df["date"])

        today = pd.Timestamp.now()
        recent_cutoff = today - timedelta(days=30)
        reference_cutoff = today - timedelta(days=365)

        recent = df[df["date"] >= recent_cutoff]
        reference = df[(df["date"] >= reference_cutoff) & (df["date"] < recent_cutoff)]

        if len(recent) < 100 or len(reference) < 100:
            return {"status": "insufficient_data"}

        # Key features to monitor
        monitor_features = ["rsi_14", "macd_hist", "volume_zscore_20", "return_1d", "rolling_std_20d"]
        drift_report = {}

        for feat in monitor_features:
            if feat not in recent.columns or feat not in reference.columns:
                continue

            ref_vals = reference[feat].dropna()
            rec_vals = recent[feat].dropna()

            if len(ref_vals) == 0 or len(rec_vals) == 0:
                continue

            ref_mean = float(ref_vals.mean())
            rec_mean = float(rec_vals.mean())
            ref_std = float(ref_vals.std())
            rec_std = float(rec_vals.std())

            # Simple drift: z-score of difference in means
            if ref_std > 0:
                z_score = abs(rec_mean - ref_mean) / ref_std
            else:
                z_score = 0

            drift_report[feat] = {
                "reference_mean": round(ref_mean, 6),
                "recent_mean": round(rec_mean, 6),
                "reference_std": round(ref_std, 6),
                "recent_std": round(rec_std, 6),
                "z_score": round(z_score, 4),
                "drift_detected": z_score > 2.0,
            }

            if z_score > 2.0:
                log.warning("[DRIFT] Drift detected in %s: z=%.2f (ref_mean=%.4f, recent_mean=%.4f)",
                           feat, z_score, ref_mean, rec_mean)

        # Save report
        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "features": drift_report,
            "drift_detected": any(f.get("drift_detected", False) for f in drift_report.values()),
        }
        report_path = Path("data/reports/daily_drift_report.json")
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

        log.info("[DRIFT] Drift report saved to %s", report_path)
        return {"status": "success", "report": report}

    except Exception:
        log.exception("[DRIFT] Drift detection failed")
        return {"status": "error"}
