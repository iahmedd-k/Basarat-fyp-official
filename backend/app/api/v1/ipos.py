from typing import Optional
from fastapi import APIRouter, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from fastapi import Depends
from app.schemas.ipo import (
    IPOResponse,
    IPOListResponse,
    IPOCalendarResponse,
    IPOPerformanceResponse,
)
from app.services.ipo_service import IPOService

router = APIRouter(prefix="/ipos", tags=["IPOs"])
log = logging.getLogger(__name__)


def _get_service(db: AsyncSession = Depends(get_db)) -> IPOService:
    return IPOService(db)


@router.get(
    "",
    response_model=IPOListResponse,
    summary="List PSX IPOs (Public)",
    description="Retrieve all PSX initial public offerings with status, sector, and Shariah compliance filters.",
)
async def list_ipos(
    status: Optional[str] = Query(None, description="Filter by status: UPCOMING, ACTIVE, LISTED, CLOSED, or ALL"),
    sector: Optional[str] = Query(None, description="Filter by industry sector"),
    is_shariah_compliant: Optional[bool] = Query(None, description="Filter by Shariah compliance"),
    q: Optional[str] = Query(None, description="Search by symbol, company name, or sector"),
    search: Optional[str] = Query(None, description="Alias for search query"),
    limit: int = Query(50, ge=1, le=100, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
    service: IPOService = Depends(_get_service),
):
    try:
        search_query = q or search
        return await service.get_ipos(
            status=status,
            sector=sector,
            is_shariah_compliant=is_shariah_compliant,
            search=search_query,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        log.exception("Error listing IPOs: %s", exc)
        raise ServiceUnavailableError("Failed to retrieve IPOs.")


@router.get(
    "/calendar",
    response_model=IPOCalendarResponse,
    summary="Get PSX IPO calendar milestones (Public)",
    description="Chronological schedule of Book Building dates, Public Subscription windows, and listing days.",
)
async def get_ipo_calendar(
    service: IPOService = Depends(_get_service),
):
    try:
        return await service.get_calendar()
    except Exception as exc:
        log.exception("Error getting IPO calendar: %s", exc)
        raise ServiceUnavailableError("Failed to retrieve IPO calendar.")


@router.get(
    "/performance",
    response_model=IPOPerformanceResponse,
    summary="Get IPO listing performance & returns (Public)",
    description="Historical returns of listed IPOs comparing strike/offer price against listing day and current market prices.",
)
async def get_ipo_performance(
    service: IPOService = Depends(_get_service),
):
    try:
        return await service.get_performance()
    except Exception as exc:
        log.exception("Error getting IPO performance: %s", exc)
        raise ServiceUnavailableError("Failed to retrieve IPO performance.")


@router.get(
    "/{symbol}",
    response_model=IPOResponse,
    summary="Get specific IPO details (Public)",
    description="Retrieve issue size, pricing, book-building timeline, and prospectus link for a specific company IPO.",
)
async def get_ipo_detail(
    symbol: str,
    service: IPOService = Depends(_get_service),
):
    try:
        clean_sym = symbol.strip().upper()
        return await service.get_ipo_by_id_or_symbol(clean_sym)
    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Error getting IPO %s: %s", symbol, exc)
        raise ServiceUnavailableError(f"Failed to retrieve IPO details for {symbol}.")
