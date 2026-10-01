import os

import pytest

from app.core.config import Settings


@pytest.mark.parametrize(
    "env_value",
    [
        "postgresql+asyncpg://postgres:postgres@localhost:5432/basarat",
        "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/basarat",
    ],
)
def test_production_settings_reject_localhost_database(monkeypatch, env_value):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345678901234567890")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", env_value)
    monkeypatch.delenv("CLOUD_DATABASE_URL", raising=False)
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')

    with pytest.raises(ValueError, match="localhost|127\.0\.0\.1|CLOUD_DATABASE_URL"):
        Settings()


def test_production_settings_use_cloud_database_when_provided(monkeypatch):
    cloud_url = "postgresql+asyncpg://prod_user:prod_pass@cloud-db.example.com:5432/basarat"
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345678901234567890")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("CLOUD_DATABASE_URL", cloud_url)
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/basarat")
    monkeypatch.setenv("DATABASE_URL_SYNC", "")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
    monkeypatch.setenv("REDIS_URL", "rediss://default:secret@redis.example.com:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "rediss://default:secret@redis.example.com:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "rediss://default:secret@redis.example.com:6379/0")

    settings = Settings()

    assert settings.DATABASE_URL == cloud_url
    assert settings.DATABASE_URL_SYNC


def test_production_settings_apply_cloud_redis_to_local_celery_urls(monkeypatch):
    cloud_redis_url = "rediss://default:secret@redis.example.com:6379/0"
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345678901234567890")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://prod:secret@db.example.com:5432/basarat")
    monkeypatch.setenv("DATABASE_URL_SYNC", "")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
    monkeypatch.setenv("CLOUD_REDIS_URL", cloud_redis_url)
    monkeypatch.setenv("REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    settings = Settings()

    assert settings.REDIS_URL == cloud_redis_url
    assert settings.CELERY_BROKER_URL == cloud_redis_url
    assert settings.CELERY_RESULT_BACKEND == cloud_redis_url


def test_production_settings_reject_local_celery_url_without_cloud_redis(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345678901234567890")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://prod:secret@db.example.com:5432/basarat")
    monkeypatch.setenv("DATABASE_URL_SYNC", "")
    monkeypatch.setenv("CORS_ORIGINS", '["https://app.example.com"]')
    monkeypatch.setenv("REDIS_URL", "rediss://default:secret@redis.example.com:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "redis://localhost:6379/1")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "rediss://default:secret@redis.example.com:6379/0")
    monkeypatch.setenv("CLOUD_REDIS_URL", "")

    with pytest.raises(ValueError, match="CELERY_BROKER_URL.*localhost"):
        Settings()


def test_production_settings_reject_https_localhost_cors(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key-12345678901234567890")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://prod:secret@db.example.com:5432/basarat")
    monkeypatch.setenv("DATABASE_URL_SYNC", "")
    monkeypatch.setenv("CORS_ORIGINS", '["https://localhost"]')
    monkeypatch.setenv("REDIS_URL", "rediss://default:secret@redis.example.com:6379/0")
    monkeypatch.setenv("CELERY_BROKER_URL", "rediss://default:secret@redis.example.com:6379/0")
    monkeypatch.setenv("CELERY_RESULT_BACKEND", "rediss://default:secret@redis.example.com:6379/0")

    with pytest.raises(ValueError, match="CORS_ORIGINS.*localhost"):
        Settings()
