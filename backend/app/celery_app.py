from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "basarat",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        # Existing tasks
        "app.tasks.scrape_market",
        "app.tasks.scrape_news",
        "app.tasks.run_forecast_inference",
        "app.tasks.compute_sentiment",
        "app.tasks.evaluate_alert_rules",
        # New: Daily workflow
        "app.tasks.daily_workflow",
        # New: Weekly retraining
        "app.tasks.weekly_retraining",
        # New: Model monitoring
        "app.tasks.model_monitoring",
    ],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Karachi",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    # Time limits for long-running tasks
    task_soft_time_limit=3600,
    task_time_limit=7200,
    beat_schedule={
        # ── Daily: data update + features + predictions + evaluation ──
        "daily-data-update": {
            "task": "app.tasks.daily_workflow.update_market_data",
            "schedule": 86400.0,  # 24 hours
        },
        "daily-feature-generation": {
            "task": "app.tasks.daily_workflow.generate_features",
            "schedule": 86400.0,
        },
        "daily-predictions": {
            "task": "app.tasks.daily_workflow.generate_predictions",
            "schedule": 86400.0,
        },
        "daily-outcome-evaluation": {
            "task": "app.tasks.daily_workflow.evaluate_pending",
            "schedule": 86400.0,
        },
        # ── Weekly: retraining pipeline ──
        "weekly-retraining": {
            "task": "app.tasks.weekly_retraining.run_weekly_pipeline",
            "schedule": 604800.0,  # 7 days
        },
        # ── Monitoring: daily ──
        "daily-performance-monitoring": {
            "task": "app.tasks.model_monitoring.monitor_performance",
            "schedule": 86400.0,
        },
        "daily-drift-detection": {
            "task": "app.tasks.model_monitoring.detect_drift",
            "schedule": 86400.0,
        },
    },
)

celery.autodiscover_tasks(["app.tasks"])
