import asyncio
import logging
from decimal import Decimal
from typing import Sequence

from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.stock import Stock
from app.models.watchlist import Watchlist, WatchlistItem
from app.schemas.watchlist import (
    WatchlistCreate,
    WatchlistDetailResponse,
    WatchlistItemCreate,
    WatchlistItemResponse,
    WatchlistItemUpdate,
    WatchlistSummaryResponse,
    WatchlistUpdate,
)
from app.services.stock_service import StockService

log = logging.getLogger(__name__)


class WatchlistService:
    def __init__(self, stock_service: StockService = Depends(StockService)):
        self.stock_service = stock_service

    async def get_user_watchlists(
        self, db: AsyncSession, user_id: str
    ) -> list[WatchlistSummaryResponse]:
        """Fetch all watchlists for a user with their item counts."""
        stmt = (
            select(
                Watchlist,
                func.count(WatchlistItem.id).label("item_count"),
            )
            .outerjoin(WatchlistItem, Watchlist.id == WatchlistItem.watchlist_id)
            .where(Watchlist.user_id == user_id)
            .group_by(Watchlist.id)
            .order_by(Watchlist.is_default.desc(), Watchlist.created_at.desc())
        )
        result = await db.execute(stmt)
        rows = result.all()

        return [
            WatchlistSummaryResponse(
                id=wl.id,
                user_id=wl.user_id,
                name=wl.name,
                description=wl.description,
                is_default=wl.is_default,
                item_count=count,
                created_at=wl.created_at.isoformat() if wl.created_at else "",
                updated_at=wl.updated_at.isoformat() if wl.updated_at else "",
            )
            for wl, count in rows
        ]

    async def get_watchlist(
        self, db: AsyncSession, watchlist_id: str, user_id: str
    ) -> Watchlist | None:
        """Fetch a specific watchlist ensuring it belongs to the user."""
        stmt = select(Watchlist).where(
            Watchlist.id == watchlist_id,
            Watchlist.user_id == user_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_default_watchlist(
        self, db: AsyncSession, user_id: str
    ) -> Watchlist:
        """Fetch the user's default watchlist, or create one if none exists."""
        stmt = select(Watchlist).where(
            Watchlist.user_id == user_id,
            Watchlist.is_default == True,
        )
        result = await db.execute(stmt)
        default_wl = result.scalar_one_or_none()

        if default_wl:
            return default_wl

        # Check if user has any watchlist at all
        first_wl_stmt = (
            select(Watchlist)
            .where(Watchlist.user_id == user_id)
            .order_by(Watchlist.created_at.asc())
        )
        result = await db.execute(first_wl_stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.is_default = True
            await db.commit()
            await db.refresh(existing)
            return existing

        # Create a new default watchlist
        new_wl = Watchlist(
            user_id=user_id,
            name="My Watchlist",
            description="Default stock watchlist",
            is_default=True,
        )
        db.add(new_wl)
        await db.commit()
        await db.refresh(new_wl)
        return new_wl

    async def create_watchlist(
        self, db: AsyncSession, user_id: str, data: WatchlistCreate
    ) -> Watchlist:
        """Create a new watchlist, managing default flag and initial symbols."""
        # Check if user already has watchlists
        count_stmt = select(func.count(Watchlist.id)).where(Watchlist.user_id == user_id)
        count_res = await db.execute(count_stmt)
        existing_count = count_res.scalar_one() or 0

        # If it's the user's first watchlist, make it default automatically
        should_be_default = data.is_default or (existing_count == 0)

        if should_be_default:
            # Unset default from any previous watchlists
            await db.execute(
                update(Watchlist)
                .where(Watchlist.user_id == user_id)
                .values(is_default=False)
            )

        watchlist = Watchlist(
            user_id=user_id,
            name=data.name.strip(),
            description=data.description.strip() if data.description else None,
            is_default=should_be_default,
        )
        db.add(watchlist)
        await db.flush()

        if data.symbols:
            seen_symbols = set()
            for sym in data.symbols:
                normalized = sym.strip().upper()
                if normalized and normalized not in seen_symbols:
                    seen_symbols.add(normalized)
                    item = WatchlistItem(
                        watchlist_id=watchlist.id,
                        symbol=normalized,
                    )
                    db.add(item)

        await db.commit()
        await db.refresh(watchlist)
        return watchlist

    async def update_watchlist(
        self, db: AsyncSession, watchlist: Watchlist, data: WatchlistUpdate
    ) -> Watchlist:
        """Update watchlist details."""
        if data.name is not None:
            watchlist.name = data.name.strip()
        if data.description is not None:
            watchlist.description = data.description.strip() if data.description else None
        if data.is_default is not None and data.is_default != watchlist.is_default:
            if data.is_default:
                # Clear default on other user's watchlists
                await db.execute(
                    update(Watchlist)
                    .where(Watchlist.user_id == watchlist.user_id)
                    .values(is_default=False)
                )
                watchlist.is_default = True
            else:
                watchlist.is_default = False

        await db.commit()
        await db.refresh(watchlist)
        return watchlist

    async def delete_watchlist(self, db: AsyncSession, watchlist: Watchlist) -> None:
        """Delete a watchlist."""
        was_default = watchlist.is_default
        user_id = watchlist.user_id
        await db.delete(watchlist)
        await db.commit()

        # If we deleted the default watchlist, promote another one to default if exists
        if was_default:
            remaining_stmt = (
                select(Watchlist)
                .where(Watchlist.user_id == user_id)
                .order_by(Watchlist.created_at.asc())
            )
            res = await db.execute(remaining_stmt)
            next_default = res.scalar_one_or_none()
            if next_default:
                next_default.is_default = True
                await db.commit()

    async def add_item(
        self,
        db: AsyncSession,
        watchlist: Watchlist,
        data: WatchlistItemCreate,
    ) -> WatchlistItem:
        """Add a stock symbol to a watchlist."""
        symbol = data.symbol.strip().upper()
        if not symbol:
            raise ValueError("Symbol cannot be empty")

        # Check for existing symbol in this watchlist
        existing_stmt = select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist.id,
            WatchlistItem.symbol == symbol,
        )
        res = await db.execute(existing_stmt)
        if res.scalar_one_or_none():
            raise ConflictError(f"Symbol '{symbol}' is already in this watchlist")

        item = WatchlistItem(
            watchlist_id=watchlist.id,
            symbol=symbol,
            target_price=Decimal(str(data.target_price)) if data.target_price is not None else None,
            notes=data.notes.strip() if data.notes else None,
        )
        db.add(item)
        await db.commit()
        await db.refresh(item)
        return item

    async def get_item(
        self, db: AsyncSession, watchlist_id: str, symbol_or_id: str
    ) -> WatchlistItem | None:
        """Find an item in a watchlist by item ID or stock symbol."""
        stmt = select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist_id,
            (WatchlistItem.id == symbol_or_id) | (WatchlistItem.symbol == symbol_or_id.strip().upper()),
        )
        res = await db.execute(stmt)
        return res.scalar_one_or_none()

    async def update_item(
        self,
        db: AsyncSession,
        item: WatchlistItem,
        data: WatchlistItemUpdate,
    ) -> WatchlistItem:
        """Update an item's target price or notes."""
        if data.target_price is not None:
            item.target_price = Decimal(str(data.target_price))
        if data.notes is not None:
            item.notes = data.notes.strip() if data.notes else None

        await db.commit()
        await db.refresh(item)
        return item

    async def delete_item(self, db: AsyncSession, item: WatchlistItem) -> None:
        """Remove an item from a watchlist."""
        await db.delete(item)
        await db.commit()

    async def check_symbol(
        self, db: AsyncSession, user_id: str, symbol: str
    ) -> tuple[bool, list[str]]:
        """Check if a symbol is present in any of the user's watchlists."""
        symbol = symbol.strip().upper()
        stmt = (
            select(WatchlistItem.watchlist_id)
            .join(Watchlist, Watchlist.id == WatchlistItem.watchlist_id)
            .where(
                Watchlist.user_id == user_id,
                WatchlistItem.symbol == symbol,
            )
        )
        res = await db.execute(stmt)
        watchlist_ids = [row[0] for row in res.all()]
        return bool(watchlist_ids), watchlist_ids

    async def enrich_items(
        self, db: AsyncSession, items: Sequence[WatchlistItem]
    ) -> list[WatchlistItemResponse]:
        """Enrich a sequence of watchlist items with live market quotes and company names."""
        if not items:
            return []

        symbols = [item.symbol for item in items]

        # 1. Fetch DB stock names and sectors
        stock_stmt = select(Stock).where(Stock.symbol.in_(symbols))
        stock_res = await db.execute(stock_stmt)
        stocks_by_symbol = {s.symbol: s for s in stock_res.scalars().all()}

        # 2. Fetch live quotes in thread pool
        quotes_map = {}
        try:
            quotes = await asyncio.to_thread(self.stock_service.get_quote_batch, symbols)
            for q in quotes:
                if isinstance(q, dict) and "symbol" in q:
                    quotes_map[q["symbol"]] = q
        except Exception as exc:
            log.warning("Could not fetch live quotes for watchlist items: %s", exc)

        enriched = []
        for item in items:
            sym = item.symbol
            quote = quotes_map.get(sym, {})
            db_stock = stocks_by_symbol.get(sym)

            company_name = (
                (db_stock.name if db_stock and db_stock.name else None)
                or (quote.get("name") if quote.get("name") != sym else None)
                or sym
            )
            sector = (
                (db_stock.sector if db_stock and db_stock.sector else None)
                or quote.get("sector")
            )

            current_price = quote.get("current")
            change = quote.get("change")
            change_pct = quote.get("change_pct")
            high = quote.get("high")
            low = quote.get("low")
            volume = quote.get("volume")

            enriched.append(
                WatchlistItemResponse(
                    id=item.id,
                    watchlist_id=item.watchlist_id,
                    symbol=item.symbol,
                    name=company_name,
                    sector=sector,
                    target_price=float(item.target_price) if item.target_price is not None else None,
                    notes=item.notes,
                    current_price=float(current_price) if current_price is not None else None,
                    change=float(change) if change is not None else None,
                    change_pct=float(change_pct) if change_pct is not None else None,
                    high=float(high) if high is not None else None,
                    low=float(low) if low is not None else None,
                    volume=int(volume) if volume is not None else None,
                    is_stale=False,
                    created_at=item.created_at.isoformat() if item.created_at else "",
                    updated_at=item.updated_at.isoformat() if item.updated_at else "",
                )
            )

        return enriched

    async def build_detail_response(
        self, db: AsyncSession, watchlist: Watchlist
    ) -> WatchlistDetailResponse:
        """Construct full watchlist detail response with enriched items."""
        items_stmt = (
            select(WatchlistItem)
            .where(WatchlistItem.watchlist_id == watchlist.id)
            .order_by(WatchlistItem.created_at.desc())
        )
        items_res = await db.execute(items_stmt)
        items = items_res.scalars().all()

        enriched_items = await self.enrich_items(db, items)
        return WatchlistDetailResponse(
            id=watchlist.id,
            user_id=watchlist.user_id,
            name=watchlist.name,
            description=watchlist.description,
            is_default=watchlist.is_default,
            items=enriched_items,
            created_at=watchlist.created_at.isoformat() if watchlist.created_at else "",
            updated_at=watchlist.updated_at.isoformat() if watchlist.updated_at else "",
        )
