import logging
import os
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
from app.core.database_urls import sync_database_url


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    PROJECT_NAME: str = "Basarat"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["development", "staging", "production", "test"] = "development"
    DEBUG: bool = False

    # Auth
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    BCRYPT_ROUNDS: int = 10

    # CORS
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ]
    TRUSTED_PROXY_IPS: list[str] = []
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "testserver"]

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/basarat"
    DATABASE_URL_SYNC: str = ""
    CLOUD_DATABASE_URL: str = ""

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CLOUD_REDIS_URL: str = ""
    REDIS_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 300

    # Celery & Task Runner
    USE_CELERY: bool = True
    RUN_STARTUP_MARKET_WARMUP: bool = True
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Firebase (push notifications)
    FIREBASE_ENABLED: bool = False
    FIREBASE_CREDENTIALS_PATH: str = ""
    FIREBASE_PROJECT_ID: str = ""

    # Cloudinary image storage
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""

    # Optional HTTP metrics endpoint; enable only on a monitored deployment.
    PROMETHEUS_METRICS_ENABLED: bool = False
    PROMETHEUS_METRICS_USERNAME: str = ""
    PROMETHEUS_METRICS_PASSWORD: str = ""

    # Transactional email (SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 465
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_FROM_EMAIL: str = ""
    SMTP_USE_TLS: bool = True
    FRONTEND_URL: str = ""
    PASSWORD_RESET_URL: str = ""

    # SendGrid
    SENDGRID_API_KEY: str = ""
    SENDGRID_FROM_EMAIL: str = ""

    # Email verification and password reset
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES: int = 10
    PASSWORD_RESET_TOKEN_EXPIRE_MINUTES: int = 10
    PASSWORD_RESET_GRANT_EXPIRE_MINUTES: int = 15

    # Clerk Auth Webhook
    CLERK_WEBHOOK_SECRET: str = ""
    CLERK_SECRET_KEY: str = ""

    # OAuth Providers (Google & Apple)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    APPLE_CLIENT_ID: str = ""  # Service ID or Bundle ID (e.g. pk.basarat.app)
    APPLE_TEAM_ID: str = ""
    APPLE_KEY_ID: str = ""

    # Stripe Payments (Subscriptions)
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PUBLISHABLE_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_MONTHLY_PKR: int = 149900  # PKR 1,499.00 in smallest unit
    STRIPE_PRICE_ANNUAL_PKR: int = 1299900  # PKR 12,999.00 in smallest unit
    STRIPE_PRICE_MONTHLY_USD: int = 499     # $4.99 in cents
    STRIPE_PRICE_ANNUAL_USD: int = 4499     # $44.99 in cents

    # HuggingFace (FinBERT sentiment via Inference API)
    HF_API_TOKEN: str = ""

    # Groq (LLM for Stock AI Assistant) — models available on free keys vary; use list from /models
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    # Prefer smaller free-tier OSS model; fall back to Qwen mid-size.
    GROQ_MODEL: str = "openai/gpt-oss-20b"
    GROQ_FALLBACK_MODEL: str = "qwen/qwen3.8-27b"

    # ML
    GRU_MODEL_PATH: str = "models/production/v3"

    # Training / Retraining
    TRAINING_LOOKBACK_YEARS: int = 5
    TRAINING_MIN_NEW_SAMPLES: int = 100
    MIN_ACCURACY_IMPROVEMENT: float = 0.01
    MIN_F1_IMPROVEMENT: float = 0.01
    MAX_ABSTENTION_INCREASE: float = 0.05
    LABEL_THRESHOLD: float = 0.01
    WINDOW_SIZE: int = 30

    # News ingestion — market-aware schedule (Asia/Karachi, UTC+5)
    NEWS_TIMEZONE: str = "Asia/Karachi"
    # PSX market session
    MARKET_OPEN_HOUR: int = 9
    MARKET_OPEN_MINUTE: int = 15
    MARKET_CLOSE_HOUR: int = 15
    MARKET_CLOSE_MINUTE: int = 30
    # Post-market ingestion window
    POST_MARKET_CLOSE_HOUR: int = 17
    POST_MARKET_CLOSE_MINUTE: int = 0
    # Live session quotes (scraper-backed shared snapshot; API stays read-only)
    MARKET_SESSION_REFRESH_ENABLED: bool = True
    MARKET_SESSION_REFRESH_SECONDS: int = 60  # Celery Beat cadence during open hours
    MARKET_QUOTES_TTL_SECONDS: int = 90  # Redis TTL ≈ refresh + buffer
    MARKET_LIVE_PUBSUB_CHANNEL: str = "market:quotes:live"
    MARKET_CIRCUIT_BREAKER_SECONDS: int = 900  # pause scrapes after PSX 403/429
    MARKET_REST_POLL_SECONDS: int = 15  # Android/web REST fallback interval (cache-only)
    # Daily fundamentals refresh. The worker is deliberately single-threaded
    # and paced because one symbol can require several upstream requests.
    FUNDAMENTALS_REFRESH_ENABLED: bool = True
    # Fundamentals are a low-frequency job; keep the shared source load
    # conservative even when the worker is running in cloud infrastructure.
    FUNDAMENTALS_REQUEST_DELAY_SECONDS: float = 30.0
    FUNDAMENTALS_REQUEST_JITTER_SECONDS: float = 15.0
    FUNDAMENTALS_REQUEST_TIMEOUT_SECONDS: float = 15.0
    FUNDAMENTALS_SYMBOL_TIMEOUT_SECONDS: float = 180.0
    FUNDAMENTALS_MAX_RETRIES: int = 2
    FUNDAMENTALS_RETRY_BASE_SECONDS: int = 60
    FUNDAMENTALS_REDIS_TTL_SECONDS: int = 172800
    FUNDAMENTALS_STALE_AFTER_DAYS: int = 7
    # Ingestion interval during active windows (seconds)
    NEWS_INGESTION_INTERVAL_MARKET: int = 1800      # 30 min during market
    NEWS_INGESTION_INTERVAL_POST_MARKET: int = 3600  # 60 min post-market
    # Manual refresh cooldown (seconds)
    NEWS_REFRESH_COOLDOWN: int = 300  # 5 minutes

    # News config flags (Section 12)
    NEWS_SCHEDULE_MINUTES: int = 30
    NEWS_MARKET_GATING_ENABLED: bool = True
    NEWS_POST_CLOSE_MINUTES: int = 0
    NEWS_MARKET_HOURS_CONFIG: str = ""  # path or DB table
    NEWS_REFRESH_COOLDOWN_SECONDS: int = 300
    PSX_FETCH_ENABLED: bool = True
    PSX_MAX_PAGES_PER_RUN: int = 5
    PSX_MIN_REQUEST_INTERVAL_SECONDS: int = 2
    PSX_BACKFILL_DAYS: int = 30
    PSX_EPS_RULE_ENABLED: bool = False
    FINBERT_ENABLED: bool = True
    SENTIMENT_MIN_CONFIDENCE: float = 0.6
    METTIS_FETCH_ENABLED: bool = True
    OGRA_FETCH_ENABLED: bool = True
    FBR_MOF_FETCH_ENABLED: bool = True

    MAX_FILE_SIZE_MB: int = 10
    LOCAL_TEMP_DIR: str = "./tmp"

    @staticmethod
    def _is_local_host(value: str | None) -> bool:
        if not value:
            return False
        parsed = urlparse(value)
        host = (parsed.hostname or "").lower()
        return host in {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        runtime_database_url = os.environ.get("DATABASE_URL")
        runtime_database_url_sync = os.environ.get("DATABASE_URL_SYNC")
        runtime_redis_url = os.environ.get("REDIS_URL")
        runtime_cloud_database_url = os.environ.get("CLOUD_DATABASE_URL")
        runtime_cloud_redis_url = os.environ.get("CLOUD_REDIS_URL")

        if runtime_database_url:
            self.DATABASE_URL = runtime_database_url
        if runtime_database_url_sync:
            self.DATABASE_URL_SYNC = runtime_database_url_sync
        if runtime_redis_url:
            self.REDIS_URL = runtime_redis_url
        if runtime_cloud_database_url:
            self.CLOUD_DATABASE_URL = runtime_cloud_database_url
        if runtime_cloud_redis_url:
            self.CLOUD_REDIS_URL = runtime_cloud_redis_url

        cloud_database_url = self.CLOUD_DATABASE_URL or ""
        cloud_redis_url = self.CLOUD_REDIS_URL or ""

        if self.ENVIRONMENT in {"staging", "production"}:
            if runtime_cloud_database_url:
                self.DATABASE_URL = runtime_cloud_database_url
                if not runtime_database_url_sync:
                    self.DATABASE_URL_SYNC = ""
            elif runtime_database_url and self._is_local_host(self.DATABASE_URL):
                raise ValueError("DATABASE_URL cannot point to localhost in production/staging. Set a cloud database URL instead.")

            if self._is_local_host(self.DATABASE_URL):
                if not cloud_database_url:
                    raise ValueError("DATABASE_URL cannot point to localhost in production/staging. Set CLOUD_DATABASE_URL.")
                self.DATABASE_URL = cloud_database_url
                if not runtime_database_url_sync:
                    self.DATABASE_URL_SYNC = ""

            if runtime_cloud_redis_url:
                self.REDIS_URL = runtime_cloud_redis_url
            elif runtime_redis_url and self._is_local_host(self.REDIS_URL):
                raise ValueError("REDIS_URL cannot point to localhost in production/staging. Set a cloud Redis URL instead.")

            for setting_name in ("REDIS_URL", "CELERY_BROKER_URL", "CELERY_RESULT_BACKEND"):
                value = getattr(self, setting_name)
                if self._is_local_host(value):
                    if not cloud_redis_url:
                        raise ValueError(f"{setting_name} cannot point to localhost in production/staging. Set a cloud Redis URL.")
                    setattr(self, setting_name, cloud_redis_url)

            if any(self._is_local_host(url) for url in (self.DATABASE_URL, self.DATABASE_URL_SYNC)):
                raise ValueError("Database URLs must not use localhost or 127.0.0.1 in production/staging.")

        if not self.DATABASE_URL_SYNC:
            self.DATABASE_URL_SYNC = sync_database_url(self.DATABASE_URL).render_as_string(hide_password=False)

        placeholder_values = {"change-me-in-production", "your-secret-key", "secret", "changeme", "dev-secret"}
        if self.SECRET_KEY.lower() in placeholder_values:
            raise ValueError(
                "SECRET_KEY must be set to a strong random value (32+ chars) in production. "
                "Generate with: openssl rand -hex 32"
            )
        if self.ENVIRONMENT in {"staging", "production"}:
            if self.DEBUG:
                raise ValueError("DEBUG must be false outside development")
            if "postgres:postgres@" in self.DATABASE_URL or "adminadmin" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL must not use development credentials outside development")
            firebase_available = False
            if self.FIREBASE_ENABLED and self.FIREBASE_CREDENTIALS_PATH:
                try:
                    firebase_available = Path(self.FIREBASE_CREDENTIALS_PATH).is_file()
                except Exception:
                    firebase_available = False
            if self.FIREBASE_ENABLED and not firebase_available:
                logging.getLogger(__name__).warning(
                    "Firebase credentials are unavailable; push notifications will be disabled."
                )
            if not all((self.SMTP_HOST, self.SMTP_FROM_EMAIL)):
                logging.getLogger(__name__).warning("SMTP_HOST or SMTP_FROM_EMAIL not configured; transactional emails will be disabled.")
            if not self.PASSWORD_RESET_URL:
                self.PASSWORD_RESET_URL = "basarat://reset-password?token={token}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
