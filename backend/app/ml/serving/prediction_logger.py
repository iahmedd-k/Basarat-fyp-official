"""Prediction logger — writes each served forecast to the predictions table."""

import logging
from datetime import datetime

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
    result = await db.execute(
        select(Prediction)
        .where(
            Prediction.symbol == symbol,
            Prediction.horizon == horizon,
            Prediction.as_of_date == as_of_date,
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
        predicted_at=datetime.utcnow(),
        predicted_direction=predicted_direction,
        bullish_pct=bullish_pct,
        bearish_pct=bearish_pct,
        sideways_pct=sideways_pct,
        top_class_probability=top_class_probability,
        as_of_date=as_of_date,
        target_date=target_date,
        model_version=model_version,
        actual_direction=None,
        was_correct=None,
        )
        db.add(row)
    else:
        row.predicted_at = datetime.utcnow()
        row.predicted_direction = predicted_direction
        row.bullish_pct = bullish_pct
        row.bearish_pct = bearish_pct
        row.sideways_pct = sideways_pct
        row.top_class_probability = top_class_probability
        row.target_date = target_date
    await db.flush()
    log.info("Logged prediction: %s %s -> %s (%.1f%%) target=%s",
             symbol, horizon, predicted_direction, top_class_probability, target_date)
    return row
