"""Model Registry — database operations for tracking model versions."""

import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def register_model(
    session: Session,
    *,
    model_version: str,
    model_type: str,
    horizon: str = "1D",
    status: str = "candidate",
    training_start_date: str | None = None,
    training_end_date: str | None = None,
    validation_start_date: str | None = None,
    validation_end_date: str | None = None,
    training_sample_count: int = 0,
    validation_sample_count: int = 0,
    metrics: dict | None = None,
    feature_version: str | None = None,
    model_path: str | None = None,
    scaler_path: str | None = None,
    metadata_path: str | None = None,
) -> int:
    """Insert a new model registry entry. Returns the new row id."""
    result = session.execute(
        text(
            """INSERT INTO model_registry
            (model_version, model_type, horizon, status,
             training_start_date, training_end_date,
             validation_start_date, validation_end_date,
             training_sample_count, validation_sample_count,
             metrics, feature_version,
             model_path, scaler_path, metadata_path,
             created_at, updated_at)
            VALUES
            (:model_version, :model_type, :horizon, :status,
             :training_start_date, :training_end_date,
             :validation_start_date, :validation_end_date,
             :training_sample_count, :validation_sample_count,
             :metrics, :feature_version,
             :model_path, :scaler_path, :metadata_path,
             :created_at, :updated_at)
            RETURNING id"""
        ),
        {
            "model_version": model_version,
            "model_type": model_type,
            "horizon": horizon,
            "status": status,
            "training_start_date": training_start_date,
            "training_end_date": training_end_date,
            "validation_start_date": validation_start_date,
            "validation_end_date": validation_end_date,
            "training_sample_count": training_sample_count,
            "validation_sample_count": validation_sample_count,
            "metrics": json.dumps(metrics) if metrics else None,
            "feature_version": feature_version,
            "model_path": model_path,
            "scaler_path": scaler_path,
            "metadata_path": metadata_path,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
        },
    )
    row_id = result.scalar_one()
    session.commit()
    log.info("Registered model: %s (type=%s, status=%s, id=%d)",
             model_version, model_type, status, row_id)
    return row_id


def promote_model(session: Session, model_version: str) -> None:
    """Promote a candidate model to production. Demotes current production."""
    # Demote current production of the same type
    model_type_row = session.execute(
        text("SELECT model_type FROM model_registry WHERE model_version = :v"),
        {"v": model_version},
    ).fetchone()
    if model_type_row:
        model_type = model_type_row[0]
        session.execute(
            text(
                """UPDATE model_registry
                SET status = 'archived', updated_at = :now
                WHERE model_type = :type AND status = 'production'"""
            ),
            {"type": model_type, "now": datetime.utcnow()},
        )

    # Promote the candidate
    session.execute(
        text(
            """UPDATE model_registry
            SET status = 'production', promoted_at = :now, updated_at = :now
            WHERE model_version = :v"""
        ),
        {"v": model_version, "now": datetime.utcnow()},
    )
    session.commit()
    log.info("Promoted model: %s -> production", model_version)


def reject_model(session: Session, model_version: str, reason: str = "") -> None:
    """Mark a candidate model as rejected."""
    session.execute(
        text(
            """UPDATE model_registry
            SET status = 'rejected', rejected_at = :now, rejection_reason = :reason,
                updated_at = :now
            WHERE model_version = :v"""
        ),
        {"v": model_version, "now": datetime.utcnow(), "reason": reason},
    )
    session.commit()
    log.info("Rejected model: %s (reason: %s)", model_version, reason)


def get_production_model(session: Session, model_type: str) -> dict | None:
    """Get the current production model for a given type."""
    result = session.execute(
        text(
            """SELECT model_version, model_type, horizon, metrics, model_path,
                      scaler_path, metadata_path, training_sample_count,
                      validation_sample_count, created_at
            FROM model_registry
            WHERE model_type = :type AND status = 'production'
            LIMIT 1"""
        ),
        {"type": model_type},
    ).fetchone()
    if not result:
        return None
    return {
        "model_version": result[0],
        "model_type": result[1],
        "horizon": result[2],
        "metrics": json.loads(result[3]) if result[3] else None,
        "model_path": result[4],
        "scaler_path": result[5],
        "metadata_path": result[6],
        "training_sample_count": result[7],
        "validation_sample_count": result[8],
        "created_at": result[9],
    }


def get_latest_candidate(session: Session, model_type: str) -> dict | None:
    """Get the most recent candidate model for a given type."""
    result = session.execute(
        text(
            """SELECT model_version, model_type, horizon, metrics, model_path,
                      scaler_path, metadata_path, training_sample_count,
                      validation_sample_count, created_at
            FROM model_registry
            WHERE model_type = :type AND status = 'candidate'
            ORDER BY created_at DESC
            LIMIT 1"""
        ),
        {"type": model_type},
    ).fetchone()
    if not result:
        return None
    return {
        "model_version": result[0],
        "model_type": result[1],
        "horizon": result[2],
        "metrics": json.loads(result[3]) if result[3] else None,
        "model_path": result[4],
        "scaler_path": result[5],
        "metadata_path": result[6],
        "training_sample_count": result[7],
        "validation_sample_count": result[8],
        "created_at": result[9],
    }


def get_model_history(session: Session, model_type: str | None = None, limit: int = 20) -> list[dict]:
    """Get model history, optionally filtered by type."""
    if model_type:
        result = session.execute(
            text(
                """SELECT model_version, model_type, horizon, status, metrics,
                          training_sample_count, validation_sample_count,
                          promoted_at, rejected_at, rejection_reason, created_at
                FROM model_registry
                WHERE model_type = :type
                ORDER BY created_at DESC
                LIMIT :limit"""
            ),
            {"type": model_type, "limit": limit},
        ).fetchall()
    else:
        result = session.execute(
            text(
                """SELECT model_version, model_type, horizon, status, metrics,
                          training_sample_count, validation_sample_count,
                          promoted_at, rejected_at, rejection_reason, created_at
                FROM model_registry
                ORDER BY created_at DESC
                LIMIT :limit"""
            ),
            {"limit": limit},
        ).fetchall()

    return [
        {
            "model_version": r[0],
            "model_type": r[1],
            "horizon": r[2],
            "status": r[3],
            "metrics": json.loads(r[4]) if r[4] else None,
            "training_sample_count": r[5],
            "validation_sample_count": r[6],
            "promoted_at": r[7],
            "rejected_at": r[8],
            "rejection_reason": r[9],
            "created_at": r[10],
        }
        for r in result
    ]
