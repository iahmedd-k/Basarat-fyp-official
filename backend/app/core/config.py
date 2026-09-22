import logging
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # CORS
    CORS_ORIGINS: list[str] = []
    TRUSTED_PROXY_IPS: list[str] = []

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/basarat"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/basarat"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_ENABLED: bool = True
    CACHE_TTL_SECONDS: int = 300

    # Celery & Task Runner
    USE_CELERY: bool = True
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Firebase (push notifications)
    FIREBASE_ENABLED: bool = False
    FIREBASE_CREDENTIALS_PATH: str = ""
    FIREBASE_PROJECT_ID: str = ""

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

    # Email verification
    EMAIL_VERIFICATION_TOKEN_EXPIRE_MINUTES: int = 30

    # Clerk Auth Webhook
    CLERK_WEBHOOK_SECRET: str = ""
    CLERK_SECRET_KEY: str = ""

    # HuggingFace (FinBERT sentiment via Inference API)
    HF_API_TOKEN: str = ""

    # Groq (LLM for Stock AI Assistant)
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # ML
    GRU_MODEL_PATH: str = "models/gru_v1"

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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        placeholder_values = {"change-me-in-production", "your-secret-key", "secret", "changeme", "dev-secret"}
        if self.SECRET_KEY.lower() in placeholder_values:
            raise ValueError(
                "SECRET_KEY must be set to a strong random value (32+ chars) in production. "
                "Generate with: openssl rand -hex 32"
            )
        if self.ENVIRONMENT in {"staging", "production"}:
            if self.DEBUG:
                raise ValueError("DEBUG must be false outside development")
            if not self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must be explicitly configured outside development")
            if "postgres:postgres@" in self.DATABASE_URL or "adminadmin" in self.DATABASE_URL:
                raise ValueError("DATABASE_URL must not use development credentials outside development")
            if self.FIREBASE_ENABLED and (
                not self.FIREBASE_CREDENTIALS_PATH
                or not Path(self.FIREBASE_CREDENTIALS_PATH).is_file()
            ):
                raise ValueError("FIREBASE_CREDENTIALS_PATH must point to a readable service-account file")
            if not all((self.SMTP_HOST, self.SMTP_FROM_EMAIL)):
                logging.getLogger(__name__).warning("SMTP_HOST or SMTP_FROM_EMAIL not configured; transactional emails will be disabled.")
            if not self.PASSWORD_RESET_URL:
                self.PASSWORD_RESET_URL = "basarat://reset-password?token={token}"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
