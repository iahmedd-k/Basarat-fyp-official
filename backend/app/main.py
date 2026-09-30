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
    etfs,
    events,
    forecast,
    ipos,
    market,
    news,
    notifications,
    portfolio,
    prices,
    recommendations,
    risk,
    sentiment,
    shariah,
    stocks,
    system,
    users,
    watchlist,
    webhooks,
    ws,
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

    # Redis → WebSocket fan-out so Celery session refreshes reach connected clients
    try:
        from app.services.market_live_bus import start_live_bus_listener

        await start_live_bus_listener()
    except Exception as exc:
        log.warning("Could not start market live bus listener: %s", exc)

    # Ask the shared Celery worker to warm market snapshots. Never scrape
    # from every API container's startup hook.
    if settings.USE_CELERY:
        try:
            from app.tasks.refresh_market_cache import refresh_market_cache
            refresh_market_cache.delay(refresh_reference=True, refresh_constituents=True)
        except Exception as exc:
            log.warning("Could not enqueue initial market cache refresh: %s", exc)

    yield

    try:
        from app.services.market_live_bus import stop_live_bus_listener

        await stop_live_bus_listener()
    except Exception as exc:
        log.warning("Market live bus shutdown error: %s", exc)

    await engine.dispose()


TAGS_METADATA = [
    {"name": "Auth", "description": "User authentication, JWT login/signup, session refresh, and password recovery."},
    {"name": "Users", "description": "User profile details, risk profile settings, and notification channel preferences."},
    {"name": "Devices", "description": "Firebase Cloud Messaging (FCM) device registration for mobile push notifications."},
    {"name": "Webhooks", "description": "Third-party service callbacks and authentication webhooks."},
    {"name": "Market", "description": "PSX market summary, indices, gainers/losers, live discovery (GET /market/live), and cache-backed quotes for REST fallback."},
    {"name": "Stocks", "description": "Individual PSX stock quotes, company profiles, fundamentals, and technical indicators."},
    {"name": "Watchlist", "description": "User stock watchlists: 1-tap bookmark toggles, baseline price tracking (change since added), and enriched live AI directional forecasts & FinBERT sentiment ratings."},
    {"name": "Forecast", "description": "ML directional forecasts (bullish/bearish/sideways): predict+save, history with real outcomes, pipeline schedule at GET /forecast/pipeline (daily 18:00 PKT)."},
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
    {"name": "WebSockets", "description": "Live PSX quote stream (WS primary). See GET /api/v1/ws/protocol and GET /api/v1/market/live for Android integration + REST fallback."},
    {"name": "Assistant", "description": "AI investment assistant chatbot with portfolio context and market guardrails."},
    {"name": "ETFs", "description": "Exchange Traded Funds (ETFs) directory, live quotes, benchmark tracking, and historical performance."},
    {"name": "IPOs", "description": "Initial Public Offerings (IPOs) directory, calendar, book building, and post-listing performance."},
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

# Allow every browser origin during development and tests. Staging/production
# require an explicit allowlist; Settings rejects wildcard origins there.
_is_development = settings.ENVIRONMENT in {"development", "test"}
if _is_development:
    _cors_origins = ["*"]
else:
    _cors_origins = [o.strip() for o in (settings.CORS_ORIGINS or []) if o and o.strip()]
    if not _cors_origins or "*" in _cors_origins:
        raise ValueError("CORS_ORIGINS must be an explicit allowlist outside development")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    # Wildcard CORS cannot be combined with credentialed browser requests.
    # Production retains credentials support with its explicit origin list.
    allow_credentials=not _is_development,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module 1 — Auth, Users & Webhooks
app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["Auth"])
app.include_router(users.router, prefix=settings.API_V1_PREFIX, tags=["Users"])
app.include_router(devices.router, prefix=settings.API_V1_PREFIX, tags=["Devices"])
app.include_router(webhooks.router, prefix=settings.API_V1_PREFIX, tags=["Webhooks"])

# Module 2 — Market Data
app.include_router(market.router, prefix=settings.API_V1_PREFIX, tags=["Market"])

# Module 3 — Stock Detail, Technical & Watchlist
app.include_router(stocks.router, prefix=settings.API_V1_PREFIX, tags=["Stocks"])
app.include_router(watchlist.router, prefix=settings.API_V1_PREFIX, tags=["Watchlist"])

# Module 4 — Forecasting
app.include_router(forecast.router, prefix=settings.API_V1_PREFIX, tags=["Forecast"])

# Module 5 — Recommendations
app.include_router(recommendations.router, prefix=settings.API_V1_PREFIX, tags=["Recommendations"])

# Module 6 — Portfolio + live prices (quote cache used by portfolio UIs)
app.include_router(portfolio.router, prefix=settings.API_V1_PREFIX, tags=["Portfolio"])
app.include_router(prices.router, prefix=settings.API_V1_PREFIX, tags=["Prices"])

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

# Module 13 — WebSockets (Live Market & Alerts)
app.include_router(ws.router, prefix=settings.API_V1_PREFIX, tags=["WebSockets"])
app.include_router(ws.router, prefix="", include_in_schema=False)

# Module 14 — ETFs & IPOs (Public & Admin CRUD)
app.include_router(etfs.router, prefix=settings.API_V1_PREFIX, tags=["ETFs"])
app.include_router(ipos.router, prefix=settings.API_V1_PREFIX, tags=["IPOs"])

# Admin Community / ETFs / IPOs
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
