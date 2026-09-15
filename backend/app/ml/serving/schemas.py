"""Pydantic response models for the forecast API."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class ForecastResponse(BaseModel):
    symbol: str
    horizon: str
    direction: str = Field(
        ...,
        description="Predicted direction: bullish, bearish, or sideways",
        examples=["bullish"],
    )
    bullish_pct: float = Field(
        ...,
        ge=0,
        le=100,
        description="Probability of bullish outcome (0-100)",
        examples=[42.3],
    )
    bearish_pct: float = Field(
        ...,
        ge=0,
        le=100,
        description="Probability of bearish outcome (0-100)",
        examples=[28.7],
    )
    sideways_pct: float = Field(
        ...,
        ge=0,
        le=100,
        description="Probability of sideways outcome (0-100)",
        examples=[29.0],
    )
    confidence: float = Field(
        ...,
        ge=0,
        le=100,
        description="Confidence of the prediction (max probability * 100)",
        examples=[42.3],
    )
    as_of_date: date = Field(
        ...,
        description="Latest date used in the input window",
        examples=["2026-09-12"],
    )
    predicted_for_date: date = Field(
        ...,
        description="The date this forecast targets (next trading day)",
        examples=["2026-09-15"],
    )
    model_version: str = Field(
        default="gru_v1",
        description="Model identifier",
        examples=["gru_v1"],
    )


class ForecastHistoryItem(BaseModel):
    predicted_at: datetime
    predicted_direction: str
    bullish_pct: float
    bearish_pct: float
    sideways_pct: float
    confidence: float
    target_date: date
    actual_direction: str | None = None
    was_correct: bool | None = None

    model_config = {"from_attributes": True}


class ForecastHistoryResponse(BaseModel):
    symbol: str
    history: list[ForecastHistoryItem]


class ErrorResponse(BaseModel):
    detail: str
