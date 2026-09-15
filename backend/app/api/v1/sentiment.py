from fastapi import APIRouter, Depends, Query

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.models.user import User
from app.schemas.auth import MarketSentimentResponse, SentimentResponse
from app.services.market_service import MarketService

router = APIRouter()


@router.get(
    "/sentiment/{symbol}",
    response_model=SentimentResponse,
    summary="Get sentiment analysis for a stock",
)
async def get_sentiment(
    symbol: str,
    user: User = Depends(get_current_user),
):
    try:
        symbol = symbol.upper()
        return SentimentResponse(
            symbol=symbol,
            score=0.0,
            label="neutral",
            article_count=0,
            trend="stable",
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch sentiment: {exc}")


@router.get(
    "/sentiment/market-overview",
    response_model=MarketSentimentResponse,
    summary="Get overall market sentiment",
)
async def get_market_sentiment(
    user: User = Depends(get_current_user),
    service: MarketService = Depends(MarketService),
):
    try:
        overview = service.get_sentiment_overview()
        return MarketSentimentResponse(
            market_mood=overview["market_mood"],
            advancing=overview["advancing"],
            declining=overview["declining"],
            unchanged=overview["unchanged"],
            advance_decline_ratio=overview["advance_decline_ratio"],
            overall_score=0.0,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch market sentiment: {exc}")
