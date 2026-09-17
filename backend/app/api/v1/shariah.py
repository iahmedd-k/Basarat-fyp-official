import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import AppError, NotFoundError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.shariah import (
    ShariahCriteriaResponse,
    ShariahKMI30Response,
    ShariahPurificationResponse,
    ShariahScreeningResponse,
)
from app.services.shariah_service import ShariahService

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> ShariahService:
    return ShariahService(db)


@router.get(
    "/shariah/kmi30",
    response_model=ShariahKMI30Response,
    summary="Get KMI-30 Shariah compliant constituents (not yet implemented)",
)
@limiter.limit("10/minute")
async def get_kmi30_shariah(
    request: Request,
    user: User = Depends(get_current_user),
):
    return ShariahKMI30Response(
        index="KMI-30",
        constituents=[],
    )


@router.get(
    "/shariah/{symbol}",
    response_model=ShariahScreeningResponse,
    summary="Get Shariah compliance screening for a stock",
)
@limiter.limit("30/minute")
async def get_shariah_screening(
    request: Request,
    symbol: str,
    user: User = Depends(get_current_user),
    service: ShariahService = Depends(_get_service),
):
    try:
        symbol = symbol.upper()
        screening = await service.get_screening(symbol)

        if screening is None:
            return ShariahScreeningResponse(
                symbol=symbol,
                is_shariah_compliant=False,
                overall_score=None,
                screening_method=None,
                screened_at=None,
            )

        return ShariahScreeningResponse(
            symbol=symbol,
            is_shariah_compliant=screening.is_shariah_compliant,
            overall_score=float(screening.debt_ratio) if screening.debt_ratio else None,
            screening_method=screening.screening_method,
            screened_at=screening.screened_at,
        )
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch Shariah screening")
        raise ServiceUnavailableError("Shariah screening temporarily unavailable.")


@router.get(
    "/shariah/{symbol}/criteria",
    response_model=ShariahCriteriaResponse,
    summary="Get detailed Shariah screening criteria",
)
@limiter.limit("30/minute")
async def get_shariah_criteria(
    request: Request,
    symbol: str,
    user: User = Depends(get_current_user),
    service: ShariahService = Depends(_get_service),
):
    try:
        symbol = symbol.upper()
        stock = await service.get_stock_by_symbol(symbol)
        if stock is None:
            raise NotFoundError("Stock not found.")

        screening = await service.get_latest_screening(stock.id)
        criteria = service.build_criteria(screening)

        return ShariahCriteriaResponse(symbol=symbol, criteria=criteria)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch Shariah criteria")
        raise ServiceUnavailableError("Shariah criteria temporarily unavailable.")


@router.get(
    "/shariah/{symbol}/purification",
    response_model=ShariahPurificationResponse,
    summary="Calculate purification amount for a holding",
)
@limiter.limit("10/minute")
async def get_shariah_purification(
    request: Request,
    symbol: str,
    holding_qty: int = Query(..., gt=0),
    holding_value: float = Query(..., gt=0),
    user: User = Depends(get_current_user),
    service: ShariahService = Depends(_get_service),
):
    try:
        symbol = symbol.upper()
        purification_amount = service.calculate_purification(holding_value)

        return ShariahPurificationResponse(
            symbol=symbol,
            holding_qty=holding_qty,
            holding_value=holding_value,
            purification_amount=purification_amount,
            purification_rate=0.025,
        )
    except Exception:
        logger.exception("Failed to calculate purification")
        raise ServiceUnavailableError("Purification calculation temporarily unavailable.")
