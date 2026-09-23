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
    summary="Get all PSX listed stocks (~500 stocks) with manual count limit, search, and sector filters (public)",
)
@router.get(
    "/market/all-stocks",
    response_model=MarketQuotesResponse,
    summary="Get all PSX listed stocks (~500 stocks) - alias (public)",
)
@limiter.limit("30/minute")
async def get_market_quotes(
    request: Request,
    limit: int = Query(500, ge=1, le=1000, description="Number of stocks to return (e.g., 10, 50, 100, 500)"),
    offset: int = Query(0, ge=0, description="Pagination offset (default 0)"),
    symbols: str | None = Query(None, description="Comma-separated list of symbols to filter (e.g., 'OGDC,PPL,HBL')"),
    sector: str | None = Query(None, description="Filter by sector name"),
    search: str | None = Query(None, description="Search keyword in symbol or sector"),
    sort_by: str = Query("volume", description="Field to sort by: 'volume', 'change_pct', 'current', 'ldcp', 'symbol'"),
    order: str = Query("desc", description="Sort order: 'desc' or 'asc'"),
    service: MarketService = Depends(MarketService),
):
    try:
        data = await service.get_market_data()

        filtered = False
        if symbols:
            symbol_list = [s.strip().upper() for s in symbols.split(",") if s.strip()]
            data = [d for d in data if d["symbol"] in symbol_list]
            filtered = True

        if sector:
            sec_lower = sector.strip().lower()
            data = [d for d in data if sec_lower in d["sector"].lower()]
            filtered = True

        if search:
            q = search.strip().lower()
            data = [d for d in data if q in d["symbol"].lower() or q in d["sector"].lower()]
            filtered = True

        # Sort data
        reverse = (order.lower() != "asc")
        if sort_by in ["volume", "change_pct", "current", "ldcp"]:
            data = sorted(data, key=lambda x: x.get(sort_by, 0.0), reverse=reverse)
        elif sort_by == "symbol":
            data = sorted(data, key=lambda x: x.get("symbol", ""), reverse=reverse)

        total_matches = len(data)
        paginated_stocks = data[offset : offset + limit]

        return MarketQuotesResponse(
            stocks=paginated_stocks,
            total=total_matches,
            limit=limit,
            offset=offset,
            filtered=filtered,
        )
    except Exception:
        raise ServiceUnavailableError("Failed to fetch market quotes")
