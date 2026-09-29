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
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.core.config import get_settings
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


# ---------------------------------------------------------------------------
# Task 1: Update Market Data
# ---------------------------------------------------------------------------

@celery.task(
    name="app.tasks.daily_workflow.update_market_data",
    bind=True,
    max_retries=3,
    default_retry_delay=300,
    acks_late=True,
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

        from app.data.scraper.run_scrape import run_scrape

        scrape_result = run_scrape(
            mode="incremental",
            delay=0.3,
        )
        if isinstance(scrape_result, dict):
            errors = int(scrape_result.get("errors", 0) or 0)
            total = int(scrape_result.get("total_symbols", 0) or 0)
            if scrape_result.get("rate_limited"):
                raise SourceRateLimited("PSX returned HTTP 403/429; retained previous snapshots and stopped this daily chain")
            if total and errors == total:
                raise RuntimeError(f"OHLCV refresh failed for every symbol ({errors}/{total})")
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
        import pandas as pd

        from app.data.scraper.symbol_universe import get_active_symbols
        from app.ml.serving.inference import (
            _run_gru,
            _run_xgb,
            _ensemble_decide,
            FEATURES_PATH,
        )
        from app.ml.serving.model_loader import artifacts, load_artifacts
        from app.ml.serving.prediction_store import (
            build_prediction_payload,
            next_trading_day,
            upsert_prediction_sync,
        )

        if not artifacts.model_ready:
            load_artifacts()

        if not artifacts.model_ready:
            log.warning("[PREDICTION] Model not ready — skipping")
            return {"status": "skipped", "reason": "model_not_ready"}

        df = pd.read_parquet(FEATURES_PATH)
        df["date"] = pd.to_datetime(df["date"])

        active = get_active_symbols()
        symbols = [e["symbol"] for e in active]
        log.info("[PREDICTION] Running predictions for %d symbols", len(symbols))

        session = _get_sync_session()
        success = 0
        failed = 0
        as_of_dates: set[str] = set()

        for sym in symbols:
            try:
                sym_df = df[df["symbol"] == sym].copy()
                sym_df = sym_df.sort_values("date").reset_index(drop=True)

                if len(sym_df) < artifacts.window_size:
                    log.warning(
                        "[PREDICTION] %s: insufficient data (%d < %d), skipping",
                        sym,
                        len(sym_df),
                        artifacts.window_size,
                    )
                    failed += 1
                    continue

                as_of_date = sym_df["date"].iloc[-1].date()
                as_of_dates.add(as_of_date.isoformat())

                gru_result = _run_gru(sym, sym_df)
                xgb_result = _run_xgb(sym, as_of_date)
                ensemble = _ensemble_decide(gru_result, xgb_result)
                target_date = next_trading_day(as_of_date, trading_days=1)

                payload = build_prediction_payload(
                    symbol=sym,
                    horizon="1D",
                    ensemble=ensemble,
                    as_of_date=as_of_date,
                    target_date=target_date,
                    gru_result=gru_result,
                    xgb_result=xgb_result,
                )
                upsert_prediction_sync(session, payload)
                session.commit()
                success += 1

            except Exception:
                log.warning("[PREDICTION] Failed for %s", sym, exc_info=True)
                session.rollback()
                failed += 1

        session.close()
        log.info(
            "[PREDICTION] Complete: %d succeeded, %d failed out of %d (as_of=%s)",
            success,
            failed,
            len(symbols),
            sorted(as_of_dates),
        )
        return {
            "status": "success",
            "success": success,
            "failed": failed,
            "total": len(symbols),
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


# ---------------------------------------------------------------------------
# Chain: Daily Workflow
# ---------------------------------------------------------------------------

@celery.task(name="app.tasks.daily_workflow.run_daily_pipeline")
def run_daily_pipeline():
    """Orchestrate the full daily workflow as a chain.

    Chain: update_data → generate_features → generate_predictions → evaluate_pending

    If any step fails, subsequent steps are skipped (Celery chain behavior).
    """
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
    except Exception as exc:
        log.warning("Could not check holiday calendar; continuing daily pipeline: %s", exc)

    # These stages are independent tasks in a serial pipeline. Immutable
    # signatures prevent Celery from injecting each prior task's result as a
    # positional argument into the next bound task (which accepts no such arg).
    from app.tasks.sentiment_tasks import aggregate_sentiment_task
    from app.tasks.recommendation_cache import refresh_recommendations_task

    workflow = chain(
        update_market_data_task.si(),
        generate_features_task.si(),
        generate_predictions_task.si(),
        evaluate_pending_predictions_task.si(),
        aggregate_sentiment_task.si(),
        refresh_recommendations_task.si(),
    )
    result = workflow.apply_async()

    log.info("[DAILY] Pipeline dispatched — group_id=%s", result.id)
    return {"status": "dispatched", "group_id": result.id}
