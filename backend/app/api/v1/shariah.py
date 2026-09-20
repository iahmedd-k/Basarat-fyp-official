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
from app.services.shariah_service import (
    KMI30_PROFILES,
    NON_COMPLIANT_SYMBOLS,
    ShariahService,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> ShariahService:
    return ShariahService(db)


@router.get(
    "/shariah/kmi30",
    response_model=ShariahKMI30Response,
    summary="Get KMI-30 Shariah compliant constituents",
)
@limiter.limit("30/minute")
async def get_kmi30_shariah(
    request: Request,
    user: User = Depends(get_current_user),
    service: ShariahService = Depends(_get_service),
):
    """Retrieve all constituent companies of the PSX KMI-30 Shariah Index."""
    try:
        constituents = await service.get_kmi30_constituents()
        return ShariahKMI30Response(
            index="KMI-30",
            total_constituents=len(constituents),
            constituents=constituents,
        )
    except Exception:
        logger.exception("Failed to fetch KMI-30 constituents")
        raise ServiceUnavailableError("KMI-30 constituents temporarily unavailable.")


@router.get(
    "/shariah/{symbol}",
    response_model=ShariahScreeningResponse,
    summary="Get Shariah compliance screening for a stock",
)
@limiter.limit("60/minute")
async def get_shariah_screening(
    request: Request,
    symbol: str,
    user: User = Depends(get_current_user),
    service: ShariahService = Depends(_get_service),
):
    """Screen an individual PSX stock against Shariah compliance guidelines."""
    try:
        sym_upper = symbol.upper().strip()
        screening = await service.get_screening(sym_upper)

        if screening is None:
            return ShariahScreeningResponse(
                symbol=sym_upper,
                is_shariah_compliant=False,
                overall_score=None,
                screening_method="PSX KMI-30 / Meezan Screening Standard",
                screened_at=None,
                compliance_summary=f"{sym_upper} is currently not classified as Shariah-compliant.",
            )

        _, purif_rate = service.calculate_purification(100.0, symbol=sym_upper)
        profile = KMI30_PROFILES.get(sym_upper) or NON_COMPLIANT_SYMBOLS.get(sym_upper, {})
        sector = profile.get("sector")

        summary = (
            f"{sym_upper} is Shariah-compliant according to PSX KMI-30 / Meezan criteria."
            if screening.is_shariah_compliant
            else f"{sym_upper} does not satisfy PSX Shariah screening criteria ({profile.get('reason', 'Financial or business non-compliance')})."
        )

        return ShariahScreeningResponse(
            symbol=sym_upper,
            is_shariah_compliant=screening.is_shariah_compliant,
            overall_score=float(screening.debt_ratio) if screening.debt_ratio is not None else None,
            screening_method=screening.screening_method or "PSX KMI-30 / Meezan Screening Standard",
            screened_at=screening.screened_at,
            sector=sector,
            purification_rate=purif_rate if screening.is_shariah_compliant else None,
            compliance_summary=summary,
        )
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch Shariah screening for %s", symbol)
        raise ServiceUnavailableError("Shariah screening temporarily unavailable.")


@router.get(
    "/shariah/{symbol}/criteria",
    response_model=ShariahCriteriaResponse,
    summary="Get detailed Shariah screening criteria",
)
@limiter.limit("60/minute")
async def get_shariah_criteria(
    request: Request,
    symbol: str,
    user: User = Depends(get_current_user),
    service: ShariahService = Depends(_get_service),
):
    """Retrieve the breakdown of all 6 Shariah screening criteria for a given stock."""
    try:
        sym_upper = symbol.upper().strip()
        screening = await service.get_screening(sym_upper)
        criteria = service.build_criteria(screening, symbol=sym_upper)

        is_compliant = screening.is_shariah_compliant if screening else False

        return ShariahCriteriaResponse(
            symbol=sym_upper,
            is_shariah_compliant=is_compliant,
            criteria=criteria,
        )
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch Shariah criteria for %s", symbol)
        raise ServiceUnavailableError("Shariah criteria temporarily unavailable.")


@router.get(
    "/shariah/{symbol}/purification",
    response_model=ShariahPurificationResponse,
    summary="Calculate purification amount for a holding",
)
@limiter.limit("60/minute")
async def get_shariah_purification(
    request: Request,
    symbol: str,
    holding_qty: int = Query(..., gt=0),
    holding_value: float = Query(..., gt=0),
    user: User = Depends(get_current_user),
    service: ShariahService = Depends(_get_service),
):
    """Calculate the Shariah purification (charitable deduction) required for a holding."""
    try:
        sym_upper = symbol.upper().strip()
        screening = await service.get_screening(sym_upper)

        custom_rate = None
        if screening and screening.interest_income_ratio is not None:
            custom_rate = float(screening.interest_income_ratio)

        purification_amount, purification_rate = service.calculate_purification(
            holding_value=holding_value,
            symbol=sym_upper,
            rate=custom_rate,
        )

        notes = (
            f"To purify income from {sym_upper}, donate PKR {purification_amount:,.2f} "
            f"({purification_rate * 100:.2f}% of dividend/holding value) to an approved Islamic charity."
        )

        return ShariahPurificationResponse(
            symbol=sym_upper,
            holding_qty=holding_qty,
            holding_value=holding_value,
            purification_amount=purification_amount,
            purification_rate=purification_rate,
            notes=notes,
        )
    except Exception:
        logger.exception("Failed to calculate purification for %s", symbol)
        raise ServiceUnavailableError("Purification calculation temporarily unavailable.")
