import logging

from fastapi import APIRouter, Depends, Path, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import AppError, NotFoundError, ServiceUnavailableError, ValidationFailedError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.schemas.shariah import (
    ShariahCriteriaResponse,
    ShariahKMI30Response,
    ShariahPurificationResponse,
    ShariahScreeningResponse,
)
from app.services.shariah_service import NON_COMPLIANT_SYMBOLS, PSX_KMI30_SCREENING, ShariahService

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
    service: ShariahService = Depends(_get_service),
):
    """Retrieve all constituent companies of the PSX KMI-30 Shariah Index."""
    try:
        constituents = await service.get_kmi30_constituents()
        if not constituents:
            raise ServiceUnavailableError("KMI-30 constituent data is temporarily unavailable.")
        return ShariahKMI30Response(
            index="KMI-30",
            total_constituents=len(constituents),
            as_of=f"{PSX_KMI30_SCREENING['accounts_as_of']}T00:00:00+00:00",
            is_stale=service.market_constituents_freshness().get("is_stale", True),
            effective_from=f"{PSX_KMI30_SCREENING['effective_from']}T00:00:00+00:00",
            source_url=PSX_KMI30_SCREENING["source_url"],
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
    symbol: str = Path(..., min_length=1, max_length=15, pattern=r"^[A-Za-z0-9][A-Za-z0-9.-]*$"),
    service: ShariahService = Depends(_get_service),
):
    """Screen an individual PSX stock against Shariah compliance guidelines."""
    try:
        sym_upper = symbol.upper().strip()
        screening = await service.get_screening(sym_upper)

        if screening is None:
            return ShariahScreeningResponse(
                symbol=sym_upper,
                screening_available=False,
                is_shariah_compliant=None,
                overall_score=None,
                screening_method=None,
                screened_at=None,
                compliance_summary=f"No Shariah screening data is available for {sym_upper}; compliance is unverified.",
            )

        profile = NON_COMPLIANT_SYMBOLS.get(sym_upper, {})
        purif_rate = (
            float(screening.interest_income_ratio)
            if screening.is_shariah_compliant and screening.interest_income_ratio is not None
            else None
        )

        source_fields = {
            field: getattr(screening, field, None)
            for field in ("data_as_of", "data_is_stale", "effective_from", "source_url",
                          "source_exception", "purification_rate_provisional")
        }
        summary = (
            f"{sym_upper} is classified by the PSX KMI-30 screening effective {source_fields['effective_from'].date()}; financial ratios are as of {source_fields['data_as_of'].date()}."
            if screening.screening_method and screening.screening_method.startswith("PSX KMI-30 screening notice")
            else f"{sym_upper} is a current PSX KMI-30 constituent; financial screening ratios are unavailable."
            if screening.is_shariah_compliant
            else f"{sym_upper} does not satisfy PSX Shariah screening criteria ({profile.get('reason', 'Financial or business non-compliance')})."
        )
        criteria = service.build_criteria(screening, symbol=sym_upper)

        return ShariahScreeningResponse(
            symbol=sym_upper,
            is_shariah_compliant=screening.is_shariah_compliant,
            overall_score=None,
            screening_method=screening.screening_method or "PSX KMI-30 / Meezan Screening Standard",
            screened_at=screening.screened_at,
            **source_fields,
            sector=profile.get("sector"),
            purification_rate=purif_rate if screening.is_shariah_compliant else None,
            criteria=criteria,
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
    symbol: str = Path(..., min_length=1, max_length=15, pattern=r"^[A-Za-z0-9][A-Za-z0-9.-]*$"),
    service: ShariahService = Depends(_get_service),
):
    """Retrieve the breakdown of all 6 Shariah screening criteria for a given stock."""
    try:
        sym_upper = symbol.upper().strip()
        screening = await service.get_screening(sym_upper)
        criteria = service.build_criteria(screening, symbol=sym_upper)

        is_compliant = screening.is_shariah_compliant if screening else None

        return ShariahCriteriaResponse(
            symbol=sym_upper,
            screening_available=screening is not None,
            is_shariah_compliant=is_compliant,
            criteria=criteria,
            data_as_of=getattr(screening, "data_as_of", None),
            data_is_stale=getattr(screening, "data_is_stale", None),
            source_url=getattr(screening, "source_url", None),
        )
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch Shariah criteria for %s", symbol)
        raise ServiceUnavailableError("Shariah criteria temporarily unavailable.")


@router.get(
    "/shariah/{symbol}/purification",
    response_model=ShariahPurificationResponse,
    summary="Calculate purification amount from dividend income",
)
@limiter.limit("60/minute")
async def get_shariah_purification(
    request: Request,
    symbol: str = Path(..., min_length=1, max_length=15, pattern=r"^[A-Za-z0-9][A-Za-z0-9.-]*$"),
    dividend_income: float = Query(..., gt=0),
    service: ShariahService = Depends(_get_service),
):
    """Calculate the Shariah purification (charitable deduction) required for a holding."""
    try:
        sym_upper = symbol.upper().strip()
        screening = await service.get_screening(sym_upper)
        if screening is None:
            raise NotFoundError(f"No Shariah screening data is available for {sym_upper}.")
        if not screening.is_shariah_compliant:
            raise ValidationFailedError(
                f"Purification is unavailable for {sym_upper} because it is screened as non-compliant."
            )

        custom_rate = None
        if screening.interest_income_ratio is not None:
            custom_rate = float(screening.interest_income_ratio)
        if custom_rate is None:
            raise ValidationFailedError(
                f"A verified purification rate is not available for {sym_upper}."
            )

        purification_amount, purification_rate = service.calculate_purification(
            dividend_income=dividend_income,
            symbol=sym_upper,
            rate=custom_rate,
        )

        is_provisional = bool(getattr(screening, "purification_rate_provisional", False))
        notes = (f"Using the PSX screening rate dated {getattr(screening, 'data_as_of', None).date()}, "
                 f"calculate PKR {purification_amount:,.2f} ({purification_rate * 100:.2f}% of dividend income). "
                 + ("PSX marks this rate provisional and subject to adjustment." if is_provisional else ""))

        return ShariahPurificationResponse(
            symbol=sym_upper,
            dividend_income=dividend_income,
            purification_amount=purification_amount,
            purification_rate=purification_rate,
            notes=notes,
            data_as_of=getattr(screening, "data_as_of", None),
            source_url=getattr(screening, "source_url", None),
            rate_is_provisional=is_provisional,
        )
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to calculate purification for %s", symbol)
        raise ServiceUnavailableError("Purification calculation temporarily unavailable.")
