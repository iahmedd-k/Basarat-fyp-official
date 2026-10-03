# Project Structure

```
Basarat-fyp-official/
+-- .github/
|   +-- workflows/
|       +-- deploy-ec2.yml          # CI/CD pipeline
+-- backend/
    +-- app/                        # Main application package
    |   +-- api/
    |   |   +-- v1/                 # API v1 route handlers
    |   |       +-- admin/          # Admin endpoints (community moderation)
    |   |       +-- assistant/      # AI assistant chat endpoints
    |   |       +-- community/      # Social trading endpoints
    |   |       +-- auth.py         # Authentication routes
    |   |       +-- market.py       # Market data routes
    |   |       +-- stocks.py       # Stock detail routes
    |   |       +-- portfolio.py    # Portfolio management routes
    |   |       +-- ... (22 total route modules)
    |   +-- core/                   # Core infrastructure
    |   |   +-- config.py           # Settings (Pydantic BaseSettings)
    |   |   +-- security.py         # JWT, bcrypt, token functions
    |   |   +-- authorization.py    # Auth dependencies
    |   |   +-- exceptions.py       # Custom exception classes
    |   |   +-- rate_limiter.py     # SlowAPI rate limiting
    |   |   +-- redis.py            # Redis cache client
    |   |   +-- logging.py          # Logging setup
    |   |   +-- task_runner.py      # Celery/in-process task dispatcher
    |   |   +-- database_urls.py    # DB URL normalization
    |   |   +-- health.py           # Health check constants
    |   +-- db/                     # Database configuration
    |   |   +-- base.py             # Engine, session factory, Base class
    |   |   +-- session.py          # get_db() dependency
    |   +-- models/                 # SQLAlchemy ORM models (19 model files)
    |   +-- schemas/                # Pydantic schemas (12 schema files)
    |   +-- services/               # Business logic layer (32 service files)
    |   |   +-- news_pipeline/      # Multi-source news scraping
    |   |   +-- portfolio/          # Portfolio calculation helpers
    |   +-- repository/             # Data access layer (2 files)
    |   +-- tasks/                  # Celery background tasks (16 task files)
    |   +-- ml/                     # Machine learning
    |   |   +-- serving/            # Model loading, inference, prediction store
    |   |   +-- training/           # Training pipelines
    |   |   +-- v2/, v3/            # Model versions
    |   +-- data/                   # Static data, scrapers, config files
    |   +-- cache/                  # Redis client module
    |   +-- main.py                 # FastAPI application entry point
    |   +-- celery_app.py           # Celery configuration and beat schedule
    +-- alembic/                    # Database migrations
    |   +-- versions/               # 19 migration files
    +-- deploy/
    |   +-- ec2/                    # EC2 deployment scripts (blue-green)
    |   +-- nginx/                  # Nginx reverse proxy configuration
    +-- models/
    |   +-- final/                  # Trained ML model artifacts
    +-- data/                       # Runtime data (OHLCV, features, config)
    +-- scripts/                    # Utility scripts (21 files)
    +-- tests/                      # Test suite
    |   +-- api/                    # API endpoint tests (17 files)
    |   +-- unit/                   # Unit tests (15 files)
    |   +-- e2e/                    # End-to-end tests
    |   +-- integration/            # Integration tests
    |   +-- performance/            # Performance tests
    |   +-- security/               # Security tests
    |   +-- conftest.py             # Test fixtures and configuration
    +-- dockerfile                  # Docker image definition
    +-- docker-compose.yml          # Development compose
    +-- docker-compose.production.yml  # Production compose
    +-- requirements.txt            # Python dependencies
    +-- requirements.lock           # Locked dependencies with hashes
    +-- alembic.ini                 # Alembic configuration
    +-- pytest.ini                  # Test configuration
    +-- .env.example                # Environment variable template
```

## Key Directories

### `app/api/v1/`
Thin route handlers that validate input, call services, and return responses. Each file corresponds to a Swagger tag group.

### `app/services/`
Contains all business logic. Services are the largest layer, handling data processing, external API calls, ML inference orchestration, and complex business rules.

### `app/models/`
SQLAlchemy ORM models defining the database schema. Each file represents a domain entity or group of related entities.

### `app/tasks/`
Celery task definitions for background processing. Each file groups related tasks (news, sentiment, alerts, etc.).

### `app/ml/serving/`
ML model serving infrastructure: model loading, inference pipeline, prediction storage, model registry, and promotion logic.

### `deploy/`
Production deployment infrastructure: EC2 blue-green deployment scripts and Nginx reverse proxy configuration.
