from datetime import datetime
import asyncio
import logging
from decimal import Decimal
from typing import Sequence

from fastapi import Depends
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.models.prediction import Prediction
from app.models.sentiment import SentimentAggregate
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

    async def get_watchlist_by_name(
        self, db: AsyncSession, name: str, user_id: str
    ) -> Watchlist | None:
        """Fetch a specific watchlist by name ensuring it belongs to the user."""
        stmt = select(Watchlist).where(
            Watchlist.name == name,
            Watchlist.user_id == user_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    async def get_or_create_default_watchlist(
        self, db: AsyncSession, user_id: str
    ) -> Watchlist:
        """Fetch the user's default watchlist, or create one if none exists.
        Uses row-level locking to prevent race conditions creating multiple defaults.
        """
        # Lock any existing default watchlist for this user
        stmt = select(Watchlist).where(
            Watchlist.user_id == user_id,
            Watchlist.is_default == True,
        ).with_for_update()
        result = await db.execute(stmt)
        default_wl = result.scalar_one_or_none()

        if default_wl:
            return default_wl

        # Lock all user's watchlists to prevent concurrent default creation
        lock_stmt = select(Watchlist).where(
            Watchlist.user_id == user_id
        ).with_for_update()
        await db.execute(lock_stmt)

        # Re-check after lock (another transaction may have created default)
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
        """Create a new watchlist, managing default flag and initial symbols.
        Uses row-level locking to prevent race conditions on default watchlist.
        """
        # Lock all user's watchlists to safely manage default flag
        lock_stmt = select(Watchlist).where(
            Watchlist.user_id == user_id
        ).with_for_update()
        await db.execute(lock_stmt)

        # Check if user already has watchlists
        count_stmt = select(func.count(Watchlist.id)).where(Watchlist.user_id == user_id)
        count_res = await db.execute(count_stmt)
        existing_count = count_res.scalar_one() or 0

        # If it's the user's first watchlist, make it default automatically
        should_be_default = data.is_default or (existing_count == 0)

        if should_be_default:
            # Unset default from any previous watchlists (atomic within lock)
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

        added_count = 0
        if data.symbols:
            seen_symbols = set()
            symbols_to_quote = [s.strip().upper() for s in data.symbols if s.strip()]
            quotes_map = {}
            if symbols_to_quote:
                try:
                    raw_quotes = await asyncio.to_thread(self.stock_service.get_quote_batch, symbols_to_quote)
                    for q in raw_quotes:
                        if isinstance(q, dict) and q.get("symbol"):
                            quotes_map[q["symbol"].upper()] = q
                except Exception as exc:
                    log.warning("Could not fetch quotes for new watchlist symbols: %s", exc)

            for sym in data.symbols:
                normalized = sym.strip().upper()
                if normalized and normalized not in seen_symbols:
                    seen_symbols.add(normalized)
                    
                    # Validate symbol exists in Stock table and is active
                    stock_stmt = select(Stock).where(
                        Stock.symbol == normalized,
                        Stock.is_active == True
                    )
                    stock_res = await db.execute(stock_stmt)
                    if not stock_res.scalar_one_or_none():
                        log.warning("Skipping invalid/inactive symbol %s during watchlist creation", normalized)
                        continue
                    
                    q = quotes_map.get(normalized, {})
                    added_p = q.get("current") or q.get("ldcp")
                    item = WatchlistItem(
                        watchlist_id=watchlist.id,
                        symbol=normalized,
                        added_price=Decimal(str(added_p)) if added_p is not None and added_p > 0 else None,
                    )
                    db.add(item)
                    added_count += 1

        await db.commit()
        await db.refresh(watchlist)
        # Store actual added count for response
        watchlist._added_count = added_count
        return watchlist

    async def update_watchlist(
        self, db: AsyncSession, watchlist: Watchlist, data: WatchlistUpdate
    ) -> Watchlist:
        """Update watchlist details. Uses locking for default flag changes."""
        if data.name is not None:
            watchlist.name = data.name.strip()
        if data.description is not None:
            watchlist.description = data.description.strip() if data.description else None
        
        # Handle default flag changes with locking to prevent race conditions
        if data.is_default is not None and data.is_default != watchlist.is_default:
            if data.is_default:
                # Lock all user's watchlists to atomically clear other defaults and set this one
                lock_stmt = select(Watchlist).where(
                    Watchlist.user_id == watchlist.user_id
                ).with_for_update()
                await db.execute(lock_stmt)
                
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
        """Add a stock symbol to a watchlist and capture the baseline added_price."""
        symbol = data.symbol.strip().upper()
        if not symbol:
            raise ValueError("Symbol cannot be empty")

        # Validate symbol exists in Stock table and is active
        stock_stmt = select(Stock).where(
            Stock.symbol == symbol,
            Stock.is_active == True
        )
        stock_res = await db.execute(stock_stmt)
        if not stock_res.scalar_one_or_none():
            raise ValueError(f"Symbol '{symbol}' not found or inactive")

        # Check for existing symbol in this watchlist
        existing_stmt = select(WatchlistItem).where(
            WatchlistItem.watchlist_id == watchlist.id,
            WatchlistItem.symbol == symbol,
        )
        res = await db.execute(existing_stmt)
        if res.scalar_one_or_none():
            raise ConflictError(f"Symbol '{symbol}' is already in this watchlist")

        # Capture baseline added_price from live quote
        added_price = None
        try:
            quote = await asyncio.to_thread(self.stock_service.get_quote, symbol)
            if quote:
                price_val = quote.get("current") or quote.get("ldcp")
                if price_val and float(price_val) > 0:
                    added_price = Decimal(str(price_val))
        except Exception as exc:
            log.warning("Could not fetch live quote for added_price on %s: %s", symbol, exc)

        item = WatchlistItem(
            watchlist_id=watchlist.id,
            symbol=symbol,
            added_price=added_price,
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

    async def toggle_symbol_in_default_watchlist(
        self, db: AsyncSession, user_id: str, symbol: str
    ) -> tuple[bool, str, WatchlistItem | None]:
        """Toggle symbol in user's default watchlist (1-tap add/remove).
        Uses row-level locking to prevent race conditions.
        Returns (is_in_watchlist, watchlist_id, item) where item is the added/removed item.
        """
        symbol = symbol.strip().upper()
        
        # Lock the default watchlist row to prevent concurrent toggles
        default_wl = await self.get_or_create_default_watchlist(db, user_id)
        
        # Lock the watchlist row for update
        lock_stmt = select(Watchlist).where(Watchlist.id == default_wl.id).with_for_update()
        await db.execute(lock_stmt)
        
        # Re-fetch item under lock
        existing_item = await self.get_item(db, default_wl.id, symbol)

        if existing_item:
            # Enrich before deleting for response
            enriched_list = await self.enrich_items(db, [existing_item])
            item_response = enriched_list[0] if enriched_list else None
            await self.delete_item(db, existing_item)
            return False, default_wl.id, item_response
        else:
            item_data = WatchlistItemCreate(symbol=symbol)
            new_item = await self.add_item(db, default_wl, item_data)
            enriched_list = await self.enrich_items(db, [new_item])
            item_response = enriched_list[0] if enriched_list else None
            return True, default_wl.id, item_response

    def _to_isoformat(self, dt) -> str:
        """Convert datetime or ISO string to ISO format string."""
        if dt is None:
            return ""
        if isinstance(dt, str):
            return dt
        return dt.isoformat()

    async def enrich_items(
        self, db: AsyncSession, items: Sequence[WatchlistItem]
    ) -> list[WatchlistItemResponse]:
        """Enrich a sequence of watchlist items with live market quotes, company names, AI forecasts, and sentiment."""
        if not items:
            return []

        symbols = [item.symbol for item in items]

        # 1. Fetch DB stock names and sectors (only active)
        stock_stmt = select(Stock).where(
            Stock.symbol.in_(symbols),
            Stock.is_active == True
        )
        stock_res = await db.execute(stock_stmt)
        stocks_by_symbol = {s.symbol: s for s in stock_res.scalars().all()}

        # Filter out items with inactive/delisted stocks
        active_symbols = set(stocks_by_symbol.keys())
        items = [item for item in items if item.symbol.upper() in active_symbols]
        if not items:
            return []
        
        symbols = [item.symbol for item in items]

        # 2. Fetch live quotes in thread pool from Redis
        quotes_map = {}
        try:
            quotes = await asyncio.to_thread(self.stock_service.get_quote_batch, symbols)
            for q in quotes:
                if isinstance(q, dict) and "symbol" in q:
                    quotes_map[q["symbol"].upper()] = q
        except Exception as exc:
            log.warning("Could not fetch live quotes for watchlist items: %s", exc)

        # 3. Batch fetch latest AI forecast predictions
        predictions_map = {}
        try:
            pred_stmt = (
                select(Prediction)
                .where(Prediction.symbol.in_(symbols), Prediction.horizon == "1D")
                .order_by(Prediction.as_of_date.desc(), Prediction.predicted_at.desc())
            )
            pred_res = await db.execute(pred_stmt)
            for p in pred_res.scalars().all():
                sym_upper = p.symbol.upper()
                if sym_upper not in predictions_map:
                    predictions_map[sym_upper] = p
        except Exception as exc:
            log.warning("Could not fetch predictions for watchlist symbols: %s", exc)

        # 4. Batch fetch latest sentiment aggregates
        sentiment_map = {}
        try:
            sent_stmt = (
                select(SentimentAggregate)
                .where(SentimentAggregate.symbol.in_(symbols), SentimentAggregate.period == "1D")
                .order_by(SentimentAggregate.period_end.desc())
            )
            sent_res = await db.execute(sent_stmt)
            for s in sent_res.scalars().all():
                sym_upper = s.symbol.upper()
                if sym_upper not in sentiment_map:
                    sentiment_map[sym_upper] = s
        except Exception as exc:
            log.warning("Could not fetch sentiment for watchlist symbols: %s", exc)

        enriched = []
        for item in items:
            sym = item.symbol.upper()
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
            curr_p_float = float(current_price) if current_price is not None else None
            change = quote.get("change")
            change_pct = quote.get("change_pct")
            high = quote.get("high")
            low = quote.get("low")
            volume = quote.get("volume")

            # Gain / loss since added
            added_p_float = float(item.added_price) if item.added_price is not None else None
            change_since_added = None
            change_since_added_pct = None
            if curr_p_float is not None and added_p_float is not None and added_p_float > 0:
                change_since_added = round(curr_p_float - added_p_float, 2)
                change_since_added_pct = round((change_since_added / added_p_float) * 100, 2)

            # AI Forecast & signal rating
            pred_row = predictions_map.get(sym)
            forecast_dir = pred_row.predicted_direction if pred_row else None
            signal_rating = None
            if pred_row:
                direction = pred_row.predicted_direction
                bull_pct = pred_row.bullish_pct or 0.0
                bear_pct = pred_row.bearish_pct or 0.0
                top_prob = pred_row.top_class_probability or 0.0
                if direction == "bullish":
                    signal_rating = "Strong Buy" if bull_pct >= 58.0 or top_prob >= 58.0 else "Buy"
                elif direction == "bearish":
                    signal_rating = "Strong Sell" if bear_pct >= 58.0 or top_prob >= 58.0 else "Sell"
                else:
                    signal_rating = "Neutral / Hold"

            # Sentiment
            sent_row = sentiment_map.get(sym)
            sent_label = sent_row.label.capitalize() if sent_row and sent_row.label else None
            sent_score = float(sent_row.overall_score) if sent_row and sent_row.overall_score is not None else None

            enriched.append(
                WatchlistItemResponse(
                    id=item.id,
                    watchlist_id=item.watchlist_id,
                    symbol=sym,
                    name=company_name,
                    sector=sector,
                    added_price=added_p_float,
                    change_since_added=change_since_added,
                    change_since_added_pct=change_since_added_pct,
                    target_price=float(item.target_price) if item.target_price is not None else None,
                    notes=item.notes,
                    current_price=curr_p_float,
                    change=float(change) if change is not None else None,
                    change_pct=float(change_pct) if change_pct is not None else None,
                    high=float(high) if high is not None else None,
                    low=float(low) if low is not None else None,
                    volume=int(volume) if volume is not None else None,
                    forecast_direction=forecast_dir,
                    signal_rating=signal_rating,
                    sentiment_label=sent_label,
                    sentiment_score=sent_score,
                    is_stale=False,
                    created_at=self._to_isoformat(item.created_at),
                    updated_at=self._to_isoformat(item.updated_at),
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
