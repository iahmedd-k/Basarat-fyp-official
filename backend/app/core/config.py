from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    PROJECT_NAME: str = "Basarat"
    API_V1_PREFIX: str = "/api/v1"
    DEBUG: bool = False

    # Auth
    SECRET_KEY: str = Field(..., min_length=32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # CORS
    CORS_ORIGINS: list[str] = []

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/basarat"
    DATABASE_URL_SYNC: str = "postgresql+psycopg2://postgres:postgres@localhost:5432/basarat"

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    CACHE_TTL_SECONDS: int = 300

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"

    # Firebase (push notifications)
    FIREBASE_CREDENTIALS_PATH: str = "firebase_credentials.json"

    # HuggingFace (FinBERT sentiment via Inference API)
    HF_API_TOKEN: str = ""

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

    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "allow"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        placeholder_values = {"change-me-in-production", "your-secret-key", "secret", "changeme", "dev-secret"}
        if self.SECRET_KEY.lower() in placeholder_values:
            raise ValueError(
                "SECRET_KEY must be set to a strong random value (32+ chars) in production. "
                "Generate with: openssl rand -hex 32"
            )


@lru_cache()
def get_settings() -> Settings:
    return Settings()
