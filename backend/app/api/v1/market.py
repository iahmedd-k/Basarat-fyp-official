from fastapi import APIRouter, Depends

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.schemas.market import (
    GainersResponse,
    IndexConstituentsResponse,
    IndicesResponse,
    LosersResponse,
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
async def get_market_indices(
    service: MarketService = Depends(MarketService),
    _user=Depends(get_current_user),
):
    try:
        indices = service.get_indices()
        return {"indices": indices}
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch market indices: {exc}")


@router.get(
    "/market/indices/kse-100",
    response_model=IndexConstituentsResponse,
    summary="Get KSE-100 index constituents",
)
async def get_kse_100_constituents(
    service: MarketService = Depends(MarketService),
    _user=Depends(get_current_user),
):
    try:
        constituents = service.get_index_constituents("KSE100")
        return {
            "index": "KSE-100",
            "code": "KSE100",
            "constituents": constituents,
        }
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch KSE-100 constituents: {exc}")


@router.get(
    "/market/indices/kse-30",
    response_model=IndexConstituentsResponse,
    summary="Get KSE-30 index constituents",
)
async def get_kse_30_constituents(
    service: MarketService = Depends(MarketService),
    _user=Depends(get_current_user),
):
    try:
        constituents = service.get_index_constituents("KSE30")
        return {
            "index": "KSE-30",
            "code": "KSE30",
            "constituents": constituents,
        }
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch KSE-30 constituents: {exc}")


@router.get(
    "/market/indices/kmi-30",
    response_model=IndexConstituentsResponse,
    summary="Get KMI-30 index constituents (Shariah compliant)",
)
async def get_kmi_30_constituents(
    service: MarketService = Depends(MarketService),
    _user=Depends(get_current_user),
):
    try:
        constituents = service.get_index_constituents("KMI30")
        return {
            "index": "KMI-30",
            "code": "KMI30",
            "shariah_compliant": True,
            "constituents": constituents,
        }
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch KMI-30 constituents: {exc}")


@router.get(
    "/market/gainers",
    response_model=GainersResponse,
    summary="Get top gaining stocks",
)
async def get_top_gainers(
    limit: int = 10,
    service: MarketService = Depends(MarketService),
    _user=Depends(get_current_user),
):
    try:
        gainers = service.get_top_gainers(limit)
        return {"gainers": gainers}
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch gainers: {exc}")


@router.get(
    "/market/losers",
    response_model=LosersResponse,
    summary="Get top losing stocks",
)
async def get_top_losers(
    limit: int = 10,
    service: MarketService = Depends(MarketService),
    _user=Depends(get_current_user),
):
    try:
        losers = service.get_top_losers(limit)
        return {"losers": losers}
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch losers: {exc}")


@router.get(
    "/market/volume-spikes",
    response_model=VolumeSpikesResponse,
    summary="Get stocks with highest volume",
)
async def get_volume_spikes(
    limit: int = 10,
    service: MarketService = Depends(MarketService),
    _user=Depends(get_current_user),
):
    try:
        spikes = service.get_volume_spikes(limit)
        return {"volume_spikes": spikes}
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch volume spikes: {exc}")


@router.get(
    "/market/sentiment-overview",
    response_model=SentimentOverview,
    summary="Get market sentiment overview",
)
async def get_sentiment_overview(
    service: MarketService = Depends(MarketService),
    _user=Depends(get_current_user),
):
    try:
        return service.get_sentiment_overview()
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch sentiment overview: {exc}")
