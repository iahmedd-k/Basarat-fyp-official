"""Forecast API — ML predict, save, and history (professional contract).

Core flow:
  GET /forecast/{symbol}           → predict + upsert into predictions
  GET /forecast/{symbol}/history   → read saved predictions + real outcomes only
  GET /forecast/pipeline           → when Celery background jobs run (PKT)

Outcomes are written only by Celery evaluate_pending (after target close is in features).
History never invents sideways/actual labels.
"""

import logging

import pandas as pd
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
from app.ml.serving.prediction_store import pkt_today, pipeline_schedule_info
from app.models.prediction import Prediction
from app.models.user import User
from app.services.recommendation_service import RecommendationEngine

from app.ml.serving.schemas import (
    ErrorResponse,
    ForecastHistoryItem,
    ForecastHistoryResponse,
    ForecastPipelineResponse,
    ForecastResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/forecast/pipeline",
    response_model=ForecastPipelineResponse,
    summary="Forecast background job schedule (when predict + evaluate run)",
)
async def get_forecast_pipeline(user: User = Depends(get_current_user)):
    """
    Documents the Celery Beat daily pipeline for Android / ops.

    **Mon–Fri 18:00 Asia/Karachi** (skips weekends & exchange holidays):
    1. Scrape OHLCV → 2. Features → 3. Upsert predictions → 4. Evaluate outcomes
    → 5. Sentiment → 6. Recommendations

    A prediction made for `target_date = next trading day` is normally scored on
    the **following** 18:00 run, once that day's close exists in features.
    """
    info = pipeline_schedule_info()
    return ForecastPipelineResponse(
        timezone=info["timezone"],
        current_date_pkt=pkt_today().isoformat(),
        daily_pipeline=info["daily_pipeline"],
        outcome_timing=info["outcome_timing"],
        api_paths=info["api_paths"],
    )


@router.get(
    "/forecast/{symbol}",
    response_model=ForecastResponse,
    summary="Predict bullish/bearish/sideways and save to history",
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
    """
    Run ensemble inference for a PSX symbol, **upsert** the prediction into
    `predictions`, and return the live forecast payload.

    Daily batch also upserts all active symbols at 18:00 PKT. Calling this
    endpoint mid-day refreshes the same unique (symbol, horizon, as_of_date) row.
    """
    try:
        if not artifacts.model_ready:
            raise ServiceUnavailableError("ML model is not loaded yet")

        result = get_forecast(symbol, horizon=horizon)

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
            from app.ml.serving.inference import FEATURES_PATH

            features_path = FEATURES_PATH
            if features_path.exists():
                df = pd.read_parquet(features_path)
                df["date"] = pd.to_datetime(df["date"])
                sym_df = (
                    df[df["symbol"] == result["symbol"]]
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

        if not target_stop or target_stop.get("target_price") is None:
            try:
                from app.services.stock_service import StockService

                stock_svc = StockService()
                quote = stock_svc.get_quote(result["symbol"])
                curr_p = (
                    float(quote.get("current") or quote.get("ldcp") or 100.0) if quote else 100.0
                )
                atr = curr_p * (0.015 if horizon == "1D" else 0.035 if horizon == "1W" else 0.075)
                mult = 2.0 if horizon == "1D" else 3.0 if horizon == "1W" else 4.0
                dir_str = str(result.get("direction", "sideways")).lower()
                if dir_str in ("bullish", "buy", "up"):
                    tp = round(curr_p + (atr * mult), 2)
                    sl = round(curr_p - (atr * mult * 0.75), 2)
                elif dir_str in ("bearish", "sell", "down"):
                    tp = round(curr_p - (atr * mult), 2)
                    sl = round(curr_p + (atr * mult * 0.75), 2)
                else:
                    tp = round(curr_p + (atr * mult), 2)
                    sl = round(curr_p - (atr * mult), 2)
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

        return _build_forecast_response(result, horizon, target_stop)

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
    """Transform raw inference output into enterprise-grade optimized response schema."""
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

    if current_price and (target_price is None or stop_loss is None):
        mult = 1.5 if horizon == "1D" else 2.5 if horizon == "1W" else 3.5
        atr = current_price * (0.015 if horizon == "1D" else 0.035 if horizon == "1W" else 0.075)
        tp = round(current_price + atr * mult, 2)
        sl = round(current_price - atr * mult, 2)
        target_price = tp
        stop_loss = sl
        expected_range = {"low": sl, "high": tp, "method": "atr_band"}
        upside_pct = round((tp - current_price) / current_price * 100, 2)
        downside_pct = round((sl - current_price) / current_price * 100, 2)
        risk_reward_ratio = 1.0
        price_target_rationale = (
            f"Neutral trading channel [{sl} - {tp}] calculated via ATR volatility band for {horizon} horizon."
        )
    elif target_price is not None and stop_loss is not None:
        price_target_rationale = (
            f"Target price and stop-loss calculated via ATR volatility interval for {horizon} horizon."
        )
    else:
        price_target_rationale = "Target and stop-loss calculations are pending current session price data."

    return ForecastResponse(
        price_target_rationale=price_target_rationale,
        symbol=result["symbol"],
        horizon=horizon,
        direction=direction,
        confidence=confidence,
        probabilities=probabilities,
        as_of_date=result["as_of_date"],
        target_date=result["predicted_for_date"],
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
    horizon: str = Query("1D", pattern="^(1D|1W|1M)$", description="Filter by prediction horizon"),
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
        symbol = symbol.upper()
        today = pkt_today()

        result = await db.execute(
            select(Prediction)
            .where(
                Prediction.symbol == symbol,
                Prediction.horizon == horizon,
            )
            .order_by(Prediction.as_of_date.desc(), Prediction.predicted_at.desc())
            .limit(limit)
        )
        rows = result.scalars().all()

        if not rows:
            raise NotFoundError(
                f"No forecast history found for symbol '{symbol}' horizon '{horizon}'. "
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

        return ForecastHistoryResponse(
            symbol=symbol,
            horizon=horizon,
            count=len(items),
            accuracy=accuracy,
            accuracy_summary=accuracy_summary,
            pending_count=pending_count,
            scored_count=scored_count,
            history=items,
        )

    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Failed to fetch forecast history for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch forecast history: {exc}")
