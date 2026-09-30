# System Architecture — Basarat

## 1. Architectural Style & High-Level Overview

Basarat is designed as a **High-Performance Asynchronous Modular Monolith** with decoupled asynchronous background workers, an in-memory pub/sub message bus, and a decoupled modern Single-Page Application (SPA) frontend.

The system combines synchronous low-latency REST and WebSocket APIs (for client interactions, live quote streaming, and AI conversations) with distributed asynchronous task processing (for market scraping, ML inference, financial NLP sentiment scoring, portfolio risk simulations, and cron workflows).

```mermaid
flowchart TB
    subgraph ClientTier["Client Layer"]
        WebClient["React 19 SPA (Vite + Modular CSS)"]
        MobileClient["Mobile App / External Client"]
    end

    subgraph IngressTier["Ingress & Routing"]
        Nginx["Reverse Proxy / TLS Ingress"]
        CORS["CORS & Security Middleware"]
        RateLimiter["Sliding Window Rate Limiter"]
    end

    subgraph APITier["FastAPI Application Server (Uvicorn Async)"]
        APIRouter["API v1 Router (146 Paths / 169 Operations)"]
        AuthDep["Auth & Token-Version Dependency"]
        WSManager["WebSocket Connection Manager"]
        LiveBusListener["Redis Live Bus Listener"]
        ContextBuilder["AI Assistant Context Builder"]
        MLServing["ML Serving Engine (In-Memory Attention-BiGRU + XGBoost)"]
    end

    subgraph ServiceTier["Service & Business Logic Layer"]
        AuthSvc["AuthService"]
        MarketSvc["MarketService"]
        StockSvc["StockService"]
        PortSvc["PortfolioService"]
        RiskSvc["RiskService"]
        ShariahSvc["ShariahService"]
        RecSvc["RecommendationService"]
        SentSvc["SentimentService"]
        CommSvc["CommunityService"]
        AssistSvc["AssistantService"]
        AlertSvc["AlertService"]
        ETFSvc["ETFService"]
        IPOSvc["IPOService"]
    end

    subgraph WorkerTier["Asynchronous Processing Layer (Celery)"]
        CeleryBeat["Celery Beat Scheduler (Asia/Karachi Crons)"]
        CeleryWorker["Celery Worker Processes"]
        DailyPipeline["Daily Market & Forecast Pipeline"]
        NewsScraper["News & PSX Scraper Tasks"]
        SentimentTasks["FinBERT NLP Sentiment Tasks"]
        MonteCarloTask["Monte Carlo Simulation Worker"]
        AlertEvalTask["Alert Rule Evaluator (Every 5m)"]
    end

    subgraph StorageTier["Data & Cache Layer"]
        Postgres[(PostgreSQL 16 Relational DB)]
        RedisCache[(Redis 7: Cache / PubSub / Celery Broker)]
    end

    subgraph ExternalTier["External Cloud Providers"]
        GroqCloud["Groq Cloud LLM API"]
        HFCloud["HuggingFace FinBERT API"]
        SendGridSMTP["SendGrid / SMTP Mail Server"]
        CloudinaryMedia["Cloudinary Media CDN"]
        PSXPortals["PSX Public Portals & Scrapers"]
        GoogleAppleOAuth["Google & Apple OAuth Providers"]
    end

    ClientTier <-->|HTTPS REST / SSE / WSS| IngressTier
    IngressTier --> CORS --> RateLimiter --> APIRouter
    APIRouter --> AuthDep
    APIRouter --> ServiceTier
    APIRouter --> WSManager
    APIRouter --> MLServing

    ServiceTier -->|SQLAlchemy Async Engine / asyncpg| Postgres
    ServiceTier -->|Cache Get/Set| RedisCache
    ServiceTier -->|Enqueue Async Job| RedisCache
    ServiceTier -->|Groq Chat| GroqCloud
    ServiceTier -->|Media Upload| CloudinaryMedia
    ServiceTier -->|OAuth Token Validation| GoogleAppleOAuth

    CeleryBeat -->|Crons| RedisCache
    CeleryWorker <-->|Pulls Jobs| RedisCache
    CeleryWorker -->|Sync Engine / psycopg2| Postgres
    CeleryWorker -->|Scrapes| PSXPortals
    CeleryWorker -->|NLP Scoring| HFCloud
    CeleryWorker -->|OTP Emails| SendGridSMTP
    CeleryWorker -->|Publishes Live Quotes| RedisCache

    LiveBusListener <-->|Subscribes to market:quotes:live| RedisCache
    LiveBusListener -->|Broadcasts Quotes| WSManager
    WSManager <-->|Streams Live Quotes| ClientTier
```

---

## 2. Layered Architecture & Module Separation

The codebase follows a clean, decoupled layered design pattern:

```text
backend/app/
├── api/            # Controller / Router layer (HTTP & WebSocket endpoints)
│   └── v1/         # Versioned endpoints, route definitions, parameter validation
├── core/           # Infrastructure & cross-cutting concerns (config, security, rate limit, logging)
├── db/             # Database connection, base declarative class, async & sync session managers
├── models/         # SQLAlchemy 2.0 ORM models and relationship definitions
├── schemas/        # Pydantic v2 schemas for request validation and response serialization
├── services/       # Core business logic, calculation engines, external API clients
├── repository/     # Specialized data access repositories (Portfolio, Sentiment)
├── ml/             # Machine learning training, feature pipelines, model loaders, inference engine
├── tasks/          # Celery asynchronous jobs, daily pipelines, scraping, monitoring
└── ws/             # WebSocket route handlers and protocol definitions
```

### 2.1 API & Presentation Layer (`app.api.v1`)
- **FastAPI Application (`main.py`):** Instantiates the ASGI application, sets up middleware (CORS, rate limiting, exception handlers), mounts routers with prefix `/api/v1`, and controls the asynchronous startup/shutdown lifespan.
- **Dependency Injection:** Endpoints declare explicit dependencies for authentication (`get_current_user`), authorization (`get_current_admin`), and database sessions (`get_db`).
- **Data Validation:** Pydantic v2 schemas rigorously validate query parameters, URL path variables, and JSON request bodies before reaching service handlers.

### 2.2 Service & Domain Layer (`app.services`)
- Encapsulates all financial algorithms, business logic, and transactional orchestration.
- **Stateless Design:** Services are instantiated per request or task with an injected `AsyncSession` or database connection, ensuring clean concurrency and transaction isolation.
- Key services include [MarketService](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/market_service.py), [StockService](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/stock_service.py), [PortfolioService](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/portfolio_service.py), [RiskService](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/risk_service.py), [ShariahService](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/shariah_service.py), [RecommendationService](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/recommendation_service.py), [AssistantService](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/assistant_service.py), and [CommunityService](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/community_service.py).

### 2.3 Machine Learning & Inference Subsystem (`app.ml`)
- **In-Memory Model Loading:** [model_loader.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/ml/serving/model_loader.py) initializes model weights, scalers, and feature metadata into a singleton during application startup.
- **Ensemble Architecture:** [inference.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/ml/serving/inference.py) combines the stationary Attention-BiGRU model (45-day window, 79 normalized features) with XGBoost v4 (fundamentals and event indicators).
- **Gating & Auditing:** Automated gating rules evaluate class probabilities and prediction gaps; full predictions and sub-model votes are persisted into the `predictions` table.

### 2.4 Data Persistence & Cache Layer (`app.db`, `app.cache`, `app.core.redis`)
- **Dual Database Driver Strategy:**
  - **Asynchronous (`asyncpg`):** Used exclusively by the FastAPI web server for high-concurrency non-blocking I/O.
  - **Synchronous (`psycopg2`):** Used by Celery worker processes and Alembic migration scripts.
- **Redis Multi-DB Partitioning:**
  - `DB 0`: Application query caching (`CACHE_TTL_SECONDS=300`), rate limiting counters, and pub/sub live bus.
  - `DB 1`: Celery message broker queue.
  - `DB 2`: Celery task result backend.

---

## 3. Request Lifecycle

A typical authenticated request follows a strictly controlled lifecycle:

```mermaid
sequenceDiagram
    autonumber
    actor Client as Web / Mobile Client
    participant RateLimit as Rate Limiter Middleware
    participant Router as API Router
    participant Auth as Auth Dependency (get_current_user)
    participant DB as PostgreSQL (AsyncSession)
    participant Service as Domain Service Layer
    participant Cache as Redis Cache
    participant External as External Service (Groq / HF)

    Client->>RateLimit: HTTP Request (Headers + Bearer Token)
    RateLimit->>Cache: Check Sliding Window Request Count
    alt Rate Limit Exceeded
        RateLimit-->>Client: 429 Too Many Requests
    end
    RateLimit->>Router: Forward Request
    Router->>Auth: Resolve User Dependency
    Auth->>Auth: Decode JWT & Validate Expiry
    Auth->>DB: Fetch User (SELECT id, token_version, is_active)
    alt Invalid Token / Version Mismatch
        Auth-->>Client: 401 Unauthorized / Token Revoked
    end
    Auth->>Router: Inject Authenticated User
    Router->>Service: Call Domain Method (e.g. get_portfolio_summary)
    Service->>Cache: Check Cached Data (if applicable)
    alt Cache Hit
        Cache-->>Service: Return Cached JSON
    else Cache Miss
        Service->>DB: Execute Async ORM Query
        opt External API Call
            Service->>External: Fetch Data / Inference
            External-->>Service: Response Payload
        end
        DB-->>Service: Database Records
        Service->>Cache: Set Cache (TTL=300s)
    end
    Service-->>Router: Domain Result
    Router-->>Client: HTTP 200 OK (Serialized JSON via Pydantic)
```

---

## 4. Live Quote Streaming & WebSocket Architecture

To achieve sub-second market quote delivery without overloading the upstream exchange or locking the web server, Basarat implements a distributed Redis Pub/Sub Live Bus pattern:

```mermaid
sequenceDiagram
    autonumber
    participant CeleryWorker as Celery Scraper Worker
    participant Redis as Redis (market:quotes:live Channel)
    participant LiveBus as FastAPI MarketLiveBus Listener
    participant WSManager as WebSocketManager
    actor ClientA as Connected Web Client
    actor ClientB as Connected Android Client

    ClientA->>WSManager: Connects /api/v1/ws/market
    ClientA->>WSManager: {"action": "subscribe", "symbols": ["ENGRO", "LUCK"]}
    ClientB->>WSManager: Connects /api/v1/ws/market
    ClientB->>WSManager: {"action": "subscribe", "symbols": ["LUCK", "OGDC"]}

    loop Every 60s (Trading Hours)
        CeleryWorker->>CeleryWorker: Ingest PSX Intraday Quotes
        CeleryWorker->>Redis: SET quotes:snapshot (Redis Hash)
        CeleryWorker->>Redis: PUBLISH market:quotes:live (JSON Quote Batch)
    end

    Redis-->>LiveBus: Message Event on market:quotes:live
    LiveBus->>WSManager: Forward Live Quotes
    WSManager->>ClientA: Push Quotes for ["ENGRO", "LUCK"]
    WSManager->>ClientB: Push Quotes for ["LUCK", "OGDC"]
```

---

## 5. Daily Asynchronous Pipeline Workflow & Off-Hours Snapshot Caching

The platform enforces a strict market-gated execution cycle:

1. **Intraday Trading Session (Mon–Fri 09:15–15:30 PKT):** High-frequency 1-minute quote scrapes, 5-minute alert checks, and 30-minute news ingestion.
2. **Market Close Final Snapshot (Mon–Fri 17:00 PKT):** Ingests official closing quotes and locks the daily snapshot in Redis with a 7-day fallback TTL.
3. **Master Daily Pipeline (Mon–Fri 18:00 PKT):** Reconciles past predictions, saves today's OHLCV, generates ML features, runs forecast inference, and updates recommendations.
4. **Nights & Weekends (Off-Hours):** All recurring polling tasks halt. The saved 17:00/18:00 snapshot serves all user requests in `<5ms` from Redis/PostgreSQL without triggering background scraping.

```mermaid
flowchart TD
    CloseSnap["17:00 PKT: Capture & Lock Final Close Snapshot in Redis"] --> StartDaily["18:00 PKT: Master Daily Pipeline Trigger"]
    StartDaily --> CheckHoliday{"Is Trading Day & Open?"}
    CheckHoliday -- "Weekend / Holiday" --> Skip["Log and Skip Execution"]
    CheckHoliday -- "Valid Market Day" --> Step1["Step 1: Update Daily Market Data & Ingest Closing OHLCV"]
    
    Step1 --> Step2["Step 2: Generate & Normalize Features (features_daily.parquet)"]
    Step2 --> Step3["Step 3: Run Ensemble Forecast Inference (Attention-BiGRU + XGBoost)"]
    Step3 --> Step4["Step 4: Persist Predictions to predictions Table (Upsert)"]
    Step4 --> Step5["Step 5: Reconcile Previous Day Predictions (Set actual_direction & was_correct)"]
    Step5 --> Step6["Step 6: Compute FinBERT News Sentiment & Rolling Aggregates"]
    Step6 --> Step7["Step 7: Recalculate Quantitative Recommendations (Buy/Hold/Sell)"]
    Step7 --> Step8["Step 8: Check Alert Rules & Portfolio Risk Threshold Breaches"]
    Step8 --> Finish["18:30 PKT: Pipeline Complete -> Enter Night/Weekend Zero-Polling Mode"]
```
