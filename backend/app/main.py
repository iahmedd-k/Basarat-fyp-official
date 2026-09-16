import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1.health import router as health_router
from app.core.config import get_settings
from app.core.exceptions import register_error_handlers
from app.core.logging import setup_logging
from app.db.base import Base, engine

# Import all models to ensure tables are created
from app.models import prediction, model_registry, training_run  # noqa: F401

from app.api.v1 import (
    alerts,
    assistant,
    auth,
    community,
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
)

settings = get_settings()
log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()

    # ── Create tables if they don't exist ──────────────────────────────
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database tables ensured")

    # ── Load ML model + scaler + metadata ──────────────────────────────
    from app.ml.serving.model_loader import load_artifacts
    load_artifacts()

    yield

    await engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    lifespan=lifespan,
)

register_error_handlers(app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Module 1 — Auth & Users
app.include_router(auth.router, prefix=settings.API_V1_PREFIX, tags=["Auth"])
app.include_router(users.router, prefix=settings.API_V1_PREFIX, tags=["Users"])
app.include_router(devices.router, prefix=settings.API_V1_PREFIX, tags=["Devices"])

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

# Module 10 — Community
app.include_router(community.router, prefix=settings.API_V1_PREFIX, tags=["Community"])

# Module 11 — Shariah Screening
app.include_router(shariah.router, prefix=settings.API_V1_PREFIX, tags=["Shariah"])

# Module 12 — Assistant
app.include_router(assistant.router, prefix=settings.API_V1_PREFIX, tags=["Assistant"])

# System
app.include_router(system.router, prefix=settings.API_V1_PREFIX, tags=["System"])
app.include_router(
    health_router,
    prefix="/api/v1",
    tags=["Health"]
)