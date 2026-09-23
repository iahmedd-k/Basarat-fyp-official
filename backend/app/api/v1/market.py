from fastapi import APIRouter, Depends, Query, Request

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.schemas.market import (
    GainersResponse,
    IndexConstituentsResponse,
    IndicesResponse,
    LosersResponse,
    MarketQuotesResponse,
    MarketQuoteItem,
    SentimentOverview,
    VolumeSpikesResponse,
)
from app.services.market_service import MarketService

router = APIRouter()


@router.get(
    "/market/indices",
    response_model=IndicesResponse,
    summary="Get main market indices",
)
@limiter.limit("60/minute")
async def get_market_indices(
    request: Request,
    service: MarketService = Depends(MarketService),
):
    try:
        indices = await service.get_indices()
        return {"indices": indices}
    except Exception:
        raise ServiceUnavailableError("Failed to fetch market indices")


@router.get(
    "/market/indices/kse-100",
    response_model=IndexConstituentsResponse,
    summary="Get KSE-100 index constituents",
)
@limiter.limit("60/minute")
async def get_kse_100_constituents(
    request: Request,
    service: MarketService = Depends(MarketService),
):
    try:
        constituents = await service.get_index_constituents("KSE100")
        return {
            "index": "KSE-100",
            "code": "KSE100",
            "constituents": constituents,
        }
    except Exception:
        raise ServiceUnavailableError("Failed to fetch KSE-100 constituents")


@router.get(
    "/market/indices/kse-30",
    response_model=IndexConstituentsResponse,
    summary="Get KSE-30 index constituents",
)
@limiter.limit("60/minute")
async def get_kse_30_constituents(
    request: Request,
    service: MarketService = Depends(MarketService),
):
    try:
        constituents = await service.get_index_constituents("KSE30")
        return {
            "index": "KSE-30",
            "code": "KSE30",
            "constituents": constituents,
        }
    except Exception:
        raise ServiceUnavailableError("Failed to fetch KSE-30 constituents")


@router.get(
    "/market/indices/kmi-30",
    response_model=IndexConstituentsResponse,
    summary="Get KMI-30 index constituents (Shariah compliant)",
)
@limiter.limit("60/minute")
async def get_kmi_30_constituents(
    request: Request,
    service: MarketService = Depends(MarketService),
):
    try:
        constituents = await service.get_index_constituents("KMI30")
        return {
            "index": "KMI-30",
            "code": "KMI30",
            "shariah_compliant": True,
            "constituents": constituents,
        }
    except Exception:
        raise ServiceUnavailableError("Failed to fetch KMI-30 constituents")


@router.get(
    "/market/gainers",
    response_model=GainersResponse,
    summary="Get top gaining stocks",
)
@limiter.limit("60/minute")
async def get_top_gainers(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    service: MarketService = Depends(MarketService),
):
    try:
        gainers = await service.get_top_gainers(limit)
        return {"gainers": gainers}
    except Exception:
        raise ServiceUnavailableError("Failed to fetch gainers")


@router.get(
    "/market/losers",
    response_model=LosersResponse,
    summary="Get top losing stocks",
)
@limiter.limit("60/minute")
async def get_top_losers(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    service: MarketService = Depends(MarketService),
):
    try:
        losers = await service.get_top_losers(limit)
        return {"losers": losers}
    except Exception:
        raise ServiceUnavailableError("Failed to fetch losers")


@router.get(
    "/market/volume-spikes",
    response_model=VolumeSpikesResponse,
    summary="Get stocks with highest volume",
)
@limiter.limit("60/minute")
async def get_volume_spikes(
    request: Request,
    limit: int = Query(10, ge=1, le=100),
    service: MarketService = Depends(MarketService),
):
    try:
        spikes = await service.get_volume_spikes(limit)
        return {"volume_spikes": spikes}
    except Exception:
        raise ServiceUnavailableError("Failed to fetch volume spikes")


@router.get(
    "/market/sentiment-overview",
    response_model=SentimentOverview,
    summary="Get market sentiment overview",
)
@limiter.limit("60/minute")
async def get_sentiment_overview(
    request: Request,
    service: MarketService = Depends(MarketService),
):
    try:
        return await service.get_sentiment_overview()
    except Exception:
        raise ServiceUnavailableError("Failed to fetch sentiment overview")


@router.get(
    "/market/quotes",
    response_model=MarketQuotesResponse,
    summary="Get market quotes with optional limit and manual symbol filter (public)",
)
@limiter.limit("30/minute")
async def get_market_quotes(
    request: Request,
    limit: int = Query(500, ge=1, le=500, description="Number of stocks to return (default 500, max 500)"),
    symbols: str | None = Query(None, description="Comma-separated list of symbols to filter (e.g., 'OGDC,PPL,HBL')"),
    service: MarketService = Depends(MarketService),
):
    try:
        data = await service.get_market_data()

        filtered = False
        if symbols:
            symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
            data = [d for d in data if d["symbol"] in symbol_list]
            filtered = True

        return MarketQuotesResponse(
            stocks=data[:limit],
            total=len(data),
            limit=limit,
            filtered=filtered,
        )
    except Exception:
        raise ServiceUnavailableError("Failed to fetch market quotes")
