# Project Overview

## Project Name

**Basarat** — Smart PSX Investment Intelligence Platform

## Project Purpose

Basarat is a comprehensive investment intelligence platform focused on the **Pakistan Stock Exchange (PSX)**. It provides retail investors with real-time market data, AI-driven stock price forecasting, sentiment analysis, portfolio management, risk analytics, and a social trading community — all through a mobile-first backend API designed for an Android client.

## Problem Being Solved

Pakistani retail investors face several challenges:

1. **Limited access to intelligent analytics** — most PSX tools offer only basic price data without AI-driven insights
2. **No unified platform** combining market data, forecasting, sentiment analysis, portfolio management, and community discussion
3. **Lack of Shariah-compliant investment screening** for Islamic investors
4. **No AI-powered investment assistant** tailored to the PSX ecosystem
5. **Fragmented information sources** requiring investors to use multiple tools

Basarat consolidates these capabilities into a single platform.

## Target Users

| User Type | Description |
|-----------|-------------|
| **Retail Investors** | Individual PSX investors seeking data-driven insights |
| **Islamic Investors** | Users requiring Shariah-compliant stock screening |
| **Active Traders** | Users monitoring live market data and price alerts |
| **Community Members** | Users sharing stock analysis and market discussion |
| **Mobile Users** | Android app users (primary client) |

## Core Value Proposition

- Real-time PSX market data via WebSockets and REST fallback
- ML-based directional stock forecasts (GRU + XGBoost ensemble)
- FinBERT NLP sentiment analysis on financial news
- Comprehensive portfolio management with P&L tracking
- Risk analytics (VaR, CVaR, Monte Carlo simulations)
- AI investment assistant powered by Groq LLM
- Shariah compliance screening (AAOIFI & KMI-30)
- Social trading community with moderation
- Automated alerts and push notifications

## Major System Capabilities

| # | Module | Description |
|---|--------|-------------|
| 1 | **Auth & Users** | JWT authentication, OAuth (Google/Apple), email OTP verification, password reset |
| 2 | **Market Data** | Live PSX quotes, indices, gainers/losers via scraping + Redis cache |
| 3 | **Stocks** | Individual stock quotes, company profiles, fundamentals, technicals |
| 4 | **Watchlists** | User stock watchlists with target prices and alerts |
| 5 | **Forecasting** | ML directional predictions (bullish/bearish/sideways) via GRU + XGBoost |
| 6 | **Recommendations** | Quantitative buy/hold/sell rankings |
| 7 | **Portfolio** | Holdings, transactions, P&L, sector allocation |
| 8 | **Risk** | VaR, CVaR, Sharpe ratio, beta, Monte Carlo, stress tests |
| 9 | **Sentiment** | FinBERT NLP analysis on PSX news and disclosures |
| 10 | **News & Events** | Financial news aggregation, corporate events calendar |
| 11 | **Alerts & Notifications** | Price alerts, risk breach alerts, push notifications (FCM) |
| 12 | **Shariah** | AAOIFI compliance screening, dividend purification |
| 13 | **Community** | Social trading feed, posts, comments, follows, moderation |
| 14 | **AI Assistant** | Groq LLM chatbot with market context and safety guardrails |
| 15 | **ETFs & IPOs** | ETF directory, IPO calendar and tracking |
| 16 | **WebSockets** | Live market quote streaming |

## Technology Stack

| Layer | Technology |
|-------|-----------|
| **Language** | Python 3.11.9 |
| **Framework** | FastAPI |
| **ORM** | SQLAlchemy 2.x (async) |
| **Database** | PostgreSQL 16 (local) / Supabase (cloud) |
| **Cache & Broker** | Redis 7 / Upstash (cloud) |
| **Task Queue** | Celery 5.x with Redis broker |
| **Authentication** | JWT (HS256) via python-jose, bcrypt |
| **ML Framework** | TensorFlow 2.16 (GRU), XGBoost, scikit-learn |
| **NLP** | HuggingFace FinBERT (Inference API) |
| **LLM** | Groq API (OpenAI-compatible) |
| **Email** | SendGrid API |
| **Push Notifications** | Firebase Cloud Messaging (FCM) |
| **Object Storage** | Cloudinary (community images) |
| **Data Scraping** | BeautifulSoup4, pypsx-toolkit, psxdata, psx-data-reader |
| **Containerization** | Docker, Docker Compose |
| **CI/CD** | GitHub Actions → AWS ECR → EC2 |
| **Reverse Proxy** | Nginx (blue-green deployment) |
| **API Documentation** | OpenAPI/Swagger (auto-generated) |
| **Migration** | Alembic |
| **Rate Limiting** | SlowAPI |

## System Boundaries

The repository contains only the **backend** application. The Android mobile client is maintained in a separate repository. This backend exposes a RESTful + WebSocket API consumed by the Android app.

## External Integrations

| Service | Purpose | Implementation Status |
|---------|---------|----------------------|
| **PSX Data Sources** | Market data scraping (pypsx-toolkit, psxdata, psx-data-reader) | Implemented |
| **Groq API** | LLM for AI investment assistant | Implemented |
| **HuggingFace Inference API** | FinBERT sentiment analysis | Implemented |
| **SendGrid** | Transactional email (OTP, password reset, alerts) | Implemented |
| **Firebase FCM** | Android push notifications | Implemented (optional) |
| **Cloudinary** | Community post image uploads | Implemented |
| **Google OAuth** | Social login | Implemented |
| **Apple OAuth** | Social login | Implemented |
| **Supabase** | Cloud PostgreSQL hosting | Implemented (production) |
| **Upstash** | Cloud Redis hosting | Implemented (production) |
| **AWS ECR** | Docker image registry | Implemented |
| **AWS EC2** | Production hosting | Implemented |

## Current Implementation Status

The system is **fully implemented** and deployed to production on AWS EC2. All 16 major modules are operational with CI/CD pipeline, blue-green deployment, and health monitoring.

## Major Limitations

1. **Backend-only repository** — No frontend/mobile source code is included; the API serves an Android client built separately
2. **Free-tier LLM constraints** — Groq free-tier imposes rate limits; fallback model configured
3. **PSX data scraping** — Data depends on PSX website availability; circuit breaker pauses scraping on 403/429 responses
4. **Single-region deployment** — Currently deployed on a single EC2 instance (not multi-AZ)
5. **No automated database backups** — Database backups depend on Supabase managed service
6. **Limited test coverage for some modules** — E2E and integration tests exist but unit test coverage varies by module
