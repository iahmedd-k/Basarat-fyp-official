from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    EngineWeightsRequest,
    EngineWeightsResponse,
    RecommendationDetailResponse,
    RecommendationsListResponse,
    RecommendationResponse,
    TargetStopResponse,
)

router = APIRouter()

_user_weights: dict[str, dict] = {}


@router.get(
    "/recommendations",
    response_model=RecommendationsListResponse,
    summary="Get stock recommendations based on risk profile",
)
async def get_recommendations(
    risk_profile: str = Query("moderate", pattern="^(conservative|moderate|aggressive)$"),
    sector: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        return RecommendationsListResponse(
            recommendations=[],
            risk_profile=risk_profile,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch recommendations: {exc}")


@router.get(
    "/recommendations/{symbol}",
    response_model=RecommendationDetailResponse,
    summary="Get detailed recommendation for a stock",
)
async def get_recommendation_detail(
    symbol: str,
    user: User = Depends(get_current_user),
):
    try:
        symbol = symbol.upper()
        return RecommendationDetailResponse(
            symbol=symbol,
            name=symbol,
            signal="hold",
            confidence=0.5,
            target_price=None,
            stop_loss=None,
            reasoning={"technical": "No data", "fundamental": "No data", "sentiment": "No data"},
            technical_score=None,
            fundamental_score=None,
            sentiment_score=None,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch recommendation: {exc}")


@router.get(
    "/recommendations/{symbol}/target-stop",
    response_model=TargetStopResponse,
    summary="Get target price and stop loss for a stock",
)
async def get_target_stop(
    symbol: str,
    user: User = Depends(get_current_user),
):
    try:
        symbol = symbol.upper()
        return TargetStopResponse(
            symbol=symbol,
            target_price=None,
            stop_loss=None,
            method="technical_analysis",
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch target/stop: {exc}")


@router.post(
    "/recommendations/engine-weights",
    response_model=EngineWeightsResponse,
    summary="Set custom engine weights for recommendations",
)
async def set_engine_weights(
    data: EngineWeightsRequest,
    user: User = Depends(get_current_user),
):
    try:
        _user_weights[user.id] = {
            "gru_weight": data.gru_weight,
            "technical_weight": data.technical_weight,
            "fundamental_weight": data.fundamental_weight,
        }
        return EngineWeightsResponse(
            gru_weight=data.gru_weight,
            technical_weight=data.technical_weight,
            fundamental_weight=data.fundamental_weight,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to set engine weights: {exc}")
