"""Legacy Celery entrypoint — delegates to the daily workflow tasks.

Prefer `app.tasks.daily_workflow.run_daily_pipeline` (Beat Mon–Fri 18:00 PKT).
This module remains for manual ops: `celery call app.tasks.run_forecast_inference.run`.
"""

import logging

from app.celery_app import celery

log = logging.getLogger(__name__)


@celery.task(name="app.tasks.run_forecast_inference.run")
def run():
    """Manual: upsert batch predictions then evaluate pending outcomes."""
    log.info("Starting forecast inference (delegating to daily_workflow tasks)")

    from app.tasks.daily_workflow import (
        evaluate_pending_predictions_task,
        generate_predictions_task,
    )

    predict_result = generate_predictions_task()
    eval_result = evaluate_pending_predictions_task()
    log.info(
        "Forecast inference complete predict=%s evaluate=%s",
        predict_result,
        eval_result,
    )
    return {"predict": predict_result, "evaluate": eval_result}
