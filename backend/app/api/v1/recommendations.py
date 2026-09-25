"""Recommendation API — personalized stock recommendations with signal synthesis.

Returns clean, flat JSON optimized for frontend rendering.
"""

import logging
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query, Path as PathParam
from starlette.concurrency import run_in_threadpool
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

def _get_user_risk_profile(user: User) -> str:
    return getattr(user, "risk_tolerance", None) or "moderate"


def _get_user_weights(user: User, defaults: dict) -> dict[str, float]:
    saved = getattr(user, "recommendation_weights", None)
    if not isinstance(saved, dict):
        return defaults.copy()
    try:
        weights = {key: float(saved.get(key, 0.0)) for key in ("gru", "technical", "fundamental", "sentiment")}
        total = sum(weights.values())
        if any(value < 0 for value in weights.values()) or total <= 0:
            return defaults.copy()
        return {key: value / total for key, value in weights.items()}
    except (KeyError, TypeError, ValueError):
        return defaults.copy()


def _summarize(r: dict) -> str:
    """Summarize the decision using only components that affected the composite."""
    signal = r.get("signal", "hold").upper()
    if r.get("signal_suppressed"):
        return f"Hold: {r.get('suppression_reason') or 'signal suppressed because market data is not fresh'}"
    reasoning = r.get("reasoning") or {}
    effective = r.get("effective_weights") or {}
    source_names = {
        "gru": "ML forecast", "ml": "ML forecast", "technical": "technicals",
        "fundamental": "fundamentals", "sentiment": "sentiment",
    }
    active = sorted(
        ((key, float(weight)) for key, weight in effective.items() if float(weight or 0) > 0),
        key=lambda entry: entry[1], reverse=True,
    )
    unavailable = []
    configured = r.get("weights") or {}
    for key in ("gru", "technical", "fundamental", "sentiment"):
        detail_key = "ml" if key == "gru" else key
        component = reasoning.get(detail_key) or {}
        if component.get("status") == "unavailable" and float(configured.get(key, configured.get(detail_key, 0)) or 0) > 0:
            unavailable.append(source_names[key])

    label = {"BUY": "Buy", "SELL": "Sell"}.get(signal, "Hold")
    if active:
        key, _ = active[0]
        source = source_names.get(key, source_names.get("gru" if key == "ml" else key, key))
        scores = r.get("signals") or {}
        score = scores.get(key, scores.get("gru" if key in {"ml", "gru"} else key))
        if score is None:
            score = r.get({"ml": "ml_signal", "gru": "ml_signal", "technical": "technical_signal", "fundamental": "fundamental_signal", "sentiment": "sentiment_signal"}.get(key, ""))
        if len(active) == 1:
            verb = "are" if key in {"technical", "fundamental"} else "is"
            detail = f"{source.capitalize()} {verb} the only available input"
        else:
            verb = "lead" if key in {"technical", "fundamental"} else "leads"
            detail = f"{source.capitalize()} {verb} the combined signals"
        if score is not None:
            detail += f" ({float(score):+.3f})"
    else:
        detail = "No signal components are available"

    summary = f"{label}: {detail}"
    if unavailable:
        summary += f"; {', '.join(unavailable)} unavailable"
    freshness = _market_data_freshness(r.get("data_as_of"))
    if freshness["data_freshness"] == "stale":
        summary += f"; market data is stale ({freshness['data_age_trading_days']} trading days old)"
    return summary


def _market_data_freshness(data_as_of: str | None, *, today: date | None = None) -> dict:
    """Report market-data age; weekends are excluded from the two-day freshness window."""
    if not data_as_of:
        return {"data_freshness": "unknown", "data_age_calendar_days": None, "data_age_trading_days": None}
    try:
        observed = date.fromisoformat(str(data_as_of)[:10])
        current = today or datetime.now(timezone.utc).date()
        calendar_days = (current - observed).days
        if calendar_days < 0:
            return {"data_freshness": "unknown", "data_age_calendar_days": None, "data_age_trading_days": None}
        trading_days = sum(
            1 for offset in range(1, calendar_days + 1)
            if (observed + timedelta(days=offset)).weekday() < 5
        )
        return {
            "data_freshness": "fresh" if trading_days <= 2 else "stale",
            "data_age_calendar_days": calendar_days,
            "data_age_trading_days": trading_days,
        }
    except (TypeError, ValueError):
        return {"data_freshness": "unknown", "data_age_calendar_days": None, "data_age_trading_days": None}


def _apply_freshness_guard(rec: dict, *, today: date | None = None) -> dict:
    """Never expose an actionable direction or ATR levels for stale/undated prices."""
    result = dict(rec)
    freshness = _market_data_freshness(result.get("data_as_of"), today=today)
    result.update(freshness)
    stale = freshness["data_freshness"] != "fresh"
    original_signal = str(result.get("signal", "hold")).upper()
    # A HOLD is not being suppressed; only a stale BUY/SELL loses its direction.
    result["signal_suppressed"] = stale and original_signal in {"BUY", "SELL"}
    result["suppression_reason"] = None
    if stale:
        age = freshness.get("data_age_trading_days")
        age_text = f"{age} trading days old" if age is not None else "freshness is unknown"
        result["confidence"] = 0.0
        result["target_price"] = None
        result["stop_loss"] = None
        result["expected_range"] = None
        result["upside_pct"] = None
        result["downside_pct"] = None
        result["risk_reward_ratio"] = None
        if result["signal_suppressed"]:
            reason = f"{original_signal} suppressed because market data is {age_text}"
            result["signal"] = "hold"
            result["suppression_reason"] = reason
            result["decision_reason"] = f"{reason}; no trade direction or ATR levels are returned."
        result["target_stop_reason"] = "Price levels are suppressed because market-data freshness could not be confirmed."
    return result


def _component_payload(rec: dict) -> dict:
    reasoning = rec.get("reasoning") or {}
    configured = _canonical_weights(rec.get("weights"))
    effective = _canonical_weights(rec.get("effective_weights"))
    signals = _canonical_signals(rec.get("signals"))
    components = {}
    for name in ("ml", "technical", "fundamental", "sentiment"):
        source_reason = reasoning.get(name) or {}
        status = source_reason.get("status")
        if status not in {"available", "unavailable"}:
            status = "available" if effective.get(name, 0) > 0 else "unavailable"
        components[name] = {
            "score": signals[name] if status == "available" else None,
            "status": status,
            "availability_reason": source_reason.get("reason") if status == "unavailable" else None,
            "configured_weight": configured[name],
            "effective_weight": effective[name],
        }
    return components


def _market_data_payload(rec: dict) -> dict:
    return {
        "as_of": rec.get("data_as_of"),
        "freshness": rec.get("data_freshness", "unknown"),
        "age_calendar_days": rec.get("data_age_calendar_days"),
        "age_trading_days": rec.get("data_age_trading_days"),
        "current_price": rec.get("current_price"),
        "currency": "PKR",
    }


def _decision_payload(rec: dict) -> dict:
    return {
        "signal": str(rec.get("signal", "hold")).upper(),
        "composite_score": round(float(rec.get("composite_score", 0) or 0), 3),
        "confidence": round(float(rec.get("confidence", 0) or 0), 3),
        "confidence_type": "heuristic_signal_strength",
        "status": rec.get("status", "available"),
        "horizon": "5 trading days",
        "reason": _decision_reason(rec),
        "suppressed": bool(rec.get("signal_suppressed", False)),
        "suppression_reason": rec.get("suppression_reason"),
    }


def _risk_payload(rec: dict) -> dict:
    return {
        "target_price": rec.get("target_price"),
        "stop_loss": rec.get("stop_loss"),
        "expected_range": rec.get("expected_range"),
        "atr_14": rec.get("atr_14"),
        "upside_pct": rec.get("upside_pct"),
        "downside_pct": rec.get("downside_pct"),
        "risk_reward_ratio": rec.get("risk_reward_ratio"),
        "method": rec.get("target_stop_method", "atr_band"),
        "explanation": _target_stop_reason(rec),
    }


def _canonical_weights(weights: dict | None) -> dict[str, float]:
    weights = weights or {}
    return {
        "ml": float(weights.get("ml", weights.get("gru", 0.0))),
        "technical": float(weights.get("technical", 0.0)),
        "fundamental": float(weights.get("fundamental", 0.0)),
        "sentiment": float(weights.get("sentiment", 0.0)),
    }


def _canonical_signals(signals: dict | None) -> dict[str, float]:
    """Return the same named, numeric component scores on every recommendation route."""
    signals = signals or {}
    return {
        "ml": float(signals.get("ml", signals.get("gru", 0.0)) or 0.0),
        "technical": float(signals.get("technical", 0.0) or 0.0),
        "fundamental": float(signals.get("fundamental", 0.0) or 0.0),
        "sentiment": float(signals.get("sentiment", 0.0) or 0.0),
    }


def _target_stop_reason(rec: dict) -> str:
    if rec.get("target_stop_reason"):
        return rec["target_stop_reason"]
    if str(rec.get("signal", "hold")).lower() == "hold":
        if rec.get("expected_range"):
            return "HOLD has no directional target or stop; the expected range is an ATR volatility envelope."
        return "No directional target or stop is available for this HOLD recommendation."
    if rec.get("target_price") is not None or rec.get("stop_loss") is not None:
        return "Directional target and stop are ATR-based volatility levels, not price forecasts or execution guarantees."
    return "Directional ATR levels are unavailable for this data."


def _decision_reason(rec: dict) -> str:
    reason = rec.get("decision_reason")
    if reason:
        return reason
    if rec.get("status") in {"partial", "insufficient_data"}:
        return "Recommendation is based on partial or insufficient data; review component availability before acting."
    return "Decision reason is unavailable for this cached recommendation."


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
):
    try:
        from app.services.recommendation_service import DEFAULT_WEIGHTS, RecommendationEngine, get_cached_recommendations

        effective_risk = risk_profile or _get_user_risk_profile(user)

        weights = _get_user_weights(user, DEFAULT_WEIGHTS)
        uses_default_weights = all(abs(weights[key] - DEFAULT_WEIGHTS[key]) < 1e-9 for key in DEFAULT_WEIGHTS)
        cached = get_cached_recommendations() if effective_risk == "moderate" and uses_default_weights else None
        if cached is not None:
            recommendations = cached
        else:
            engine = RecommendationEngine(weights=weights)
            recommendations = await run_in_threadpool(
                engine.get_all_recommendations,
                risk_tolerance=effective_risk,
                sector_filter=sector,
                weights=weights,
            )

        recommendations = [_apply_freshness_guard(r) for r in recommendations]

        if sector:
            recommendations = [
                r for r in recommendations
                if str(r.get("sector") or "").casefold() == sector.casefold()
            ]

        total_count = len(recommendations)
        recommendations = recommendations[:limit]

        items = [
            RecommendationItem(
                symbol=r["symbol"],
                name=r.get("name"),
                sector=r.get("sector"),
                decision=_decision_payload(r),
                components=_component_payload(r),
                market_data=_market_data_payload(r),
                risk=_risk_payload(r),
                summary=_summarize(r),
            )
            for r in recommendations
        ]

        return RecommendationsListResponse(
            count=len(items),
            total_count=total_count,
            generated_at=datetime.now(timezone.utc),
            risk_profile=effective_risk,
            recommendations=items,
        )

    except Exception as exc:
        log.exception("Failed to fetch recommendations")
        raise ServiceUnavailableError("Failed to fetch recommendations")


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
        user_w = _get_user_weights(user, DEFAULT_WEIGHTS)
        return EngineWeightsResponse(
            weights={
                "ml": user_w["gru"],
                "technical": user_w["technical"],
                "fundamental": user_w["fundamental"],
                "sentiment": user_w["sentiment"],
            },
        )
    except Exception:
        log.exception("Failed to get engine weights")
        raise ServiceUnavailableError("Failed to get engine weights")


@router.post(
    "/recommendations/engine-weights",
    response_model=EngineWeightsResponse,
    summary="Set custom engine weights",
)
async def set_engine_weights(
    data: EngineWeightsRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        user.recommendation_weights = {
            "gru": data.gru_weight,
            "technical": data.technical_weight,
            "fundamental": data.fundamental_weight,
            "sentiment": data.sentiment_weight,
        }
        db.add(user)
        return EngineWeightsResponse(
            weights={
                "ml": data.gru_weight,
                "technical": data.technical_weight,
                "fundamental": data.fundamental_weight,
                "sentiment": data.sentiment_weight,
            },
        )
    except Exception as exc:
        raise ServiceUnavailableError("Failed to set engine weights")


@router.get(
    "/recommendations/{symbol}",
    response_model=RecommendationDetailResponse,
    summary="Get detailed recommendation for a stock",
)
async def get_recommendation_detail(
    symbol: str = PathParam(..., min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.&-]+$"),
    user: User = Depends(get_current_user),
):
    try:
        symbol = symbol.upper()

        from app.services.recommendation_service import RecommendationEngine, DEFAULT_WEIGHTS

        engine = RecommendationEngine(weights=_get_user_weights(user, DEFAULT_WEIGHTS))
        rec = await run_in_threadpool(
            engine.get_recommendation,
            symbol,
            risk_tolerance=_get_user_risk_profile(user),
            weights=engine.weights,
        )

        rec = _apply_freshness_guard(rec)

        return RecommendationDetailResponse(
            symbol=symbol,
            name=rec.get("name"),
            sector=rec.get("sector"),
            generated_at=datetime.now(timezone.utc),
            decision=_decision_payload(rec),
            components=_component_payload(rec),
            market_data=_market_data_payload(rec),
            risk=_risk_payload(rec),
            risk_profile=_get_user_risk_profile(user),
            summary=_summarize(rec),
        )

    except Exception as exc:
        log.exception("Failed to fetch recommendation for %s", symbol)
        raise ServiceUnavailableError("Failed to fetch recommendation")


@router.get(
    "/recommendations/{symbol}/target-stop",
    response_model=TargetStopResponse,
    summary="Get target price and stop loss",
)
async def get_target_stop(
    symbol: str = PathParam(..., min_length=1, max_length=20, pattern=r"^[A-Za-z0-9.&-]+$"),
    user: User = Depends(get_current_user),
):
    try:
        symbol = symbol.upper()

        from app.services.recommendation_service import RecommendationEngine, DEFAULT_WEIGHTS

        engine = RecommendationEngine(weights=_get_user_weights(user, DEFAULT_WEIGHTS))
        rec = await run_in_threadpool(
            engine.get_recommendation,
            symbol,
            risk_tolerance=_get_user_risk_profile(user),
            weights=engine.weights,
        )
        rec = _apply_freshness_guard(rec)

        return TargetStopResponse(
            symbol=symbol,
            generated_at=datetime.now(timezone.utc),
            decision=_decision_payload(rec),
            market_data=_market_data_payload(rec),
            risk=_risk_payload(rec),
            risk_profile=_get_user_risk_profile(user),
        )

    except Exception as exc:
        log.exception("Failed to fetch target/stop for %s", symbol)
        raise ServiceUnavailableError("Failed to fetch target/stop")
