"""Forecast API — GRU model inference endpoints."""

import logging

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

        result = get_forecast(symbol)

        await log_prediction(
            db,
            symbol=result["symbol"],
            horizon=result["horizon"],
            predicted_direction=result["direction"],
            bullish_pct=result["bullish_pct"],
            bearish_pct=result["bearish_pct"],
            sideways_pct=result["sideways_pct"],
            confidence=result["confidence"],
            as_of_date=result["as_of_date"],
            target_date=result["predicted_for_date"],
            model_version=result["model_version"],
        )

        return ForecastResponse(**result)

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

        items = [
            ForecastHistoryItem(
                predicted_at=row.predicted_at,
                predicted_direction=row.predicted_direction,
                bullish_pct=row.bullish_pct,
                bearish_pct=row.bearish_pct,
                sideways_pct=row.sideways_pct,
                confidence=row.confidence,
                target_date=row.target_date,
                actual_direction=row.actual_direction,
                was_correct=row.was_correct,
            )
            for row in rows
        ]

        return ForecastHistoryResponse(symbol=symbol, history=items)

    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Failed to fetch forecast history for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch forecast history: {exc}")
