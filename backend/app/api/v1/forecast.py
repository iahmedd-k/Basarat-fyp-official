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
from app.core.redis import cache_get, cache_set, dataset_refresh_ready
from app.db.session import get_db
from app.ml.serving.inference import (
    InsufficientHistoryError,
    SymbolNotFoundError,
    forecast_cache_key,
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
    ForecastResponse,
)

import pandas as pd
from pydantic import ValidationError
from app.services.recommendation_service import RecommendationEngine

log = logging.getLogger(__name__)

router = APIRouter()


def _prediction_result(row: Prediction) -> dict:
    model_details = {}
    for prefix, model_name in (("gru", "gru_v2"), ("xgb", "xgb_v4")):
        direction = getattr(row, f"{prefix}_direction")
        if direction is None:
            continue
        model_details[model_name] = {
            "direction": direction,
            "bullish_pct": getattr(row, f"{prefix}_bullish_pct"),
            "bearish_pct": getattr(row, f"{prefix}_bearish_pct"),
            "sideways_pct": getattr(row, f"{prefix}_sideways_pct"),
            "gap_pp": getattr(row, f"{prefix}_gap_pp"),
        }
    return {
        "symbol": row.symbol,
        "horizon": row.horizon,
        "direction": row.predicted_direction,
        "bullish_pct": row.bullish_pct,
        "bearish_pct": row.bearish_pct,
        "sideways_pct": row.sideways_pct,
        "top_class_probability": row.top_class_probability,
        "as_of_date": row.as_of_date,
        "predicted_for_date": row.target_date,
        "model_version": row.model_version,
        "model_details": model_details,
        "gate_reason": row.gate_reason or "",
        "market_context": None,
    }


def _latest_feature_date(symbol: str) -> date | None:
    from app.ml.serving.inference import get_features_dataframe

    features = get_features_dataframe()
    if features.empty or not {"symbol", "date"}.issubset(features.columns):
        return None
    symbol_rows = features[features["symbol"].astype(str).str.upper() == symbol]
    if symbol_rows.empty:
        return None
    return pd.to_datetime(symbol_rows["date"]).max().date()


@router.get(
    "/forecast/{symbol}",
    response_model=ForecastResponse,
    summary="Predict bullish/bearish/sideways with ensemble GRU+XGBoost and save to history",
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
    Prefer the latest daily prediction row, falling back to inference only
    when no batch prediction exists for the requested symbol and horizon.

    The daily batch refreshes all active KSE-100 symbols before market open.
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

        cache_key = f"forecast:response:v5:{symbol_upper}:{horizon}"
        cached = await cache_get(cache_key)
        if cached and isinstance(cached, dict):
            try:
                return ForecastResponse(**cached)
            except ValidationError as exc:
                log.warning(
                    "Ignoring invalid cached forecast for %s/%s: %s",
                    symbol_upper,
                    horizon,
                    exc,
                )

        saved_result = await db.execute(
            select(Prediction)
            .where(
                Prediction.symbol == symbol_upper,
                Prediction.horizon == horizon,
            )
            .order_by(Prediction.as_of_date.desc(), Prediction.predicted_at.desc())
            .limit(1)
        )
        saved_prediction = saved_result.scalar_one_or_none()
        shared_cache_ready = await dataset_refresh_ready("forecasts")
        saved_prediction_is_fresh = False
        if saved_prediction is not None and shared_cache_ready:
            try:
                latest_data_date = await run_in_threadpool(_latest_feature_date, symbol_upper)
                saved_prediction_is_fresh = (
                    latest_data_date is not None
                    and saved_prediction.as_of_date == latest_data_date
                )
            except Exception:
                log.warning(
                    "Could not verify saved forecast freshness for %s; using live inference",
                    symbol_upper,
                    exc_info=True,
                )

        if saved_prediction is not None and saved_prediction_is_fresh:
            result = _prediction_result(saved_prediction)
        elif not artifacts.model_ready:
            raise ServiceUnavailableError(
                "A fresh forecast is unavailable: Redis is down, the daily refresh has not "
                "completed, or the saved prediction is stale; ML inference is not ready."
            )
        else:
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

        target_stop = {"current_price": None, "target_price": None, "stop_loss": None}
        try:
            from app.ml.serving.inference import get_features_dataframe

            df = get_features_dataframe()
            if not pd.api.types.is_datetime64_any_dtype(df["date"]):
                df["date"] = pd.to_datetime(df["date"])
            as_of_date = pd.Timestamp(result["as_of_date"])
            sym_df = (
                df[
                    (df["symbol"] == result["symbol"])
                    & (df["date"] <= as_of_date)
                ]
                .copy()
                .sort_values("date")
                .reset_index(drop=True)
            )
            if not sym_df.empty:
                engine = RecommendationEngine()
                target_stop = engine.compute_target_stop(
                    result["symbol"],
                    sym_df,
                    ml_direction=result.get("direction"),
                    horizon=horizon,
                )
        except Exception:
            log.warning("Target/stop computation failed for %s", result["symbol"], exc_info=True)

        if (
            (not target_stop or target_stop.get("target_price") is None)
            and result.get("direction") in ("bullish", "bearish")
        ):
            try:
                from app.services.stock_service import StockService

                stock_svc = StockService()
                quote = stock_svc.get_quote(result["symbol"])
                curr_p = (
                    float(quote.get("current") or quote.get("ldcp"))
                    if quote and (quote.get("current") or quote.get("ldcp"))
                    else 0.0
                )
                if curr_p <= 0:
                    raise ValueError("No current price is available for target/stop calculation")
                atr = float(result.get("atr_14") or 0.0)
                mult = 2.0 if horizon == "1D" else 3.0 if horizon == "1W" else 3.5 if horizon == "2W" else 4.0
                dir_str = str(result.get("direction", "sideways")).lower()
                if dir_str in ("bullish", "buy", "up") and atr > 0:
                    tp = round(curr_p + (atr * mult), 2)
                    sl = round(curr_p - (atr * mult * 0.75), 2)
                elif dir_str in ("bearish", "sell", "down") and atr > 0:
                    tp = round(curr_p - (atr * mult), 2)
                    sl = round(curr_p + (atr * mult * 0.75), 2)
                else:
                    raise ValueError("ATR is unavailable for target/stop calculation")
                up_pct = round((tp - curr_p) / curr_p * 100, 2)
                down_pct = round((sl - curr_p) / curr_p * 100, 2)
                rr = round(abs(tp - curr_p) / max(0.01, abs(curr_p - sl)), 2)
                target_stop = {
                    "symbol": result["symbol"],
                    "current_price": round(curr_p, 2),
                    "target_price": tp,
                    "stop_loss": sl,
                    "expected_range": {"low": min(sl, tp), "high": max(sl, tp), "method": "atr_band"},
                    "upside_pct": up_pct,
                    "downside_pct": down_pct,
                    "risk_reward_ratio": rr,
                    "method": "atr_band",
                }
            except Exception as exc:
                log.warning(
                    "Fallback target/stop computation failed for %s: %s",
                    result["symbol"],
                    exc,
                )

        response = _build_forecast_response(result, horizon, target_stop)
        if shared_cache_ready:
            await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response

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


def _build_forecast_response(result: dict, horizon: str, target_stop: dict | None = None) -> ForecastResponse:
    """Transform raw inference output into enterprise-grade ensemble response schema."""
    direction = result["direction"]
    top_prob = result["top_class_probability"]
    confidence = round(top_prob / 100.0, 3)

    probabilities = {
        "bullish": result["bullish_pct"],
        "bearish": result["bearish_pct"],
        "sideways": result["sideways_pct"],
    }

    if direction == "bullish":
        signal_rating = "Strong Buy" if probabilities["bullish"] >= 58.0 or confidence >= 0.58 else "Buy"
    elif direction == "bearish":
        signal_rating = "Strong Sell" if probabilities["bearish"] >= 58.0 or confidence >= 0.58 else "Sell"
    else:
        signal_rating = "Neutral / Hold"

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

    current_price = None
    target_price = None
    stop_loss = None
    expected_range = None
    upside_pct = None
    downside_pct = None
    risk_reward_ratio = None

    if target_stop:
        current_price = target_stop.get("current_price")
        target_price = target_stop.get("target_price")
        stop_loss = target_stop.get("stop_loss")
        expected_range = target_stop.get("expected_range")
        upside_pct = target_stop.get("upside_pct")
        downside_pct = target_stop.get("downside_pct")
        risk_reward_ratio = target_stop.get("risk_reward_ratio")

    if current_price and direction in ("bullish", "bearish") and (target_price is None or stop_loss is None):
        price_target_rationale = "Target and stop-loss are unavailable because a verified ATR value is missing."
    elif target_price is not None and stop_loss is not None:
        price_target_rationale = (
            f"Target price and stop-loss calculated via ATR volatility interval for {horizon} horizon."
        )
    elif direction not in ("bullish", "bearish") and expected_range:
        price_target_rationale = "Neutral forecasts have no directional target or stop; the expected range is an ATR volatility envelope."
    else:
        price_target_rationale = "Target and stop-loss calculations are pending current session price data."

    as_of = result["as_of_date"]
    target_d = result["predicted_for_date"]

    HORIZON_LABELS = {
        "1D": "1-Day (1 Trading Day)",
        "1W": "1-Week (5 Trading Days)",
        "2W": "2-Weeks (10 Trading Days)",
        "1M": "1-Month (22 Trading Days)",
    }
    HORIZON_TRADING_DAYS = {"1D": 1, "1W": 5, "2W": 10, "1M": 22}

    horizon_label = HORIZON_LABELS.get(horizon, f"{horizon} (5 Trading Days)")
    trading_days = HORIZON_TRADING_DAYS.get(horizon, 5)

    as_of_label = as_of.strftime("%a, %b %d, %Y") if hasattr(as_of, "strftime") else str(as_of)
    target_label = f"Target by {target_d.strftime('%a, %b %d, %Y')}" if hasattr(target_d, "strftime") else f"Target by {target_d}"

    from zoneinfo import ZoneInfo
    from datetime import datetime as dt
    pkt_now = dt.now(ZoneInfo("Asia/Karachi"))
    market_status = "closed" if pkt_now.weekday() >= 5 else "open"

    return ForecastResponse(
        price_target_rationale=price_target_rationale,
        symbol=result["symbol"],
        horizon=horizon,
        horizon_label=horizon_label,
        trading_days=trading_days,
        direction=direction,
        confidence=confidence,
        probabilities=probabilities,
        as_of_date=as_of,
        as_of_label=as_of_label,
        target_date=target_d,
        target_label=target_label,
        market_status=market_status,
        current_price=current_price,
        target_price=target_price,
        expected_range=expected_range,
        stop_loss=stop_loss,
        signal_rating=signal_rating,
        upside_pct=upside_pct,
        downside_pct=downside_pct,
        risk_reward_ratio=risk_reward_ratio,
        model_version=result["model_version"],
        gate_reason=result.get("gate_reason", ""),
        models=models,
        market_context=result.get("market_context"),
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
                "Predictions appear after GET /forecast/{symbol}, the 18:00 PKT workflow, "
                "or the 05:30 PKT pre-market refresh."
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
