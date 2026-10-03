# Configuration

## Configuration Sources

All configuration flows through `app/core/config.py` using Pydantic `BaseSettings`:

1. `.env` file (loaded by Pydantic)
2. Environment variables (override `.env`)
3. Docker Compose `environment:` section (override both)
4. Default values in `Settings` class

## Environment-Specific Configuration

### Development
```
ENVIRONMENT=development
DEBUG=false
DATABASE_URL=postgresql+asyncpg://basarat:password@localhost:5432/basarat
REDIS_URL=redis://localhost:6379/0
USE_CELERY=true
CORS_ORIGINS=["*"]
```

### Testing
```
ENVIRONMENT=test
REDIS_ENABLED=false
USE_CELERY=false
TESTING=true
SECRET_KEY=local-ci-only-signing-key-at-least-32-chars
```

### Production
```
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=<CLOUD_DATABASE_URL>
REDIS_URL=<CLOUD_REDIS_URL>
CORS_ORIGINS=["https://yourdomain.com"]
FIREBASE_ENABLED=true
```

## Production Safety Checks

The `Settings.__init__()` method enforces:
- CORS_ORIGINS must not include localhost
- DATABASE_URL must not point to localhost
- REDIS_URL must not point to localhost
- SECRET_KEY must not be a placeholder value
- DEBUG must be false
- Database credentials must not use development defaults

## Dangerous Settings to Avoid in Production

| Setting | Risk | Current Protection |
|---------|------|--------------------|
| `DEBUG=true` | Stack traces exposed | Validated in config |
| `CORS_ORIGINS=["*"]` | Any origin allowed | Validated in config (but middleware uses `["*"]` directly) |
| `SECRET_KEY=changeme` | Tokens forgeable | Validated against placeholder list |
| localhost database URL | Wrong database | Validated in config |
