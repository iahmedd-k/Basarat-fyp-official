import logging
from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import BadRequestError, NotFoundError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.portfolio import TransactionType
from app.models.user import User
from app.repository.portfolio_repository import PortfolioRepository
from app.schemas.portfolio import (
    BulkPriceRequest,
    BulkPriceResponse,
    ErrorResponse,
    PriceResponse,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdate,
)
from app.services.portfolio import PriceCacheService, PSXApiClient, ValuationEngine
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portfolio", tags=["portfolio-transactions"])


def get_repo(db: AsyncSession = Depends(get_db)) -> PortfolioRepository:
    return PortfolioRepository(db)


def get_psx_client(stock_service: StockService = Depends(StockService)) -> PSXApiClient:
    return PSXApiClient(stock_service)


def get_price_cache_service(
    db: AsyncSession = Depends(get_db),
    psx_client: PSXApiClient = Depends(get_psx_client),
    repo: PortfolioRepository = Depends(get_repo),
) -> PriceCacheService:
    return PriceCacheService(db, psx_client, repo)


def get_valuation_engine(
    db: AsyncSession = Depends(get_db),
    price_cache_service: PriceCacheService = Depends(get_price_cache_service),
    repo: PortfolioRepository = Depends(get_repo),
) -> ValuationEngine:
    return ValuationEngine(db, price_cache_service, repo)


@router.post(
    "/transactions",
    response_model=TransactionResponse,
    status_code=201,
    summary="Create a new buy/sell transaction",
    responses={
        400: {"model": ErrorResponse, "description": "Invalid symbol or insufficient quantity"},
        404: {"model": ErrorResponse, "description": "Stock not found"},
    },
)
@limiter.limit("20/minute")
async def create_transaction(
    request: Request,
    data: TransactionCreate,
    user: User = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_repo),
    valuation: ValuationEngine = Depends(get_valuation_engine),
):
    # Validate symbol exists on PSX
    if not valuation.price_cache.psx_client.is_symbol_valid(data.symbol):
        raise BadRequestError(
            error="INVALID_SYMBOL",
            message=f"Symbol '{data.symbol}' not found on PSX.",
        )

    # Validate SELL quantity
    if data.type == "SELL":
        valid, msg = await valuation.validate_sell_quantity(user.id, data.symbol, data.quantity)
        if not valid:
            raise BadRequestError(
                error="INSUFFICIENT_QUANTITY",
                message=msg,
            )

    transaction = await repo.create_transaction(
        user_id=user.id,
        symbol=data.symbol,
        type=TransactionType(data.type),
        quantity=data.quantity,
        price=data.price,
        fees=data.fees,
        transaction_date=data.transaction_date,
    )
    return transaction


@router.get(
    "/transactions",
    response_model=TransactionListResponse,
    summary="List transactions with pagination and optional symbol filter",
)
@limiter.limit("30/minute")
async def list_transactions(
    request: Request,
    user: User = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_repo),
    symbol: str | None = Query(None, description="Filter by symbol"),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
):
    transactions, total = await repo.list_transactions(
        user_id=user.id,
        symbol=symbol,
        page=page,
        limit=limit,
    )
    return {
        "data": transactions,
        "pagination": {"page": page, "limit": limit, "total": total},
    }


@router.get(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get a single transaction by ID",
    responses={404: {"model": ErrorResponse}},
)
@limiter.limit("30/minute")
async def get_transaction(
    request: Request,
    transaction_id: str,
    user: User = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_repo),
):
    transaction = await repo.get_transaction(transaction_id, user.id)
    if not transaction:
        raise NotFoundError("Transaction not found.")
    return transaction


@router.put(
    "/transactions/{transaction_id}",
    response_model=TransactionResponse,
    summary="Update a transaction",
    responses={404: {"model": ErrorResponse}},
)
@limiter.limit("10/minute")
async def update_transaction(
    request: Request,
    transaction_id: str,
    data: TransactionUpdate,
    user: User = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_repo),
    valuation: ValuationEngine = Depends(get_valuation_engine),
):
    transaction = await repo.get_transaction(transaction_id, user.id)
    if not transaction:
        raise NotFoundError("Transaction not found.")

    # Validate SELL quantity if quantity is being updated
    if data.quantity is not None and transaction.type == TransactionType.SELL:
        valid, msg = await valuation.validate_sell_quantity(
            user.id, transaction.symbol, data.quantity
        )
        if not valid:
            raise BadRequestError(
                error="INSUFFICIENT_QUANTITY",
                message=msg,
            )

    updated = await repo.update_transaction(
        transaction,
        quantity=data.quantity,
        price=data.price,
        fees=data.fees,
        transaction_date=data.transaction_date,
    )
    return updated


@router.delete(
    "/transactions/{transaction_id}",
    status_code=200,
    summary="Delete a transaction",
    responses={404: {"model": ErrorResponse}},
)
@limiter.limit("10/minute")
async def delete_transaction(
    request: Request,
    transaction_id: str,
    user: User = Depends(get_current_user),
    repo: PortfolioRepository = Depends(get_repo),
):
    transaction = await repo.get_transaction(transaction_id, user.id)
    if not transaction:
        raise NotFoundError("Transaction not found.")
    await repo.delete_transaction(transaction)
    return {"success": True, "message": "Transaction deleted."}