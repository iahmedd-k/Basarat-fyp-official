"""Prediction logger — writes each served forecast to the predictions table."""

import logging
from datetime import date, datetime, time

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.prediction import Prediction

log = logging.getLogger(__name__)


async def log_prediction(
    db: AsyncSession,
    *,
    symbol: str,
    horizon: str,
    predicted_direction: str,
    bullish_pct: float,
    bearish_pct: float,
    sideways_pct: float,
    top_class_probability: float,
    as_of_date,
    target_date,
    model_version: str = "ensemble",
) -> Prediction:
    """Upsert one forecast observation per symbol, horizon, session and model."""
    today = datetime.utcnow().date()
    as_of_d = as_of_date.date() if isinstance(as_of_date, datetime) else as_of_date
    target_d = target_date.date() if isinstance(target_date, datetime) else target_date

    # Align predicted_at with market session
    if as_of_d < today:
        pred_time = datetime.combine(as_of_d, time(16, 0, 0))
    else:
        pred_time = datetime.utcnow()

    result = await db.execute(
        select(Prediction)
        .where(
            Prediction.symbol == symbol,
            Prediction.horizon == horizon,
            Prediction.as_of_date == as_of_d,
            Prediction.model_version == model_version,
            Prediction.actual_direction.is_(None),
        )
        .order_by(Prediction.predicted_at.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    if row is None:
        row = Prediction(
            symbol=symbol,
            horizon=horizon,
            predicted_at=pred_time,
            predicted_direction=predicted_direction,
            bullish_pct=bullish_pct,
            bearish_pct=bearish_pct,
            sideways_pct=sideways_pct,
            top_class_probability=top_class_probability,
            as_of_date=as_of_d,
            target_date=target_d,
            model_version=model_version,
            actual_direction=None,
            was_correct=None,
        )
        db.add(row)
    else:
        row.predicted_at = pred_time
        row.predicted_direction = predicted_direction
        row.bullish_pct = bullish_pct
        row.bearish_pct = bearish_pct
        row.sideways_pct = sideways_pct
        row.top_class_probability = top_class_probability
        row.target_date = target_d
    await db.flush()
    log.info("Logged prediction: %s %s -> %s (%.1f%%) target=%s",
             symbol, horizon, predicted_direction, top_class_probability, target_d)
    return row
