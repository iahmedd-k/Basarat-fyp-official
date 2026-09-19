"""Celery task — run batch forecast inference for all active symbols.

Runs daily (via celery-beat schedule). Loads the model, iterates over all
active symbols, runs inference, and logs each prediction to the database.
Stores individual GRU and XGB outputs alongside ensemble results for
audit trail and model comparison.

Also backfills actual_direction/was_correct for past predictions whose
target_date has passed.
"""

import logging
from datetime import date, datetime, timedelta
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.celery_app import celery

log = logging.getLogger(__name__)


def _get_sync_session() -> Session:
    from app.core.config import get_settings
    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    return sessionmaker(bind=engine)()


@celery.task(name="app.tasks.run_forecast_inference.run")
def run():
    """Daily batch: run inference for all active symbols + backfill old predictions."""
    log.info("Starting daily forecast inference task")

    try:
        _run_batch_forecast()
    except Exception:
        log.exception("Batch forecast failed")

    try:
        _backfill_actuals()
    except Exception:
        log.exception("Backfill actuals failed")

    log.info("Daily forecast inference task complete")


def _run_batch_forecast():
    """Run inference for every active symbol and log to DB."""
    import pandas as pd

    from app.data.scraper.symbol_universe import get_active_symbols
    from app.ml.serving.inference import (
        _ensemble_decide,
        _run_gru,
        _run_xgb,
        FEATURES_PATH,
    )
    from app.ml.serving.model_loader import artifacts

    if not artifacts.model_ready:
        log.warning("Model not ready — skipping batch forecast")
        return

    # Load features once
    df = pd.read_parquet(FEATURES_PATH)
    df["date"] = pd.to_datetime(df["date"])

    active = get_active_symbols()
    symbols = [e["symbol"] for e in active]
    log.info("Running batch forecast for %d symbols", len(symbols))

    session = _get_sync_session()
    success = 0
    failed = 0

    for sym in symbols:
        try:
            sym_df = df[df["symbol"] == sym].copy()
            sym_df = sym_df.sort_values("date").reset_index(drop=True)

            if len(sym_df) < artifacts.window_size:
                log.warning("Skipping %s: insufficient data (%d rows)", sym, len(sym_df))
                failed += 1
                continue

            as_of_date = sym_df["date"].iloc[-1].date()

            # Run both models individually
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
            log.warning("Forecast failed for %s", sym, exc_info=True)
            session.rollback()
            failed += 1

    session.close()
    log.info("Batch forecast: %d succeeded, %d failed out of %d", success, failed, len(symbols))


def _backfill_actuals():
    """For predictions whose target_date has passed, compute actual direction and was_correct."""
    import pandas as pd

    from app.data.features.labeling import DEFAULT_THRESHOLD, label_from_return
    from app.ml.serving.model_loader import artifacts

    if not artifacts.model_ready:
        return

    features_path = Path("data/features/features_daily.parquet")
    if not features_path.exists():
        log.warning("features_daily.parquet not found — skipping backfill")
        return

    features_df = pd.read_parquet(features_path)
    features_df["date"] = pd.to_datetime(features_df["date"])

    session = _get_sync_session()

    # Find predictions that need backfilling
    rows = session.execute(
        text(
            """SELECT id, symbol, predicted_direction, as_of_date, target_date
            FROM predictions
            WHERE actual_direction IS NULL
              AND target_date <= :today
            ORDER BY target_date ASC
            LIMIT 5000"""
        ),
        {"today": date.today()},
    ).fetchall()

    if not rows:
        log.info("No predictions need backfilling")
        session.close()
        return

    log.info("Backfilling %d predictions", len(rows))
    updated = 0

    for row in rows:
        pred_id, symbol, predicted_direction, as_of_date, target_date = row

        sym_df = features_df[features_df["symbol"] == symbol].copy()
        sym_df = sym_df.sort_values("date")

        as_of_dt = pd.Timestamp(as_of_date)
        target_dt = pd.Timestamp(target_date)

        close_as_of = sym_df.loc[sym_df["date"] == as_of_dt, "close"]
        close_target = sym_df.loc[sym_df["date"] == target_dt, "close"]

        if close_as_of.empty or close_target.empty:
            continue

        c_as_of = float(close_as_of.iloc[0])
        c_target = float(close_target.iloc[0])

        if c_as_of == 0:
            continue

        fwd_return = (c_target - c_as_of) / c_as_of
        actual_direction = label_from_return(fwd_return, DEFAULT_THRESHOLD)

        was_correct = predicted_direction == actual_direction

        session.execute(
            text(
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

        if updated % 200 == 0:
            session.commit()

    session.commit()
    session.close()
    log.info("Backfilled %d predictions with actual directions", updated)
