"""Daily Workflow — Celery tasks for the daily data → features → predictions chain.

This module implements the daily trading day workflow:
  1. Update market data (incremental scrape)
  2. Generate features (technical indicators + macro + labels + sequences)
  3. Generate predictions (GRU + XGB ensemble for all active symbols)

Tasks are designed to be chained:
  update_market_data_task → generate_features_task → generate_predictions_task

If any step fails, subsequent steps are skipped.
"""

import json
import logging
import time
from datetime import date, datetime, timedelta
from pathlib import Path

from celery import chain, group
from celery.exceptions import SoftTimeLimitExceeded

from app.celery_app import celery

log = logging.getLogger(__name__)


class SourceRateLimited(RuntimeError):
    """Stop the daily chain after an explicit upstream rate-limit response."""


def _get_sync_session():
    from app.db.base import get_sync_session_factory
    return get_sync_session_factory()()


# ---------------------------------------------------------------------------
# Task 1: Update Market Data
# ---------------------------------------------------------------------------

@celery.task(
    name="app.tasks.daily_workflow.update_market_data",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
    soft_time_limit=4 * 60 * 60,
    time_limit=5 * 60 * 60,
)
def update_market_data_task(self):
    """Incremental OHLCV scrape for all active symbols.

    Runs the existing scraper in incremental mode. Idempotent — running
    twice will only append new days.
    """
    log.info("[DATA] Starting daily market data update")

    try:
        import asyncio
        from datetime import datetime
        from zoneinfo import ZoneInfo
        today_pkt = datetime.now(ZoneInfo("Asia/Karachi"))
        if today_pkt.weekday() >= 5:
            return {"status": "skipped", "reason": "weekend", "timestamp": datetime.utcnow().isoformat()}
        from app.services.news_pipeline.market_schedule import is_holiday
        if asyncio.run(is_holiday()):
            log.info("[DATA] Exchange holiday; retaining prior session snapshots")
            return {"status": "skipped", "reason": "exchange_holiday", "timestamp": datetime.utcnow().isoformat()}

        from app.data.scraper.run_after_close import run_after_close_scrape

        scrape_result = run_after_close_scrape()
        if isinstance(scrape_result, dict):
            errors = int(scrape_result.get("errors", 0) or 0)
            total = int(scrape_result.get("total_symbols", 0) or 0)
            if scrape_result.get("rate_limited"):
                raise SourceRateLimited("PSX returned HTTP 403/429; retained previous snapshots and stopped this daily chain")
            if total and errors == total:
                raise RuntimeError(f"OHLCV refresh failed for every symbol ({errors}/{total})")
            if total and not int(scrape_result.get("ok", 0) or 0):
                raise RuntimeError("OHLCV refresh returned no updated symbols; refusing to continue with stale prices")
            log.info(
                "[DATA] Market data update complete: updated=%s skipped=%s errors=%s no_data=%s",
                scrape_result.get("ok"), scrape_result.get("skipped"), errors, scrape_result.get("no_data"),
            )
        else:
            log.info("[DATA] Market data update complete")
        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}

    except SoftTimeLimitExceeded:
        log.error("[DATA] Market data update timed out")
        raise self.retry(countdown=600)
    except SourceRateLimited:
        log.exception("[DATA] Source denied requests; stopping pipeline without retry")
        raise
    except Exception as exc:
        log.exception("[DATA] Market data update failed")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 2: Generate Features
# ---------------------------------------------------------------------------

@celery.task(
    name="app.tasks.daily_workflow.generate_features",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def generate_features_task(self):
    """Run the full feature engineering pipeline.

    Rebuilds features_daily.parquet, sequences.npz, and feature_columns.json
    from the latest OHLCV data.
    """
    log.info("[FEATURES] Starting feature generation")

    try:
        from app.data.features.run_features import run_features

        run_features()
        log.info("[FEATURES] Feature generation complete")
        return {"status": "success", "timestamp": datetime.utcnow().isoformat()}

    except SoftTimeLimitExceeded:
        log.error("[FEATURES] Feature generation timed out")
        raise self.retry(countdown=300)
    except Exception as exc:
        log.exception("[FEATURES] Feature generation failed")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 3: Generate Predictions
# ---------------------------------------------------------------------------

@celery.task(
    name="app.tasks.daily_workflow.generate_predictions",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def generate_predictions_task(self):
    """Run batch inference for all active symbols and upsert into predictions.

    Uses production GRU + XGB ensemble. Idempotent per (symbol, horizon, as_of_date).
    """
    log.info("[PREDICTION] Starting daily prediction generation")

    try:
        from app.core.redis import set_dataset_status_sync

        set_dataset_status_sync("forecasts", "pending")
        import pandas as pd

        from app.data.scraper.symbol_universe import get_active_symbols
        from app.ml.serving.inference import (
            FEATURES_PATH,
            forecast_cache_key,
            get_forecast,
        )
        from app.ml.serving.model_loader import artifacts, load_artifacts
        from app.ml.serving.prediction_store import (
            build_prediction_payload,
            upsert_prediction_sync,
        )

        if not artifacts.model_ready and not artifacts.xgb_ready:
            load_artifacts()

        if not artifacts.model_ready and not artifacts.xgb_ready:
            raise RuntimeError("Prediction model is not ready; refusing to publish downstream recommendations")

        df = pd.read_parquet(FEATURES_PATH)
        df["date"] = pd.to_datetime(df["date"])

        active = get_active_symbols()
        symbols = [
            str(entry["symbol"]).strip().upper()
            for entry in active
            if entry.get("symbol")
        ]
        if len(symbols) != len(set(symbols)):
            raise RuntimeError("KSE-100 symbol universe contains duplicate symbols")
        symbols.sort()
        if not symbols:
            raise RuntimeError("KSE-100 symbol universe is empty; refusing to publish forecasts")
        log.info("[PREDICTION] Running predictions for %d symbols", len(symbols))

        session = _get_sync_session()
        success = 0
        failed = 0
        as_of_dates: set[str] = set()
        forecast_keys: set[str] = set()
        failures: list[str] = []

        try:
            for sym in symbols:
                try:
                    sym_df = (
                        df[df["symbol"].astype(str).str.upper() == sym]
                        .copy()
                        .sort_values("date")
                        .reset_index(drop=True)
                    )
                    if len(sym_df) < artifacts.window_size:
                        raise RuntimeError(
                            f"insufficient feature history ({len(sym_df)} < {artifacts.window_size})"
                        )

                    as_of_date = sym_df["date"].iloc[-1].date()
                    as_of_dates.add(as_of_date.isoformat())
                    for horizon in ("1D", "1W", "2W", "1M"):
                        forecast = get_forecast(sym, horizon=horizon, sym_df=sym_df)
                        model_details = forecast.get("model_details") or {}
                        gru_result = model_details.get("gru_v2")
                        xgb_result = model_details.get("xgb_v4")
                        ensemble = {
                            "direction": forecast["direction"],
                            "bullish_pct": forecast["bullish_pct"],
                            "bearish_pct": forecast["bearish_pct"],
                            "sideways_pct": forecast["sideways_pct"],
                            "top_class_probability": forecast["top_class_probability"],
                            "model_version": forecast["model_version"],
                            "gate_reason": forecast.get("gate_reason", ""),
                        }
                        payload = build_prediction_payload(
                            symbol=sym,
                            horizon=horizon,
                            ensemble=ensemble,
                            as_of_date=forecast["as_of_date"],
                            target_date=forecast["predicted_for_date"],
                            gru_result=gru_result,
                            xgb_result=xgb_result,
                        )
                        upsert_prediction_sync(session, payload)
                        forecast_keys.add(
                            forecast_cache_key(sym, horizon, forecast["as_of_date"])
                        )

                    session.commit()
                    success += 1

                except Exception as exc:
                    log.warning("[PREDICTION] Failed for %s: %s", sym, exc, exc_info=True)
                    session.rollback()
                    failed += 1
                    failures.append(f"{sym}: {exc}")
        finally:
            session.close()

        if failed:
            raise RuntimeError(
                f"Forecast refresh incomplete: {success}/{len(symbols)} symbols succeeded; "
                f"first failures: {'; '.join(failures[:10])}"
            )

        from app.core.redis import get_sync_redis_client

        redis = get_sync_redis_client()
        if redis is None:
            raise RuntimeError("Redis is unavailable; forecast cache refresh was not completed")
        redis.ping()
        pipeline = redis.pipeline()
        for key in forecast_keys:
            pipeline.exists(key)
        cache_results = pipeline.execute()
        if len(cache_results) != len(forecast_keys):
            raise RuntimeError(
                f"Forecast Redis verification returned {len(cache_results)} results "
                f"for {len(forecast_keys)} keys"
            )
        if len(forecast_keys) != len(symbols) * 4:
            raise RuntimeError(
                f"Forecast cache coverage mismatch: expected {len(symbols) * 4}, "
                f"prepared {len(forecast_keys)}"
            )
        missing_cache_count = sum(1 for present in cache_results if not present)
        if missing_cache_count:
            raise RuntimeError(f"{missing_cache_count} forecast Redis cache keys are missing")
        set_dataset_status_sync("forecasts", "success")

        log.info(
            "[PREDICTION] Complete: %d succeeded, %d failed out of %d; cached=%d (as_of=%s)",
            success,
            failed,
            len(symbols),
            len(forecast_keys),
            sorted(as_of_dates),
        )
        return {
            "status": "success",
            "success": success,
            "failed": failed,
            "total": len(symbols),
            "cached": len(forecast_keys),
            "as_of_dates": sorted(as_of_dates),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except SoftTimeLimitExceeded:
        log.error("[PREDICTION] Prediction generation timed out")
        raise self.retry(countdown=300)
    except Exception as exc:
        log.exception("[PREDICTION] Prediction generation failed")
        raise self.retry(exc=exc)


# ---------------------------------------------------------------------------
# Task 4: Evaluate Pending Predictions
# ---------------------------------------------------------------------------

@celery.task(
    name="app.tasks.daily_workflow.evaluate_pending",
    bind=True,
    max_retries=2,
    default_retry_delay=120,
    acks_late=True,
)
def evaluate_pending_predictions_task(self):
    """Resolve actual outcomes for predictions whose target_date close is in features.

    Runs as step 4 of the daily pipeline (after features refresh). Uses absolute
    FEATURES_PATH and Asia/Karachi calendar dates.
    """
    log.info("[EVALUATION] Starting outcome evaluation")

    try:
        session = _get_sync_session()
        try:
            from app.ml.serving.prediction_store import evaluate_pending_predictions_sync

            result = evaluate_pending_predictions_sync(session)
            log.info("[EVALUATION] Complete: %s", result)
            return result
        finally:
            session.close()

    except SoftTimeLimitExceeded:
        log.error("[EVALUATION] Outcome evaluation timed out")
        raise self.retry(countdown=300)
    except Exception as exc:
        log.exception("[EVALUATION] Outcome evaluation failed")
        raise self.retry(exc=exc)


@celery.task(
    name="app.tasks.daily_workflow.warm_technical_indicators",
    bind=True,
    max_retries=2,
    default_retry_delay=60,
    acks_late=True,
)
def warm_technical_indicators_task(self):
    """Pre-calculate and populate technical indicators, price history, and overview in Redis."""
    log.info("[TECH-WARMER] Starting background pre-calculation of technical indicators and price history")
    try:
        from app.data.scraper.run_after_close import get_refresh_symbols
        from app.services.stock_service import StockService

        symbols = get_refresh_symbols()
        service = StockService()
        warmed = 0
        for sym in symbols:
            try:
                # 1. Warm technical indicators for default settings (24h TTL)
                service.technical_indicators(sym, indicators="RSI,MACD,BB,SMA,ADX", period=14, limit=30)
                # 2. Warm price history for standard ranges (24h TTL)
                for r in ("1M", "1W", "1Y"):
                    service.get_price_history(sym, range=r)
                # 3. Warm stock overview (120s TTL)
                service.get_overview(sym)
                warmed += 1
            except Exception as e:
                log.debug("[TECH-WARMER] Could not warm %s: %s", sym, e)

        log.info(
            "[TECH-WARMER] Technical indicators pre-calculation complete: %d/%d symbols warmed",
            warmed,
            len(symbols),
        )
        return {
            "status": "success",
            "warmed": warmed,
            "total_symbols": len(symbols),
            "timestamp": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        log.exception("[TECH-WARMER] Technical indicators warming failed")
        return {"status": "error", "error": str(exc)}


# ---------------------------------------------------------------------------
# Chain: Daily Workflow
# ---------------------------------------------------------------------------

@celery.task(name="app.tasks.daily_workflow.run_daily_pipeline")
def run_daily_pipeline():
    """Orchestrate the full daily workflow as a chain.

    Chain: update_data → warm_technical_indicators → generate_features → generate_predictions → evaluate_pending → sentiment → recs
    """
    from app.core.redis import get_sync_redis_client

    log.info("[DAILY] Starting full daily pipeline")

    # Gate before dispatching the chain. Returning "skipped" from the first
    # chained task would still allow Celery to continue with stale downstream
    # features, sentiment and recommendation publication.
    import asyncio
    from zoneinfo import ZoneInfo
    now_pkt = datetime.now(ZoneInfo("Asia/Karachi"))
    if now_pkt.weekday() >= 5:
        return {"status": "skipped", "reason": "weekend"}
    try:
        from app.services.news_pipeline.market_schedule import is_holiday
        if asyncio.run(is_holiday()):
            return {"status": "skipped", "reason": "exchange_holiday"}
    except Exception:
        log.exception("Could not check holiday calendar; refusing to start daily pipeline")
        return {"status": "skipped", "reason": "holiday_check_unavailable"}

    dispatch_key = "jobs:daily-workflow:dispatch-lock"
    client = get_sync_redis_client()
    if client is None:
        log.error("[DAILY] Redis is unavailable; refusing to dispatch an uncoordinated pipeline")
        return {"status": "blocked", "reason": "redis_unavailable"}
    if not client.set(dispatch_key, "1", nx=True, ex=21600):
        log.info("[DAILY] A daily pipeline is already dispatched; skipping duplicate")
        return {"status": "skipped", "reason": "already_dispatched"}

    # These stages are independent tasks in a serial pipeline. Immutable
    # signatures prevent Celery from injecting each prior task's result as a
    # positional argument into the next bound task (which accepts no such arg).
    from app.tasks.sentiment_tasks import aggregate_sentiment_task
    from app.tasks.recommendation_cache import refresh_recommendations_task

    workflow = chain(
        update_market_data_task.si(),
        warm_technical_indicators_task.si(),
        generate_features_task.si(),
        generate_predictions_task.si(),
        evaluate_pending_predictions_task.si(),
        aggregate_sentiment_task.si(),
        refresh_recommendations_task.si(),
    )
    try:
        result = workflow.apply_async()
    except Exception:
        try:
            client.delete(dispatch_key)
        except Exception:
            log.exception("[DAILY] Could not clear dispatch lock after enqueue failure")
        raise

    log.info("[DAILY] Pipeline dispatched — group_id=%s", result.id)
    return {"status": "dispatched", "group_id": result.id}


@celery.task(
    name="app.tasks.daily_workflow.run_morning_market_intelligence",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
)
def run_morning_market_intelligence(self):
    """Refresh all KSE-100 forecasts and recommendations before market open."""
    import asyncio
    from zoneinfo import ZoneInfo

    from app.core.redis import get_sync_redis_client

    now_pkt = datetime.now(ZoneInfo("Asia/Karachi"))
    if now_pkt.weekday() >= 5:
        return {"status": "skipped", "reason": "weekend"}

    try:
        from app.services.news_pipeline.market_schedule import is_holiday

        if asyncio.run(is_holiday()):
            return {"status": "skipped", "reason": "exchange_holiday"}
    except Exception as exc:
        log.exception("[MORNING] Could not check holiday calendar; refusing to dispatch")
        raise self.retry(exc=exc)

    dispatch_key = f"jobs:morning-market-intelligence:{now_pkt.date().isoformat()}"
    status_key = f"jobs:morning-market-intelligence:status:{now_pkt.date().isoformat()}"
    redis = None
    try:
        redis = get_sync_redis_client()
        if redis is None:
            raise RuntimeError("Redis is unavailable; refusing duplicate-unsafe dispatch")
        if not redis.set(dispatch_key, "1", nx=True, ex=12 * 60 * 60):
            return {"status": "skipped", "reason": "already_dispatched"}
        redis.set(status_key, "pending", ex=36 * 60 * 60)
        from app.core.redis import set_dataset_status_sync

        set_dataset_status_sync("forecasts", "pending")
        set_dataset_status_sync("recommendations", "pending")

        from app.tasks.recommendation_cache import refresh_recommendations_task
        from app.tasks.refresh_market_cache import refresh_market_cache

        workflow = chain(
            refresh_market_cache.si(
                refresh_reference=True,
                refresh_constituents=True,
                require_complete=True,
            ),
            generate_predictions_task.si(),
            refresh_recommendations_task.si(),
            mark_morning_market_intelligence_success.si(now_pkt.date().isoformat()),
        )
        result = workflow.apply_async()
    except Exception as exc:
        try:
            if redis is not None:
                redis.set(status_key, "failed", ex=36 * 60 * 60)
                redis.delete(dispatch_key)
        except Exception:
            log.exception("[MORNING] Could not clear dispatch lock after enqueue failure")
        log.exception("[MORNING] Could not dispatch forecast/recommendation refresh")
        raise self.retry(exc=exc)

    log.info("[MORNING] Forecast/recommendation refresh dispatched — group_id=%s", result.id)
    return {"status": "dispatched", "group_id": result.id}


@celery.task(
    name="app.tasks.daily_workflow.mark_morning_market_intelligence_success",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def mark_morning_market_intelligence_success(self, refresh_date: str):
    """Mark the pre-market chain ready only after forecasts and recommendations succeed."""
    from app.core.redis import get_sync_redis_client

    redis = get_sync_redis_client()
    if redis is None:
        raise self.retry(exc=RuntimeError("Redis is unavailable while marking refresh complete"))
    status_key = f"jobs:morning-market-intelligence:status:{refresh_date}"
    try:
        redis.set(status_key, "success", ex=36 * 60 * 60)
    except Exception as exc:
        log.exception("[MORNING] Could not mark refresh complete")
        raise self.retry(exc=exc)
    return {"status": "success", "refresh_date": refresh_date}
