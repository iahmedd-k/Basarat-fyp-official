# Software Design Document (SDD)

## Project: Basarat — Smart PSX Investment Intelligence Platform

**Document Version:** 2.0  
**Status:** Approved  
**Author:** Engineering Team  
**Architecture:** Layered Asynchronous Monolith + Distributed Event/Task Workers

---

## 1. Introduction & Executive Summary

### 1.1 Purpose
This Software Design Document (SDD) provides a comprehensive description of the software architecture and system design for **Basarat**, an end-to-end investment intelligence platform targeting the Pakistan Stock Exchange (PSX). It encompasses both **High-Level Design (HLD)** and **Low-Level Design (LLD)** to serve as an authoritative technical blueprint for engineers, evaluators, and system architects.

### 1.2 System Scope
The Basarat platform ingests real-time and end-of-day market feeds, corporate disclosures, and multi-source financial news, processing this data through an AI/ML intelligence pipeline (BiGRU + XGBoost price forecasting, FinBERT NLP sentiment scoring, and quantitative multi-factor ranking). It delivers this intelligence via a mobile-first RESTful API, Server-Sent Events (SSE) streaming, and real-time WebSocket live quote broadcast to an Android client.

---

## PART I: HIGH-LEVEL DESIGN (HLD)

---

## 2. High-Level Architectural Design

### 2.1 C4 Context Diagram (System Ecosystem)

```mermaid
flowchart TD
    subgraph Clients ["Client Applications"]
        MOBILE["Android Mobile Client (Kotlin / Compose)"]
        ADMIN_WEB["Admin Web Console"]
    end

    subgraph BasaratCore ["Basarat System Boundary"]
        API_GATEWAY["Nginx Ingress & Reverse Proxy"]
        API_APP["FastAPI Application Server"]
        CELERY_WORKERS["Distributed Celery Worker Fleet"]
        CELERY_BEAT["Celery Beat Periodic Scheduler"]
        REDIS_LAYER[("Redis 7 Cache, Broker & Pub/Sub")]
        POSTGRES_LAYER[("PostgreSQL 16 Relational DB")]
    end

    subgraph ExternalFeeds ["Market & News Feeds"]
        PSX_PORTAL["PSX Ticker Portal & Data Feeds"]
        NEWS_PORTALS["Financial News Outlets (BR, Dawn, Mettis, SBP, SECP)"]
    end

    subgraph AICloud ["AI Cloud Services"]
        GROQ_LLM["Groq Cloud API (Llama 3.3 70B RAG)"]
        HF_FINBERT["HuggingFace FinBERT NLP API"]
    end

    subgraph PushEmail ["Notification & Cloud Infrastructure"]
        FCM["Firebase Cloud Messaging (FCM)"]
        SENDGRID["SendGrid Email Dispatcher"]
        CLOUDINARY["Cloudinary Media CDN"]
    end

    MOBILE -->|HTTPS / WSS| API_GATEWAY
    ADMIN_WEB -->|HTTPS| API_GATEWAY
    API_GATEWAY --> API_APP

    API_APP --> REDIS_LAYER
    API_APP --> POSTGRES_LAYER
    API_APP --> GROQ_LLM
    API_APP --> CLOUDINARY

    CELERY_BEAT -->|Enqueue Tasks| REDIS_LAYER
    REDIS_LAYER -->|Dispatch| CELERY_WORKERS
    CELERY_WORKERS --> POSTGRES_LAYER
    CELERY_WORKERS --> REDIS_LAYER
    CELERY_WORKERS --> PSX_PORTAL
    CELERY_WORKERS --> NEWS_PORTALS
    CELERY_WORKERS --> HF_FINBERT
    CELERY_WORKERS --> FCM
    CELERY_WORKERS --> SENDGRID

    REDIS_LAYER -->|Pub/Sub Live Ticks| API_APP
    API_APP -->|WebSocket Stream| MOBILE
```

### 2.2 Container & Infrastructure Architecture

```mermaid
flowchart LR
    subgraph Host ["Production Host (Oracle Cloud OCI / Docker Compose)"]
        subgraph Services ["Application Services"]
            APP["basarat-app-1<br/>(FastAPI / Uvicorn Port 8000)"]
            MIGRATE["basarat-migrate-1<br/>(Alembic Upgrade Head)"]
            WORKER["basarat-celery-worker-1<br/>(Alerts / ML / Ingestion)"]
            BEAT["basarat-celery-beat-1<br/>(Periodic Scheduler)"]
        end

        subgraph DataStores ["Data & In-Memory Stores"]
            REDIS["basarat-redis-1<br/>(Redis 7 Port 6379)"]
            POSTGRES[("PostgreSQL 16 DB<br/>(Managed Cloud)")]
        end
    end

    APP --> POSTGRES
    APP --> REDIS
    MIGRATE -.->|One-shot Run| POSTGRES
    WORKER --> REDIS
    WORKER --> POSTGRES
    BEAT --> REDIS
```

### 2.3 Layered System Decomposition

The system is partitioned into 6 distinct tiers:
1. **Presentation & Routing Tier (`app/api/v1/`)**: 22 modular routers handling REST endpoints and WebSocket handshakes.
2. **Security & Middleware Tier (`app/core/`)**: Correlation IDs (`X-Request-ID`), TrustedHost filtering, CORS origin control, SlowAPI rate-limiting, and error transformation.
3. **Domain Business Logic Tier (`app/services/`)**: 32 domain services encapsulating financial computations, news pipelines, recommendation engines, and chat orchestration.
4. **Machine Learning Tier (`app/ml/` & `models/production/`)**: Versioned serving and training code in `app/ml/`, with active serialized forecast artifacts in `models/production/v3/`.
5. **Asynchronous Task Processing Tier (`app/tasks/`)**: Celery workers executing post-close pipelines, intraday market caches, news ingestion, and alert monitoring.
6. **Persistence & Cache Tier (`app/models/`, `app/db/`, Redis)**: SQLAlchemy relational models and database access in `app/models/` and `app/db/`, plus Redis in-memory pub/sub/cache structures. This is separate from serialized ML artifacts in `models/`.

---

## PART II: LOW-LEVEL DESIGN (LLD)

---

## 3. Detailed Component & Class Design

### 3.1 Service Dependency Injection Class Diagram

```mermaid
classDiagram
    class BaseService {
        #AsyncSession db
        +__init__(db: AsyncSession)
    }

    class MarketService {
        +get_live_market_summary() MarketSummaryResponse
        +get_benchmark_indices() List~IndexQuote~
        +get_top_gainers_losers() GainersLosersResponse
    }

    class StockService {
        +get_stock_overview(symbol: str) StockOverview
        +get_historical_ohlcv(symbol: str, range: str) List~OHLCV~
        +calculate_technical_indicators(symbol: str) TechnicalIndicators
    }

    class PortfolioService {
        -ValuationEngine valuation_engine
        +get_portfolio_summary(user_id: UUID) PortfolioSummary
        +execute_transaction(user_id: UUID, tx: TransactionCreate) TransactionResponse
        +get_holdings_with_pnl(user_id: UUID) List~HoldingResponse~
    }

    class RiskService {
        +calculate_parametric_var(user_id: UUID, confidence: float) VaRResult
        +run_monte_carlo_simulation(user_id: UUID, simulations: int) MonteCarloResult
        +execute_historical_stress_test(user_id: UUID, scenario: str) StressTestResult
    }

    class AssistantService {
        -GroqClient groq_client
        -AssistantSafety safety_guard
        -AssistantContextCache context_cache
        +chat(user_id: UUID, message: str) ChatResponse
        +chat_stream(user_id: UUID, message: str) AsyncGenerator
    }

    BaseService <|-- MarketService
    BaseService <|-- StockService
    BaseService <|-- PortfolioService
    BaseService <|-- RiskService
    BaseService <|-- AssistantService
```

---

## 4. Subsystem Execution Sequences

### 4.1 End-to-End Daily Post-Close Workflow Sequence

```mermaid
sequenceDiagram
    autonumber
    participant Beat as Celery Beat
    participant Worker as Celery ML Worker
    participant Lock as Redis Lock
    participant Scraper as PSX Ingestion Scraper
    participant Staging as Parquet Staging
    participant ML as ML Inference Engine
    participant DB as PostgreSQL
    participant Cache as Redis Cache

    Beat->>Worker: Trigger `daily_workflow` (15:35 PKT)
    Worker->>Lock: Acquire `lock:scraper:daily_close`
    Worker->>Worker: Check if PSX Trading Day & Not Holiday
    Worker->>Scraper: Execute `run_after_close.py`
    loop Every 10 Symbols
        Scraper->>Scraper: Fetch OHLCV & Pause 150s (Prevent 429)
        Scraper->>Staging: Write Staged Parquet Files
    end
    Scraper-->>Worker: Verify 100% Ingestion Completeness
    Worker->>Worker: Promote Staged Parquet to Production Dataset
    Worker->>ML: Run `run_forecast_inference()`
    ML->>ML: Compute Feature Engineering (Returns, Volatility, RSI, MACD, BB)
    ML->>ML: Run BiGRU + XGBoost Ensemble Inference (1D, 7D, 14D, 30D)
    ML->>DB: Bulk Upsert Predictions Table
    Worker->>Worker: Recompute Quant Recommendations (Top Picks)
    Worker->>Cache: Invalidate & Warm `recs:top_picks`
    Worker->>Lock: Release `lock:scraper:daily_close`
```

### 4.2 Real-Time Portfolio Transaction Execution & P&L Recalculation

```mermaid
sequenceDiagram
    autonumber
    participant User as Mobile Client
    participant Router as `/api/v1/portfolio/transactions`
    participant Auth as Auth Dependency
    participant Service as PortfolioService
    participant Valuation as ValuationEngine
    participant DB as PostgreSQL
    participant Cache as Redis Cache

    User->>Router: POST Transaction `{symbol: "OGDC", type: "BUY", qty: 500, price: 140.0}`
    Router->>Auth: Validate JWT Bearer Token
    Auth-->>Router: Authenticated `User`
    Router->>Service: `execute_transaction(user.id, tx_payload)`
    Service->>DB: Insert record into `portfolio_transactions`
    Service->>DB: Query all active transactions for `portfolio_id` & `symbol`
    Service->>Valuation: Compute weighted average cost basis & cumulative position
    Service->>DB: Upsert `portfolio_holdings` (symbol, qty=500, avg_buy_price=140.0)
    Service->>Cache: Invalidate user's portfolio summary cache
    Service->>DB: Commit Async Transaction
    Service-->>Router: `TransactionResponse`
    Router-->>User: HTTP 201 Created `{transaction_id: "...", holdings: [...]}`
```

---

## 5. Architectural Design Patterns Applied

| Pattern | Implementation in Basarat | Benefit |
|---|---|---|
| **Dependency Injection** | FastAPI `Depends(get_db)`, `Depends(get_current_user)`, `Depends(_get_service)` | Loose coupling, testability with mock dependencies. |
| **Repository / Service** | `app/services/` encapsulating business rules, `app/db/` handling transactions | Clear separation between transport (API) and business logic. |
| **Publish / Subscribe** | Redis Channel `psx:market:live_quotes` consumed by `WebSocketManager` | Decouples live market ingestion from thousands of concurrent WebSocket client connections. |
| **Single-Flight Lock** | Redis `SET lock:key token NX EX 60` in scrapers and daily workflows | Guarantees single-writer execution, eliminating race conditions and duplicate upstream API calls. |
| **Circuit Breaker** | `MARKET_CIRCUIT_BREAKER_SECONDS` (900s) on PSX HTTP 403/429 responses | Protects system and IP from permanent upstream bans during PSX portal disruptions. |
| **Retrieval-Augmented Generation (RAG)** | `AssistantService` dynamically enriching Groq prompt with live ticker metrics | Eliminates LLM hallucinations on stock metrics and guarantees up-to-date analysis. |
| **Defense-in-Depth Security** | Correlation IDs, TrustedHost, CORS, SlowAPI rate limiting, Bcrypt work factor 12 | Comprehensive protection against OWASP Top 10 web vulnerabilities. |
