from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "basarat",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Karachi",
    enable_utc=True,
    task_track_started=True,
    beat_schedule={
        "scrape-market-hourly": {
            "task": "app.tasks.scrape_market.run",
            "schedule": 3600.0,
        },
        "scrape-news-every-30m": {
            "task": "app.tasks.scrape_news.run",
            "schedule": 1800.0,
        },
        "run-forecast-daily": {
            "task": "app.tasks.run_forecast_inference.run",
            "schedule": 86400.0,
        },
        "compute-sentiment-every-30m": {
            "task": "app.tasks.compute_sentiment.run",
            "schedule": 1800.0,
        },
        "evaluate-alerts-minute": {
            "task": "app.tasks.evaluate_alert_rules.run",
            "schedule": 60.0,
        },
        "retrain-gru-monthly": {
            "task": "app.tasks.retrain_gru_model.run",
            "schedule": 2592000.0,
        },
    },
)

celery.autodiscover_tasks(["app.tasks"])
