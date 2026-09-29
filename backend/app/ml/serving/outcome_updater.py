"""Outcome updater — resolve actual outcomes for past predictions.

Standalone:
    python -m app.ml.serving.outcome_updater

Prefer the Celery daily pipeline step `evaluate_pending` (18:00 PKT).
This script uses the same shared evaluator.
"""

import logging
import sys

from app.ml.serving.prediction_store import evaluate_pending_predictions_sync, pkt_today

log = logging.getLogger("outcome_updater")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        stream=sys.stdout,
    )

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from app.core.config import get_settings

    settings = get_settings()
    engine = create_engine(settings.DATABASE_URL_SYNC, pool_pre_ping=True)
    session = sessionmaker(bind=engine)()
    try:
        log.info("Running outcome evaluation for PKT date %s", pkt_today())
        result = evaluate_pending_predictions_sync(session)
        log.info("OUTCOME UPDATER COMPLETE: %s", result)
    finally:
        session.close()


if __name__ == "__main__":
    main()
