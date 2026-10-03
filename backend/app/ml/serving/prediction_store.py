"""Shared prediction persistence + outcome evaluation (API + Celery).

Flow (professional contract):
  1. After session features are ready → upsert prediction (bullish/bearish/sideways)
  2. When target_date close is available → set actual_direction + was_correct
  3. History API only reads; it never invents outcomes
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta
from pathlib import Path
from typing import Any, Optional
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.prediction import Prediction

log = logging.getLogger(__name__)

PKT = ZoneInfo("Asia/Karachi")


def pkt_today() -> date:
    return datetime.now(PKT).date()


def next_trading_day(from_date: date, trading_days: int = 1) -> date:
    """Advance N weekdays (Mon–Fri). Holidays are not skipped here (features gate)."""
    target = from_date
    added = 0
    while added < trading_days:
        target += timedelta(days=1)
        if target.weekday() < 5:
            added += 1
    return target


def session_predicted_at(as_of_d: date) -> datetime:
    """Stamp predictions at ~16:00 PKT on as_of_date when backfilling older sessions."""
    today = pkt_today()
    if as_of_d < today:
        return datetime.combine(as_of_d, time(16, 0, 0))
    return datetime.now(PKT).replace(tzinfo=None)


def features_parquet_path() -> Path:
    from app.ml.serving.inference import FEATURES_PATH

    return Path(FEATURES_PATH)


def _coerce_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    return date.fromisoformat(str(value)[:10])


def _model_fields_from_parts(
    gru_result: dict | None,
    xgb_result: dict | None,
    gate_reason: str | None,
) -> dict[str, Any]:
    return {
        "gru_direction": gru_result.get("direction") if gru_result else None,
        "gru_bullish_pct": gru_result.get("bullish_pct") if gru_result else None,
        "gru_bearish_pct": gru_result.get("bearish_pct") if gru_result else None,
        "gru_sideways_pct": gru_result.get("sideways_pct") if gru_result else None,
        "gru_gap_pp": gru_result.get("gap_pp") if gru_result else None,
        "xgb_direction": xgb_result.get("direction") if xgb_result else None,
        "xgb_bullish_pct": xgb_result.get("bullish_pct") if xgb_result else None,
        "xgb_bearish_pct": xgb_result.get("bearish_pct") if xgb_result else None,
        "xgb_sideways_pct": xgb_result.get("sideways_pct") if xgb_result else None,
        "xgb_gap_pp": xgb_result.get("gap_pp") if xgb_result else None,
        "gate_reason": gate_reason or "",
    }


def _apply_prediction_fields(row: Prediction, fields: dict[str, Any]) -> None:
    for key, value in fields.items():
        if value is None and key.startswith(("gru_", "xgb_")):
            # Keep existing audit fields when API path omits component models
            if getattr(row, key, None) is not None:
                continue
        setattr(row, key, value)


def build_prediction_payload(
    *,
    symbol: str,
    horizon: str,
    ensemble: dict,
    as_of_date,
    target_date,
    gru_result: dict | None = None,
    xgb_result: dict | None = None,
) -> dict[str, Any]:
    as_of_d = _coerce_date(as_of_date)
    target_d = _coerce_date(target_date)
    payload = {
        "symbol": str(symbol).upper().strip(),
        "horizon": horizon,
        "predicted_at": session_predicted_at(as_of_d),
        "predicted_direction": ensemble["direction"],
        "bullish_pct": float(ensemble["bullish_pct"]),
        "bearish_pct": float(ensemble["bearish_pct"]),
        "sideways_pct": float(ensemble["sideways_pct"]),
        "top_class_probability": float(ensemble["top_class_probability"]),
        "as_of_date": as_of_d,
        "target_date": target_d,
        "model_version": str(ensemble.get("model_version") or "ensemble"),
    }
    payload.update(
        _model_fields_from_parts(
            gru_result,
            xgb_result,
            ensemble.get("gate_reason"),
        )
    )
    return payload


def upsert_prediction_sync(session: Session, payload: dict[str, Any]) -> Prediction:
    """Idempotent write: one row per (symbol, horizon, as_of_date)."""
    result = session.execute(
        select(Prediction)
        .where(
            Prediction.symbol == payload["symbol"],
            Prediction.horizon == payload["horizon"],
            Prediction.as_of_date == payload["as_of_date"],
        )
        .order_by(Prediction.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = Prediction(
            **{k: v for k, v in payload.items()},
            actual_direction=None,
            was_correct=None,
        )
        session.add(row)
    else:
        # Never wipe a resolved outcome when re-saving the same session prediction
        preserve_actual = row.actual_direction
        preserve_correct = row.was_correct
        _apply_prediction_fields(row, payload)
        if preserve_actual is not None:
            row.actual_direction = preserve_actual
            row.was_correct = preserve_correct

    session.flush()
    return row


async def upsert_prediction_async(db: AsyncSession, payload: dict[str, Any]) -> Prediction:
    result = await db.execute(
        select(Prediction)
        .where(
            Prediction.symbol == payload["symbol"],
            Prediction.horizon == payload["horizon"],
            Prediction.as_of_date == payload["as_of_date"],
        )
        .order_by(Prediction.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()

    if row is None:
        row = Prediction(
            **{k: v for k, v in payload.items()},
            actual_direction=None,
            was_correct=None,
        )
        db.add(row)
    else:
        preserve_actual = row.actual_direction
        preserve_correct = row.was_correct
        _apply_prediction_fields(row, payload)
        if preserve_actual is not None:
            row.actual_direction = preserve_actual
            row.was_correct = preserve_correct

    await db.flush()
    return row


def score_was_correct(predicted_direction: str, actual_direction: str) -> Optional[bool]:
    """Uncertain/abstention predictions are recorded but not scored."""
    if predicted_direction in ("uncertain", None):
        return None
    return predicted_direction == actual_direction


def evaluate_pending_predictions_sync(
    session: Session,
    *,
    limit: int = 5000,
) -> dict[str, Any]:
    """Resolve actual_direction from feature closes once target session is in parquet."""
    import pandas as pd
    from sqlalchemy import text as sql_text

    from app.data.features.labeling import DEFAULT_THRESHOLD, label_from_return

    path = features_parquet_path()
    if not path.is_file():
        log.warning("[EVALUATION] features parquet missing at %s", path)
        return {"status": "skipped", "reason": "no_features", "updated": 0}

    features_df = pd.read_parquet(path)
    features_df["date"] = pd.to_datetime(features_df["date"]).dt.date
    today = pkt_today()

    rows = session.execute(
        sql_text(
            """SELECT id, symbol, horizon, predicted_direction, as_of_date, target_date
            FROM predictions
            WHERE actual_direction IS NULL
              AND target_date <= :today
            ORDER BY target_date ASC
            LIMIT :limit"""
        ),
        {"today": today, "limit": limit},
    ).fetchall()

    if not rows:
        return {"status": "success", "updated": 0, "correct": 0, "skipped_missing_close": 0}

    updated = 0
    correct = 0
    uncertain_excluded = 0
    skipped_missing_close = 0

    for row in rows:
        pred_id, symbol, _horizon, predicted_direction, as_of_date, target_date = row
        as_of_d = _coerce_date(as_of_date)
        target_d = _coerce_date(target_date)

        sym_df = features_df[features_df["symbol"] == symbol].sort_values("date")
        as_of_close = sym_df.loc[sym_df["date"] == as_of_d, "close"]
        target_close = sym_df.loc[sym_df["date"] == target_d, "close"]

        if as_of_close.empty or target_close.empty:
            skipped_missing_close += 1
            continue

        c_as_of = float(as_of_close.iloc[0])
        c_target = float(target_close.iloc[0])
        if c_as_of == 0:
            skipped_missing_close += 1
            continue

        fwd_return = (c_target - c_as_of) / c_as_of
        actual_direction = label_from_return(fwd_return, DEFAULT_THRESHOLD)
        was_correct = score_was_correct(predicted_direction, actual_direction)
        if predicted_direction == "uncertain":
            uncertain_excluded += 1

        session.execute(
            sql_text(
                """UPDATE predictions
                SET actual_direction = :actual_direction,
                    was_correct = :was_correct
                WHERE id = :id AND actual_direction IS NULL"""
            ),
            {
                "actual_direction": actual_direction,
                "was_correct": was_correct,
                "id": pred_id,
            },
        )
        updated += 1
        if was_correct:
            correct += 1

        if updated % 200 == 0:
            session.commit()

    session.commit()
    return {
        "status": "success",
        "updated": updated,
        "correct": correct,
        "uncertain_excluded": uncertain_excluded,
        "skipped_missing_close": skipped_missing_close,
        "as_of_pkt": today.isoformat(),
        "timestamp": datetime.now(PKT).isoformat(),
    }
