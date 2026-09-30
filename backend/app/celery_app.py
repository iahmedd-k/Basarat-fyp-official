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
        "app.tasks.refresh_market_cache",
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
        "app.tasks.alert_tasks",
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
        # ── 1. Intraday Live Quotes (Mon–Fri 09:15 to 15:30 PKT Only) ──
        # Scrapes PSX once a minute during active trading session only.
        "refresh-market-session": {
            "task": "app.tasks.refresh_market_cache.refresh_market_session",
            "schedule": crontab(minute="*/1", hour="9-15", day_of_week="1-5"),
        },
        # ── 2. Intraday Alert Rules Evaluation (Mon–Fri 09:15 to 15:30 PKT Only) ──
        # Evaluates price triggers and target thresholds during trading session.
        "evaluate-alert-rules": {
            "task": "app.tasks.alert_tasks.evaluate_alert_rules",
            "schedule": crontab(minute="*/5", hour="9-15", day_of_week="1-5"),
        },
        # ── 3. News & Announcement Ingestion (Mon–Fri 09:00 to 17:00 PKT Only) ──
        # Ingests market news during active trading and post-close disclosure window.
        "news-ingestion-market-aware": {
            "task": "app.tasks.scrape_news.run",
            "schedule": crontab(minute="*/30", hour="9-17", day_of_week="1-5"),
        },
        # ── 4. Market Close Final Snapshot (Mon–Fri 17:00 PKT Once) ──
        # Ingests final session quotes and locks the daily close snapshot into Redis cache.
        # This saved data serves all evening and weekend users until next morning.
        "refresh-market-close-snapshot": {
            "task": "app.tasks.refresh_market_cache.refresh_market_cache",
            "kwargs": {"refresh_reference": True},
            "schedule": crontab(hour=17, minute=0, day_of_week="1-5"),
        },
        # ── 5. Master Daily Pipeline (Mon–Fri 18:00 PKT Once) ──
        # Reconciles yesterday's predictions, saves today's closes, generates ML features,
        # computes tomorrow's directional forecasts, and recalculates stock recommendations.
        "daily-workflow": {
            "task": "app.tasks.daily_workflow.run_daily_pipeline",
            "schedule": crontab(hour=18, minute=0, day_of_week="1-5"),
        },
        # ── 6. Daily Portfolio Risk Monitoring (Mon–Fri 18:30 PKT Once) ──
        "daily-risk-threshold-monitoring": {
            "task": "app.tasks.risk_tasks.check_all_portfolios_risk_breaches",
            "schedule": crontab(hour=18, minute=30, day_of_week="1-5"),
        },
        # ── 7. Rescore Failed Sentiment (Mon–Fri 10:00 to 17:00 PKT Hourly) ──
        "rescore-failed-sentiment": {
            "task": "app.tasks.sentiment_tasks.rescore_failed_sentiment",
            "schedule": crontab(minute=0, hour="10-17", day_of_week="1-5"),
        },
        # ── 8. Daily Drift & Performance Monitoring (Daily 06:00 & 07:00 PKT) ──
        "daily-performance-monitoring": {
            "task": "app.tasks.model_monitoring.monitor_performance",
            "schedule": crontab(hour=6, minute=0, day_of_week="1-5"),
        },
        "daily-drift-detection": {
            "task": "app.tasks.model_monitoring.detect_drift",
            "schedule": crontab(hour=7, minute=0, day_of_week="1-5"),
        },
        # ── 9. Weekly Index Constituents Refresh (Sunday 04:15 PKT Once) ──
        "refresh-market-constituents": {
            "task": "app.tasks.refresh_market_cache.refresh_market_cache",
            "kwargs": {"refresh_reference": True, "refresh_constituents": True},
            "schedule": crontab(day_of_week=0, minute=15, hour=4),
        },
        # ── 10. Weekly ML Model Retraining (Sunday 04:00 PKT Once) ──
        "weekly-retraining": {
            "task": "app.tasks.weekly_retraining.run_weekly_pipeline",
            "schedule": crontab(day_of_week=0, hour=4, minute=0),
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
