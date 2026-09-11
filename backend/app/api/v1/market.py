from fastapi import APIRouter, Depends

from app.services.market_service import MarketService

router = APIRouter()


@router.get("/market/indices")
def get_market_indices(
    service: MarketService = Depends(MarketService),
):
    return {"indices": service.get_indices()}


@router.get("/market/indices/kse-100")
def get_kse_100_constituents(
    service: MarketService = Depends(MarketService),
):
    return {
        "index": "KSE-100",
        "code": "KSE100",
        "constituents": service.get_index_constituents("KSE100"),
    }


@router.get("/market/indices/kse-30")
def get_kse_30_constituents(
    service: MarketService = Depends(MarketService),
):
    return {
        "index": "KSE-30",
        "code": "KSE30",
        "constituents": service.get_index_constituents("KSE30"),
    }


@router.get("/market/indices/kmi-30")
def get_kmi_30_constituents(
    service: MarketService = Depends(MarketService),
):
    return {
        "index": "KMI-30",
        "code": "KMI30",
        "shariah_compliant": True,
        "constituents": service.get_index_constituents("KMI30"),
    }


@router.get("/market/gainers")
def get_top_gainers(
    limit: int = 10,
    service: MarketService = Depends(MarketService),
):
    return {"gainers": service.get_top_gainers(limit)}


@router.get("/market/losers")
def get_top_losers(
    limit: int = 10,
    service: MarketService = Depends(MarketService),
):
    return {"losers": service.get_top_losers(limit)}


@router.get("/market/volume-spikes")
def get_volume_spikes(
    limit: int = 10,
    service: MarketService = Depends(MarketService),
):
    return {"volume_spikes": service.get_volume_spikes(limit)}


@router.get("/market/sentiment-overview")
def get_sentiment_overview(
    service: MarketService = Depends(MarketService),
):
    return service.get_sentiment_overview()