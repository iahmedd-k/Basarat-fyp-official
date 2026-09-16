"""Forecast API — ML inference endpoints.

Returns clean, flat JSON optimized for frontend rendering.
"""

import logging
from datetime import timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.ml.serving.inference import (
    InsufficientHistoryError,
    SymbolNotFoundError,
    get_forecast,
)
from app.ml.serving.model_loader import artifacts
from app.ml.serving.prediction_logger import log_prediction
from app.models.prediction import Prediction
from app.models.user import User

from app.ml.serving.schemas import (
    ErrorResponse,
    ForecastHistoryItem,
    ForecastHistoryResponse,
    ForecastResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/forecast/{symbol}",
    response_model=ForecastResponse,
    summary="Get ML forecast for a stock",
    responses={
        404: {"model": ErrorResponse, "description": "Symbol not found"},
        503: {"model": ErrorResponse, "description": "ML model not ready"},
    },
)
async def get_stock_forecast(
    symbol: str,
    horizon: str = Query("1D", pattern="^(1D|1W|1M)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        if not artifacts.model_ready:
            raise ServiceUnavailableError("ML model is not loaded yet")

        result = get_forecast(symbol, horizon=horizon)

        # Log prediction to database
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
        )

        # Build optimized response
        return _build_forecast_response(result, horizon)

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


def _build_forecast_response(result: dict, horizon: str) -> ForecastResponse:
    """Transform raw inference output into optimized response schema."""
    direction = result["direction"]
    top_prob = result["top_class_probability"]
    confidence = round(top_prob / 100.0, 3)

    probabilities = {
        "bullish": result["bullish_pct"],
        "bearish": result["bearish_pct"],
        "sideways": result["sideways_pct"],
    }

    # Transform model_details into cleaner format
    models = None
    if result.get("model_details"):
        models = {}
        for model_name, detail in result["model_details"].items():
            short_name = "gru" if "gru" in model_name else "xgb" if "xgb" in model_name else model_name
            models[short_name] = {
                "direction": detail["direction"],
                "bullish_pct": detail["bullish_pct"],
                "bearish_pct": detail["bearish_pct"],
                "sideways_pct": detail["sideways_pct"],
                "gap_pp": detail["gap_pp"],
            }

    # Get current price from market context
    market_ctx = result.get("market_context")
    current_price = None
    if market_ctx:
        stock_ret_20d = market_ctx.get("stock_return_20d")
        # We don't have current_price directly, but we can estimate from context
        # The actual price is available through stock_service, skip for now

    return ForecastResponse(
        symbol=result["symbol"],
        horizon=horizon,
        direction=direction,
        confidence=confidence,
        probabilities=probabilities,
        as_of_date=result["as_of_date"],
        target_date=result["predicted_for_date"],
        current_price=current_price,
        model_version=result["model_version"],
        gate_reason=result.get("gate_reason", ""),
        models=models,
        market_context=market_ctx,
    )


@router.get(
    "/forecast/{symbol}/history",
    response_model=ForecastHistoryResponse,
    summary="Get historical forecast accuracy",
    responses={
        404: {"model": ErrorResponse, "description": "Symbol not found"},
    },
)
async def get_forecast_history(
    symbol: str,
    limit: int = Query(30, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        symbol = symbol.upper()

        result = await db.execute(
            select(Prediction)
            .where(Prediction.symbol == symbol)
            .order_by(Prediction.predicted_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

        if not rows:
            raise NotFoundError(f"No forecast history found for symbol '{symbol}'")

        # Build optimized history items
        items = []
        scored_count = 0
        correct_count = 0

        for row in rows:
            probs = {
                "bullish": row.bullish_pct,
                "bearish": row.bearish_pct,
                "sideways": row.sideways_pct,
            }
            conf = round(row.top_class_probability / 100.0, 3) if row.top_class_probability else 0

            actual = None
            if row.actual_direction is not None:
                actual = {
                    "direction": row.actual_direction,
                    "was_correct": row.was_correct,
                }
                if row.predicted_direction != "uncertain":
                    scored_count += 1
                    if row.was_correct:
                        correct_count += 1

            items.append(ForecastHistoryItem(
                predicted_at=row.predicted_at,
                predicted_direction=row.predicted_direction,
                probabilities=probs,
                confidence=conf,
                target_date=row.target_date,
                actual=actual,
            ))

        accuracy = round(correct_count / scored_count, 4) if scored_count > 0 else None

        return ForecastHistoryResponse(
            symbol=symbol,
            horizon="1D",
            count=len(items),
            accuracy=accuracy,
            history=items,
        )

    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Failed to fetch forecast history for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch forecast history: {exc}")
