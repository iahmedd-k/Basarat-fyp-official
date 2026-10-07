"""Forecast API — ML predict, save, and history (professional contract).

Core flow:
  GET /forecast/{symbol}           → predict + upsert into predictions
  GET /forecast/{symbol}/history   → read saved predictions + real outcomes only

Outcomes are written only by Celery evaluate_pending (after target close is in features).
History never invents sideways/actual labels.
"""

import logging
import math
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from starlette.concurrency import run_in_threadpool
from sqlalchemy import case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.redis import cache_get, cache_set
from app.db.session import get_db
from app.ml.serving.inference import (
    InsufficientHistoryError,
    SymbolNotFoundError,
    get_forecast,
)
from app.ml.serving.model_loader import artifacts
from app.ml.serving.prediction_logger import log_prediction
from app.ml.serving.prediction_store import pkt_today
from app.models.prediction import Prediction
from app.models.event import MarketEvent
from app.models.stock import Stock
from app.models.user import User
from app.services.news_pipeline.market_schedule import is_market_hours

from app.ml.serving.schemas import (
    ErrorResponse,
    ForecastHistoryItem,
    ForecastHistoryResponse,
    ForecastSummaryResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/forecast/{symbol}",
    response_model=ForecastSummaryResponse,
    summary="Predict bullish/bearish/sideways and save to history",
    responses={
        404: {"model": ErrorResponse, "description": "Symbol not found"},
        503: {"model": ErrorResponse, "description": "ML model not ready"},
    },
)
async def get_stock_forecast(
    symbol: str,
    horizon: str = Query(
        "1W",
        pattern="^(1D|1W|2W|1M)$",
        description="Forecast horizon: '1D' (1 trading day), '1W' (5 trading days, default), '2W' (10 trading days), or '1M' (22 trading days).",
    ),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Run ensemble inference for a PSX symbol, **upsert** the prediction into
    `predictions`, and return the live forecast payload.

    Daily batch also upserts all active symbols at 18:00 PKT. Calling this
    endpoint mid-day refreshes the same unique (symbol, horizon, as_of_date) row.
    """
    try:
        symbol_upper = symbol.strip().upper()

        # Enforce KSE-100 universe constraint
        from app.data.scraper.symbol_universe import get_active_symbols
        try:
            kse_symbols = {s["symbol"].upper() for s in get_active_symbols()}
        except Exception:
            kse_symbols = set()

        if kse_symbols and symbol_upper not in kse_symbols:
            raise NotFoundError(
                f"Symbol '{symbol_upper}' is not part of the active KSE-100 universe. "
                "AI Forecasts and Ensemble ML models are trained and calibrated exclusively for KSE-100 constituent stocks."
            )

        if not artifacts.model_ready:
            raise ServiceUnavailableError("ML model is not loaded yet")

        result = await run_in_threadpool(get_forecast, symbol_upper, horizon=horizon)

        await log_prediction(
            db,
            symbol=result["symbol"],
            horizon=result["horizon"],
            predicted_direction=result["direction"],
            bullish_pct=result["bullish_pct"],
            bearish_pct=result["bearish_pct"],
            sideways_pct=result["sideways_pct"],
            top_class_probability=result["top_class_probability"],
            as_of_date=result["as_of_date"],
            target_date=result["predicted_for_date"],
            model_version=result["model_version"],
            gate_reason=result.get("gate_reason", ""),
            model_details=result.get("model_details"),
        )

        stock_name_result = await db.execute(
            select(Stock.name).where(func.upper(Stock.symbol) == symbol_upper).limit(1)
        )
        stock_name = stock_name_result.scalar_one_or_none()

        horizon_ends = _as_date(result["predicted_for_date"])
        today = pkt_today()
        events_result = await db.execute(
            select(MarketEvent)
            .where(
                MarketEvent.event_date >= today,
                MarketEvent.event_date <= horizon_ends,
                or_(MarketEvent.symbol == symbol_upper, MarketEvent.symbol.is_(None)),
            )
            .order_by(MarketEvent.event_date.asc())
        )
        events = [
            {"type": _event_type_for_response(event), "date": event.event_date}
            for event in events_result.scalars().all()
        ]

        record_result = await db.execute(
            select(
                func.count(Prediction.id),
                func.sum(case((Prediction.was_correct.is_(True), 1), else_=0)),
            ).where(
                Prediction.symbol == symbol_upper,
                Prediction.horizon == horizon,
                Prediction.actual_direction.is_not(None),
                Prediction.predicted_direction.in_(("bullish", "bearish")),
            )
        )
        evaluated_count, correct_count = record_result.one()
        track_record = None
        if evaluated_count:
            track_record = {
                "evaluated_predictions": evaluated_count,
                "accuracy_pct": round((correct_count or 0) / evaluated_count * 100, 1),
            }

        return _build_forecast_response(
            result,
            horizon,
            name=stock_name,
            upcoming_events=events,
            track_record=track_record,
            market_open=await is_market_hours(),
        )

    except SymbolNotFoundError as exc:
        raise NotFoundError(str(exc))
    except InsufficientHistoryError as exc:
        raise ServiceUnavailableError(str(exc))
    except ServiceUnavailableError:
        raise
    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Forecast failed for %s", symbol)
        raise ServiceUnavailableError(f"Failed to generate forecast: {exc}")


def _as_date(value) -> date:
    if isinstance(value, datetime):
        return value.date()
    return value if isinstance(value, date) else date.fromisoformat(str(value)[:10])


def _finite_float(value) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _response_direction(direction: str) -> str:
    return {
        "bullish": "up",
        "buy": "up",
        "up": "up",
        "bearish": "down",
        "sell": "down",
        "down": "down",
        "sideways": "sideways",
        "uncertain": "uncertain",
    }.get(str(direction).lower(), "uncertain")


def _event_type_for_response(event: MarketEvent) -> str:
    if event.event_type == "dividend":
        text = f"{event.title} {event.description or ''}".casefold()
        if "ex-date" in text or "ex date" in text or "ex-dividend" in text or "ex dividend" in text:
            return "dividend_ex_date"
    return event.event_type


def _build_forecast_response(
    result: dict,
    horizon: str,
    *,
    name: str | None = None,
    upcoming_events: list[dict] | None = None,
    track_record: dict | None = None,
    market_open: bool = False,
) -> ForecastSummaryResponse:
    """Shape actual inference, feature, and persistence values into the public contract."""
    trading_days_by_horizon = {"1D": 1, "1W": 5, "2W": 10, "1M": 22}
    trading_days = trading_days_by_horizon[horizon]
    data_as_of = _as_date(result["as_of_date"])
    target_date = _as_date(result["predicted_for_date"])
    current_price = _finite_float(result.get("current_price"))
    volatility_14d = _finite_float(result.get("volatility_14d"))

    lower = upper = None
    if current_price is not None and current_price > 0 and volatility_14d is not None and volatility_14d >= 0:
        distance = current_price * volatility_14d * math.sqrt(trading_days)
        lower = round(max(0.0, current_price - distance), 2)
        upper = round(current_price + distance, 2)

    raw_direction = _response_direction(result["direction"])
    top_probability = _finite_float(result.get("top_class_probability")) or 0.0
    strength = "high" if top_probability >= 75 else "medium" if top_probability >= 60 else "low"

    bullish_pct = _finite_float(result.get("bullish_pct"))
    bearish_pct = _finite_float(result.get("bearish_pct"))
    directional_total = (bullish_pct or 0.0) + (bearish_pct or 0.0)
    up_probability = down_probability = None
    if directional_total > 0:
        up_probability = round((bullish_pct or 0.0) / directional_total * 100, 1)
        down_probability = round((bearish_pct or 0.0) / directional_total * 100, 1)

    model_summaries = []
    model_directions = []
    for model_name, detail in (result.get("model_details") or {}).items():
        model_direction = _response_direction(detail.get("direction", "uncertain"))
        model_probability_key = {
            "up": "bullish_pct",
            "down": "bearish_pct",
            "sideways": "sideways_pct",
        }.get(model_direction)
        model_probability = _finite_float(detail.get(model_probability_key)) if model_probability_key else None
        if model_probability is None:
            model_probability = _finite_float(detail.get("top_class_probability"))
        if model_probability is None:
            continue
        normalized_name = "gru" if "gru" in model_name.casefold() else "xgb" if "xgb" in model_name.casefold() else model_name
        model_summaries.append({
            "name": normalized_name,
            "direction": model_direction,
            "pct": round(model_probability, 1),
        })
        model_directions.append(model_direction)

    if len(model_directions) >= 2:
        agreement = "full" if len(set(model_directions)) == 1 else "partial"
    else:
        agreement = "partial" if model_directions else "none"

    market_context = result.get("market_context") or {}
    movement = {}
    movement_fields = {
        "stock_5d_pct": "stock_return_5d",
        "stock_20d_pct": "stock_return_20d",
        "market_5d_pct": "market_return_5d",
        "market_20d_pct": "market_return_20d",
    }
    for output_field, source_field in movement_fields.items():
        value = _finite_float(market_context.get(source_field))
        movement[output_field] = round(value * 100, 2) if value is not None else None

    stock_20d = _finite_float(market_context.get("stock_return_20d"))
    market_20d = _finite_float(market_context.get("market_return_20d"))
    vs_market = None
    if stock_20d is not None and market_20d is not None:
        delta = stock_20d - market_20d
        vs_market = "in_line" if abs(delta) < 0.001 else "stronger" if delta > 0 else "weaker"

    pkt_today_date = pkt_today()
    return ForecastSummaryResponse(
        schema_version=1,
        symbol=result["symbol"],
        name=name,
        currency="PKR",
        generated_at=datetime.now(timezone.utc),
        data_as_of=data_as_of,
        freshness="fresh" if data_as_of >= pkt_today_date - timedelta(days=3) else "stale",
        market_status="open" if market_open else "closed",
        horizon={"code": horizon, "trading_days": trading_days, "ends_on": target_date},
        available_horizons=["1D", "1W", "2W", "1M"],
        price={"current": round(current_price, 2) if current_price is not None else None},
        outlook={"direction": raw_direction, "strength": strength},
        levels={"lower": lower, "upper": upper, "basis": "volatility_14d"},
        recent_movement={**movement, "vs_market": vs_market},
        agreement=agreement,
        upcoming_events=upcoming_events or [],
        track_record=track_record,
        details={
            "up_probability_pct": up_probability,
            "down_probability_pct": down_probability,
            "models": model_summaries,
            "indicators": {
                "rsi": _finite_float(result.get("rsi")),
                "macd_hist": _finite_float(result.get("macd_hist")),
            },
        },
    )


@router.get(
    "/forecast/{symbol}/history",
    response_model=ForecastHistoryResponse,
    summary="Get saved forecast history and real accuracy",
    responses={
        404: {"model": ErrorResponse, "description": "No history for symbol"},
    },
)
async def get_forecast_history(
    symbol: str,
    horizon: str = Query("1W", pattern="^(1D|1W|2W|1M)$", description="Filter by prediction horizon"),
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Read durable predictions for a symbol.

    - **evaluated**: `actual_direction` set by the daily evaluate job from real closes
    - **pending_target_date**: target session not finished yet (PKT)
    - **pending_evaluation**: target day passed but close not scored yet (job pending / missing data)

    This endpoint is read-only — it never invents outcomes.
    """
    try:
        symbol_upper = symbol.strip().upper()

        # Enforce KSE-100 universe constraint
        from app.data.scraper.symbol_universe import get_active_symbols
        try:
            kse_symbols = {s["symbol"].upper() for s in get_active_symbols()}
        except Exception:
            kse_symbols = set()

        if kse_symbols and symbol_upper not in kse_symbols:
            raise NotFoundError(
                f"Symbol '{symbol_upper}' is not part of the active KSE-100 universe. "
                "AI Forecast history is tracked exclusively for KSE-100 constituent stocks."
            )

        cache_key = f"forecast:history:v2:{symbol_upper}:{horizon}:{limit}"
        cached = await cache_get(cache_key)
        if cached:
            return ForecastHistoryResponse(**cached)

        today = pkt_today()

        result = await db.execute(
            select(Prediction)
            .where(
                Prediction.symbol == symbol_upper,
                Prediction.horizon == horizon,
            )
            .order_by(Prediction.as_of_date.desc(), Prediction.predicted_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

        if not rows:
            raise NotFoundError(
                f"No forecast history found for symbol '{symbol_upper}' horizon '{horizon}'. "
                "Predictions appear after GET /forecast/{symbol} or the 18:00 PKT daily job."
            )

        items = []
        scored_count = 0
        correct_count = 0
        neutral_count = 0
        pending_count = 0

        for row in rows:
            probs = {
                "bullish": row.bullish_pct,
                "bearish": row.bearish_pct,
                "sideways": row.sideways_pct,
            }
            conf = round(row.top_class_probability / 100.0, 3) if row.top_class_probability else 0

            if row.actual_direction is not None:
                actual = {
                    "status": "evaluated",
                    "direction": row.actual_direction,
                    "was_correct": row.was_correct,
                    "evaluation_note": (
                        f"Market outcome evaluated as '{row.actual_direction}' "
                        f"using close on target date {row.target_date}."
                    ),
                }
                if row.predicted_direction in ("bullish", "bearish"):
                    scored_count += 1
                    if row.was_correct:
                        correct_count += 1
                else:
                    neutral_count += 1
            elif row.target_date > today:
                pending_count += 1
                actual = {
                    "status": "pending_target_date",
                    "direction": "pending",
                    "was_correct": None,
                    "evaluation_note": (
                        f"Prediction active. Target date ({row.target_date}) has not completed yet (PKT)."
                    ),
                }
            else:
                pending_count += 1
                actual = {
                    "status": "pending_evaluation",
                    "direction": "pending",
                    "was_correct": None,
                    "evaluation_note": (
                        f"Target date {row.target_date} has passed; waiting for daily evaluate job "
                        "once the close is present in features (normally next 18:00 PKT pipeline)."
                    ),
                }

            items.append(
                ForecastHistoryItem(
                    predicted_at=row.predicted_at,
                    predicted_direction=row.predicted_direction,
                    probabilities=probs,
                    confidence=conf,
                    as_of_date=row.as_of_date,
                    target_date=row.target_date,
                    actual=actual,
                )
            )

        accuracy = round(correct_count / scored_count, 4) if scored_count > 0 else None
        if accuracy is not None:
            accuracy_summary = (
                f"Directional accuracy: {round(accuracy * 100, 1)}% across {scored_count} "
                f"decisive bullish/bearish signals "
                f"({neutral_count} neutral; {pending_count} pending)."
            )
        elif pending_count:
            accuracy_summary = (
                f"{pending_count} prediction(s) still pending evaluation; "
                f"{neutral_count} neutral. Accuracy appears after outcomes are scored."
            )
        else:
            accuracy_summary = (
                f"All {len(items)} predictions in this window are neutral/holding regimes."
            )

        response = ForecastHistoryResponse(
            symbol=symbol_upper,
            horizon=horizon,
            count=len(items),
            accuracy=accuracy,
            accuracy_summary=accuracy_summary,
            pending_count=pending_count,
            scored_count=scored_count,
            history=items,
        )
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response

    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Failed to fetch forecast history for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch forecast history: {exc}")
