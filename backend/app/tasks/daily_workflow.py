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
        from app.data.scraper.run_scrape import run_scrape

        scrape_result = run_scrape(
            mode="incremental",
            delay=0.3,
        )
        if isinstance(scrape_result, dict):
            errors = int(scrape_result.get("errors", 0) or 0)
            total = int(scrape_result.get("total_symbols", 0) or 0)
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
    """Run batch inference for all active symbols.

    Uses the current production GRU + XGB models with the existing
    ensemble gate. Stores each prediction to the database with
    individual model outputs preserved.
    """
    log.info("[PREDICTION] Starting daily prediction generation")

    try:
        import pandas as pd
        from sqlalchemy import text

        from app.data.scraper.symbol_universe import get_active_symbols
        from app.ml.serving.inference import (
            _run_gru,
            _run_xgb,
            _ensemble_decide,
            FEATURES_PATH,
        )
        from app.ml.serving.model_loader import artifacts

        if not artifacts.model_ready:
            log.warning("[PREDICTION] Model not ready — skipping")
            return {"status": "skipped", "reason": "model_not_ready"}

        # Load features once
        df = pd.read_parquet(FEATURES_PATH)
        df["date"] = pd.to_datetime(df["date"])

        active = get_active_symbols()
        symbols = [e["symbol"] for e in active]
        log.info("[PREDICTION] Running predictions for %d symbols", len(symbols))

        session = _get_sync_session()
        success = 0
        failed = 0

        for sym in symbols:
            try:
                sym_df = df[df["symbol"] == sym].copy()
                sym_df = sym_df.sort_values("date").reset_index(drop=True)

                if len(sym_df) < artifacts.window_size:
                    log.warning("[PREDICTION] %s: insufficient data (%d < %d), skipping",
                                sym, len(sym_df), artifacts.window_size)
                    failed += 1
                    continue

                as_of_date = sym_df["date"].iloc[-1].date()

                # Run both models
                gru_result = _run_gru(sym, sym_df)
                xgb_result = _run_xgb(sym, as_of_date)

                # Ensemble decision
                ensemble = _ensemble_decide(gru_result, xgb_result)

                # Calculate target_date (1D horizon)
                target_date = as_of_date
                days_added = 0
                while days_added < 1:
                    target_date += timedelta(days=1)
                    if target_date.weekday() < 5:
                        days_added += 1

                # Extract individual model details
                gru_dir = gru_result["direction"] if gru_result else None
                gru_bull = gru_result["bullish_pct"] if gru_result else None
                gru_bear = gru_result["bearish_pct"] if gru_result else None
                gru_side = gru_result["sideways_pct"] if gru_result else None
                gru_gap = gru_result["gap_pp"] if gru_result else None

                xgb_dir = xgb_result["direction"] if xgb_result else None
                xgb_bull = xgb_result["bullish_pct"] if xgb_result else None
                xgb_bear = xgb_result["bearish_pct"] if xgb_result else None
                xgb_side = xgb_result["sideways_pct"] if xgb_result else None
                xgb_gap = xgb_result["gap_pp"] if xgb_result else None

                session.execute(
                    text(
                        """INSERT INTO predictions
                        (symbol, horizon, predicted_at, predicted_direction,
                         bullish_pct, bearish_pct, sideways_pct, top_class_probability,
                         as_of_date, target_date, model_version,
                         actual_direction, was_correct,
                         gru_direction, gru_bullish_pct, gru_bearish_pct, gru_sideways_pct, gru_gap_pp,
                         xgb_direction, xgb_bullish_pct, xgb_bearish_pct, xgb_sideways_pct, xgb_gap_pp,
                         gate_reason)
                        VALUES
                        (:symbol, :horizon, :predicted_at, :predicted_direction,
                         :bullish_pct, :bearish_pct, :sideways_pct, :top_class_probability,
                         :as_of_date, :target_date, :model_version,
                         NULL, NULL,
                         :gru_direction, :gru_bullish_pct, :gru_bearish_pct, :gru_sideways_pct, :gru_gap_pp,
                         :xgb_direction, :xgb_bullish_pct, :xgb_bearish_pct, :xgb_sideways_pct, :xgb_gap_pp,
                         :gate_reason)"""
                    ),
                    {
                        "symbol": sym,
                        "horizon": "1D",
                        "predicted_at": datetime.utcnow(),
                        "predicted_direction": ensemble["direction"],
                        "bullish_pct": ensemble["bullish_pct"],
                        "bearish_pct": ensemble["bearish_pct"],
                        "sideways_pct": ensemble["sideways_pct"],
                        "top_class_probability": ensemble["top_class_probability"],
                        "as_of_date": as_of_date,
                        "target_date": target_date,
                        "model_version": ensemble["model_version"],
                        "gru_direction": gru_dir,
                        "gru_bullish_pct": gru_bull,
                        "gru_bearish_pct": gru_bear,
                        "gru_sideways_pct": gru_side,
                        "gru_gap_pp": gru_gap,
                        "xgb_direction": xgb_dir,
                        "xgb_bullish_pct": xgb_bull,
                        "xgb_bearish_pct": xgb_bear,
                        "xgb_sideways_pct": xgb_side,
                        "xgb_gap_pp": xgb_gap,
                        "gate_reason": ensemble.get("gate_reason", ""),
                    },
                )
                session.commit()
                success += 1

            except Exception:
                log.warning("[PREDICTION] Failed for %s", sym, exc_info=True)
                session.rollback()
                failed += 1

        session.close()
        log.info("[PREDICTION] Complete: %d succeeded, %d failed out of %d",
                 success, failed, len(symbols))
        return {
            "status": "success",
            "success": success,
            "failed": failed,
            "total": len(symbols),
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
    """Resolve actual outcomes for predictions whose target_date has passed.

    Uses trading dates (not calendar days) to determine when outcomes
    are available. For 1D horizon, waits 1 trading day. For 1W, waits
    5 trading days. For 1M, waits 21 trading days.
    """
    log.info("[EVALUATION] Starting outcome evaluation")

    try:
        import pandas as pd
        from sqlalchemy import text as sql_text

        from app.data.features.labeling import DEFAULT_THRESHOLD, label_from_return

        features_path = Path("data/features/features_daily.parquet")
        if not features_path.exists():
            log.warning("[EVALUATION] features_daily.parquet not found — skipping")
            return {"status": "skipped", "reason": "no_features"}

        features_df = pd.read_parquet(features_path)
        features_df["date"] = pd.to_datetime(features_df["date"]).dt.date

        session = _get_sync_session()
        today = date.today()

        # Find predictions that need backfilling
        rows = session.execute(
            sql_text(
                """SELECT id, symbol, horizon, predicted_direction, as_of_date, target_date
                FROM predictions
                WHERE actual_direction IS NULL
                  AND target_date <= :today
                ORDER BY target_date ASC
                LIMIT 5000"""
            ),
            {"today": today},
        ).fetchall()

        if not rows:
            log.info("[EVALUATION] No unresolved predictions")
            session.close()
            return {"status": "success", "updated": 0}

        log.info("[EVALUATION] Evaluating %d pending predictions", len(rows))
        updated = 0
        correct = 0
        uncertain_excluded = 0

        for row in rows:
            pred_id, symbol, horizon, predicted_direction, as_of_date, target_date = row

            sym_df = features_df[features_df["symbol"] == symbol].sort_values("date")
            as_of_close = sym_df.loc[sym_df["date"] == as_of_date, "close"]
            target_close = sym_df.loc[sym_df["date"] == target_date, "close"]

            if as_of_close.empty or target_close.empty:
                continue

            c_as_of = float(as_of_close.iloc[0])
            c_target = float(target_close.iloc[0])

            if c_as_of == 0:
                continue

            fwd_return = (c_target - c_as_of) / c_as_of
            actual_direction = label_from_return(fwd_return, DEFAULT_THRESHOLD)

            # "uncertain" predictions: record actual but don't score
            if predicted_direction == "uncertain":
                was_correct = None
                uncertain_excluded += 1
            else:
                was_correct = predicted_direction == actual_direction

            session.execute(
                sql_text(
                    """UPDATE predictions
                    SET actual_direction = :actual_direction,
                        was_correct = :was_correct
                    WHERE id = :id"""
                ),
                {
                    "actual_direction": actual_direction,
                    "was_correct": was_correct,
                    "id": pred_id,
                },
            )
            updated += 1
            if was_correct:
                correct += 1

            if updated % 200 == 0:
                session.commit()

        session.commit()
        session.close()

        log.info("[EVALUATION] Complete: %d updated, %d correct (%.1f%%), %d uncertain excluded",
                 updated, correct,
                 correct / updated * 100 if updated else 0,
                 uncertain_excluded)
        return {
            "status": "success",
            "updated": updated,
            "correct": correct,
            "uncertain_excluded": uncertain_excluded,
            "timestamp": datetime.utcnow().isoformat(),
        }

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

    # These stages are independent tasks in a serial pipeline. Immutable
    # signatures prevent Celery from injecting each prior task's result as a
    # positional argument into the next bound task (which accepts no such arg).
    workflow = chain(
        update_market_data_task.si(),
        generate_features_task.si(),
        generate_predictions_task.si(),
        evaluate_pending_predictions_task.si(),
    )
    result = workflow.apply_async()

    log.info("[DAILY] Pipeline dispatched — group_id=%s", result.id)
    return {"status": "dispatched", "group_id": result.id}
