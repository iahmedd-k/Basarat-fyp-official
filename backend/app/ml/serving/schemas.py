"""Pydantic response models for the Forecast and Recommendation APIs.

Design principles:
  - Flat structure where possible (no unnecessary nesting)
  - Every field self-documenting with descriptions
  - Consistent naming across endpoints
  - Frontend can render directly without reshaping
"""

from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator


# ═══════════════════════════════════════════════════════════════════════
# Forecast Schemas
# ═══════════════════════════════════════════════════════════════════════

class ForecastProbabilities(BaseModel):
    """Class probabilities as percentages; the three values sum to about 100."""

    bullish: float = Field(..., description="Bullish class probability, percent (0–100).", examples=[58.4])
    bearish: float = Field(..., description="Bearish class probability, percent (0–100).", examples=[22.0])
    sideways: float = Field(..., description="Sideways class probability, percent (0–100).", examples=[19.6])


class ForecastModelDetail(BaseModel):
    """One component model's prediction; gap_pp is measured in percentage points."""

    direction: str = Field(..., description="This model's predicted direction.", examples=["bullish"])
    bullish_pct: float = Field(..., description="Bullish probability, percent (0–100).", examples=[61.0])
    bearish_pct: float = Field(..., description="Bearish probability, percent (0–100).", examples=[20.0])
    sideways_pct: float = Field(..., description="Sideways probability, percent (0–100).", examples=[19.0])
    gap_pp: float = Field(..., description="Gap between this model's highest and second-highest class probabilities, in percentage points.", examples=[41.0])


class ExpectedPriceRange(BaseModel):
    """ATR-derived price interval, present when the direction is sideways/uncertain."""

    low: float = Field(..., description="Lower price bound, in PKR.", examples=[139.5])
    high: float = Field(..., description="Upper price bound, in PKR.", examples=[145.5])
    method: str = Field(..., description="Method used to derive the range.", examples=["atr_range"])


class ForecastMarketContext(BaseModel):
    """Recent market and relative returns. Values are decimal returns, not percentages."""

    market_return_5d: float | None = Field(None, description="PSX market return over five trading days; 0.012 means 1.2%.", examples=[0.012])
    market_return_20d: float | None = Field(None, description="PSX market return over 20 trading days; 0.034 means 3.4%.", examples=[0.034])
    stock_return_20d: float | None = Field(None, description="Stock return over 20 trading days; -0.058 means -5.8%.", examples=[-0.058])
    stock_relative_return_20d: float | None = Field(None, description="Stock return minus market return over 20 trading days, as a decimal.", examples=[-0.092])


class ForecastResponse(BaseModel):
    """Forecast response. Probabilities are percentages; confidence is a 0–1 score."""

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "symbol": "UBL",
                "horizon": "1D",
                "direction": "bullish",
                "confidence": 0.584,
                "probabilities": {"bullish": 58.4, "bearish": 22.0, "sideways": 19.6},
                "as_of_date": "2026-09-22",
                "target_date": "2026-09-23",
                "current_price": 142.5,
                "target_price": 148.0,
                "expected_range": None,
                "stop_loss": 138.0,
                "signal_rating": "Strong Buy",
                "upside_pct": 3.86,
                "downside_pct": -3.16,
                "risk_reward_ratio": 1.22,
                "model_version": "ensemble",
                "gate_reason": "agree(bullish)",
                "models": {
                    "gru": {"direction": "bullish", "bullish_pct": 61.0, "bearish_pct": 20.0, "sideways_pct": 19.0, "gap_pp": 42.0},
                    "xgb": {"direction": "bullish", "bullish_pct": 56.0, "bearish_pct": 24.0, "sideways_pct": 20.0, "gap_pp": 32.0},
                },
                "market_context": {
                    "market_return_5d": 0.012,
                    "market_return_20d": 0.034,
                    "stock_return_20d": -0.058,
                    "stock_relative_return_20d": -0.092,
                },
            }],
        }
    }

    symbol: str = Field(
        ..., description="PSX stock ticker", examples=["OGDC"]
    )
    horizon: str = Field(
        ..., description="Forecast horizon: '1D', '1W', or '1M'",
        examples=["1D"],
    )
    direction: str = Field(
        ...,
        description="Ensemble direction: bullish, bearish, sideways, or uncertain.",
        examples=["bullish"],
    )
    confidence: float = Field(
        ...,
        ge=0, le=1,
        description="Top-class probability on a 0–1 scale (0.584 = 58.4%). Uncalibrated model score; not a guaranteed accuracy estimate.",
        examples=[0.72],
    )

    # Probability breakdown
    probabilities: ForecastProbabilities = Field(
        ...,
        description="Class probabilities as percentages (0–100); expected to sum to approximately 100.",
        examples=[{"bullish": 42.3, "bearish": 28.7, "sideways": 29.0}],
    )

    # Dates
    as_of_date: date = Field(
        ..., description="Latest date represented in the input market-data window.",
        examples=["2026-09-12"],
    )
    target_date: date = Field(
        ..., description="Target trading date: 1, 5, or 22 trading days ahead for 1D, 1W, or 1M.",
        examples=["2026-09-15"],
    )

    # Price context
    current_price: float | None = Field(
        default=None,
        description="Stock's closing price on as_of_date, in PKR.",
        examples=[142.50],
    )
    target_price: float | None = Field(
        default=None,
        description="ATR-based target price in PKR; null for sideways or uncertain directions.",
        examples=[148.00],
    )
    expected_range: ExpectedPriceRange | None = Field(
        default=None,
        description="ATR-based price interval in PKR, returned for sideways or uncertain directions.",
        examples=[{"low": 139.5, "high": 145.5, "method": "atr_range"}],
    )
    stop_loss: float | None = Field(
        default=None,
        description="ATR-based stop-loss level in PKR.",
        examples=[135.00],
    )
    signal_rating: str | None = Field(
        default=None,
        description="Institutional signal rating: 'Strong Buy', 'Buy', 'Hold / Neutral', 'Sell', 'Strong Sell'",
        examples=["Strong Buy"],
    )
    upside_pct: float | None = Field(
        default=None,
        description="Signed target-price return relative to current_price, in percent (not a decimal ratio).",
        examples=[+5.2],
    )
    downside_pct: float | None = Field(
        default=None,
        description="Signed stop-loss return relative to current_price, in percent (not a decimal ratio).",
        examples=[-3.5],
    )
    risk_reward_ratio: float | None = Field(
        default=None,
        description="Absolute target reward divided by stop-loss risk; unitless. Null when no target exists.",
        examples=[1.49],
    )

    # Model source
    model_version: str = Field(
        default="ensemble",
        description="Model source/version label. 'ensemble' means the GRU and XGBoost outputs were combined.",
        examples=["ensemble"],
    )
    gate_reason: str = Field(
        default="",
        description="Machine-readable ensemble gating reason; for example, agree(bullish). Treat as diagnostic text.",
        examples=["agree(bullish)"],
    )

    # Individual model breakdown (optional, for transparency)
    models: dict[str, ForecastModelDetail] | None = Field(
        default=None,
        description="Component predictions keyed by model ('gru', 'xgb'). Probability fields use percent; gap_pp is percentage points.",
        examples=[{
            "gru": {"direction": "bullish", "bullish_pct": 45.0, "bearish_pct": 25.0, "sideways_pct": 30.0, "gap_pp": 20.0},
            "xgb": {"direction": "bullish", "bullish_pct": 39.6, "bearish_pct": 32.4, "sideways_pct": 28.0, "gap_pp": 7.2},
        }],
    )

    # Market context (optional, informational)
    market_context: ForecastMarketContext | None = Field(
        default=None,
        description="Recent PSX and stock returns as decimal ratios (0.012 = 1.2%). Informational context, not a model input/output guarantee.",
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

class RecommendationDecision(BaseModel):
    signal: str
    composite_score: float = Field(ge=-1, le=1)
    confidence: float = Field(ge=0, le=1, description="Heuristic signal strength, not probability of success.")
    confidence_type: str = "heuristic_signal_strength"
    status: str = "available"
    horizon: str = "5 trading days"
    reason: str = ""
    suppressed: bool = False
    suppression_reason: str | None = None


class RecommendationComponent(BaseModel):
    score: float | None = Field(default=None, ge=-1, le=1, description="Directional component score in [-1, 1]; null when unavailable.")
    status: str = "unavailable"
    availability_reason: str | None = Field(default=None, description="Why the component score is unavailable, when applicable.")
    configured_weight: float = Field(default=0.0, ge=0, le=1)
    effective_weight: float = Field(default=0.0, ge=0, le=1)
    details: dict = Field(default_factory=dict, description="Source probabilities, observation date, and component-specific evidence.")


class RecommendationMarketData(BaseModel):
    as_of: str | None = None
    freshness: str = "unknown"
    age_calendar_days: int | None = None
    age_trading_days: int | None = None
    analysis_as_of: str | None = None
    analysis_freshness: str = "unknown"
    analysis_age_calendar_days: int | None = None
    analysis_age_trading_days: int | None = None
    current_price: float | None = None
    currency: str = "PKR"


class RecommendationRiskLevels(BaseModel):
    target_price: float | None = None
    stop_loss: float | None = None
    expected_range: ExpectedPriceRange | None = None
    atr_14: float | None = None
    upside_pct: float | None = None
    downside_pct: float | None = None
    risk_reward_ratio: float | None = None
    method: str | None = None
    explanation: str | None = None


class RecommendationItem(BaseModel):
    """Compact recommendation card with grouped decision, components, data, and risk."""

    symbol: str
    name: str | None = None
    sector: str | None = None
    decision: RecommendationDecision
    components: dict[str, RecommendationComponent]
    market_data: RecommendationMarketData
    risk: RecommendationRiskLevels
    summary: str


class RecommendationsListResponse(BaseModel):
    """List of stock recommendations, sorted by composite score."""

    model_config = {
        "json_schema_extra": {
            "examples": [{
                "count": 1,
                "risk_profile": "moderate",
                "recommendations": [{
                    "symbol": "OGDC", "name": "OGDC", "sector": "Energy",
                    "decision": {"signal": "BUY", "composite_score": 0.36, "confidence": 0.72,
                                 "status": "available", "horizon": "5 trading days", "suppressed": False},
                    "components": {"ml": {"score": 0.4, "status": "available", "configured_weight": 0.3, "effective_weight": 0.3}},
                    "market_data": {"as_of": "2026-09-24", "freshness": "fresh", "age_calendar_days": 1,
                                    "age_trading_days": 1, "current_price": 142.5, "currency": "PKR"},
                    "risk": {"target_price": 148.0, "stop_loss": 138.0, "risk_reward_ratio": 1.22,
                             "method": "atr_band"},
                    "summary": "Buy: ML forecast leads the combined signals (+0.400)",
                }],
            }],
        }
    }

    count: int = Field(
        ..., description="Number of recommendations returned"
    )
    total_count: int = Field(..., description="Number of recommendations matching filters before applying limit.")
    generated_at: datetime = Field(..., description="UTC time when this response was assembled.")
    risk_profile: str = Field(
        ..., description="Risk profile used for target/stop calculation",
        examples=["moderate"],
    )
    recommendations: list[RecommendationItem]


class RecommendationDetailResponse(BaseModel):
    """Structured recommendation detail for a single symbol."""

    symbol: str
    name: str | None = None
    sector: str | None = None
    generated_at: datetime
    decision: RecommendationDecision
    components: dict[str, RecommendationComponent]
    market_data: RecommendationMarketData
    risk: RecommendationRiskLevels
    risk_profile: str = "moderate"
    summary: str


class TargetStopResponse(BaseModel):
    """Target price and stop-loss for a single symbol."""

    symbol: str
    generated_at: datetime
    decision: RecommendationDecision
    market_data: RecommendationMarketData
    risk: RecommendationRiskLevels
    risk_profile: str = "moderate"


class EngineWeightsRequest(BaseModel):
    gru_weight: float = Field(0.40, ge=0.0, le=1.0, description="Weight for the ML signal; field name retained for API compatibility.")
    ml_weight: float | None = Field(default=None, ge=0.0, le=1.0, description="Canonical Android/mobile field for the XGBoost ML signal weight.")
    technical_weight: float = Field(0.35, ge=0.0, le=1.0)
    fundamental_weight: float = Field(0.25, ge=0.0, le=1.0)
    sentiment_weight: float = Field(0.0, ge=0.0, le=1.0, description="Weight for recent per-stock FinBERT news sentiment.")

    @model_validator(mode="before")
    @classmethod
    def accept_canonical_ml_weight(cls, values):
        if isinstance(values, dict) and values.get("ml_weight") is not None:
            if "gru_weight" in values and abs(float(values["gru_weight"]) - float(values["ml_weight"])) > 1e-6:
                raise ValueError("gru_weight and ml_weight must match when both are provided")
            values = {**values, "gru_weight": values["ml_weight"]}
        return values

    @model_validator(mode="after")
    def weights_must_sum_to_one(self):
        total = self.gru_weight + self.technical_weight + self.fundamental_weight + self.sentiment_weight
        if abs(total - 1.0) > 1e-6:
            raise ValueError("Engine weights must sum to 1.0")
        return self


class EngineWeightsResponse(BaseModel):
    weights: dict[str, float] = Field(
        ..., description="Configured normalized source weights keyed by ml, technical, fundamental, and sentiment.",
        examples=[{"ml": 0.3, "technical": 0.25, "fundamental": 0.25, "sentiment": 0.2}],
    )


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
    status: str = "available"
    message: str | None = None
    portfolio_value: float | None = None
    covered_portfolio_value: float | None = None
    var_loss_amount: float | None = None
    cvar_loss_amount: float | None = None
    currency: str = "PKR"
    symbols_used: list[str] = Field(default_factory=list)
    symbols_excluded: list[str] = Field(default_factory=list)
    data_as_of: str | None = None
    lookback_start: str | None = None


class MonteCarloRequest(BaseModel):
    """Request body for starting a Monte Carlo simulation."""

    num_simulations: int = Field(
        default=1000,
        ge=100,
        le=10000,
        description="Number of Monte Carlo paths (simulated price trajectories)",
        examples=[1000],
    )
    horizon_days: int = Field(
        default=30,
        ge=1,
        le=365,
        description="Forecast horizon in trading days (e.g., 30 days = ~1.5 months)",
        examples=[30],
    )
    seed: int | None = Field(default=None, ge=0, le=4294967295, description="Optional seed for repeatable simulations")

    model_config = {
        "json_schema_extra": {
            "example": {
                "num_simulations": 1000,
                "horizon_days": 30
            }
        }
    }


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
    message: str | None = None
    portfolio_value: float | None = None
    currency: str | None = None
    method: str | None = None
    assumptions: str | None = None
    data_as_of: str | None = None
    symbols_used: list[str] = Field(default_factory=list)
    symbols_excluded: list[str] = Field(default_factory=list)
    tail_estimate_reliable: bool | None = None


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
    status: str = "available"
    method: str = "illustrative_one_step_sector_shock"
    worst_case_loss_value: float | None = None
    assumption_note: str | None = None
    currency: str = "PKR"


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
    confidence: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Confidence level in the sentiment signal (0 to 1)",
        examples=[0.82],
    )
    positive_ratio: float | None = Field(
        default=None,
        description="Proportion of positive news items (0.0 to 1.0)",
        examples=[0.75],
    )
    neutral_ratio: float | None = Field(
        default=None,
        description="Proportion of neutral news items (0.0 to 1.0)",
        examples=[0.15],
    )
    negative_ratio: float | None = Field(
        default=None,
        description="Proportion of negative news items (0.0 to 1.0)",
        examples=[0.10],
    )
    article_count: int = Field(
        ..., description="Number of articles/posts analyzed", examples=[12],
    )
    trend: str = Field(
        ..., description="Score trend: improving, declining, stable",
        examples=["improving"],
    )
    daily_scores: list[dict] | None = Field(
        default=None,
        description="Daily aggregated scores for chart: [{date, score, count}]",
    )
    updated_at: str | None = Field(
        default=None,
        description="ISO 8601 timestamp of analysis generation",
        examples=["2026-09-24T02:00:00Z"],
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
    score_distribution: dict | None = Field(
        default=None,
        description="Distribution: {positive: N, neutral: M, negative: K}",
    )


class SentimentHistoryPoint(BaseModel):
    """Single point in sentiment history time series."""

    date: str = Field(..., examples=["2026-09-15"])
    score: float = Field(..., examples=[0.35])
    label: str = Field(..., examples=["positive"])
    article_count: int = Field(default=0)
    positive_ratio: float | None = None
    neutral_ratio: float | None = None
    negative_ratio: float | None = None
    trend: str | None = None
    daily_scores: list[dict] | None = None


class SentimentHistoryResponse(BaseModel):
    """Historical sentiment time series for a symbol."""

    symbol: str = Field(..., examples=["OGDC"])
    period: str = Field(..., examples=["1M"])
    data: list[SentimentHistoryPoint]


class SentimentNewsItem(BaseModel):
    """News article with sentiment."""

    id: str
    title: str
    source: str | None = None
    published_at: str | None = None
    url: str | None = None
    sentiment: str | None = None
    sentiment_score: float | None = None
    sentiment_model: str | None = None
    positive_score: float | None = None
    neutral_score: float | None = None
    negative_score: float | None = None


class SentimentNewsResponse(BaseModel):
    """Paginated news with sentiment for a symbol."""

    symbol: str = Field(..., examples=["OGDC"])
    items: list[SentimentNewsItem]
    total: int
    page: int
    limit: int
