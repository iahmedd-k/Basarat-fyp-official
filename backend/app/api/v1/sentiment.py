"""Sentiment API — FinBERT-based stock and market sentiment.

Pipeline: Module 8 (news) → FinBERT → aggregated score.
Rolling 7-day decay-weighted average for per-stock sentiment.
"""

import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.ml.serving.schemas import (
    MarketSentimentResponse,
    SentimentHistoryResponse,
    SentimentNewsResponse,
    SentimentResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/sentiment/{symbol}",
    response_model=SentimentResponse,
    summary="Get sentiment analysis for a stock",
)
@limiter.limit("60/minute")
async def get_sentiment(
    request: Request,
    symbol: str,
    days: int = Query(7, ge=1, le=90, description="Rolling window in days"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        symbol = symbol.upper()

        from app.services.sentiment_service import (
            compute_stock_sentiment,
            get_cached_sentiment,
        )

        # Try cache first (fresh within 1 hour)
        cached = get_cached_sentiment(symbol)
        if cached is not None:
            return SentimentResponse(
                symbol=cached["symbol"],
                score=cached["score"],
                label=cached["label"],
                confidence=cached.get("confidence"),
                positive_ratio=cached.get("positive_ratio"),
                neutral_ratio=cached.get("neutral_ratio"),
                negative_ratio=cached.get("negative_ratio"),
                article_count=cached["article_count"],
                trend=cached["trend"],
                daily_scores=cached.get("daily_scores"),
                updated_at=cached.get("updated_at"),
            )

        # Compute live
        result = await compute_stock_sentiment(db, symbol, days=days)
        return SentimentResponse(
            symbol=result["symbol"],
            score=result["score"],
            label=result["label"],
            confidence=result.get("confidence"),
            positive_ratio=result.get("positive_ratio"),
            neutral_ratio=result.get("neutral_ratio"),
            negative_ratio=result.get("negative_ratio"),
            article_count=result["article_count"],
            trend=result["trend"],
            daily_scores=result.get("daily_scores"),
            updated_at=result.get("updated_at"),
        )

    except Exception as exc:
        log.exception("Sentiment fetch failed for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch sentiment: {exc}")


@router.get(
    "/sentiment/{symbol}/history",
    response_model=SentimentHistoryResponse,
    summary="Get historical sentiment time series for a stock",
)
@limiter.limit("60/minute")
async def get_sentiment_history(
    request: Request,
    symbol: str,
    period: str = Query("1M", pattern="^(1D|1W|1M|3M|6M|1Y)$"),
    limit: int = Query(100, ge=1, le=500),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        symbol = symbol.upper()

        from app.services.sentiment_service import get_sentiment_history

        result = await get_sentiment_history(db, symbol, period, limit)
        return SentimentHistoryResponse(**result)

    except Exception as exc:
        log.exception("Sentiment history fetch failed for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch sentiment history: {exc}")


@router.get(
    "/sentiment/{symbol}/news",
    response_model=SentimentNewsResponse,
    summary="Get paginated news articles with sentiment for a stock",
)
@limiter.limit("60/minute")
async def get_sentiment_news(
    request: Request,
    symbol: str,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    from_date: str | None = Query(None, description="Filter from date (YYYY-MM-DD)"),
    to_date: str | None = Query(None, description="Filter to date (YYYY-MM-DD)"),
    sentiment: str | None = Query(None, pattern="^(POSITIVE|NEGATIVE|NEUTRAL)$"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        symbol = symbol.upper()

        from app.services.sentiment_service import get_sentiment_news
        from datetime import datetime

        from_dt = datetime.fromisoformat(from_date) if from_date else None
        to_dt = datetime.fromisoformat(to_date) if to_date else None

        items, total = await get_sentiment_news(
            db, symbol, page, limit, from_dt, to_dt, sentiment
        )

        return SentimentNewsResponse(
            symbol=symbol,
            items=items,
            total=total,
            page=page,
            limit=limit,
        )

    except Exception as exc:
        log.exception("Sentiment news fetch failed for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch sentiment news: {exc}")


@router.get(
    "/sentiment/market-overview",
    response_model=MarketSentimentResponse,
    summary="Get overall market sentiment",
)
@limiter.limit("60/minute")
async def get_market_sentiment(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        from app.services.sentiment_service import (
            compute_market_sentiment,
            get_cached_market_sentiment,
        )

        # Try cache first
        cached = get_cached_market_sentiment()
        if cached is not None:
            return MarketSentimentResponse(**cached)

        # Compute live
        result = await compute_market_sentiment(db)
        return MarketSentimentResponse(**result)

    except Exception as exc:
        log.exception("Market sentiment fetch failed")
        raise ServiceUnavailableError(f"Failed to fetch market sentiment: {exc}")