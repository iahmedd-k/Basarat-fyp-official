"""Prediction logger — API path upserts into predictions via shared store."""

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.ml.serving.prediction_store import build_prediction_payload, upsert_prediction_async
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
    gate_reason: str = "",
    gru_result: dict | None = None,
    xgb_result: dict | None = None,
    model_details: dict | None = None,
) -> Prediction:
    """Upsert one forecast observation per symbol, horizon, and session date."""
    if model_details and not gru_result:
        gru_result = (
            model_details.get("gru")
            or model_details.get("gru_v1")
            or model_details.get("gru_v2")
        )
    if model_details and not xgb_result:
        xgb_result = (
            model_details.get("xgb")
            or model_details.get("xgb_v1")
            or model_details.get("xgb_v4")
        )

    ensemble = {
        "direction": predicted_direction,
        "bullish_pct": bullish_pct,
        "bearish_pct": bearish_pct,
        "sideways_pct": sideways_pct,
        "top_class_probability": top_class_probability,
        "model_version": model_version,
        "gate_reason": gate_reason,
    }
    payload = build_prediction_payload(
        symbol=symbol,
        horizon=horizon,
        ensemble=ensemble,
        as_of_date=as_of_date,
        target_date=target_date,
        gru_result=gru_result,
        xgb_result=xgb_result,
    )
    row = await upsert_prediction_async(db, payload)
    log.info(
        "Logged prediction: %s %s -> %s (%.1f%%) as_of=%s target=%s",
        symbol,
        horizon,
        predicted_direction,
        top_class_probability,
        payload["as_of_date"],
        payload["target_date"],
    )
    return row
