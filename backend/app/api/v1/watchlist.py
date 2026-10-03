import logging
import re
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ConflictError, NotFoundError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.models.watchlist import WatchlistItem
from app.schemas.watchlist import (
    WatchlistCheckResponse,
    WatchlistCreate,
    WatchlistDetailResponse,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistItemUpdate,
    WatchlistSummaryResponse,
    WatchlistUpdate,
)
from app.services.watchlist_service import WatchlistService

log = logging.getLogger(__name__)

router = APIRouter()

_SYMBOL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,9}$")


def _validate_stock_reference(value: str) -> str:
    """Validate a ticker symbol or company-name lookup value."""
    value = value.strip()
    valid_name = (
        bool(value)
        and any(char.isalpha() for char in value)
        and all(
            char.isalnum() or char.isspace() or char in "&.,'()/-"
            for char in value
        )
    )
    if (
        not value
        or len(value) > 100
        or any(ord(char) < 32 for char in value)
        or not (_SYMBOL_PATTERN.fullmatch(value) or valid_name)
    ):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Enter a stock symbol or company name up to 100 characters.",
        )
    return value


def _validate_symbol(symbol: str) -> str:
    """Normalize and validate a ticker symbol used in symbol-only routes."""
    value = symbol.strip().upper()
    if not _SYMBOL_PATTERN.fullmatch(value):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid stock symbol '{value}'. Symbols must be 2-10 alphanumeric characters starting with a letter.",
        )
    return value


# ── Watchlist Collection Endpoints ──────────────────────────────────────────


@router.get(
    "/watchlists",
    response_model=list[WatchlistSummaryResponse],
    summary="List all user watchlists",
)
@limiter.limit("60/minute")
async def get_watchlists(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Retrieve all watchlists owned by the authenticated user with item counts."""
    try:
        return await service.get_user_watchlists(db, user.id)
    except Exception as exc:
        log.exception("Error fetching watchlists for user %s: %s", user.id, exc)
        raise ServiceUnavailableError(f"Failed to fetch watchlists: {exc}")


@router.post(
    "/watchlists",
    response_model=WatchlistSummaryResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new watchlist",
)
@limiter.limit("30/minute")
async def create_watchlist(
    request: Request,
    data: WatchlistCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Create a new stock watchlist for the authenticated user.

    Optionally populate with an initial list of stock symbols.
    """
    try:
        stock_references = list(dict.fromkeys(
            _validate_stock_reference(value) for value in (data.symbols or [])
        ))
        data = data.model_copy(update={"symbols": stock_references})
        wl = await service.create_watchlist(db, user.id, data)
        item_count = await db.scalar(
            select(func.count(WatchlistItem.id)).where(
                WatchlistItem.watchlist_id == wl.id
            )
        )
        return WatchlistSummaryResponse(
            id=wl.id,
            user_id=wl.user_id,
            name=wl.name,
            description=wl.description,
            is_default=wl.is_default,
            item_count=item_count or 0,
            created_at=wl.created_at.isoformat() if wl.created_at else "",
            updated_at=wl.updated_at.isoformat() if wl.updated_at else "",
        )
    except HTTPException:
        raise
    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Error creating watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to create watchlist: {exc}")


# ── Special Watchlist Endpoints (Placed before parameterized {watchlist_id}) ─


@router.get(
    "/watchlists/default",
    response_model=WatchlistDetailResponse,
    summary="Get user's default watchlist",
)
@limiter.limit("60/minute")
async def get_default_watchlist(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Retrieve the user's default watchlist with live enriched stock quotes.

    If the user does not have a default watchlist, one is automatically provisioned.
    """
    try:
        wl = await service.get_or_create_default_watchlist(db, user.id)
        return await service.build_detail_response(db, wl)
    except Exception as exc:
        log.exception("Error getting default watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to fetch default watchlist: {exc}")


@router.get(
    "/watchlists/check/{symbol}",
    response_model=WatchlistCheckResponse,
    summary="Check if a stock symbol is in user's watchlists",
)
@limiter.limit("60/minute")
async def check_symbol_in_watchlists(
    request: Request,
    symbol: str = Path(..., description="Stock symbol to check (e.g. SYS, OGDC)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Check whether a given stock symbol exists in any of the user's watchlists."""
    validated_symbol = _validate_symbol(symbol)
    try:
        is_in, wl_ids = await service.check_symbol(db, user.id, validated_symbol)
        return WatchlistCheckResponse(
            symbol=validated_symbol,
            is_in_watchlist=is_in,
            watchlist_ids=wl_ids,
        )
    except Exception as exc:
        log.exception("Error checking watchlist symbol %s: %s", validated_symbol, exc)
        raise ServiceUnavailableError(f"Failed to check watchlist symbol: {exc}")


# ── Individual Watchlist CRUD ───────────────────────────────────────────────


@router.get(
    "/watchlists/{watchlist_id}",
    response_model=WatchlistDetailResponse,
    summary="Get watchlist details with live stock quotes",
)
@limiter.limit("60/minute")
async def get_watchlist_detail(
    request: Request,
    watchlist_id: str = Path(..., description="Unique Watchlist ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Get watchlist by ID with all tracked stocks enriched with real-time PSX market prices."""
    wl = await service.get_watchlist(db, watchlist_id, user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with ID '{watchlist_id}' not found")

    try:
        return await service.build_detail_response(db, wl)
    except Exception as exc:
        log.exception("Error building watchlist detail response: %s", exc)
        raise ServiceUnavailableError(f"Failed to fetch watchlist details: {exc}")


@router.patch(
    "/watchlists/{watchlist_id}",
    response_model=WatchlistSummaryResponse,
    summary="Update watchlist metadata",
)
@limiter.limit("30/minute")
async def update_watchlist(
    request: Request,
    data: WatchlistUpdate,
    watchlist_id: str = Path(..., description="Unique Watchlist ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Update watchlist name, description, or default status."""
    wl = await service.get_watchlist(db, watchlist_id, user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with ID '{watchlist_id}' not found")

    try:
        updated = await service.update_watchlist(db, wl, data)
        count_stmt = select(func.count(WatchlistItem.id)).where(WatchlistItem.watchlist_id == updated.id)
        count_res = await db.execute(count_stmt)
        item_count = count_res.scalar_one() or 0

        return WatchlistSummaryResponse(
            id=updated.id,
            user_id=updated.user_id,
            name=updated.name,
            description=updated.description,
            is_default=updated.is_default,
            item_count=item_count,
            created_at=updated.created_at.isoformat() if updated.created_at else "",
            updated_at=updated.updated_at.isoformat() if updated.updated_at else "",
        )
    except Exception as exc:
        log.exception("Error updating watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to update watchlist: {exc}")


@router.delete(
    "/watchlists/{watchlist_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a watchlist",
)
@limiter.limit("30/minute")
async def delete_watchlist(
    request: Request,
    watchlist_id: str = Path(..., description="Unique Watchlist ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Delete a watchlist and all symbols contained within it."""
    wl = await service.get_watchlist(db, watchlist_id, user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with ID '{watchlist_id}' not found")

    try:
        await service.delete_watchlist(db, wl)
    except Exception as exc:
        log.exception("Error deleting watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to delete watchlist: {exc}")


# ── Watchlist Item CRUD ─────────────────────────────────────────────────────


@router.post(
    "/watchlists/{watchlist_id}/items",
    response_model=WatchlistItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a stock symbol to watchlist",
)
@limiter.limit("60/minute")
async def add_watchlist_item(
    request: Request,
    data: WatchlistItemCreate,
    watchlist_id: str = Path(..., description="Unique Watchlist ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Add a stock symbol to an existing watchlist with optional target price and notes."""
    wl = await service.get_watchlist(db, watchlist_id, user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with ID '{watchlist_id}' not found")

    data = data.model_copy(update={"symbol": _validate_stock_reference(data.symbol)})

    try:
        item = await service.add_item(db, wl, data)
        enriched_list = await service.enrich_items(db, [item])
        return enriched_list[0]
    except ConflictError:
        raise
    except NotFoundError:
        raise
    except Exception as exc:
        log.exception("Error adding stock to watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to add symbol to watchlist: {exc}")


@router.patch(
    "/watchlists/{watchlist_id}/items/{symbol_or_item_id}",
    response_model=WatchlistItemResponse,
    summary="Update watchlist item target price or notes",
)
@limiter.limit("60/minute")
async def update_watchlist_item(
    request: Request,
    data: WatchlistItemUpdate,
    watchlist_id: str = Path(..., description="Unique Watchlist ID"),
    symbol_or_item_id: str = Path(..., description="Stock symbol (e.g. SYS) or unique Item ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Update target price alert threshold or personal notes for a tracked symbol in a watchlist."""
    wl = await service.get_watchlist(db, watchlist_id, user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with ID '{watchlist_id}' not found")

    item = await service.get_item(db, watchlist_id, symbol_or_item_id)
    if not item:
        raise NotFoundError(f"Stock '{symbol_or_item_id}' not found in watchlist")

    try:
        updated_item = await service.update_item(db, item, data)
        enriched_list = await service.enrich_items(db, [updated_item])
        return enriched_list[0]
    except Exception as exc:
        log.exception("Error updating watchlist item: %s", exc)
        raise ServiceUnavailableError(f"Failed to update watchlist item: {exc}")


@router.delete(
    "/watchlists/{watchlist_id}/items/{symbol_or_item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a stock symbol from watchlist",
)
@limiter.limit("60/minute")
async def delete_watchlist_item(
    request: Request,
    watchlist_id: str = Path(..., description="Unique Watchlist ID"),
    symbol_or_item_id: str = Path(..., description="Stock symbol (e.g. SYS) or unique Item ID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Remove a tracked stock symbol from a watchlist."""
    wl = await service.get_watchlist(db, watchlist_id, user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with ID '{watchlist_id}' not found")

    item = await service.get_item(db, watchlist_id, symbol_or_item_id)
    if not item:
        raise NotFoundError(f"Stock '{symbol_or_item_id}' not found in watchlist")

    try:
        await service.delete_item(db, item)
    except Exception as exc:
        log.exception("Error removing item from watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to remove item from watchlist: {exc}")
