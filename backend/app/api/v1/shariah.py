from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.shariah import ShariahScreening
from app.models.stock import Stock
from app.models.user import User
from app.schemas.auth import (
    ShariahCriteriaResponse,
    ShariahKMI30Response,
    ShariahPurificationResponse,
    ShariahScreeningResponse,
)

router = APIRouter()


@router.get(
    "/shariah/{symbol}",
    response_model=ShariahScreeningResponse,
    summary="Get Shariah compliance screening for a stock",
)
async def get_shariah_screening(
    symbol: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        symbol = symbol.upper()

        stock_result = await db.execute(
            select(Stock).where(Stock.symbol == symbol)
        )
        stock = stock_result.scalars().first()
        if stock is None:
            raise NotFoundError(f"Stock '{symbol}' not found.")

        result = await db.execute(
            select(ShariahScreening)
            .where(ShariahScreening.stock_id == stock.id)
            .order_by(ShariahScreening.screened_at.desc())
            .limit(1)
        )
        screening = result.scalars().first()

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
            screened_at=screening.screened_at.isoformat() if screening.screened_at else None,
        )
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch Shariah screening: {exc}")


@router.get(
    "/shariah/{symbol}/criteria",
    response_model=ShariahCriteriaResponse,
    summary="Get detailed Shariah screening criteria",
)
async def get_shariah_criteria(
    symbol: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        symbol = symbol.upper()

        stock_result = await db.execute(
            select(Stock).where(Stock.symbol == symbol)
        )
        stock = stock_result.scalars().first()
        if stock is None:
            raise NotFoundError(f"Stock '{symbol}' not found.")

        result = await db.execute(
            select(ShariahScreening)
            .where(ShariahScreening.stock_id == stock.id)
            .order_by(ShariahScreening.screened_at.desc())
            .limit(1)
        )
        screening = result.scalars().first()

        criteria = [
            {"name": "Debt Ratio", "threshold": 0.33, "value": float(screening.debt_ratio) if screening and screening.debt_ratio else None, "pass": bool(screening and screening.debt_ratio and float(screening.debt_ratio) < 0.33)},
            {"name": "Interest Income Ratio", "threshold": 0.05, "value": float(screening.interest_income_ratio) if screening and screening.interest_income_ratio else None, "pass": bool(screening and screening.interest_income_ratio and float(screening.interest_income_ratio) < 0.05)},
            {"name": "Non-Compliant Assets", "threshold": 0.05, "value": None, "pass": True},
        ]

        return ShariahCriteriaResponse(symbol=symbol, criteria=criteria)
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch Shariah criteria: {exc}")


@router.get(
    "/shariah/{symbol}/purification",
    response_model=ShariahPurificationResponse,
    summary="Calculate purification amount for a holding",
)
async def get_shariah_purification(
    symbol: str,
    holding_qty: int = Query(..., gt=0),
    holding_value: float = Query(..., gt=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        symbol = symbol.upper()

        purification_rate = 0.025
        purification_amount = holding_value * purification_rate

        return ShariahPurificationResponse(
            symbol=symbol,
            holding_qty=holding_qty,
            holding_value=holding_value,
            purification_amount=round(purification_amount, 2),
            purification_rate=purification_rate,
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to calculate purification: {exc}")


@router.get(
    "/shariah/kmi30",
    response_model=ShariahKMI30Response,
    summary="Get KMI-30 Shariah compliant constituents",
)
async def get_kmi30_shariah(
    user: User = Depends(get_current_user),
):
    try:
        return ShariahKMI30Response(
            index="KMI-30",
            constituents=[],
        )
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch KMI-30 constituents: {exc}")
