"""Pydantic response models for the forecast API."""

from datetime import date, datetime

from pydantic import BaseModel, Field


class ModelDetail(BaseModel):
    """Individual model prediction detail (for debug/analysis)."""
    direction: str
    bullish_pct: float
    bearish_pct: float
    sideways_pct: float
    top_class_probability: float
    gap_pp: float


class MarketContext(BaseModel):
    """Market context informational data for the frontend.

    Shows how the stock is performing relative to the broader PSX market.
    These are pure informational fields — they do NOT affect the gate decision.
    """
    market_return_5d: float | None = Field(
        default=None,
        description="KSE-100 proxy (equal-weighted) 5-day cumulative return. Positive = broad market up.",
        examples=[0.012],
    )
    market_return_20d: float | None = Field(
        default=None,
        description="KSE-100 proxy (equal-weighted) 20-day cumulative return. Positive = broad market up.",
        examples=[0.034],
    )
    stock_return_20d: float | None = Field(
        default=None,
        description="This stock's raw 20-day cumulative return.",
        examples=[-0.058],
    )
    stock_relative_return_20d: float | None = Field(
        default=None,
        description="Stock's 20d return minus market's 20d return. Positive = stock outperforming the market.",
        examples=[-0.092],
    )


class ForecastResponse(BaseModel):
    symbol: str
    horizon: str
    direction: str = Field(
        ...,
        description=(
            "Ensemble-gated predicted direction: "
            "'bullish', 'bearish', 'sideways', or 'uncertain' "
            "(when models disagree or either is near-tie). "
            "Both models must agree AND be non-near-tie to assert a directional call."
        ),
        examples=["bullish"],
    )
    bullish_pct: float = Field(
        ...,
        ge=0,
        le=100,
        description="Ensemble probability of bullish outcome (0-100). Average of both models when both available.",
        examples=[42.3],
    )
    bearish_pct: float = Field(
        ...,
        ge=0,
        le=100,
        description="Ensemble probability of bearish outcome (0-100). Average of both models when both available.",
        examples=[28.7],
    )
    sideways_pct: float = Field(
        ...,
        ge=0,
        le=100,
        description="Ensemble probability of sideways outcome (0-100). Average of both models when both available.",
        examples=[29.0],
    )
    top_class_probability: float = Field(
        ...,
        ge=0,
        le=100,
        description="Probability of the top predicted class (ensemble-averaged when both models agree)",
        examples=[42.3],
    )
    as_of_date: date = Field(
        ...,
        description="Latest date used in the input window",
        examples=["2026-09-12"],
    )
    predicted_for_date: date = Field(
        ...,
        description="The date this forecast targets (next trading day for 1D)",
        examples=["2026-09-15"],
    )
    model_version: str = Field(
        default="ensemble",
        description="Model source: 'gru_v1', 'xgb_weighted', 'ensemble', or 'none'",
        examples=["ensemble"],
    )
    model_details: dict[str, ModelDetail] | None = Field(
        default=None,
        description="Individual model predictions for debug/analysis. Keys are model names.",
    )
    gate_reason: str = Field(
        default="",
        description="Why this direction was chosen: agree(bullish), near_tie(...), disagree(...), single_model, etc.",
        examples=["agree(bullish)"],
    )
    market_context: MarketContext | None = Field(
        default=None,
        description="Market context: how this stock performs relative to the PSX market. Informational only — does not affect the gate.",
    )


class ForecastHistoryItem(BaseModel):
    predicted_at: datetime
    predicted_direction: str
    bullish_pct: float
    bearish_pct: float
    sideways_pct: float
    top_class_probability: float
    target_date: date
    actual_direction: str | None = None
    was_correct: bool | None = None

    model_config = {"from_attributes": True}


class ForecastHistoryResponse(BaseModel):
    symbol: str
    history: list[ForecastHistoryItem]


class ErrorResponse(BaseModel):
    detail: str
