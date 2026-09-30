# Project Structure & Repository Layout — Basarat

## 1. Repository Root Overview

```text
Basarat-fyp-official/
├── .github/                   # GitHub Actions automated workflows
│   └── workflows/
│       └── deploy-ec2.yml     # Self-hosted EC2 automated deployment workflow
├── backend/                   # Python FastAPI backend application
│   ├── alembic/               # Database schema migrations
│   │   └── versions/          # 17 versioned Alembic migration scripts
│   ├── app/                   # Core application source code
│   ├── data/                  # ML feature parquets, raw datasets, scalers
│   ├── models/                # Trained ML model weights (GRU, XGBoost)
│   ├── reports/               # Route audit reports, Swagger audit artifacts
│   ├── scripts/               # Diagnostic, seeding, and migration helper scripts
│   ├── tests/                 # Automated test suite (unit, api, security, e2e)
│   ├── Dockerfile             # Container definition for API & Celery services
│   ├── docker-compose.yml     # Local development multi-container composition
│   ├── docker-compose.production.yml # Production multi-container composition
│   ├── requirements.txt       # Production Python dependencies
│   ├── requirements-test.txt  # Test and QA Python dependencies
│   └── .env.example           # Backend environment template
├── frontend/                  # React 19 Single Page Application (Vite)
│   ├── public/                # Static public assets (icons, logos)
│   ├── src/                   # React components, pages, API clients, styles
│   │   ├── api/               # API clients, WebSocket live streams, fallbacks
│   │   ├── components/        # UI components (charts, modals, page views)
│   │   ├── Landing_pages/     # Hero, Market Pulse, and Stock Preview sections
│   │   ├── utils/             # Formatters and currency helpers
│   │   ├── App.jsx            # Main application layout, routing, and state
│   │   ├── App.css            # Tailored styling and dark-mode tokens
│   │   └── main.jsx           # React DOM root entry point
│   ├── package.json           # Node.js dependencies and build scripts
│   ├── vite.config.js         # Vite build tool configuration
│   └── .env.example           # Frontend environment template
└── docs/                      # Complete enterprise/FYP-grade documentation
```

---

## 2. Backend Architecture Decomposition (`backend/app/`)

```text
backend/app/
│
├── api/                       # Controller Layer: API route declarations
│   └── v1/
│       ├── admin/             # Administrative routes (Community moderation)
│       ├── assistant/         # AI Assistant chat and SSE streaming routes
│       ├── community/         # Social feed, posts, comments, follows, profiles
│       ├── alerts.py          # Custom price/indicator alert rules and user alerts
│       ├── auth.py            # Signup, login, refresh, logout, password reset
│       ├── devices.py         # Mobile FCM device token registration
│       ├── etfs.py            # Exchange Traded Funds catalog & performance
│       ├── events.py          # PSX corporate events & AGM calendar
│       ├── forecast.py        # ML directional forecasts and history
│       ├── health.py          # Liveness & readiness probes
│       ├── ipos.py            # Initial Public Offerings directory & calendar
│       ├── market.py          # Live discovery, indices, gainers, losers, quotes
│       ├── news.py            # Paginated financial news & ingestion status
│       ├── notifications.py   # In-app notification center inbox
│       ├── portfolio.py       # Portfolio transactions, holdings, P&L, allocation
│       ├── prices.py          # Fast quote lookup cache for portfolio UIs
│       ├── recommendations.py # Quantitative stock buy/hold/sell rankings
│       ├── risk.py            # VaR, CVaR, stress testing, async Monte Carlo
│       ├── sentiment.py       # FinBERT sentiment scores & rolling aggregates
│       ├── shariah.py         # AAOIFI & KMI-30 compliance & purification
│       ├── stocks.py          # Stock search, overview, technicals, fundamentals
│       ├── users.py           # User profile & risk preference settings
│       ├── webhooks.py        # Third-party callbacks (Clerk webhook)
│       └── ws.py              # WebSocket market quote & alert streams
│
├── core/                      # Infrastructure & Cross-Cutting Concerns
│   ├── authorization.py       # JWT extraction & get_current_user dependencies
│   ├── config.py              # Pydantic BaseSettings environment loader
│   ├── database_urls.py       # Async/Sync database URL normalizer
│   ├── exceptions.py          # AppError hierarchy & global exception handlers
│   ├── logging.py             # Centralized logging configuration
│   ├── rate_limiter.py        # Sliding-window IP rate limiter
│   ├── redis.py               # Redis connection manager & helpers
│   └── security.py            # bcrypt hashing, JWT encode/decode, OTP hashing
│
├── db/                        # Database Connection & Sessions
│   ├── base.py                # SQLAlchemy declarative Base & AsyncEngine
│   └── session.py             # get_db async session dependency provider
│
├── models/                    # SQLAlchemy ORM Database Entities
│   ├── alert.py               # Alert & AlertRule models
│   ├── assistant.py           # AssistantConversation & AssistantMessage models
│   ├── community.py           # Posts, Comments, Likes, Follows, Reports, Actions
│   ├── etf.py                 # ETF directory model
│   ├── event.py               # MarketEvent corporate calendar model
│   ├── forecast.py            # Legacy Forecast model
│   ├── ipo.py                 # IPO pipeline model
│   ├── model_registry.py      # MLOps model registry model
│   ├── news.py                # NewsArticle, NewsArticleSymbol, SourceState
│   ├── portfolio.py           # PortfolioTransaction model & TransactionType
│   ├── prediction.py          # Predictions table (GRU + XGBoost audit store)
│   ├── risk.py                # RiskAssessment model
│   ├── sentiment.py           # SentimentResult & SentimentAggregate models
│   ├── shariah.py             # ShariahScreening model
│   ├── stock.py               # Stock & StockPrice models
│   ├── training_run.py        # MLOps TrainingRun tracking model
│   ├── user.py                # User, RefreshToken, PasswordResetToken, Device
│   └── watchlist.py           # Watchlist & WatchlistItem models
│
├── schemas/                   # Pydantic v2 Request/Response Schemas
│   ├── assistant.py           # Chat request/response schemas
│   ├── auth.py                # Signup, login, token, user summary schemas
│   ├── community.py           # Post, comment, follow, report schemas
│   ├── etf.py                 # ETF request/response schemas
│   ├── ipo.py                 # IPO request/response schemas
│   ├── market.py              # Indices, market summary, quote schemas
│   ├── news.py                # News feed & source state schemas
│   ├── portfolio.py           # Transaction, holding, P&L schemas
│   ├── shariah.py             # Compliance & purification schemas
│   ├── stock.py               # Technicals, fundamentals, stock search schemas
│   └── watchlist.py           # Watchlist creation, item, and toggle schemas
│
├── services/                  # Business Logic & Calculation Engines
│   ├── alert_service.py       # Alert rule evaluation service
│   ├── assistant_service.py   # AI Assistant orchestration & message handling
│   ├── assistant_context.py   # Dynamic portfolio/quote context builder
│   ├── assistant_safety.py    # Prompt injection & financial safety guardrails
│   ├── auth_service.py        # User authentication, OTPs, session rotation
│   ├── cloudinary_service.py  # Image upload & CDN asset management
│   ├── community_service.py   # Social feed, moderation & reporting logic
│   ├── email_service.py       # SendGrid & SMTP transactional email client
│   ├── etf_service.py         # ETF data & performance calculations
│   ├── event_service.py       # Corporate events calendar management
│   ├── groq_client.py         # Groq LLM API client wrapper
│   ├── ipo_service.py         # IPO pipeline & return calculations
│   ├── market_live_bus.py     # Redis Pub/Sub live market listener
│   ├── market_service.py      # Market indices, gainers/losers, discovery
│   ├── news_service.py        # News aggregation & filtering
│   ├── notification_service.py# In-app notification inbox management
│   ├── portfolio_service.py   # Average Cost Basis, P&L, holdings calculation
│   ├── recommendation_service.py # Multi-factor quantitative scoring engine
│   ├── risk_service.py        # VaR, CVaR, Monte Carlo task dispatcher
│   ├── sentiment_service.py   # FinBERT scoring & rolling aggregates
│   ├── shariah_service.py     # AAOIFI / KMI-30 compliance screening
│   ├── stock_service.py       # Stock technical indicators & fundamentals
│   ├── watchlist_service.py   # Watchlist management & live price enrichment
│   └── websocket_manager.py   # WebSocket connection & subscription manager
│
├── ml/                        # Machine Learning Subsystem
│   ├── serving/               # Model loaders, Attention-BiGRU, inference engine
│   ├── training/              # Deep learning training & feature pipelines
│   └── v3/                    # XGBoost v3/v4 training & feature engineer
│
├── tasks/                     # Celery Background Jobs & Cron Pipelines
│   ├── alert_tasks.py         # Alert rule evaluation worker (every 5m)
│   ├── community_tasks.py     # Social notifications and spam cleanup
│   ├── daily_workflow.py      # Master daily pipeline (18:00 PKT Mon-Fri)
│   ├── model_monitoring.py    # Daily model drift & performance monitoring
│   ├── news_tasks.py          # News processing tasks
│   ├── refresh_market_cache.py# Market quote scraper & session snapshot
│   ├── risk_tasks.py          # Monte Carlo simulation & risk threshold worker
│   ├── scrape_news.py         # External news scraper (every 30m)
│   ├── sentiment_tasks.py     # FinBERT scoring & rescoring workers
│   └── weekly_retraining.py   # Weekly retraining pipeline (Sunday 04:00 PKT)
│
├── celery_app.py              # Celery instance, broker configs, and beat schedule
└── main.py                    # Application entry point, lifespan, CORS, middleware
```

---

## 3. Frontend Architecture Decomposition (`frontend/src/`)

```text
frontend/src/
│
├── api/                       # Network Clients & Live Streams
│   ├── assistant.js           # AI Assistant REST & SSE stream client
│   ├── auth.js                # Auth client (signup, login, refresh, reset)
│   ├── cache.js               # Client-side in-memory caching utility
│   ├── config.js              # Base API URL configuration
│   ├── dashboard.js           # Market, indices, and quotes API client
│   ├── forecast.js            # Directional forecast API client
│   ├── forecastFallback.js    # Offline mock forecasts for demo resilience
│   ├── liveStream.js          # WebSocket client for live quote streaming
│   ├── news.js                # News feed API client
│   ├── newsFallback.js        # Offline mock news data
│   ├── recommendations.js     # Stock recommendations API client
│   ├── risk.js                # VaR, CVaR, and Monte Carlo simulation client
│   ├── riskFallback.js        # Offline mock risk analytics
│   ├── sentiment.js           # FinBERT sentiment API client
│   └── sentimentFallback.js   # Offline mock sentiment data
│
├── components/                # Modular React UI Components
│   ├── ArticleDetailModal.jsx # Full-screen news article reader modal
│   ├── AuthModal.jsx          # Unified Sign In / Sign Up / Social OAuth modal
│   ├── FloatingCopilotButton.jsx # Floating AI Assistant launcher button
│   ├── ForgotPasswordFlow.jsx # 3-Step password recovery modal
│   ├── MarketActivityPage.jsx # Market overview, gainers/losers, indices
│   ├── MonteCarloChart.jsx    # Interactive SVG/Canvas Monte Carlo cone chart
│   ├── OtpInput.jsx           # 6-digit segmented OTP entry component
│   ├── PortfolioPage.jsx      # Portfolio ledger, holdings table, P&L summary
│   ├── ProHeader.jsx          # Navigation header, market status, user menu
│   ├── RiskPage.jsx           # Risk analytics dashboard (VaR, CVaR, Stress)
│   ├── SentimentPage.jsx      # FinBERT sentiment dashboard & rolling trends
│   ├── ShariahBadge.jsx       # AAOIFI / KMI-30 compliance visual tag
│   ├── StockDetail.jsx        # Complete individual stock view (Tabs, charts)
│   ├── StockForecastSection.jsx # ML forecast probability gauge & accuracy
│   ├── StockFundamentals.jsx  # Financial ratios, P/E, EPS, balance sheet
│   ├── StockPriceChart.jsx    # Interactive Candlestick / Area price chart
│   ├── StockTechnicals.jsx    # RSI, MACD, Moving Average momentum indicators
│   └── VerifyEmailPage.jsx    # Standalone email verification page
│
├── Landing_pages/             # Public Showcase Sections
│   ├── Hero.jsx               # Hero landing banner and value proposition
│   ├── MarktePulsepage.jsx    # Live market ticker bar and overview
│   ├── News_Seciton.jsx       # Featured financial news carousel
│   └── Stockperview.jsx       # Interactive stock search and preview widget
│
├── utils/
│   └── formatters.js          # PKR currency, percentages, date formatters
│
├── App.jsx                    # Root component with routing, active page state
├── App.css                    # Complete design system, dark palette, glassmorphism
└── main.jsx                   # Entry point mounting React root
```
