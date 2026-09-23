from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery = Celery(
    "basarat",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.tasks.scrape_news",
        "app.tasks.news_tasks",
        "app.tasks.run_forecast_inference",
        "app.tasks.daily_workflow",
        "app.tasks.weekly_retraining",
        "app.tasks.model_monitoring",
        "app.tasks.recommendation_cache",
        "app.tasks.risk_tasks",
        "app.tasks.sentiment_tasks",
        "app.tasks.community_tasks",
        "app.tasks.push_notifications",
        "app.tasks.email",
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
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    # Time limits for long-running tasks
    task_soft_time_limit=3600,
    task_time_limit=7200,
    beat_schedule={
        # ── Daily: data update + features + predictions + evaluation ──
        "daily-workflow": {
            "task": "app.tasks.daily_workflow.run_daily_pipeline",
            "schedule": crontab(hour=2, minute=0),  # 02:00 PKT
        },
        # ── Weekly: retraining pipeline ──
        "weekly-retraining": {
            "task": "app.tasks.weekly_retraining.run_weekly_pipeline",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),  # Sunday 04:00 PKT
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
        # ── PSX Portfolio Announcements: every 10 min during active hours ──
        "sync-portfolio-announcements": {
            "task": "app.tasks.news_tasks.sync_portfolio_announcements",
            "schedule": crontab(minute="*/10"),
        },
        # ── Rescore failed sentiment: hourly ──
        "rescore-failed-sentiment": {
            "task": "app.tasks.sentiment_tasks.rescore_failed_sentiment",
            "schedule": crontab(minute=0),  # Hourly
        },
    },
)

celery.autodiscover_tasks(["app.tasks"])

from celery.signals import worker_process_init


@worker_process_init.connect
def reset_db_connections(**kwargs):
    """Dispose any parent-inherited connections when a worker process forks."""
    try:
        from app.db.base import engine, _sync_engine
        engine.sync_engine.dispose()
        if _sync_engine is not None:
            _sync_engine.dispose()
    except Exception:
        pass


