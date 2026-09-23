import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import register_error_handlers
from app.core.logging import setup_logging
from app.core.rate_limiter import add_rate_limiting
from app.db.base import engine

# Import all models to ensure tables are created
from app.models import prediction, model_registry, training_run  # noqa: F401

from app.api.v1 import (
    alerts,
    auth,
    devices,
    events,
    forecast,
    market,
    news,
    notifications,
    portfolio,
    recommendations,
    risk,
    sentiment,
    shariah,
    stocks,
    system,
    users,
    webhooks,
)
from app.api.v1.community import (
    posts_router as community_posts_router,
    comments_router as community_comments_router,
    follows_router as community_follows_router,
    profile_router as community_profile_router,
    notifications_router as community_notifications_router,
)
from app.api.v1.admin import community_router as admin_community_router
from app.api.v1.assistant import chat_router as assistant_chat_router

settings = get_settings()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    # ── Load ML model + scaler + metadata ──────────────────────────────
    from app.ml.serving.model_loader import load_artifacts
    load_artifacts()

    # ── Background Pre-Warm Market Cache in Redis ──────────────────────
    import asyncio
    from app.services.market_service import MarketService

    async def _warm_market_cache():
        try:
            svc = MarketService()
            await svc.get_indices()
            await svc.get_index_constituents("KSE100")
            await svc.get_index_constituents("KSE30")
            await svc.get_index_constituents("KMI30")
            await svc.get_market_data()
            log.info("Market cache pre-warmed successfully on startup")
        except Exception as exc:
            log.warning("Market cache pre-warming encounter: %s", exc)

    asyncio.create_task(_warm_market_cache())

    yield

    await engine.dispose()


TAGS_METADATA = [
    {"name": "Auth", "description": "User authentication, JWT login/signup, session refresh, and password recovery."},
    {"name": "Users", "description": "User profile details, risk profile settings, and notification channel preferences."},
    {"name": "Devices", "description": "Firebase Cloud Messaging (FCM) device registration for mobile push notifications."},
    {"name": "Webhooks", "description": "Third-party service callbacks and authentication webhooks."},
    {"name": "Market", "description": "Real-time & historical PSX market summary, indices, gainers, losers, and volume leaders."},
    {"name": "Stocks", "description": "Individual PSX stock quotes, company profiles, fundamentals, and technical indicators."},
    {"name": "Forecast", "description": "AI price predictions, prediction intervals, and deep learning model performance metrics."},
    {"name": "Recommendations", "description": "Automated quantitative stock buy/hold/sell rankings and investment signals."},
    {"name": "Portfolio", "description": "Portfolio valuation, holdings, P&L, stock/sector allocations, and transaction ledger."},
    {"name": "Risk", "description": "Portfolio risk analytics, Value-at-Risk (VaR), CVaR, Monte Carlo simulations, and stress tests."},
    {"name": "Sentiment", "description": "FinBERT NLP sentiment analysis on PSX news and corporate disclosures."},
    {"name": "News", "description": "Real-time financial news, corporate announcements, and regulatory disclosures."},
    {"name": "Events", "description": "PSX corporate events calendar, AGM dates, earnings releases, and dividend payouts."},
    {"name": "Alerts", "description": "Custom user-defined price, metric, and portfolio alert rules."},
    {"name": "Notifications", "description": "In-app notification center inbox and unread state management."},
    {"name": "Shariah", "description": "AAOIFI & KMI-30 Shariah compliance screening and dividend purification calculators."},
    {"name": "Community", "description": "Social trading feed, stock discussions, comments, follow network, and user moderation."},
    {"name": "Assistant", "description": "AI investment assistant chatbot with portfolio context and market guardrails."},
    {"name": "Admin Community", "description": "Moderator and admin actions for managing reported posts and comments."},
    {"name": "Health", "description": "Service liveness and dependency readiness health probes."},
]

app = FastAPI(
    title="Basarat API",
    version="1.0.0",
    openapi_tags=TAGS_METADATA,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

register_error_handlers(app)
add_rate_limiting(app)

# CORS configuration - explicit allowlist including required frontend origins
configured_origins = list(settings.CORS_ORIGINS) if settings.CORS_ORIGINS else []
required_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
cors_origins = list(dict.fromkeys(configured_origins + required_origins))
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

# Module 1 — Auth, Users & Webhooks
app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["Auth"])
app.include_router(users.router, prefix=settings.API_V1_PREFIX, tags=["Users"])
app.include_router(devices.router, prefix=settings.API_V1_PREFIX, tags=["Devices"])
app.include_router(webhooks.router, prefix=settings.API_V1_PREFIX, tags=["Webhooks"])

# Module 2 — Market Data
app.include_router(market.router, prefix=settings.API_V1_PREFIX, tags=["Market"])

# Module 3 — Stock Detail & Technical
app.include_router(stocks.router, prefix=settings.API_V1_PREFIX, tags=["Stocks"])

# Module 4 — Forecasting
app.include_router(forecast.router, prefix=settings.API_V1_PREFIX, tags=["Forecast"])

# Module 5 — Recommendations
app.include_router(recommendations.router, prefix=settings.API_V1_PREFIX, tags=["Recommendations"])

# Module 6 — Portfolio
app.include_router(portfolio.router, prefix=settings.API_V1_PREFIX, tags=["Portfolio"])

# Module 7 — Risk & Sentiment
app.include_router(risk.router, prefix=settings.API_V1_PREFIX, tags=["Risk"])
app.include_router(sentiment.router, prefix=settings.API_V1_PREFIX, tags=["Sentiment"])

# Module 8 — News & Events
app.include_router(news.router, prefix=settings.API_V1_PREFIX, tags=["News"])
app.include_router(events.router, prefix=settings.API_V1_PREFIX, tags=["Events"])

# Module 9 — Alerts & Notifications
app.include_router(alerts.router, prefix=settings.API_V1_PREFIX, tags=["Alerts"])
app.include_router(notifications.router, prefix=settings.API_V1_PREFIX, tags=["Notifications"])

# Module 10 — Shariah Screening
app.include_router(shariah.router, prefix=settings.API_V1_PREFIX, tags=["Shariah"])

# Module 11 — Community
app.include_router(community_posts_router, prefix=settings.API_V1_PREFIX, tags=["Community"])
app.include_router(community_comments_router, prefix=settings.API_V1_PREFIX, tags=["Community"])
app.include_router(community_follows_router, prefix=settings.API_V1_PREFIX, tags=["Community"])
app.include_router(community_profile_router, prefix=settings.API_V1_PREFIX, tags=["Community"])
app.include_router(community_notifications_router, prefix=settings.API_V1_PREFIX, tags=["Community"])

# Module 12 — Assistant
app.include_router(assistant_chat_router, prefix=settings.API_V1_PREFIX, tags=["Assistant"])

# Admin Community
app.include_router(admin_community_router, prefix=settings.API_V1_PREFIX, tags=["Admin Community"])

# Health & System Probes (Single Health tag in Swagger)
app.include_router(health_router, prefix=settings.API_V1_PREFIX, tags=["Health"])
app.include_router(health_router, prefix="", include_in_schema=False)
app.include_router(system.router, prefix=settings.API_V1_PREFIX, include_in_schema=False)

@app.get("/", include_in_schema=False)
async def root():
    return {
        "message": "Basarat API",
        "version": "v1",
        "status": "online",
        "openapi_url": f"{settings.API_V1_PREFIX}/openapi.json",
    }
