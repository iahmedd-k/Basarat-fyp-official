# Requirements Specification

## System Requirements

| Requirement | Details | Status |
|-------------|---------|--------|
| Python 3.11.9 runtime | Backend application runtime | Implemented |
| PostgreSQL 16+ database | Primary data store | Implemented |
| Redis 7+ | Caching, message broker, pub/sub | Implemented |
| Docker & Docker Compose | Container orchestration | Implemented |
| 2+ GB RAM | ML model loading (TensorFlow, XGBoost) | Implemented |

## User Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| UR-001 | Users shall register with email/password or OAuth (Google/Apple) | Implemented |
| UR-002 | Users shall view real-time PSX market data | Implemented |
| UR-003 | Users shall receive ML-based stock price forecasts | Implemented |
| UR-004 | Users shall manage a stock portfolio with buy/sell transactions | Implemented |
| UR-005 | Users shall view portfolio risk analytics | Implemented |
| UR-006 | Users shall view news sentiment analysis | Implemented |
| UR-007 | Users shall set price alerts on stocks | Implemented |
| UR-008 | Users shall create and manage watchlists | Implemented |
| UR-009 | Users shall interact with an AI investment assistant | Implemented |
| UR-010 | Users shall participate in a social trading community | Implemented |
| UR-011 | Users shall screen stocks for Shariah compliance | Implemented |
| UR-012 | Users shall view ETF and IPO listings | Implemented |
| UR-013 | Users shall receive push notifications for alerts | Implemented |
| UR-014 | Users shall receive automated stock recommendations | Implemented |

## Software Requirements

| Component | Version | Purpose |
|-----------|---------|---------|
| FastAPI | ≥0.110 | Web framework |
| SQLAlchemy | ≥2.0 | ORM (async) |
| asyncpg | ≥0.29 | PostgreSQL async driver |
| Celery | ≥5.0 | Distributed task queue |
| TensorFlow | 2.16.1 | GRU neural network |
| XGBoost | ≥2.0 | Gradient boosting classifier |
| scikit-learn | ≥1.4 | ML utilities and preprocessing |
| python-jose | ≥3.0 | JWT token handling |
| bcrypt | ≥4.0 | Password hashing |
| Alembic | ≥1.13 | Database migrations |
| SlowAPI | ≥0.1 | Rate limiting |
| httpx | ≥0.27 | Async HTTP client |
| BeautifulSoup4 | ≥4.12 | HTML parsing for scrapers |
| cloudinary | ≥1.36 | Image upload SDK |
| firebase-admin | ≥6.5 | FCM push notifications |

## External Service Requirements

| Service | Required | Fallback |
|---------|----------|----------|
| PostgreSQL | Yes | None (required) |
| Redis | No (in-process fallback) | In-memory cache dictionary |
| Groq API | No | Assistant feature disabled |
| HuggingFace API | No | Sentiment analysis disabled |
| SendGrid | No | Email features disabled |
| Firebase FCM | No | Push notifications disabled |
| Cloudinary | No | Image upload disabled |

## Infrastructure Requirements

### Development

- Docker Desktop or local PostgreSQL + Redis
- Python 3.11.9 with pip
- `.env` configuration file

### Production

- AWS EC2 instance (self-hosted runner)
- AWS ECR (container registry)
- Supabase PostgreSQL (managed database)
- Upstash Redis (managed cache/broker)
- Nginx reverse proxy
- Docker Engine

## Security Requirements

| ID | Requirement | Status |
|----|-------------|--------|
| SEC-001 | Passwords hashed with bcrypt | Implemented |
| SEC-002 | JWT tokens with expiry and rotation | Implemented |
| SEC-003 | Rate limiting on auth endpoints | Implemented |
| SEC-004 | Input validation via Pydantic schemas | Implemented |
| SEC-005 | CORS configuration | Implemented (permissive in dev) |
| SEC-006 | Production credential validation | Implemented |
| SEC-007 | Role-based access control (user/admin) | Implemented |
| SEC-008 | OTP-based email verification | Implemented |
| SEC-009 | Refresh token rotation with revocation | Implemented |
| SEC-010 | Non-root Docker container execution | Implemented (production) |

## Data Requirements

| Requirement | Status |
|-------------|--------|
| PSX stock prices (OHLCV) stored locally | Implemented |
| User data with UUID primary keys | Implemented |
| Financial news with sentiment scores | Implemented |
| ML predictions with audit trail | Implemented |
| Portfolio transactions with decimal precision | Implemented |
| Community posts with moderation state | Implemented |

## Integration Requirements

| Integration | Protocol | Status |
|-------------|----------|--------|
| PSX market data | HTTP scraping | Implemented |
| Groq LLM API | HTTPS (OpenAI-compatible) | Implemented |
| HuggingFace API | HTTPS | Implemented |
| SendGrid email | HTTPS REST API | Implemented |
| Firebase FCM | Firebase Admin SDK | Implemented |
| Cloudinary | SDK / HTTPS | Implemented |
| Google OAuth | ID Token verification | Implemented |
| Apple OAuth | ID Token verification | Implemented |

## Deployment Requirements

| Requirement | Status |
|-------------|--------|
| Blue-green deployment on EC2 | Implemented |
| Automated CI/CD via GitHub Actions | Implemented |
| Immutable Docker images (SHA-tagged) | Implemented |
| Database migration before deployment | Implemented |
| Health check verification before traffic switch | Implemented |
| Rollback capability | Implemented |
