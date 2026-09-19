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
    MARKET_OPEN_MINUTE: int = 30
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

    # Community share links / deep links
    SHARE_BASE_URL: str = "https://yourapp.link"
    DEEP_LINK_SCHEME: str = "yourapp"
    ANDROID_PACKAGE: str = "com.yourapp.android"
    PLAY_STORE_URL: str = "https://play.google.com/store/apps/details?id=com.yourapp.android"
    TEASER_IMAGE_URL: str = "https://yourapp.com/static/share-preview.png"
    COMMUNITY_REPORT_THRESHOLD: int = 5

    # Cloudinary (community media uploads) — leave empty keys to disable uploads
    CLOUDINARY_CLOUD_NAME: str = ""
    CLOUDINARY_API_KEY: str = ""
    CLOUDINARY_API_SECRET: str = ""
    CLOUDINARY_FOLDER: str = "basarat/community"
    MAX_FILE_SIZE_MB: int = 10
    LOCAL_TEMP_DIR: str = "./tmp"
    CLOUDINARY_ALLOWED_MIMES: list[str] = [
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/gif",
        "image/bmp",
        "image/heic",
    ]

    class Config:
        env_file = ".env"
        case_sensitive = True

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
