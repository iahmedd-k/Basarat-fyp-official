"""Sentiment API — FinBERT-based stock and market sentiment.

Pipeline: Module 8 (news) + Module 10 (community) → FinBERT → aggregated score.
Rolling 7-day decay-weighted average for per-stock sentiment.
"""

import logging

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.ml.serving.schemas import (
    SentimentResponse,
    MarketSentimentResponse,
)

log = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/sentiment/{symbol}",
    response_model=SentimentResponse,
    summary="Get sentiment analysis for a stock",
)
async def get_sentiment(
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
                article_count=cached["article_count"],
                trend=cached["trend"],
                source_breakdown=cached.get("source_breakdown"),
                daily_scores=cached.get("daily_scores"),
            )

        # Compute live
        result = await compute_stock_sentiment(db, symbol, days=days)
        return SentimentResponse(
            symbol=result["symbol"],
            score=result["score"],
            label=result["label"],
            article_count=result["article_count"],
            trend=result["trend"],
            source_breakdown=result.get("source_breakdown"),
            daily_scores=result.get("daily_scores"),
        )

    except Exception as exc:
        log.exception("Sentiment fetch failed for %s", symbol)
        raise ServiceUnavailableError(f"Failed to fetch sentiment: {exc}")


@router.get(
    "/sentiment/market-overview",
    response_model=MarketSentimentResponse,
    summary="Get overall market sentiment",
)
async def get_market_sentiment(
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
