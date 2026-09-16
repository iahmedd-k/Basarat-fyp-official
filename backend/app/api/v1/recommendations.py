"""Recommendation API — personalized stock recommendations with signal synthesis.

Returns clean, flat JSON optimized for frontend rendering.
"""

import logging

from fastapi import APIRouter, Depends, Query
from pathlib import Path

import pandas as pd
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.ml.serving.schemas import (
    EngineWeightsRequest,
    EngineWeightsResponse,
    RecommendationItem,
    RecommendationDetailResponse,
    RecommendationsListResponse,
    TargetStopResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()

_user_weights: dict[str, dict] = {}


def _get_user_risk_profile(user: User) -> str:
    return getattr(user, "risk_tolerance", None) or "moderate"


def _summarize(r: dict) -> str:
    """One-line summary from recommendation dict."""
    signal = r.get("signal", "hold").upper()
    reasoning = r.get("reasoning", {})
    ml_reason = reasoning.get("ml", {}).get("reason", "")
    tech_reason = reasoning.get("technical", {}).get("reason", "")
    core_score = r.get("composite_score", 0)

    parts = []
    if signal == "BUY":
        parts.append("Strong buy")
    elif signal == "SELL":
        parts.append("Sell signal")
    else:
        parts.append("Hold")

    if ml_reason:
        parts.append(ml_reason)
    if tech_reason:
        parts.append(tech_reason)

    return ": ".join(parts[:2]) if len(parts) > 1 else parts[0]


@router.get(
    "/recommendations",
    response_model=RecommendationsListResponse,
    summary="Get stock recommendations",
)
async def get_recommendations(
    risk_profile: str = Query("moderate", pattern="^(conservative|moderate|aggressive)$"),
    sector: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        from app.services.recommendation_service import (
            RecommendationEngine,
            get_cached_recommendations,
        )

        effective_risk = risk_profile or _get_user_risk_profile(user)

        cached = get_cached_recommendations()
        if cached is not None:
            recommendations = cached
        else:
            engine = RecommendationEngine()
            recommendations = engine.get_all_recommendations(
                risk_tolerance=effective_risk,
                sector_filter=sector,
            )

        if sector:
            recommendations = [
                r for r in recommendations
                if r.get("sector", "").lower() == sector.lower()
            ]

        recommendations = recommendations[:limit]

        items = [
            RecommendationItem(
                symbol=r["symbol"],
                signal=r["signal"].upper(),
                confidence=round(r["confidence"], 3),
                composite_score=round(r.get("composite_score", 0), 3),
                target_price=r.get("target_price"),
                stop_loss=r.get("stop_loss"),
                summary=_summarize(r),
            )
            for r in recommendations
        ]

        return RecommendationsListResponse(
            count=len(items),
            risk_profile=effective_risk,
            recommendations=items,
        )

    except Exception as exc:
        log.exception("Failed to fetch recommendations")
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

        from app.services.recommendation_service import RecommendationEngine

        engine = RecommendationEngine()
        rec = engine.get_recommendation(
            symbol,
            risk_tolerance=_get_user_risk_profile(user),
        )

        reasoning = rec.get("reasoning", {})

        signals = {
            "ml": round(reasoning.get("ml", {}).get("signal", 0), 3)
                  if isinstance(reasoning.get("ml"), dict) else 0,
            "technical": round(reasoning.get("technical", {}).get("signal", 0), 3)
                         if isinstance(reasoning.get("technical"), dict) else 0,
            "fundamental": round(reasoning.get("fundamental", {}).get("signal", 0), 3)
                           if isinstance(reasoning.get("fundamental"), dict) else 0,
        }

        return RecommendationDetailResponse(
            symbol=symbol,
            signal=rec["signal"].upper(),
            confidence=round(rec["confidence"], 3),
            composite_score=round(rec.get("composite_score", 0), 3),
            signals=signals,
            target_price=rec.get("target_price"),
            stop_loss=rec.get("stop_loss"),
            current_price=rec.get("current_price"),
            atr_14=rec.get("atr_14"),
            reasoning=reasoning,
            weights=engine._weights,
        )

    except Exception as exc:
        log.exception("Failed to fetch recommendation for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch recommendation: {exc}")


@router.get(
    "/recommendations/{symbol}/target-stop",
    response_model=TargetStopResponse,
    summary="Get target price and stop loss",
)
async def get_target_stop(
    symbol: str,
    user: User = Depends(get_current_user),
):
    try:
        symbol = symbol.upper()

        from app.services.recommendation_service import RecommendationEngine

        features_path = Path("data/features/features_daily.parquet")
        if not features_path.exists():
            return TargetStopResponse(
                symbol=symbol,
                method="atr_band",
                risk_tolerance=_get_user_risk_profile(user),
            )

        df = pd.read_parquet(features_path)
        df["date"] = pd.to_datetime(df["date"])
        sym_df = df[df["symbol"] == symbol].copy().sort_values("date").reset_index(drop=True)

        engine = RecommendationEngine()
        result = engine.compute_target_stop(
            symbol,
            sym_df,
            risk_tolerance=_get_user_risk_profile(user),
        )

        current = result.get("current_price")
        target = result.get("target_price")
        stop = result.get("stop_loss")

        upside = round((target - current) / current * 100, 1) if current and target else None
        downside = round((stop - current) / current * 100, 1) if current and stop else None

        return TargetStopResponse(
            symbol=symbol,
            current_price=current,
            target_price=target,
            stop_loss=stop,
            method=result.get("method", "atr_band"),
            atr_14=result.get("atr_14"),
            risk_tolerance=_get_user_risk_profile(user),
            upside_pct=upside,
            downside_pct=downside,
        )

    except Exception as exc:
        log.exception("Failed to fetch target/stop for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch target/stop: {exc}")


@router.post(
    "/recommendations/engine-weights",
    response_model=EngineWeightsResponse,
    summary="Set custom engine weights",
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
