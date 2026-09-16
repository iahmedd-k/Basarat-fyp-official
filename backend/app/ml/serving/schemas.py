"""Pydantic response models for the Forecast and Recommendation APIs.

Design principles:
  - Flat structure where possible (no unnecessary nesting)
  - Every field self-documenting with descriptions
  - Consistent naming across endpoints
  - Frontend can render directly without reshaping
"""

from datetime import date, datetime

from pydantic import BaseModel, Field


# ═══════════════════════════════════════════════════════════════════════
# Forecast Schemas
# ═══════════════════════════════════════════════════════════════════════

class ForecastResponse(BaseModel):
    """Forecast output — flat, self-contained, ready for the frontend."""

    symbol: str = Field(
        ..., description="PSX stock ticker", examples=["OGDC"]
    )
    horizon: str = Field(
        ..., description="Forecast horizon: '1D', '1W', or '1M'",
        examples=["1D"],
    )
    direction: str = Field(
        ...,
        description="Predicted direction: 'bullish', 'bearish', 'sideways', or 'uncertain'",
        examples=["bullish"],
    )
    confidence: float = Field(
        ...,
        ge=0, le=1,
        description="Confidence in the direction (0 = no confidence, 1 = max confidence). Derived from top_class_probability normalized to [0,1].",
        examples=[0.72],
    )

    # Probability breakdown
    probabilities: dict[str, float] = Field(
        ...,
        description="Probability for each direction (0-100). Keys: bullish, bearish, sideways.",
        examples=[{"bullish": 42.3, "bearish": 28.7, "sideways": 29.0}],
    )

    # Dates
    as_of_date: date = Field(
        ..., description="Latest date in the input data window",
        examples=["2026-09-12"],
    )
    target_date: date = Field(
        ..., description="Date this forecast targets (next trading day for 1D)",
        examples=["2026-09-15"],
    )

    # Price context
    current_price: float | None = Field(
        default=None,
        description="Stock's closing price on as_of_date",
        examples=[142.50],
    )
    target_price: float | None = Field(
        default=None,
        description="Projected target price (ensemble composite estimate)",
        examples=[148.00],
    )
    stop_loss: float | None = Field(
        default=None,
        description="Suggested stop-loss (ATR-based)",
        examples=[135.00],
    )

    # Model source
    model_version: str = Field(
        default="ensemble",
        description="Source: 'gru_v1', 'xgb_weighted', 'ensemble', or 'none'",
        examples=["ensemble"],
    )
    gate_reason: str = Field(
        default="",
        description="Why this direction: 'agree(bullish)', 'near_tie(...)', 'disagree(...)', 'single_model'",
        examples=["agree(bullish)"],
    )

    # Individual model breakdown (optional, for transparency)
    models: dict[str, dict] | None = Field(
        default=None,
        description="Individual model predictions. Keys: 'gru', 'xgb'. Each has direction, probabilities, gap_pp.",
        examples=[{
            "gru": {"direction": "bullish", "bullish_pct": 45.0, "bearish_pct": 25.0, "sideways_pct": 30.0, "gap_pp": 20.0},
            "xgb": {"direction": "bullish", "bullish_pct": 39.6, "bearish_pct": 32.4, "sideways_pct": 28.0, "gap_pp": 7.2},
        }],
    )

    # Market context (optional, informational)
    market_context: dict | None = Field(
        default=None,
        description="How this stock performs relative to PSX market. Informational only.",
        examples=[{
            "market_return_5d": 0.012,
            "market_return_20d": 0.034,
            "stock_return_20d": -0.058,
            "stock_relative_return_20d": -0.092,
        }],
    )


class ForecastHistoryItem(BaseModel):
    """Single historical prediction record."""

    predicted_at: datetime = Field(
        ..., description="When the prediction was made"
    )
    direction: str = Field(
        ..., alias="predicted_direction",
        description="Predicted direction"
    )
    probabilities: dict[str, float] = Field(
        ..., description="Probability breakdown"
    )
    confidence: float = Field(
        ..., description="Top class probability normalized to [0,1]"
    )
    target_date: date = Field(
        ..., description="Date this prediction targeted"
    )
    actual: dict | None = Field(
        default=None,
        description="Actual outcome: {direction, was_correct}",
    )

    model_config = {"from_attributes": True, "populate_by_name": True}


class ForecastHistoryResponse(BaseModel):
    """Forecast history for a single symbol."""

    symbol: str
    horizon: str = "1D"
    count: int = Field(
        ..., description="Number of historical predictions returned"
    )
    accuracy: float | None = Field(
        default=None,
        description="Overall accuracy across scored predictions (excludes uncertain)",
    )
    history: list[ForecastHistoryItem]


class ErrorResponse(BaseModel):
    detail: str


# ═══════════════════════════════════════════════════════════════════════
# Recommendation Schemas
# ═══════════════════════════════════════════════════════════════════════

class RecommendationItem(BaseModel):
    """Single stock recommendation — used in list view."""

    symbol: str = Field(..., examples=["OGDC"])
    signal: str = Field(
        ..., description="BUY, SELL, or HOLD", examples=["buy"]
    )
    confidence: float = Field(
        ..., ge=0, le=1,
        description="Signal confidence (0-1)", examples=[0.72],
    )
    composite_score: float = Field(
        ..., description="Raw composite signal (-1 to +1). Positive = bullish.",
        examples=[0.35],
    )
    target_price: float | None = Field(
        default=None, description="ATR-based target price", examples=[148.0],
    )
    stop_loss: float | None = Field(
        default=None, description="ATR-based stop-loss", examples=[135.0],
    )
    summary: str = Field(
        ..., description="One-line human-readable summary",
        examples=["Strong buy: ML+Technical agree bullish, RSI=35 oversold"],
    )


class RecommendationsListResponse(BaseModel):
    """List of stock recommendations, sorted by composite score."""

    count: int = Field(
        ..., description="Number of recommendations returned"
    )
    risk_profile: str = Field(
        ..., description="Risk profile used for target/stop calculation",
        examples=["moderate"],
    )
    recommendations: list[RecommendationItem]


class RecommendationDetailResponse(BaseModel):
    """Full recommendation detail for a single symbol."""

    symbol: str
    signal: str = Field(
        ..., description="BUY, SELL, or HOLD", examples=["buy"]
    )
    confidence: float = Field(
        ..., ge=0, le=1, description="Signal confidence (0-1)"
    )
    composite_score: float = Field(
        ..., description="Raw composite signal (-1 to +1)"
    )

    # Individual signal scores
    signals: dict[str, float] = Field(
        ...,
        description="Individual signal scores. Keys: ml, technical, fundamental. Each in [-1, 1].",
        examples=[{"ml": 0.45, "technical": 0.38, "fundamental": 0.15}],
    )

    # Target / stop
    target_price: float | None = Field(
        default=None, description="ATR-based target price"
    )
    stop_loss: float | None = Field(
        default=None, description="ATR-based stop-loss"
    )
    current_price: float | None = Field(
        default=None, description="Current closing price"
    )
    atr_14: float | None = Field(
        default=None, description="14-day ATR used for target/stop"
    )

    # Detailed reasoning
    reasoning: dict = Field(
        ...,
        description="Breakdown of each signal source. Keys: ml, technical, fundamental.",
        examples=[{
            "ml": {"rsi": "RSI=35.2", "macd": "MACD_hist=0.0012", "sma": "close_vs_sma20=0.023"},
            "technical": {"rsi": "RSI=35.2", "macd": "MACD_cross=0.0012", "bb": "BB_pos=0.35"},
            "fundamental": {"pe": "P/E=8.5", "year_momentum": "1Y_change=-15.2%"},
        }],
    )

    # Weights used
    weights: dict[str, float] = Field(
        ..., description="Engine weights used for this calculation",
        examples=[{"gru": 0.40, "technical": 0.35, "fundamental": 0.25}],
    )


class TargetStopResponse(BaseModel):
    """Target price and stop-loss for a single symbol."""

    symbol: str
    current_price: float | None = None
    target_price: float | None = None
    stop_loss: float | None = None
    method: str = Field(
        default="atr_band",
        description="Calculation method",
        examples=["atr_band"],
    )
    atr_14: float | None = Field(
        default=None,
        description="14-day ATR value used",
    )
    risk_tolerance: str = Field(
        default="moderate",
        description="Risk tolerance profile used for multipliers",
    )
    upside_pct: float | None = Field(
        default=None,
        description="Target upside as % of current price",
        examples=[3.8],
    )
    downside_pct: float | None = Field(
        default=None,
        description="Stop-loss downside as % of current price",
        examples=[-5.2],
    )


class EngineWeightsRequest(BaseModel):
    gru_weight: float = Field(0.33, ge=0.0, le=1.0)
    technical_weight: float = Field(0.33, ge=0.0, le=1.0)
    fundamental_weight: float = Field(0.34, ge=0.0, le=1.0)


class EngineWeightsResponse(BaseModel):
    gru_weight: float
    technical_weight: float
    fundamental_weight: float


# ═══════════════════════════════════════════════════════════════════════
# Risk Schemas
# ═══════════════════════════════════════════════════════════════════════

class RiskVaRResponse(BaseModel):
    """Value at Risk and Conditional VaR response."""

    confidence: int = Field(
        ..., description="Confidence level (90, 95, or 99)", examples=[95]
    )
    horizon: str = Field(
        ..., description="Risk horizon: '1D', '1W', '1M'", examples=["1D"]
    )
    var_value: float | None = Field(
        default=None,
        description="Value at Risk (negative = potential loss). Historical simulation.",
        examples=[-0.0234],
    )
    cvar_value: float | None = Field(
        default=None,
        description="Conditional VaR (Expected Shortfall). Mean loss beyond VaR.",
        examples=[-0.0351],
    )
    method: str = Field(
        default="historical_simulation",
        description="Calculation method",
        examples=["historical_simulation"],
    )
    num_observations: int = Field(
        default=0,
        description="Number of historical return observations used",
        examples=[252],
    )
    annualized_volatility: float | None = Field(
        default=None,
        description="Annualized portfolio volatility (std * sqrt(252))",
        examples=[0.1856],
    )


class MonteCarloRequest(BaseModel):
    """Request body for starting a Monte Carlo simulation."""

    num_simulations: int = Field(
        1000, ge=100, le=10000,
        description="Number of Monte Carlo paths",
    )
    horizon_days: int = Field(
        30, ge=1, le=365,
        description="Forecast horizon in trading days",
    )


class MonteCarloResponse(BaseModel):
    """Response when Monte Carlo simulation is started (async)."""

    job_id: str = Field(
        ..., description="Task ID to poll for results", examples=["abc123"]
    )
    status: str = Field(
        default="pending",
        description="Job status: pending, running, completed, failed",
    )
    num_simulations: int | None = None
    horizon_days: int | None = None
    message: str | None = None


class MonteCarloResultResponse(BaseModel):
    """Monte Carlo simulation result (polled)."""

    job_id: str
    status: str = Field(
        ..., description="pending, running, completed, failed"
    )
    num_simulations: int | None = None
    horizon_days: int | None = None
    params: dict | None = Field(
        default=None,
        description="Simulation parameters: daily_drift, daily_volatility, annualized values",
    )
    percentiles: dict[str, float] | None = Field(
        default=None,
        description="Terminal return percentiles: p1, p5, p10, p25, p50, p75, p90, p95, p99",
    )
    stats: dict | None = Field(
        default=None,
        description="Stats: mean_return, std_return, prob_loss, max_drawdown, best_case",
    )
    paths_sample: list[list[float]] | None = Field(
        default=None,
        description="Sample of MC paths for visualization (max 50)",
    )
    error: str | None = None
    completed_at: str | None = None


class StressTestResponse(BaseModel):
    """Stress test scenario result."""

    scenario: str = Field(
        ..., description="Scenario name", examples=["2008_crash"]
    )
    name: str = Field(
        ..., description="Human-readable scenario name",
        examples=["2008 Global Financial Crisis"],
    )
    description: str = Field(
        ..., description="Scenario description",
        examples=["Simulates the 2008 GFC"],
    )
    portfolio_impact: float = Field(
        ..., description="Portfolio impact as decimal (-0.45 = -45%)",
        examples=[-0.45],
    )
    portfolio_impact_value: float = Field(
        ..., description="Absolute portfolio value impact (PKR)",
        examples=[-450000],
    )
    worst_case_loss: float = Field(
        ..., description="Worst-case loss as decimal", examples=[-0.60],
    )
    volatility_multiplier: float = Field(
        ..., description="How much volatility increases during stress",
        examples=[2.5],
    )
    recovery_days: int = Field(
        ..., description="Estimated recovery time in trading days",
        examples=[540],
    )
    current_value: float = Field(
        ..., description="Current portfolio value (PKR)", examples=[1000000],
    )
    stressed_value: float = Field(
        ..., description="Portfolio value after stress", examples=[550000],
    )
    holding_impacts: list[dict] = Field(
        ..., description="Per-holding impact breakdown",
    )


# ═══════════════════════════════════════════════════════════════════════
# Sentiment Schemas
# ═══════════════════════════════════════════════════════════════════════

class SentimentResponse(BaseModel):
    """Per-stock sentiment analysis result."""

    symbol: str = Field(..., examples=["OGDC"])
    score: float = Field(
        ..., description="Overall sentiment score (-1 = bearish, +1 = bullish)",
        examples=[0.35],
    )
    label: str = Field(
        ..., description="Sentiment label: positive, negative, neutral",
        examples=["positive"],
    )
    article_count: int = Field(
        ..., description="Number of articles/posts analyzed", examples=[12],
    )
    trend: str = Field(
        ..., description="Score trend: improving, declining, stable",
        examples=["improving"],
    )
    source_breakdown: dict | None = Field(
        default=None,
        description="Count by source type: {news: N, community: M}",
        examples=[{"news": 8, "community": 4}],
    )
    daily_scores: list[dict] | None = Field(
        default=None,
        description="Daily aggregated scores for chart: [{date, score, count}]",
    )


class MarketSentimentResponse(BaseModel):
    """Market-wide sentiment overview."""

    market_mood: str = Field(
        ..., description="Overall mood: bullish, bearish, neutral",
        examples=["neutral"],
    )
    overall_score: float = Field(
        ..., description="Aggregate sentiment score (-1 to +1)", examples=[0.05],
    )
    article_count: int = Field(
        default=0, description="Total news articles analyzed",
    )
    community_post_count: int = Field(
        default=0, description="Total community posts analyzed",
    )
    advancing: int = Field(
        ..., description="Number of stocks with positive returns", examples=[35],
    )
    declining: int = Field(
        ..., description="Number of stocks with negative returns", examples=[25],
    )
    unchanged: int = Field(
        ..., description="Number of stocks with flat returns", examples=[10],
    )
    advance_decline_ratio: float = Field(
        ..., description="Advancing / declining ratio", examples=[1.4],
    )
    news_sentiment_avg: float = Field(
        default=0.0,
        description="Average news sentiment score",
    )
    community_sentiment_avg: float = Field(
        default=0.0,
        description="Average community sentiment score",
    )
    score_distribution: dict | None = Field(
        default=None,
        description="Distribution: {positive: N, neutral: M, negative: K}",
    )
