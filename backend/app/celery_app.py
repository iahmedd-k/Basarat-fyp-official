from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()
broker_urls = [settings.CELERY_BROKER_URL]
if settings.CLOUD_REDIS_URL and settings.CLOUD_REDIS_URL not in broker_urls:
    broker_urls.append(settings.CLOUD_REDIS_URL)

celery = Celery(
    "basarat",
    broker=broker_urls,
    backend=settings.CELERY_RESULT_BACKEND,
include=[
        "app.tasks.scrape_news",
        "app.tasks.refresh_market_cache",
        "app.tasks.news_tasks",
        "app.tasks.run_forecast_inference",
        "app.tasks.daily_workflow",
        "app.tasks.refresh_fundamentals",
        "app.tasks.weekly_retraining",
        "app.tasks.model_monitoring",
        "app.tasks.recommendation_cache",
        "app.tasks.risk_tasks",
        "app.tasks.community_tasks",
        "app.tasks.push_notifications",
        "app.tasks.alert_tasks",
        "app.tasks.email",
        "app.tasks.health",
        "app.tasks.refresh_shariah_cache",
        "app.tasks.refresh_etf_ipo",
        "app.tasks.portfolio_tasks",
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
    task_default_queue="default",
    beat_scheduler="app.core.celery_beat:HeartbeatPersistentScheduler",
    task_routes={
        "app.tasks.health.*": {"queue": "health"},
        "app.tasks.refresh_market_cache.refresh_market_session": {"queue": "market-live"},
        "app.tasks.refresh_market_cache.refresh_market_cache": {"queue": "market-live"},
        "app.tasks.scrape_news.run": {"queue": "news"},
        "app.tasks.news_tasks.*": {"queue": "news"},
        "app.tasks.refresh_fundamentals.*": {"queue": "fundamentals"},
        "app.tasks.weekly_retraining.*": {"queue": "ml-training"},
        "app.tasks.daily_workflow.*": {"queue": "data-pipeline"},
    },
    result_expires=86400,
    broker_connection_retry_on_startup=True,
    broker_failover_strategy="round-robin",
    # Time limits for long-running tasks
    task_soft_time_limit=3600,
    task_time_limit=7200,
    beat_schedule={
        "celery-beat-heartbeat": {
            "task": "app.tasks.health.beat_heartbeat",
            "schedule": 30.0,
        },
        # ── Daily: data update + features + predictions + evaluation ──
        # Mon–Thu 15:35 and Fri 16:35 Asia/Karachi, five minutes after the
        # configured PSX close (the pipeline skips weekends and holidays):
        #   update_market_data → generate_features → generate_predictions (upsert)
        #   → evaluate_pending (set actual_direction from closes) → sentiment → recs
        "daily-workflow": {
            "task": "app.tasks.daily_workflow.run_daily_pipeline",
            "schedule": crontab(hour=15, minute=35, day_of_week="1-4"),
        },
        "daily-workflow-friday": {
            "task": "app.tasks.daily_workflow.run_daily_pipeline",
            "schedule": crontab(hour=16, minute=35, day_of_week="5"),
        },
        # Fundamentals are refreshed separately so a slow/rate-limited source
        # cannot block the OHLCV/features/predictions chain.
        "daily-fundamentals": {
            "task": "app.tasks.refresh_fundamentals.refresh_fundamentals",
            "schedule": crontab(hour=17, minute=30, day_of_week="1-4"),
        },
        "daily-fundamentals-friday": {
            "task": "app.tasks.refresh_fundamentals.refresh_fundamentals",
            "schedule": crontab(hour=18, minute=0, day_of_week="5"),
        },
        # ── Weekly: retraining pipeline ──
        "weekly-retraining": {
            "task": "app.tasks.weekly_retraining.run_weekly_pipeline",
            "schedule": crontab(day_of_week=1, hour=4, minute=0),  # Monday 04:00 PKT
        },
        # ── Monitoring: daily ──
        "daily-performance-monitoring": {
            "task": "app.tasks.model_monitoring.monitor_performance",
            "schedule": crontab(hour=6, minute=0, day_of_week="1-5"),
        },
        "daily-drift-detection": {
            "task": "app.tasks.model_monitoring.detect_drift",
            "schedule": crontab(hour=7, minute=0, day_of_week="1-5"),
        },
        "refresh-shariah-cache": {
            "task": "app.tasks.refresh_shariah_cache.refresh_shariah_cache",
            "schedule": crontab(hour=9, minute=5, day_of_week="1-5"),
        },
        # ── Save the previous session's final quote snapshot once after close ──
        # API handlers serve this shared Redis snapshot; they do not scrape PSX.
        "refresh-market-close-snapshot": {
            "task": "app.tasks.refresh_market_cache.refresh_market_cache",
            "kwargs": {"refresh_reference": True},
            "schedule": crontab(hour=17, minute=0, day_of_week="1-5"),
        },
        "refresh-market-screener": {
            "task": "app.tasks.refresh_market_cache.refresh_market_cache",
            "kwargs": {"refresh_quotes": False, "refresh_screener": True},
            "schedule": crontab(minute="*/30", hour="9-15", day_of_week="1-5"),
        },
        "refresh-etf-ipo-catalogs": {
            "task": "app.tasks.refresh_etf_ipo.refresh_etf_ipo_catalogs",
            "schedule": crontab(minute="*/30", hour="9-16", day_of_week="1-5"),
        },
        # ── Intraday shared snapshot during weekdays (task self-gates hours) ──
        # A weekday crontab prevents even enqueueing this task on weekends.
        "refresh-market-session": {
            "task": "app.tasks.refresh_market_cache.refresh_market_session",
            "schedule": crontab(minute="*", day_of_week="1-5"),
        },
        # ── Evaluate Alert Rules & Watchlist Targets every 5 minutes (task gates hours) ──
        "evaluate-alert-rules": {
            "task": "app.tasks.alert_tasks.evaluate_alert_rules",
            "schedule": crontab(minute="*/5", day_of_week="1-5"),
        },
        # ── Daily Portfolio Risk Breach Monitoring ──
        "daily-risk-threshold-monitoring": {
            "task": "app.tasks.risk_tasks.check_all_portfolios_risk_breaches",
            "schedule": crontab(hour=18, minute=30, day_of_week="1-5"),
        },
        # Sentiment and recommendation publication run as dependent final
        # stages of daily-workflow, after OHLCV/features/forecast finish.
        # ── News ingestion: every 30 min on the clock, task gates on market hours ──
        "news-ingestion-market-aware": {
            "task": "app.tasks.scrape_news.run",
            "schedule": crontab(minute="*/30", day_of_week="1-5"),
        },
        # Index membership changes rarely; refresh it weekly, not on every API day.
        "refresh-market-constituents": {
            "task": "app.tasks.refresh_market_cache.refresh_market_cache",
            "kwargs": {"refresh_reference": True, "refresh_constituents": True},
            "schedule": crontab(day_of_week=5, minute=15, hour=4),
        },
        # ── Rescore failed sentiment: hourly ──
        "rescore-failed-sentiment": {
            "task": "app.tasks.sentiment_tasks.rescore_failed_sentiment",
            "schedule": crontab(minute=0, day_of_week="1-5"),  # Hourly on trading weekdays
        },
        # ── Portfolio performance precomputation: daily after market close ──
        # Runs 10 minutes after daily-workflow completes (15:45 Mon-Thu, 16:45 Fri)
        "precompute-portfolio-performance": {
            "task": "app.tasks.portfolio_tasks.precompute_all_portfolio_performance",
            "schedule": crontab(hour=15, minute=45, day_of_week="1-4"),
        },
        "precompute-portfolio-performance-friday": {
            "task": "app.tasks.portfolio_tasks.precompute_all_portfolio_performance",
            "schedule": crontab(hour=16, minute=45, day_of_week="5"),
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
