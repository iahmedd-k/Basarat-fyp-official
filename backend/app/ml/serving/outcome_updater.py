"""Outcome updater — daily script that resolves actual outcomes for past predictions.

Standalone script (no Celery):
    python -m app.ml.serving.outcome_updater

For every predictions row where target_date <= today AND actual_direction IS NULL,
looks up the actual close price for target_date from features_daily.parquet,
computes the realized return vs the close price at the as_of_date,
applies the same 1% threshold from labeling.py to classify actual_direction,
sets was_correct = (actual_direction == predicted_direction).

Convention for "uncertain" predictions:
    - actual_direction is still resolved (the market moved, we record what happened)
    - was_correct is set to NULL (not scored) — "uncertain" is an abstention,
      not a wrong call. This keeps accuracy metrics meaningful: only directional
      claims are scored.
"""

import logging
import sys
from datetime import date, datetime

import pandas as pd
from sqlalchemy import select

from app.data.features.labeling import DEFAULT_THRESHOLD
from app.db.base import async_session_factory
from app.models.prediction import Prediction

log = logging.getLogger("outcome_updater")

FEATURES_PATH = "data/features/features_daily.parquet"


def _classify_return(forward_return: float, threshold: float = DEFAULT_THRESHOLD) -> str:
    """Classify a forward return into bullish/bearish/sideways using the same
    threshold as labeling.py."""
    if forward_return > threshold:
        return "bullish"
    elif forward_return < -threshold:
        return "bearish"
    return "sideways"


async def update_outcomes() -> None:
    """Resolve actual outcomes for all pending predictions."""
    today = date.today()

    # Load features data once
    features = pd.read_parquet(FEATURES_PATH)
    features["date"] = pd.to_datetime(features["date"]).dt.date

    async with async_session_factory() as db:
        # Find all unresolved predictions where target_date has passed
        result = await db.execute(
            select(Prediction).where(
                Prediction.target_date <= today,
                Prediction.actual_direction.is_(None),
            )
        )
        rows = result.scalars().all()

        if not rows:
            log.info("No unresolved predictions to update")
            return

        updated = 0
        correct = 0
        uncertain_excluded = 0
        total_resolved = 0

        for row in rows:
            # Look up close prices
            sym_features = features[features["symbol"] == row.symbol].sort_values("date")
            as_of_close = sym_features.loc[sym_features["date"] == row.as_of_date, "close"]
            target_close = sym_features.loc[sym_features["date"] == row.target_date, "close"]

            if as_of_close.empty or target_close.empty:
                log.warning("Missing price data for %s (as_of=%s, target=%s), skipping",
                            row.symbol, row.as_of_date, row.target_date)
                continue

            as_of_price = float(as_of_close.iloc[0])
            target_price = float(target_close.iloc[0])
            forward_return = (target_price - as_of_price) / as_of_price

            actual_direction = _classify_return(forward_return)

            # "uncertain" predictions: record actual but don't score
            if row.predicted_direction == "uncertain":
                was_correct = None
                uncertain_excluded += 1
            else:
                was_correct = actual_direction == row.predicted_direction

            row.actual_direction = actual_direction
            row.was_correct = was_correct
            await db.flush()

            updated += 1
            if was_correct:
                correct += 1

            log.info("Resolved %s target=%s: return=%.4f -> %s (predicted=%s, correct=%s)",
                     row.symbol, row.target_date, forward_return,
                     actual_direction, row.predicted_direction, was_correct)

        await db.commit()

        # Overall accuracy summary (exclude uncertain from accuracy calc)
        result = await db.execute(
            select(Prediction).where(
                Prediction.was_correct.is_not(None),
                Prediction.predicted_direction != "uncertain",
            )
        )
        all_scored = result.scalars().all()
        total_resolved = len(all_scored)
        total_correct = sum(1 for r in all_scored if r.was_correct)

        log.info("=" * 60)
        log.info("OUTCOME UPDATER COMPLETE")
        log.info("  Updated this run:    %d rows", updated)
        log.info("  Correct this run:    %d / %d (%.1f%%)", correct, updated,
                 correct / updated * 100 if updated else 0)
        log.info("  Uncertain excluded:  %d rows (not scored)", uncertain_excluded)
        log.info("  Overall scored:      %d total (excl uncertain)", total_resolved)
        log.info("  Overall accuracy:    %d / %d (%.1f%%)",
                 total_correct, total_resolved,
                 total_correct / total_resolved * 100 if total_resolved else 0)
        log.info("=" * 60)


def main() -> None:
    import asyncio

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    asyncio.run(update_outcomes())


if __name__ == "__main__":
    main()
