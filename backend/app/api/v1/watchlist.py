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
    WatchlistToggleResponse,
    WatchlistUpdate,
)
from app.services.watchlist_service import WatchlistService

log = logging.getLogger(__name__)

router = APIRouter()

_SYMBOL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,9}$")


def _validate_symbol(symbol: str) -> str:
    """Normalize and validate a stock symbol."""
    symbol = symbol.strip().upper()
    if not _SYMBOL_PATTERN.match(symbol):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid stock symbol '{symbol}'. Symbols must be 2-10 alphanumeric characters starting with a letter.",
        )
    return symbol


# ── Watchlist Collection Endpoints ──────────────────────────────────────────


@router.get(
    "/watchlists",
    response_model=list[WatchlistSummaryResponse],
    summary="List all user watchlists",
    description="Retrieve all watchlists owned by the authenticated user with aggregated item counts.",
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
    description="Create a new named stock watchlist for the authenticated user, optionally populated with an initial symbol array.",
)
@limiter.limit("30/minute")
async def create_watchlist(
    request: Request,
    data: WatchlistCreate,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Create a new stock watchlist for the authenticated user."""
    try:
        wl = await service.create_watchlist(db, user.id, data)
        # Use actual count from service (stored in _added_count) or query DB
        item_count = getattr(wl, '_added_count', 0)
        return WatchlistSummaryResponse(
            id=wl.id,
            user_id=wl.user_id,
            name=wl.name,
            description=wl.description,
            is_default=wl.is_default,
            item_count=item_count,
            created_at=wl.created_at.isoformat() if wl.created_at else "",
            updated_at=wl.updated_at.isoformat() if wl.updated_at else "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        log.exception("Error creating watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to create watchlist: {exc}")


# ── Special Watchlist Endpoints ───────────────────────────────────────────────


@router.get(
    "/watchlists/default",
    response_model=WatchlistDetailResponse,
    summary="Get user's default watchlist with live data & AI badges",
    description="Retrieve the user's primary default watchlist with live Redis market quotes, price-since-added performance, AI forecasts, and news sentiment.",
)
@limiter.limit("60/minute")
async def get_default_watchlist(
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Retrieve the user's default watchlist with live enriched stock quotes."""
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
    description="Check whether a given stock symbol exists in any user watchlist (used for 1-tap active star/heart bookmark UI icons).",
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


@router.post(
    "/watchlists/toggle/{symbol}",
    response_model=WatchlistToggleResponse,
    summary="1-Tap Toggle stock in default watchlist (Add/Remove)",
    description="Seamless 1-tap bookmark action: adds the stock if absent (capturing live baseline price) or removes it if already present.",
)
@limiter.limit("60/minute")
async def toggle_symbol_in_default_watchlist(
    request: Request,
    symbol: str = Path(..., description="Stock symbol to toggle (e.g. SYS, OGDC)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Toggle a stock in the user's default watchlist (1-tap add or remove)."""
    validated_symbol = _validate_symbol(symbol)
    try:
        is_in, wl_id, item = await service.toggle_symbol_in_default_watchlist(db, user.id, validated_symbol)
        item_response = None
        if item:
            enriched_list = await service.enrich_items(db, [item])
            item_response = enriched_list[0] if enriched_list else None

        action_str = "added" if is_in else "removed"
        message_str = f"{validated_symbol} added to your watchlist" if is_in else f"{validated_symbol} removed from your watchlist"
        return WatchlistToggleResponse(
            symbol=validated_symbol,
            is_in_watchlist=is_in,
            action=action_str,
            watchlist_id=wl_id,
            item=item_response,
            message=message_str,
        )
    except Exception as exc:
        log.exception("Error toggling watchlist symbol %s: %s", validated_symbol, exc)
        raise ServiceUnavailableError(f"Failed to toggle watchlist symbol: {exc}")


# ── Individual Watchlist CRUD ───────────────────────────────────────────────


@router.get(
    "/watchlists/{watchlist_id}",
    response_model=WatchlistDetailResponse,
    summary="Get watchlist details with live stock quotes (by ID)",
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


@router.get(
    "/watchlists/name/{name}",
    response_model=WatchlistDetailResponse,
    summary="Get watchlist details with live stock quotes (by name)",
    description="Retrieve a watchlist by its name (user-visible identifier) instead of internal ID.",
)
@limiter.limit("60/minute")
async def get_watchlist_by_name(
    request: Request,
    name: str = Path(..., description="Watchlist name (e.g. 'Tech Focus', 'Dividend Gems')"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Get watchlist by name with all tracked stocks enriched with real-time PSX market prices."""
    wl = await service.get_watchlist_by_name(db, name.strip(), user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with name '{name}' not found")

    try:
        return await service.build_detail_response(db, wl)
    except Exception as exc:
        log.exception("Error building watchlist detail response: %s", exc)
        raise ServiceUnavailableError(f"Failed to fetch watchlist details: {exc}")


@router.patch(
    "/watchlists/{watchlist_id}",
    response_model=WatchlistSummaryResponse,
    summary="Update watchlist metadata (by ID)",
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


@router.patch(
    "/watchlists/name/{name}",
    response_model=WatchlistSummaryResponse,
    summary="Update watchlist metadata (by name)",
    description="Update a watchlist using its name instead of internal ID.",
)
@limiter.limit("30/minute")
async def update_watchlist_by_name(
    request: Request,
    data: WatchlistUpdate,
    name: str = Path(..., description="Watchlist name (e.g. 'Tech Focus', 'Dividend Gems')"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Update watchlist name, description, or default status using its name."""
    wl = await service.get_watchlist_by_name(db, name.strip(), user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with name '{name}' not found")

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
    summary="Delete a watchlist (by ID)",
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


@router.delete(
    "/watchlists/name/{name}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a watchlist (by name)",
    description="Delete a watchlist using its name instead of internal ID.",
)
@limiter.limit("30/minute")
async def delete_watchlist_by_name(
    request: Request,
    name: str = Path(..., description="Watchlist name (e.g. 'Tech Focus', 'Dividend Gems')"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Delete a watchlist and all symbols contained within it using its name."""
    wl = await service.get_watchlist_by_name(db, name.strip(), user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with name '{name}' not found")

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
    summary="Add a stock symbol to watchlist (by ID)",
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

    _validate_symbol(data.symbol)

    try:
        item = await service.add_item(db, wl, data)
        enriched_list = await service.enrich_items(db, [item])
        return enriched_list[0]
    except ConflictError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        log.exception("Error adding stock to watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to add symbol to watchlist: {exc}")


@router.post(
    "/watchlists/name/{name}/items",
    response_model=WatchlistItemResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Add a stock symbol to watchlist (by name)",
    description="Add a stock symbol to a watchlist using its name instead of internal ID.",
)
@limiter.limit("60/minute")
async def add_watchlist_item_by_name(
    request: Request,
    data: WatchlistItemCreate,
    name: str = Path(..., description="Watchlist name (e.g. 'Tech Focus', 'Dividend Gems')"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Add a stock symbol to an existing watchlist using its name."""
    wl = await service.get_watchlist_by_name(db, name.strip(), user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with name '{name}' not found")

    _validate_symbol(data.symbol)

    try:
        item = await service.add_item(db, wl, data)
        enriched_list = await service.enrich_items(db, [item])
        return enriched_list[0]
    except ConflictError:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    except Exception as exc:
        log.exception("Error adding stock to watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to add symbol to watchlist: {exc}")


@router.patch(
    "/watchlists/{watchlist_id}/items/{symbol}",
    response_model=WatchlistItemResponse,
    summary="Update watchlist item target price or notes (by ID)",
)
@limiter.limit("60/minute")
async def update_watchlist_item(
    request: Request,
    data: WatchlistItemUpdate,
    watchlist_id: str = Path(..., description="Unique Watchlist ID"),
    symbol: str = Path(..., description="Stock symbol (e.g. SYS, OGDC)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Update target price alert threshold or personal notes for a tracked symbol in a watchlist."""
    wl = await service.get_watchlist(db, watchlist_id, user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with ID '{watchlist_id}' not found")

    validated_symbol = _validate_symbol(symbol)
    item = await service.get_item(db, watchlist_id, validated_symbol)
    if not item:
        raise NotFoundError(f"Stock '{validated_symbol}' not found in watchlist")

    try:
        updated_item = await service.update_item(db, item, data)
        enriched_list = await service.enrich_items(db, [updated_item])
        return enriched_list[0]
    except Exception as exc:
        log.exception("Error updating watchlist item: %s", exc)
        raise ServiceUnavailableError(f"Failed to update watchlist item: {exc}")


@router.patch(
    "/watchlists/name/{name}/items/{symbol}",
    response_model=WatchlistItemResponse,
    summary="Update watchlist item target price or notes (by name)",
    description="Update an item in a watchlist using its name instead of internal ID.",
)
@limiter.limit("60/minute")
async def update_watchlist_item_by_name(
    request: Request,
    data: WatchlistItemUpdate,
    name: str = Path(..., description="Watchlist name (e.g. 'Tech Focus', 'Dividend Gems')"),
    symbol: str = Path(..., description="Stock symbol (e.g. SYS, OGDC)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Update target price alert threshold or personal notes for a tracked symbol in a watchlist."""
    wl = await service.get_watchlist_by_name(db, name.strip(), user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with name '{name}' not found")

    validated_symbol = _validate_symbol(symbol)
    item = await service.get_item(db, wl.id, validated_symbol)
    if not item:
        raise NotFoundError(f"Stock '{validated_symbol}' not found in watchlist")

    try:
        updated_item = await service.update_item(db, item, data)
        enriched_list = await service.enrich_items(db, [updated_item])
        return enriched_list[0]
    except Exception as exc:
        log.exception("Error updating watchlist item: %s", exc)
        raise ServiceUnavailableError(f"Failed to update watchlist item: {exc}")


@router.delete(
    "/watchlists/{watchlist_id}/items/{symbol}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a stock symbol from watchlist (by ID)",
)
@limiter.limit("60/minute")
async def delete_watchlist_item(
    request: Request,
    watchlist_id: str = Path(..., description="Unique Watchlist ID"),
    symbol: str = Path(..., description="Stock symbol (e.g. SYS, OGDC)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Remove a tracked stock symbol from a watchlist."""
    wl = await service.get_watchlist(db, watchlist_id, user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with ID '{watchlist_id}' not found")

    validated_symbol = _validate_symbol(symbol)
    item = await service.get_item(db, watchlist_id, validated_symbol)
    if not item:
        raise NotFoundError(f"Stock '{validated_symbol}' not found in watchlist")

    try:
        await service.delete_item(db, item)
    except Exception as exc:
        log.exception("Error removing item from watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to remove item from watchlist: {exc}")


@router.delete(
    "/watchlists/name/{name}/items/{symbol}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Remove a stock symbol from watchlist (by name)",
    description="Remove a stock symbol from a watchlist using its name instead of internal ID.",
)
@limiter.limit("60/minute")
async def delete_watchlist_item_by_name(
    request: Request,
    name: str = Path(..., description="Watchlist name (e.g. 'Tech Focus', 'Dividend Gems')"),
    symbol: str = Path(..., description="Stock symbol (e.g. SYS, OGDC)"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    service: WatchlistService = Depends(WatchlistService),
):
    """Remove a tracked stock symbol from a watchlist using its name."""
    wl = await service.get_watchlist_by_name(db, name.strip(), user.id)
    if not wl:
        raise NotFoundError(f"Watchlist with name '{name}' not found")

    validated_symbol = _validate_symbol(symbol)
    item = await service.get_item(db, wl.id, validated_symbol)
    if not item:
        raise NotFoundError(f"Stock '{validated_symbol}' not found in watchlist")

    try:
        await service.delete_item(db, item)
    except Exception as exc:
        log.exception("Error removing item from watchlist: %s", exc)
        raise ServiceUnavailableError(f"Failed to remove item from watchlist: {exc}")
