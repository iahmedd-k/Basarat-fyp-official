"""Portfolio API Router."""

import logging
from datetime import date
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import BadRequestError, NotFoundError, ValidationFailedError
from app.db.session import get_db
from app.models.portfolio import TransactionType
from app.models.user import User
from app.schemas.portfolio import (
    AllocationResponse,
    HoldingDetailResponse,
    HoldingItem,
    HoldingItem as HoldingItemSchema,
    PerformanceResponse,
    PortfolioQueryParams,
    PortfolioResponse,
    PnLResponse,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.portfolio_service import PortfolioService
from app.services.portfolio_calculation import (
    InsufficientHoldingError,
    InvalidTransactionHistoryError,
    SymbolNotFoundError,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def get_portfolio_service(
    db: AsyncSession = Depends(get_db),
) -> PortfolioService:
    return PortfolioService(db)


# ── Portfolio Summary ────────────────────────────────────────────────────────

@router.get(
    "/portfolio",
    response_model=PortfolioResponse,
    summary="Get complete portfolio overview with summary and holdings",
)
async def get_portfolio(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Get the authenticated user's complete portfolio.
    
    Returns portfolio summary (total invested, current value, P&L) 
    and all active holdings with current market values.
    """
    try:
        return await service.get_portfolio(user.id)
    except Exception as exc:
        logger.exception("Get portfolio failed")
        raise BadRequestError(f"Failed to fetch portfolio: {exc}")


# ── Holdings ──────────────────────────────────────────────────────────────────

@router.get(
    "/portfolio/holdings",
    response_model=list[HoldingItem],
    summary="Get all active holdings",
)
async def get_holdings(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Get list of active holdings with current market values."""
    try:
        return await service.get_holdings(user.id)
    except Exception as exc:
        logger.exception("Get holdings failed")
        raise BadRequestError(f"Failed to fetch holdings: {exc}")


@router.get(
    "/portfolio/holdings/{symbol}",
    response_model=HoldingDetailResponse,
    summary="Get detailed view of a single holding",
)
async def get_holding_detail(
    symbol: str,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Get detailed information about a specific holding including transaction history."""
    try:
        return await service.get_holding_detail(user.id, symbol)
    except NotFoundError:
        raise
    except Exception as exc:
        logger.exception("Get holding detail failed")
        raise BadRequestError(f"Failed to fetch holding detail: {exc}")


# ── P&L ───────────────────────────────────────────────────────────────────────

@router.get(
    "/portfolio/pnl",
    response_model=PnLResponse,
    summary="Get portfolio profit/loss breakdown",
)
async def get_pnl(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Get realized, unrealized, and total P&L for the portfolio."""
    try:
        return await service.get_pnl(user.id)
    except Exception as exc:
        logger.exception("Get P&L failed")
        raise BadRequestError(f"Failed to fetch P&L: {exc}")


# ── Allocation ────────────────────────────────────────────────────────────────

@router.get(
    "/portfolio/allocation",
    response_model=AllocationResponse,
    summary="Get portfolio allocation by stock and sector",
)
async def get_allocation(
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Get portfolio allocation breakdown by individual stocks and sectors."""
    try:
        return await service.get_allocation(user.id)
    except Exception as exc:
        logger.exception("Get allocation failed")
        raise BadRequestError(f"Failed to fetch allocation: {exc}")


# ── Performance ───────────────────────────────────────────────────────────────

@router.get(
    "/portfolio/performance",
    response_model=PerformanceResponse,
    summary="Get portfolio performance over time",
)
async def get_performance(
    period: Literal["1D", "1W", "1M", "3M", "6M", "1Y", "ALL"] = Query(
        "1M", description="Time period for performance chart"
    ),
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Get portfolio performance time series for the specified period."""
    try:
        return await service.get_performance(user.id, period)
    except Exception as exc:
        logger.exception("Get performance failed")
        raise BadRequestError(f"Failed to fetch performance: {exc}")


# ── Transaction History ───────────────────────────────────────────────────────

@router.get(
    "/portfolio/transactions",
    response_model=TransactionListResponse,
    summary="Get paginated transaction history with optional filters",
)
async def get_transactions(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    symbol: str | None = Query(None, description="Filter by symbol"),
    transaction_type: Literal["BUY", "SELL"] | None = Query(None, description="Filter by type"),
    from_date: date | None = Query(None, description="Filter from date (YYYY-MM-DD)"),
    to_date: date | None = Query(None, description="Filter to date (YYYY-MM-DD)"),
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Get paginated transaction history with optional filters."""
    try:
        txn_type = TransactionType(transaction_type) if transaction_type else None
        transactions, total = await service.get_transactions(
            user_id=user.id,
            page=page,
            limit=limit,
            symbol=symbol,
            transaction_type=txn_type,
            from_date=from_date,
            to_date=to_date,
        )
        
        items = [
            TransactionResponse(
                id=t.id,
                symbol=t.symbol,
                transaction_type=t.transaction_type.value,
                quantity=t.quantity,
                price=t.price,
                fee=t.fee,
                transaction_date=t.transaction_date,
                created_at=t.created_at,
                updated_at=t.updated_at,
            )
            for t in transactions
        ]
        
        return TransactionListResponse(
            items=items,
            total=total,
            page=page,
            limit=limit,
        )
    except Exception as exc:
        logger.exception("Get transactions failed")
        raise BadRequestError(f"Failed to fetch transactions: {exc}")


@router.get(
    "/portfolio/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get a single transaction by ID",
)
async def get_transaction(
    transaction_id: str,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Get a single transaction by its ID."""
    try:
        txn = await service.get_transaction(transaction_id, user.id)
        return TransactionResponse(
            id=txn.id,
            symbol=txn.symbol,
            transaction_type=txn.transaction_type.value,
            quantity=txn.quantity,
            price=txn.price,
            fee=txn.fee,
            transaction_date=txn.transaction_date,
            created_at=txn.created_at,
            updated_at=txn.updated_at,
        )
    except NotFoundError:
        raise
    except Exception as exc:
        logger.exception("Get transaction failed")
        raise BadRequestError(f"Failed to fetch transaction: {exc}")


# ── Create Transaction ────────────────────────────────────────────────────────

@router.post(
    "/portfolio/transactions",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new BUY or SELL transaction",
)
async def create_transaction(
    data: TransactionCreate,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Record a new BUY or SELL transaction.
    
    For SELL: validates that user has sufficient holdings.
    """
    try:
        txn_type = TransactionType(data.transaction_type)
        txn = await service.create_transaction(
            user_id=user.id,
            symbol=data.symbol,
            transaction_type=txn_type,
            quantity=data.quantity,
            price=data.price,
            fee=data.fee,
            transaction_date=data.transaction_date,
        )
        
        return TransactionResponse(
            id=txn.id,
            symbol=txn.symbol,
            transaction_type=txn.transaction_type.value,
            quantity=txn.quantity,
            price=txn.price,
            fee=txn.fee,
            transaction_date=txn.transaction_date,
            created_at=txn.created_at,
            updated_at=txn.updated_at,
        )
    except SymbolNotFoundError as e:
        raise ValidationFailedError(str(e), code="INVALID_SYMBOL", field="symbol")
    except InsufficientHoldingError as e:
        raise ValidationFailedError(str(e), code="INSUFFICIENT_HOLDING", field="quantity")
    except ValidationFailedError:
        raise
    except Exception as exc:
        logger.exception("Create transaction failed")
        raise BadRequestError(f"Failed to create transaction: {exc}")


# ── Update Transaction ────────────────────────────────────────────────────────

@router.patch(
    "/portfolio/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="Update a transaction (with full re-validation)",
)
async def update_transaction(
    transaction_id: str,
    data: TransactionUpdate,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Update a transaction.
    
    After update, the complete transaction history for that symbol is re-validated
    to ensure no negative holdings occur at any point.
    """
    try:
        txn = await service.update_transaction(
            transaction_id=transaction_id,
            user_id=user.id,
            quantity=data.quantity,
            price=data.price,
            fee=data.fee,
            transaction_date=data.transaction_date,
        )
        
        return TransactionResponse(
            id=txn.id,
            symbol=txn.symbol,
            transaction_type=txn.transaction_type.value,
            quantity=txn.quantity,
            price=txn.price,
            fee=txn.fee,
            transaction_date=txn.transaction_date,
            created_at=txn.created_at,
            updated_at=txn.updated_at,
        )
    except NotFoundError:
        raise
    except InvalidTransactionHistoryError as e:
        raise ValidationFailedError(str(e), code="INVALID_TRANSACTION_HISTORY")
    except Exception as exc:
        logger.exception("Update transaction failed")
        raise BadRequestError(f"Failed to update transaction: {exc}")


# ── Delete Transaction ────────────────────────────────────────────────────────

@router.delete(
    "/portfolio/transactions/{transaction_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a transaction (with validation)",
)
async def delete_transaction(
    transaction_id: str,
    user: User = Depends(get_current_user),
    service: PortfolioService = Depends(get_portfolio_service),
):
    """Delete a transaction.
    
    Before deletion, validates that removing this transaction would not
    create negative holdings at any point in the transaction history.
    """
    try:
        await service.delete_transaction(transaction_id, user.id)
    except NotFoundError:
        raise
    except InvalidTransactionHistoryError as e:
        raise ValidationFailedError(str(e), code="INVALID_TRANSACTION_HISTORY")
    except Exception as exc:
        logger.exception("Delete transaction failed")
        raise BadRequestError(f"Failed to delete transaction: {exc}")