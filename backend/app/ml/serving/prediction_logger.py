"""Prediction logger — writes each served forecast to the predictions table."""

import logging
from datetime import datetime

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
    confidence: float,
    as_of_date,
    target_date,
    model_version: str = "gru_v1",
) -> Prediction:
    """Insert one row per served forecast — every call to GET /forecast."""
    row = Prediction(
        symbol=symbol,
        horizon=horizon,
        predicted_at=datetime.utcnow(),
        predicted_direction=predicted_direction,
        bullish_pct=bullish_pct,
        bearish_pct=bearish_pct,
        sideways_pct=sideways_pct,
        confidence=confidence,
        as_of_date=as_of_date,
        target_date=target_date,
        model_version=model_version,
        actual_direction=None,
        was_correct=None,
    )
    db.add(row)
    await db.flush()
    log.info("Logged prediction: %s %s -> %s (%.1f%%) target=%s",
             symbol, horizon, predicted_direction, confidence, target_date)
    return row
