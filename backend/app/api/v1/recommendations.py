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
    parts = []
    if signal == "BUY":
        parts.append("Strong buy")
    elif signal == "SELL":
        parts.append("Sell signal")
    else:
        parts.append("Hold")

    detail = ml_reason or tech_reason
    if not detail:
        for source in ("ml", "technical", "fundamental"):
            factors = reasoning.get(source, {})
            if isinstance(factors, dict):
                detail = next((f"{key}: {value}" for key, value in factors.items() if isinstance(value, (str, int, float))), "")
                if detail:
                    break
    if detail:
        parts.append(detail)

    return ": ".join(parts[:2]) if len(parts) > 1 else parts[0]


@router.get(
    "/recommendations",
    response_model=RecommendationsListResponse,
    summary="Get stock recommendations",
)
async def get_recommendations(
    risk_profile: str | None = Query(None, pattern="^(conservative|moderate|aggressive)$"),
    sector: str | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        from app.services.recommendation_service import (
            RecommendationEngine,
            get_cached_recommendations,
        )

        effective_risk = risk_profile or _get_user_risk_profile(user)

        cached = get_cached_recommendations() if effective_risk == "moderate" else None
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
                name=r.get("name"),
                sector=r.get("sector"),
                signal=r["signal"].upper(),
                confidence=round(r["confidence"], 3),
                composite_score=round(r.get("composite_score", 0), 3),
                current_price=r.get("current_price"),
                target_price=r.get("target_price"),
                stop_loss=r.get("stop_loss"),
                expected_range=r.get("expected_range"),
                upside_pct=r.get("upside_pct"),
                downside_pct=r.get("downside_pct"),
                risk_reward_ratio=r.get("risk_reward_ratio"),
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
    "/recommendations/engine-weights",
    response_model=EngineWeightsResponse,
    summary="Get current or default engine weights",
)
async def get_engine_weights(
    user: User = Depends(get_current_user),
):
    try:
        from app.services.recommendation_service import DEFAULT_WEIGHTS
        user_w = _user_weights.get(user.id, {})
        return EngineWeightsResponse(
            gru_weight=user_w.get("gru_weight", DEFAULT_WEIGHTS.get("gru", 0.40)),
            technical_weight=user_w.get("technical_weight", DEFAULT_WEIGHTS.get("technical", 0.35)),
            fundamental_weight=user_w.get("fundamental_weight", DEFAULT_WEIGHTS.get("fundamental", 0.25)),
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to get engine weights: {exc}")


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

        from app.services.recommendation_service import RecommendationEngine, DEFAULT_WEIGHTS

        engine = RecommendationEngine()
        rec = engine.get_recommendation(
            symbol,
            risk_tolerance=_get_user_risk_profile(user),
        )

        reasoning = rec.get("reasoning", {})

        signals = rec.get("signals") or {"ml": 0.0, "technical": 0.0, "fundamental": 0.0}

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
            expected_range=rec.get("expected_range"),
            upside_pct=rec.get("upside_pct"),
            downside_pct=rec.get("downside_pct"),
            risk_reward_ratio=rec.get("risk_reward_ratio"),
            target_stop_method=rec.get("target_stop_method"),
            risk_profile=_get_user_risk_profile(user),
            reasoning=reasoning,
            weights=rec.get("weights", getattr(engine, "weights", DEFAULT_WEIGHTS)),
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
        sym_df = pd.DataFrame()
        if features_path.exists():
            try:
                df = pd.read_parquet(features_path)
                df["date"] = pd.to_datetime(df["date"])
                sym_df = df[df["symbol"] == symbol].copy().sort_values("date").reset_index(drop=True)
            except Exception as parquet_err:
                log.warning("Error reading parquet in get_target_stop: %s", parquet_err)

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
        risk = abs(current - stop) if current and stop else 0
        reward = abs(target - current) if current and target else 0
        risk_reward = round(reward / risk, 2) if risk > 0 and reward > 0 else None

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
            expected_range=result.get("expected_range"),
            risk_reward_ratio=risk_reward,
        )

    except Exception as exc:
        log.exception("Failed to fetch target/stop for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch target/stop: {exc}")
