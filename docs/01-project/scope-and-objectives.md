# Scope and Objectives

## Project Objective

To build an intelligent PSX investment platform that democratizes access to advanced financial analytics — including ML-based forecasting, NLP sentiment analysis, risk quantification, and AI-assisted investment guidance — for Pakistani retail investors through a mobile-first API backend.

## Primary Objectives

1. **Real-time market intelligence** — Provide live PSX market data, quotes, and indices via WebSocket and REST APIs
2. **AI-powered forecasting** — Deliver directional stock price predictions using ensemble ML models (GRU + XGBoost)
3. **Sentiment-driven insights** — Analyze financial news sentiment using FinBERT NLP to inform investment decisions
4. **Portfolio management** — Enable complete portfolio tracking with transaction history, P&L, and sector allocation
5. **Risk analytics** — Compute institutional-grade risk metrics (VaR, CVaR, Monte Carlo simulations)
6. **AI investment assistant** — Provide a context-aware chatbot for personalized investment guidance
7. **Shariah compliance** — Screen stocks against AAOIFI criteria for Islamic investors

## Secondary Objectives

1. **Social trading community** — Build a discussion platform for stock-specific and market-wide conversations
2. **Automated alerts** — Trigger price-based notifications via push notifications and in-app alerts
3. **ETF & IPO tracking** — Directory and calendar for exchange-traded funds and initial public offerings
4. **Automated stock recommendations** — Generate quantitative buy/hold/sell rankings
5. **Model lifecycle management** — Automate weekly retraining with quality gates for model promotion

## In-Scope Functionality

- User authentication (email/password, Google OAuth, Apple OAuth)
- Email OTP verification and password reset flows
- PSX market data aggregation and caching
- Individual stock detail, fundamentals, and technicals
- Multi-watchlist management with target prices
- GRU + XGBoost ensemble stock direction forecasting
- FinBERT sentiment analysis on news articles
- Portfolio transaction recording and analytics
- Risk assessment (VaR, CVaR, Sharpe, Beta, stress tests)
- Automated alert rule evaluation and notification delivery
- Social trading posts, comments, follows, and moderation
- AI investment chatbot with safety guardrails
- ETF and IPO directory management
- WebSocket live quote streaming
- Background job scheduling (Celery Beat)
- CI/CD pipeline with blue-green deployment
- Health monitoring (liveness + readiness probes)

## Out-of-Scope Functionality

- **Mobile client application** — Android app is maintained in a separate repository
- **Web frontend** — No web client is included in this repository
- **Trade execution** — The platform does not execute actual stock trades on PSX
- **Real-time order book data** — Only aggregated quote data, not order-book depth
- **International markets** — Only PSX (Pakistan Stock Exchange) is supported
- **Payment processing** — No subscription or payment integration
- **Multi-language support** — API responses are English-only
- **Real-time video/audio** — No live streaming features

## Assumptions

1. The primary client is an Android mobile application communicating via REST/WebSocket APIs
2. PSX market data is obtainable via public web scraping (pypsx-toolkit, psxdata, psx-data-reader)
3. Groq free-tier API provides sufficient capacity for the AI assistant in the current user base
4. HuggingFace Inference API provides reliable FinBERT model access
5. Supabase PostgreSQL and Redis provide adequate performance for production workloads
6. A single Oracle Cloud OCI ARM64 instance handles the current traffic volume

## Constraints

1. **Budget** — Free-tier or low-cost cloud services (Groq, HuggingFace, Supabase, Oracle Cloud Always Free)
2. **PSX data access** — Dependent on public scraping; no official PSX data API
3. **ML model size** — Limited by VM memory allocation (TensorFlow + XGBoost loaded in memory)
4. **Celery concurrency** — Production worker runs with `--concurrency=1` to manage memory
5. **Database connections** — Managed connection pooling (pool_size=3, max_overflow=2)

## Dependencies

| Dependency | Type | Risk |
|-----------|------|------|
| PSX website availability | External data source | Medium — circuit breaker mitigates scraping failures |
| Groq API | LLM provider | Low — fallback model configured; assistant degrades gracefully |
| HuggingFace API | NLP inference | Low — sentiment scoring retries hourly for failures |
| SendGrid | Email delivery | Low — auth works without email; features degrade gracefully |
| Supabase | Managed database | Medium — single database provider |
| Oracle OCI / GHCR | Infrastructure | Medium — deployment depends on Oracle VM and GHCR availability |

## Known Limitations

1. WebSocket connections are per-instance (no multi-instance WebSocket sharing)
2. ML models are loaded into memory on startup; cold start takes ~2 minutes
3. News scraping is subject to PSX rate limiting (circuit breaker: 900s pause on 403/429)
4. Community image uploads depend on Cloudinary availability
5. No real-time trade execution capability

## Future Expansion Possibilities

> **Note:** The following are potential future features identified from the architecture. They are **not currently implemented**.

1. Multi-market support (KSE-100, KSE-30, KMI-30 constituent expansion)
2. Web frontend application
3. Options and derivatives analytics
4. Social sentiment scoring from community posts
5. Advanced portfolio optimization (Markowitz, Black-Litterman)
6. Multi-language support (Urdu, Arabic)
7. Payment/subscription tiers
8. Multi-region deployment for high availability
