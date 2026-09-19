from celery import Celery
from celery.schedules import crontab

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
        # New: Recommendation cache
        "app.tasks.recommendation_cache",
        # New: Risk tasks (Monte Carlo, threshold alerts)
        "app.tasks.risk_tasks",
        # New: Sentiment aggregation
        "app.tasks.sentiment_tasks",
        # New: Community tasks
        "app.tasks.community_tasks",
    ],
)

from celery.schedules import crontab

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
            "schedule": crontab(hour=2, minute=0),  # 02:00 PKT
        },
        "daily-feature-generation": {
            "task": "app.tasks.daily_workflow.generate_features",
            "schedule": crontab(hour=3, minute=0),
        },
        "daily-predictions": {
            "task": "app.tasks.daily_workflow.generate_predictions",
            "schedule": crontab(hour=4, minute=0),
        },
        "daily-outcome-evaluation": {
            "task": "app.tasks.daily_workflow.evaluate_pending",
            "schedule": crontab(hour=5, minute=0),
        },
        # ── Weekly: retraining pipeline ──
        "weekly-retraining": {
            "task": "app.tasks.weekly_retraining.run_weekly_pipeline",
            "schedule": crontab(day_of_week=0, hour=1, minute=0),  # Sunday 01:00
        },
        # ── Monitoring: daily ──
        "daily-performance-monitoring": {
            "task": "app.tasks.model_monitoring.monitor_performance",
            "schedule": crontab(hour=6, minute=0),
        },
        "daily-drift-detection": {
            "task": "app.tasks.model_monitoring.detect_drift",
            "schedule": crontab(hour=7, minute=0),
        },
        # ── Recommendations: refresh every 4 hours ──
        "refresh-recommendations": {
            "task": "app.tasks.recommendation_cache.refresh_recommendations",
            "schedule": crontab(minute=0, hour="*/4"),
        },
        # ── Sentiment: aggregate daily ──
        "daily-sentiment-aggregation": {
            "task": "app.tasks.sentiment_tasks.aggregate_sentiment",
            "schedule": crontab(hour=8, minute=0),
        },
        # ── News ingestion: every 30 min on the clock, task gates on market hours ──
        "news-ingestion-market-aware": {
            "task": "app.tasks.scrape_news.run",
            "schedule": crontab(minute="*/30"),  # Every 30 min on the clock
        },
        # ── Rescore failed sentiment: hourly ──
        "rescore-failed-sentiment": {
            "task": "app.tasks.sentiment_tasks.rescore_failed_sentiment",
            "schedule": crontab(minute=0),  # Hourly
        },
    },
)

celery.autodiscover_tasks(["app.tasks"])
