# System Architecture

## 1. Executive Architecture Summary

**Basarat** is a high-performance, mobile-first investment intelligence platform tailored for the **Pakistan Stock Exchange (PSX)**. The backend system is designed around a **modular layered architecture** coupled with an asynchronous, distributed event and task processing pipeline powered by **FastAPI**, **Celery**, **PostgreSQL 16**, and **Redis 7**.

The platform is engineered to deliver real-time stock quotes, AI-driven directional price forecasts (GRU + XGBoost ensemble), FinBERT natural language sentiment analysis, automated quantitative stock recommendations, multi-portfolio tracking with P&L and risk analytics (VaR / CVaR / Monte Carlo), Shariah compliance screening, an AI-powered conversational investment copilot (Groq LLM), and a social trading community feed.

---

## 2. High-Level Architecture (C4 Model)

### 2.1 C4 Level 1: System Context Diagram

The System Context diagram illustrates how external users, client applications, and external systems interact with the Basarat backend.

```mermaid
flowchart TD
    subgraph Users ["Users & Client Tier"]
        USER["Retail & Institutional Investors"]
        ADMIN["System Administrators & Moderators"]
        ANDROID["Basarat Mobile App (Android)<br/>Kotlin / Jetpack Compose"]
    end

    subgraph BasaratCore ["Basarat System Boundary"]
        BACKEND["Basarat Backend Platform<br/>FastAPI / Celery / Redis / PostgreSQL"]
    end

    subgraph ExternalSources ["External Financial Data Sources"]
        PSX_DATA["PSX Official Portals & Ticker Feeds<br/>pypsx-toolkit / DPS Portal"]
        NEWS_SOURCES["Financial News Outlets<br/>Business Recorder / Dawn / Mettis / OGRA / SBP"]
    end

    subgraph ExternalAI ["AI & NLP Cloud Providers"]
        GROQ["Groq Cloud API<br/>Llama 3 70B / Mixtral (Fast LLM Inference)"]
        HF["HuggingFace Inference API<br/>FinBERT Financial Sentiment Model"]
    end

    subgraph ExternalServices ["Third-Party Cloud Services"]
        FCM["Firebase Cloud Messaging (FCM)<br/>Mobile Push Notifications"]
        SENDGRID["SendGrid API<br/>Transactional Email & OTPs"]
        CLOUDINARY["Cloudinary CDN<br/>User Avatars & Community Images"]
        AUTH_PROV["OAuth Providers<br/>Google OAuth 2.0 / Apple ID"]
    end

    USER -->|Interacts with UI| ANDROID
    ADMIN -->|Moderates Content| ANDROID
    ANDROID -->|HTTPS REST API & WSS WebSockets| BACKEND

    BACKEND -->|Market Data Scraping & Quotes| PSX_DATA
    BACKEND -->|RSS & Regulatory News Ingestion| NEWS_SOURCES
    BACKEND -->|Conversational RAG Queries| GROQ
    BACKEND -->|NLP Financial Sentiment Scoring| HF
    BACKEND -->|Dispatches Push Alerts| FCM
    BACKEND -->|Sends Auth Verification & Alerts| SENDGRID
    BACKEND -->|Uploads & Optimizes Images| CLOUDINARY
    BACKEND -->|Validates Social Auth Tokens| AUTH_PROV
```

---

### 2.2 C4 Level 2: Container Architecture Diagram

The Container diagram illustrates the runtime deployment topology of Docker containers and data stores within the Basarat infrastructure.

```mermaid
flowchart TD
    subgraph Client ["Client Device"]
        APP["Android Mobile Client"]
    end

    subgraph Ingress ["Edge & Security Ingress"]
        NGINX["Nginx Reverse Proxy<br/>TLS Termination, Rate Limiting (20 req/s, burst 50),<br/>Request Routing, Static Asset Cache"]
    end

    subgraph AppContainer ["Core API Service Container (FastAPI)"]
        UVICORN["Uvicorn ASGI Server<br/>(Worker Pool)"]
        FASTAPI["FastAPI Web Framework"]
        MIDDLEWARE["Middleware Stack<br/>• Correlation ID (X-Request-ID)<br/>• TrustedHost Security<br/>• CORS Origin Enforcer<br/>• SlowAPI Rate Limiter<br/>• RFC 7807 Error Handler"]
        ROUTERS["API v1 Route Handlers<br/>(22 Domain Routers)"]
        DEP_INJ["Dependency Injection & Auth<br/>(get_db, get_current_user, RBAC)"]
        SERVICES["Domain Services Layer<br/>(Market, Portfolio, Risk, Recommendations, etc.)"]
        WS_MGR["WebSocket Manager<br/>(Live Quote Streamer & Topic Broadcaster)"]
        ML_ENGINE["ML Inference Engine<br/>(Loaded GRU + XGBoost Models)"]
    end

    subgraph WorkerFleet ["Distributed Celery Workers"]
        WORKER_GENERAL["Celery General Worker<br/>(Alerts, Notifications, Emails, Community)"]
        WORKER_ML["Celery Data & ML Worker<br/>(Daily Workflow, Ingestion, Predictions, Retraining)"]
        WORKER_MARKET["Celery Live Worker<br/>(Intraday Market Snapshots & News Ingestion)"]
    end

    subgraph Scheduler ["Task Scheduler"]
        BEAT["Celery Beat Scheduler<br/>(Crontab & Periodic Dispatcher)"]
    end

    subgraph DataStorage ["Data & Cache Storage Tier"]
        POSTGRES[("PostgreSQL 16 Database<br/>(SQLAlchemy Async ORM / asyncpg)<br/>20+ Domain Tables & Migrations")]
        REDIS[("Redis 7 In-Memory Cache & Broker<br/>• Celery Task Queue Broker<br/>• Live Ticker & Market Snapshot Cache<br/>• Single-Flight Locks & Dedup Keys<br/>• Rate Limit Token Buckets<br/>• WebSocket Pub/Sub Bus")]
    end

    subgraph MigrationService ["One-Shot Migration Container"]
        ALEMBIC["Alembic Migration Runner<br/>(Runs before API startup on deployment)"]
    end

    APP -->|HTTPS REST (Port 443)| NGINX
    APP -->|WSS WebSockets (Port 443)| NGINX

    NGINX -->|HTTP Reverse Proxy (Port 8000)| UVICORN
    UVICORN --> FASTAPI
    FASTAPI --> MIDDLEWARE
    MIDDLEWARE --> ROUTERS
    ROUTERS --> DEP_INJ
    DEP_INJ --> SERVICES
    SERVICES --> ML_ENGINE
    SERVICES --> WS_MGR

    SERVICES -->|Async SQL (asyncpg)| POSTGRES
    SERVICES -->|Cache Read/Write / Locks| REDIS
    WS_MGR -->|Pub/Sub Subscribe| REDIS

    BEAT -->|Enqueue Periodic Tasks| REDIS
    REDIS -->|Task Dispatch| WORKER_GENERAL
    REDIS -->|Task Dispatch| WORKER_ML
    REDIS -->|Task Dispatch| WORKER_MARKET

    WORKER_GENERAL -->|Sync SQL (psycopg2)| POSTGRES
    WORKER_ML -->|Sync SQL (psycopg2)| POSTGRES
    WORKER_MARKET -->|Sync SQL (psycopg2)| POSTGRES

    WORKER_GENERAL -->|Read/Write Cache & State| REDIS
    WORKER_ML -->|Read/Write Cache & State| REDIS
    WORKER_MARKET -->|Publish Live Quotes| REDIS

    ALEMBIC -.->|Run Schema Upgrades| POSTGRES
```

---

## 3. Component Architecture & Layering

The system is organized into distinct functional layers adhering to separation of concerns and dependency inversion principles:

```mermaid
graph TD
    subgraph L1 ["1. API Presentation Layer (app/api/v1/)"]
        A1[Auth & User Routers]
        A2[Market & Stock Routers]
        A3[Portfolio & Risk Routers]
        A4[AI Assistant & Recommendations]
        A5[News, Sentiment & Events]
        A6[Alerts, Devices & Notifications]
        A7[Community & Social Routers]
        A8[Shariah, ETFs, IPOs, Health]
    end

    subgraph L2 ["2. Security & Middleware Layer (app/core/)"]
        M1[Correlation ID Middleware]
        M2[TrustedHost & CORS Security]
        M3[SlowAPI Rate Limiting]
        M4[Authentication & RBAC Dependencies]
        M5[Global Exception Handlers]
    end

    subgraph L3 ["3. Domain Service Layer (app/services/)"]
        S1[MarketService & LiveBus]
        S2[StockService & PriceCacheService]
        S3[PortfolioService & ValuationEngine]
        S4[RiskService & MonteCarloEngine]
        S5[RecommendationService]
        S6[SentimentService & FinBERT]
        S7[AssistantService & GroqClient]
        S8[NewsPipeline Ingestion Engine]
        S9[AlertService & NotificationService]
        S10[ShariahScreeningService]
        S11[CommunityService & Moderation]
        S12[WebSocketManager]
    end

    subgraph L4 ["4. ML & Analytics Layer (app/ml/ & backend/models/)"]
        ML1[BiGRU Neural Network Horizon Forecaster]
        ML2[XGBoost Gradient Boosted Classifier]
        ML3[Ensemble Voting & Calibration Engine]
        ML4[Technical Indicator Calculation TA-Lib]
        ML5[Model Evaluation & Drift Tracker]
    end

    subgraph L5 ["5. Background Job Subsystem (app/tasks/)"]
        T1[daily_workflow: Close OHLCV -> ML -> Eval]
        T2[refresh_market_cache: Intraday 60s quotes]
        T3[scrape_news & sentiment_tasks: Ingestion]
        T4[alert_tasks: Real-time price trigger evaluation]
        T5[risk_tasks: Portfolio stress & breach checks]
        T6[weekly_retraining: Model hyperparameter tuning]
    end

    subgraph L6 ["6. Data Persistence & Cache Layer"]
        D1[(PostgreSQL 16 Database)]
        D2[(Redis 7 Cache / Broker / PubSub)]
    end

    L1 --> L2
    L2 --> L3
    L3 --> L4
    L3 --> L6
    L5 --> L3
    L5 --> L4
    L5 --> L6
```

---

## 4. Low-Level Subsystem Architecture & Workflows

### 4.1 Real-Time Market Data Ingestion & WebSocket Streaming Bus

The platform provides sub-second live PSX ticker quotes to mobile clients using a Redis Pub/Sub backplane that coordinates distributed Celery workers with asynchronous FastAPI WebSocket connection pools.

```mermaid
sequenceDiagram
    autonumber
    participant PSX as PSX Data Source / Ticker Feed
    participant Worker as Celery Live Market Worker
    participant Redis as Redis Cache & Pub/Sub
    participant WS as WebSocket Manager (FastAPI)
    participant Client as Android Mobile App

    Note over Worker,PSX: Intraday Loop (Every 60s or Ticker Event)
    Worker->>Redis: Check Single-Flight Ingestion Lock
    alt Lock Acquired
        Worker->>PSX: Scrape Latest Live Market Snapshot (Indices, Equities)
        PSX-->>Worker: Raw Quote Records & Ticker Tapes
        Worker->>Worker: Sanitize, Normalize & Calculate % Change
        Worker->>Redis: Write Cache Key `market:quotes:live` (TTL 90s)
        Worker->>Redis: Publish Event to Channel `psx:market:live_quotes`
        Worker->>Redis: Release Ingestion Lock
    else Lock Held by Another Process
        Worker->>Worker: Skip Execution (Avoid Upstream Duplication)
    end

    Note over WS,Redis: WebSocket Manager Listen Loop
    Redis-->>WS: Broadcast `psx:market:live_quotes` payload
    WS->>WS: Filter active subscriptions by client ticker watchlists
    WS-->>Client: Send JSON message via WSS: `{type: "QUOTE_UPDATE", data: [...]}`
```

---

### 4.2 Multi-Source News Ingestion, NLP Sentiment Scoring & Deduplication Pipeline

The news ingestion engine aggregates articles and corporate announcements across 8 Pakistani financial and regulatory portals, filters duplicates, scores sentiment using FinBERT, links stock symbols, and tags market impact.

```mermaid
flowchart TD
    subgraph Sources ["News & Regulatory Ingestion Feeds"]
        S_BR["Business Recorder RSS"]
        S_DAWN["Dawn Business News"]
        S_METTIS["Mettis Global"]
        S_PSX["PSX Company Announcements"]
        S_SBP["State Bank of Pakistan (SBP)"]
        S_SECP["SECP Regulatory Notices"]
        S_OGRA["OGRA Petroleum Directives"]
        S_FBR["FBR Fiscal Directives"]
    end

    subgraph Pipeline ["News Ingestion Pipeline (app/services/news_pipeline/)"]
        COLLECT["Parallel Feed Collectors"]
        DEDUP["Deduplication Engine<br/>(SHA-256 Title Hash & SimHash Fuzzy Match)"]
        TAGGER["Symbol Tagger & Named Entity Recognition<br/>(Extracts PSX Symbols e.g. OGDC, PPL, LUCK)"]
        CLASSIFIER["Event Classifier<br/>(Earnings, Dividend, Mergers, Regulatory, Macro)"]
        SCORER["Market Impact Scorer<br/>(High, Medium, Low, Neutral)"]
        FINBERT["FinBERT Financial Sentiment Scorer<br/>(Positive, Negative, Neutral with Confidence)"]
    end

    subgraph Storage ["Storage & Alerting"]
        DB_NEWS[("PostgreSQL: news_articles,<br/>news_ticker_mentions,<br/>sentiment_results")]
        ALERT_DISPATCH["Alert Engine Dispatch<br/>(Triggers Sentiment Impact Alerts)"]
    end

    Sources --> COLLECT
    COLLECT --> DEDUP
    DEDUP -->|Unique Articles| TAGGER
    TAGGER --> CLASSIFIER
    CLASSIFIER --> SCORER
    SCORER --> FINBERT
    FINBERT --> DB_NEWS
    FINBERT --> ALERT_DISPATCH
```

---

### 4.3 Post-Market Automated Daily Workflow & ML Forecasting Inference

Every trading day after market close (Mon–Thu 15:35 PKT, Fri 16:35 PKT), Celery Beat kicks off the mission-critical automated pipeline:

```mermaid
flowchart TD
    subgraph Trigger ["Scheduler Trigger"]
        BEAT["Celery Beat Scheduler<br/>(Mon-Thu 15:35, Fri 16:35 PKT)"]
    end

    subgraph Step1 ["Step 1: OHLCV Data Acquisition"]
        CHECK_HOLIDAY{"Is PSX Trading Day?<br/>(Check Calendar & Holidays)"}
        SCRAPER["Scraper Engine (run_after_close.py)<br/>• Incremental Symbol Fetch<br/>• Batching (10 symbols + pause)<br/>• Atomic Staging Directory"]
        VERIFY{"Verify Data Completeness<br/>(All symbols present?)"}
        PROMOTE["Promote Staged Parquet<br/>to Production Dataset"]
    end

    subgraph Step2 ["Step 2: Feature Engineering & Technicals"]
        FE["Feature Generation Engine<br/>• Returns, Volatility, Log Volumes<br/>• Technicals: RSI-14, MACD, BB, SMA-20/50/200, ATR<br/>• Macro & Sector Factors"]
    end

    subgraph Step3 ["Step 3: ML Model Inference Fleet"]
        GRU["Bidirectional GRU Model<br/>(Sequential Time Series Pattern Extraction)"]
        XGB["XGBoost Classifier<br/>(Tabular Feature Interactions & Splits)"]
        ENSEMBLE["Calibrated Ensemble Voting Engine<br/>(Weighted Probability Calibration)"]
        PRED_STORE["Store Horizon Predictions<br/>(1-Day, 7-Day, 30-Day Bullish/Bearish/Sideways)"]
    end

    subgraph Step4 ["Step 4: Recommendation Engine & Evaluation"]
        RECS["Recompute Quantitative Stock Rankings<br/>(35% Technicals + 35% Fundamentals + 20% ML Forecast + 10% Sentiment)"]
        CACHE_RECS["Warm Redis Recommendation Cache"]
        EVAL["Evaluate Previous Horizon Predictions<br/>(Compare target_date price with actual close)"]
        STORE_EVAL["Record Accuracy & Drift Metrics in DB"]
    end

    BEAT --> CHECK_HOLIDAY
    CHECK_HOLIDAY -->|Yes| SCRAPER
    CHECK_HOLIDAY -->|No / Weekend| END_TASK([Exit Workflow])
    SCRAPER --> VERIFY
    VERIFY -->|Success| PROMOTE
    VERIFY -->|Partial/Failed| PRESERVE([Preserve Last Known Good Dataset])
    PROMOTE --> FE
    FE --> GRU & XGB
    GRU & XGB --> ENSEMBLE
    ENSEMBLE --> PRED_STORE
    PRED_STORE --> RECS
    RECS --> CACHE_RECS
    CACHE_RECS --> EVAL
    EVAL --> STORE_EVAL
```

---

### 4.4 AI Investment Assistant (Copilot) RAG Architecture & Safety Guardrails

The Basarat AI Copilot leverages Groq’s ultra-low latency Llama-3-70B model infused with live market quotes, technical indicators, portfolio status, and Shariah screening data, protected by strict financial safety guardrails.

```mermaid
sequenceDiagram
    autonumber
    participant User as Mobile User
    participant Router as Assistant Router (`/api/v1/assistant/chat`)
    participant Safety as Safety & Prompt Guardrails
    participant Context as Context Aggregator & RAG Builder
    participant Cache as Assistant Context Cache (Redis)
    participant Groq as Groq LLM API (Llama 3 70B)
    participant DB as PostgreSQL (Chat History)

    User->>Router: Send Message: "Should I buy OGDC today?"
    Router->>Safety: Pre-Inference Safety Check (Prompt Injection, Non-financial queries, Restricted advice)
    alt Safety Violation Detected
        Safety-->>Router: Refusal Message / Educational Guidance
        Router-->>User: Structured Safe Response
    else Valid Query
        Router->>Context: Build RAG Context for Ticker "OGDC"
        Context->>Cache: Query Cached Ticker Fundamentals, Live Quote, ML Forecast, FinBERT Sentiment
        alt Cache Miss
            Context->>Context: Fetch from Database / Service Layer
            Context->>Cache: Cache Context (TTL 5 min)
        end
        Context->>DB: Fetch Recent Conversation History (Last 10 turns)
        Context-->>Router: Formatted System Prompt + Financial Context + User Query
        Router->>Groq: Generate Completion (Stream or Synchronous)
        Groq-->>Router: Raw LLM Output
        Router->>Safety: Post-Inference Guardrails (Ensure Disclaimers & No Guaranteed Return claims)
        Router->>DB: Persist User Message & Assistant Response
        Router-->>User: Final Response with Reasoning, Sources & Disclaimer
    end
```

---

### 4.5 Portfolio Valuation Engine & Quantitative Risk Analytics (VaR / Monte Carlo)

The portfolio and risk sub-systems perform real-time mark-to-market valuations, sector exposure audits, and statistical risk simulations (Value at Risk, Conditional VaR, and Monte Carlo scenarios).

```mermaid
flowchart LR
    subgraph Input ["User Portfolio Input"]
        TX["Transaction Ledger<br/>(Buy / Sell Orders, Cash Deposits)"]
        HOLDINGS["Calculated Holdings<br/>(Symbols, Quantities, Cost Basis)"]
    end

    subgraph Valuation ["Valuation Engine (app/services/portfolio/)"]
        LIVE_PRICES["Live Price Resolver<br/>(Redis Live Cache -> Last Known OHLCV Close)"]
        MTM["Mark-to-Market Calculator<br/>• Current Value<br/>• Unrealized P&L<br/>• Realized P&L<br/>• Daily Return %"]
        SECTOR_ALLOC["Sector & Asset Allocation Breakdown"]
    end

    subgraph RiskAnalytics ["Quantitative Risk Engine (app/services/risk_service.py)"]
        VAR_PARAMETRIC["Parametric VaR (95% & 99% CI)"]
        VAR_HISTORICAL["Historical Simulation VaR"]
        CVAR["Conditional VaR (Expected Shortfall)"]
        SHARPE_BETA["Sharpe Ratio, Sortino & Beta vs KSE-100"]
        MONTE_CARLO["Monte Carlo 10,000-Path Simulation<br/>(Projected Return & Loss Probability Distributions)"]
        STRESS_TEST["Stress Testing against Historical Crises<br/>(2008 Crash, COVID 2020, 2023 FX Devaluation)"]
    end

    TX --> HOLDINGS
    HOLDINGS --> LIVE_PRICES
    LIVE_PRICES --> MTM
    MTM --> SECTOR_ALLOC
    MTM --> VAR_PARAMETRIC & VAR_HISTORICAL & CVAR
    MTM --> SHARPE_BETA
    MTM --> MONTE_CARLO & STRESS_TEST
```

---

## 5. Security & Network Architecture

1. **Edge Protection & Rate Limiting**:
   - **Nginx Ingress**: Rate limits client requests (20 requests/second per IP with burst capacity of 50).
   - **SlowAPI Application Rate Limiting**: Enforces strict endpoint-specific limits (e.g., Auth Login 5/min, Password Reset 3/min, AI Chat 15/min).
   - **TrustedHostMiddleware**: Enforces valid `Host` headers; rejects wildcard (`*`) and localhost in production.
   - **CORSMiddleware**: Restricts origins strictly to configured mobile and web client domains.

2. **Authentication & Session Security**:
   - **JWT Tokens**: Cryptographically signed access tokens (HS256) with short lifetimes (60 minutes) and rotating refresh tokens (7 days).
   - **Bcrypt Password Hashing**: Passwords salted and hashed with work factor 12.
   - **Request Correlation**: Middleware automatically assigns or propagates an `X-Request-ID` across every incoming request and downstream response.

3. **Production Isolation**:
   - Database operations use parameterized queries exclusively through SQLAlchemy ORM, mitigating SQL injection risks.
   - External credentials (Firebase Service Account, Database Passwords, SendGrid Keys, Groq API Keys) are injected strictly via container environment variables and never baked into Docker images.
