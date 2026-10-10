import asyncio
import json
import logging
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import and_, func, select

from app.core.redis import (
    cache_get,
    cache_set,
    cache_invalidate,
    cache_invalidate_pattern,
    cache_get_many,
    get_redis_client,
)
from app.core.exceptions import (
    BadRequestError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.models.portfolio import PortfolioSnapshot, PortfolioTransaction, TransactionType
from app.models.stock import Stock
from app.models.stock import StockPrice
from app.repository.portfolio_repository import PortfolioRepository
from app.services.market_service import MarketService
from app.services.portfolio_calculation import (
    InsufficientHoldingError,
    InvalidTransactionHistoryError,
    PortfolioError,
    SymbolNotFoundError,
    calculate_allocation,
    calculate_holding_from_position,
    calculate_performance_time_series,
    calculate_portfolio_summary,
    calculate_position,
    validate_transaction_sequence,
)
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

# Redis cache keys
MARKET_QUOTES_KEY = "market:quotes"
MARKET_QUOTES_FALLBACK_KEY = "market:quotes:last_known"

# Portfolio cache TTL (5 minutes)
PORTFOLIO_CACHE_TTL = 300
PORTFOLIO_SNAPSHOT_CACHE_TTL = 26 * 60 * 60
PORTFOLIO_PERFORMANCE_PERIODS = ("1D", "1W", "1M", "3M", "6M", "1Y", "ALL")


class PortfolioService:
    def __init__(
        self,
        db: AsyncSession,
        repo: PortfolioRepository | None = None,
        stock_service: StockService | None = None,
        market_service: MarketService | None = None,
    ):
        self.db = db
        self.repo = repo or PortfolioRepository(db)
        self.stock_service = stock_service or StockService()
        self.market_service = market_service or MarketService()

    async def _invalidate_portfolio_cache(self, user_id: str) -> None:
        """Invalidate all cached portfolio data for a user in parallel."""
        try:
            tasks = [
                cache_invalidate(f"portfolio:summary:{user_id}"),
                cache_invalidate(f"portfolio:pnl:{user_id}"),
                cache_invalidate(f"portfolio:allocation:{user_id}"),
                cache_invalidate_pattern(f"portfolio:holding_detail:{user_id}:*"),
                cache_invalidate_pattern(f"portfolio:performance:{user_id}:*"),
                cache_invalidate_pattern(f"portfolio:txns:{user_id}:*"),
            ]
            await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as exc:
            logger.warning("Error invalidating portfolio cache for user %s: %s", user_id, exc)

    # ── Transaction Operations ────────────────────────────────────────────────

    async def create_transaction(
        self,
        user_id: str,
        symbol: str,
        transaction_type: TransactionType,
        quantity: Decimal,
        price: Decimal,
        fee: Decimal,
        transaction_date: date,
    ) -> PortfolioTransaction:
        """Create a new portfolio transaction with validation."""
        symbol = symbol.upper()

        # Validate symbol exists
        stock = await self._get_stock(symbol)
        if not stock:
            raise SymbolNotFoundError(f"Symbol '{symbol}' not found in stock universe")

        # Get existing transactions for this symbol
        existing_txns = await self.repo.get_user_transactions_for_symbol(user_id, symbol)

        # Create new transaction object for validation
        new_txn = PortfolioTransaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            fee=fee,
            transaction_date=transaction_date,
        )

        # Validate the sequence
        try:
            validate_transaction_sequence(existing_txns, new_txn)
        except ValueError as e:
            raise InsufficientHoldingError(str(e))

        # Create the transaction
        txn = await self.repo.create_transaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type=transaction_type,
            quantity=quantity,
            price=price,
            fee=fee,
            transaction_date=transaction_date,
        )
        await self._invalidate_portfolio_cache(user_id)
        await self.refresh_portfolio_snapshot(user_id)
        return txn

    async def create_completed_trade(
        self,
        user_id: str,
        symbol: str,
        quantity: Decimal,
        buy_price: Decimal,
        buy_date: date,
        buy_fee: Decimal,
        sell_price: Decimal,
        sell_date: date,
        sell_fee: Decimal,
    ) -> dict:
        """Record a completed round-trip trade (BUY + SELL) atomically with full validation."""
        symbol = symbol.upper()

        if sell_date < buy_date:
            raise InvalidTransactionHistoryError("sell_date cannot be earlier than buy_date")

        # Validate symbol exists
        stock = await self._get_stock(symbol)
        if not stock:
            raise SymbolNotFoundError(f"Symbol '{symbol}' not found in stock universe")

        # Get existing transactions for this symbol
        existing_txns = await self.repo.get_user_transactions_for_symbol(user_id, symbol)

        # Build candidate buy and sell objects for sequence validation
        new_buy = PortfolioTransaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type=TransactionType.BUY,
            quantity=quantity,
            price=buy_price,
            fee=buy_fee,
            transaction_date=buy_date,
        )
        new_sell = PortfolioTransaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type=TransactionType.SELL,
            quantity=quantity,
            price=sell_price,
            fee=sell_fee,
            transaction_date=sell_date,
        )

        # Validate that applying BUY then SELL preserves valid non-negative history
        try:
            seq_with_buy = validate_transaction_sequence(existing_txns, new_buy)
            validate_transaction_sequence(seq_with_buy, new_sell)
        except ValueError as e:
            raise InsufficientHoldingError(str(e))

        # Create both transactions atomically in DB
        buy_txn = await self.repo.create_transaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type=TransactionType.BUY,
            quantity=quantity,
            price=buy_price,
            fee=buy_fee,
            transaction_date=buy_date,
        )
        sell_txn = await self.repo.create_transaction(
            user_id=user_id,
            symbol=symbol,
            transaction_type=TransactionType.SELL,
            quantity=quantity,
            price=sell_price,
            fee=sell_fee,
            transaction_date=sell_date,
        )

        await self._invalidate_portfolio_cache(user_id)
        await self.refresh_portfolio_snapshot(user_id)

        total_invested = (quantity * buy_price) + buy_fee
        total_proceeds = (quantity * sell_price) - sell_fee
        realized_pnl = total_proceeds - total_invested
        realized_pnl_percent = float(((total_proceeds - total_invested) / total_invested) * 100) if total_invested > 0 else 0.0
        holding_period_days = (sell_date - buy_date).days

        return {
            "symbol": symbol,
            "quantity": quantity,
            "buy_price": buy_price,
            "buy_date": buy_date,
            "buy_fee": buy_fee,
            "sell_price": sell_price,
            "sell_date": sell_date,
            "sell_fee": sell_fee,
            "holding_period_days": holding_period_days,
            "total_invested": total_invested,
            "total_proceeds": total_proceeds,
            "realized_pnl": realized_pnl,
            "realized_pnl_percent": round(realized_pnl_percent, 2),
            "buy_transaction": buy_txn,
            "sell_transaction": sell_txn,
        }

    async def get_transaction(self, transaction_id: str, user_id: str) -> PortfolioTransaction:
        """Get a single transaction by ID."""
        txn = await self.repo.get_transaction(transaction_id, user_id)
        if not txn:
            raise NotFoundError("Transaction not found")
        return txn

    async def get_transactions(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        symbol: str | None = None,
        transaction_type: TransactionType | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
    ) -> tuple[list[PortfolioTransaction], int]:
        """Get paginated transaction history with optional filters."""
        return await self.repo.get_transactions(
            user_id=user_id,
            page=page,
            limit=limit,
            symbol=symbol,
            transaction_type=transaction_type,
            from_date=from_date,
            to_date=to_date,
        )

    async def update_transaction(
        self,
        transaction_id: str,
        user_id: str,
        quantity: Decimal | None = None,
        price: Decimal | None = None,
        fee: Decimal | None = None,
        transaction_date: date | None = None,
    ) -> PortfolioTransaction:
        """Update a transaction with full re-validation of the symbol's history."""
        txn = await self.get_transaction(transaction_id, user_id)
        symbol = txn.symbol

        # Build updated transaction for validation
        updated_txn = PortfolioTransaction(
            id=txn.id,
            user_id=user_id,
            symbol=symbol,
            transaction_type=txn.transaction_type,
            quantity=quantity if quantity is not None else txn.quantity,
            price=price if price is not None else txn.price,
            fee=fee if fee is not None else txn.fee,
            transaction_date=transaction_date if transaction_date is not None else txn.transaction_date,
            created_at=txn.created_at,
            updated_at=datetime.utcnow(),
        )

        # Get other transactions for this symbol
        other_txns = await self.repo.get_user_transactions_for_symbol(
            user_id, symbol, exclude_transaction_id=transaction_id
        )

        # Validate the complete sequence
        try:
            validate_transaction_sequence(other_txns, updated_txn, exclude_txn_id=transaction_id)
        except ValueError as e:
            raise InvalidTransactionHistoryError(str(e))

        # Perform the update
        updated = await self.repo.update_transaction(
            transaction_id=transaction_id,
            user_id=user_id,
            quantity=quantity,
            price=price,
            fee=fee,
            transaction_date=transaction_date,
        )
        if not updated:
            raise NotFoundError("Transaction not found after update")
        await self._invalidate_portfolio_cache(user_id)
        await self.refresh_portfolio_snapshot(user_id)
        return updated

    async def delete_transaction(self, transaction_id: str, user_id: str) -> None:
        """Delete a transaction after validating the resulting history."""
        txn = await self.get_transaction(transaction_id, user_id)
        symbol = txn.symbol

        # Get other transactions for this symbol
        other_txns = await self.repo.get_user_transactions_for_symbol(
            user_id, symbol, exclude_transaction_id=transaction_id
        )

        # Validate the sequence without this transaction
        try:
            validate_transaction_sequence(other_txns, exclude_txn_id=transaction_id)
        except ValueError as e:
            raise InvalidTransactionHistoryError(
                f"Deleting this transaction would create invalid history: {e}"
            )

        # Delete the transaction
        deleted = await self.repo.delete_transaction(transaction_id, user_id)
        if not deleted:
            raise NotFoundError("Transaction not found")
        await self._invalidate_portfolio_cache(user_id)
        await self.refresh_portfolio_snapshot(user_id)

    async def get_holdings(self, user_id: str) -> list[dict]:
        """Get list of current active holdings for a user."""
        portfolio = await self.get_portfolio(user_id)
        return portfolio.get("holdings", []) if isinstance(portfolio, dict) else []

    async def get_portfolio(self, user_id: str) -> dict:
        """Get the portfolio from Redis or its durable close-based snapshot."""
        cache_key = f"portfolio:summary:{user_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        snapshot = await self.db.get(PortfolioSnapshot, user_id)
        if snapshot is not None:
            await self._publish_snapshot_caches(snapshot.payload, user_id)
            return snapshot.payload["portfolio"]

        payload = await self.refresh_portfolio_snapshot(user_id)
        return payload["portfolio"]

    async def refresh_portfolio_snapshot(self, user_id: str) -> dict:
        """Calculate, persist, and publish a user's portfolio from daily closes."""
        all_txns = await self.repo.get_all_user_transactions(user_id)
        txns_by_symbol: dict[str, list[PortfolioTransaction]] = defaultdict(list)
        for txn in all_txns:
            txns_by_symbol[txn.symbol].append(txn)

        positions = {
            symbol: calculate_position(txns)
            for symbol, txns in txns_by_symbol.items()
        }
        active_symbols = [
            symbol for symbol, position in positions.items() if position.is_active
        ]
        current_prices, price_dates = await self._get_latest_closing_prices(active_symbols)
        summary, holdings = calculate_portfolio_summary(positions, current_prices, price_dates)

        if holdings:
            stock_info = await self.repo.get_stock_info(list(holdings.keys()))
            for symbol, holding in holdings.items():
                stock = stock_info.get(symbol)
                if stock:
                    holding["company_name"] = stock.name
                    holding["sector"] = stock.sector

        portfolio = {
            "summary": summary,
            "holdings": list(holdings.values()),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        snapshot_date = max(price_dates.values()).date() if price_dates else date.today()
        payload = json.loads(json.dumps({
            "portfolio": portfolio,
            "pnl": {
                "realized_pnl": summary["realized_pnl"],
                "unrealized_pnl": summary["unrealized_pnl"],
                "total_pnl": summary["total_pnl"],
                "total_pnl_percent": summary["total_pnl_percent"],
                "today_pnl": summary["today_pnl"],
            },
            "allocation": calculate_allocation(holdings),
            "snapshot_date": snapshot_date.isoformat(),
        }, default=str))

        snapshot = await self.db.get(PortfolioSnapshot, user_id)
        if snapshot is None:
            snapshot = PortfolioSnapshot(
                user_id=user_id,
                snapshot_date=snapshot_date,
                payload=payload,
            )
            self.db.add(snapshot)
        else:
            snapshot.snapshot_date = snapshot_date
            snapshot.payload = payload
        await self.db.flush()
        await self._publish_snapshot_caches(payload, user_id)
        return payload

    async def _publish_snapshot_caches(self, payload: dict, user_id: str) -> None:
        await asyncio.gather(
            cache_set(
                f"portfolio:summary:{user_id}",
                payload["portfolio"],
                ttl_seconds=PORTFOLIO_SNAPSHOT_CACHE_TTL,
            ),
            cache_set(
                f"portfolio:pnl:{user_id}",
                payload["pnl"],
                ttl_seconds=PORTFOLIO_SNAPSHOT_CACHE_TTL,
            ),
            cache_set(
                f"portfolio:allocation:{user_id}",
                payload["allocation"],
                ttl_seconds=PORTFOLIO_SNAPSHOT_CACHE_TTL,
            ),
        )

    async def _get_latest_closing_prices(
        self, symbols: list[str]
    ) -> tuple[dict[str, Decimal], dict[str, datetime]]:
        if not symbols:
            return {}, {}

        latest_prices = (
            select(
                StockPrice.stock_id.label("stock_id"),
                func.max(StockPrice.date).label("latest_date"),
            )
            .join(Stock, Stock.id == StockPrice.stock_id)
            .where(Stock.symbol.in_(symbols))
            .group_by(StockPrice.stock_id)
            .subquery()
        )
        result = await self.db.execute(
            select(
                Stock.symbol,
                StockPrice.date,
                StockPrice.close,
                StockPrice.adjusted_close,
            )
            .join(StockPrice, StockPrice.stock_id == Stock.id)
            .join(
                latest_prices,
                and_(
                    latest_prices.c.stock_id == StockPrice.stock_id,
                    latest_prices.c.latest_date == StockPrice.date,
                ),
            )
            .where(Stock.symbol.in_(symbols))
        )

        prices: dict[str, Decimal] = {}
        price_dates: dict[str, datetime] = {}
        for symbol, price_date, close, adjusted_close in result.all():
            value = close if close is not None else adjusted_close
            if value is not None and Decimal(str(value)) > 0:
                prices[symbol] = Decimal(str(value))
                price_dates[symbol] = datetime.combine(
                    price_date, datetime.min.time(), tzinfo=timezone.utc
                )
        return prices, price_dates

    async def get_holdings(self, user_id: str) -> list[dict]:
        """Get active holdings only."""
        portfolio = await self.get_portfolio(user_id)
        return portfolio["holdings"]

    async def get_holding_detail(self, user_id: str, symbol: str) -> dict:
        """Get detailed view of a single holding including transactions."""
        symbol = symbol.upper()
        cache_key = f"portfolio:holding_detail:{user_id}:{symbol}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        # Get all transactions for this symbol
        txns = await self.repo.get_user_transactions_for_symbol(user_id, symbol)
        if not txns:
            raise NotFoundError(f"No transactions found for {symbol}")

        # Calculate position
        position = calculate_position(txns)

        # Portfolio valuations use the latest stored daily close, not live quotes.
        prices, dates = await self._get_latest_closing_prices([symbol])
        current_price = None
        price_updated_at = None
        if symbol in prices:
            current_price = prices[symbol]
            price_updated_at = dates.get(symbol) or datetime.now(timezone.utc)

        # Get stock info
        stock_info = await self.repo.get_stock_info([symbol])
        stock = stock_info.get(symbol)

        # Get portfolio total value for weight calculation (use cached summary if available)
        cached_summary = await cache_get(f"portfolio:summary:{user_id}")
        if isinstance(cached_summary, dict) and "summary" in cached_summary:
            total_portfolio_value = Decimal(str(cached_summary["summary"].get("current_value", "0")))
        else:
            portfolio = await self.get_portfolio(user_id)
            total_portfolio_value = Decimal(str(portfolio["summary"]["current_value"]))

        # Build holding detail
        price_info = calculate_holding_from_position(
            position, current_price, price_updated_at, total_portfolio_value
        )

        # Convert transactions to response format
        txn_responses = []
        for t in txns:
            txn_responses.append({
                "id": t.id,
                "symbol": t.symbol,
                "transaction_type": t.transaction_type.value,
                "quantity": t.quantity,
                "price": t.price,
                "fee": t.fee,
                "transaction_date": t.transaction_date,
                "created_at": t.created_at,
                "updated_at": t.updated_at,
            })

        result = {
            "symbol": symbol,
            "company_name": stock.name if stock else None,
            "sector": stock.sector if stock else None,
            "quantity": position.remaining_quantity,
            "average_cost": position.average_cost,
            "current_price": current_price,
            "invested_value": position.total_cost_basis,
            "market_value": price_info["market_value"],
            "unrealized_pnl": price_info["unrealized_pnl"],
            "unrealized_pnl_percent": price_info["unrealized_pnl_percent"],
            "realized_pnl": position.realized_pnl,
            "portfolio_weight": price_info["portfolio_weight"],
            "transactions": txn_responses,
            "price_updated_at": price_updated_at,
            "price_status": price_info["price_status"],
        }
        await cache_set(cache_key, result, ttl_seconds=PORTFOLIO_CACHE_TTL)
        return result

    async def get_pnl(self, user_id: str) -> dict:
        """Get portfolio P&L breakdown."""
        cache_key = f"portfolio:pnl:{user_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        portfolio = await self.get_portfolio(user_id)
        summary = portfolio["summary"]
        
        realized = Decimal(str(summary.get("realized_pnl", "0")))
        total_pnl = Decimal(str(summary.get("total_pnl", "0")))
        unrealized = Decimal(str(summary.get("unrealized_pnl", total_pnl - realized)))

        result = {
            "realized_pnl": realized,
            "unrealized_pnl": unrealized,
            "total_pnl": total_pnl,
            "total_pnl_percent": summary.get("total_pnl_percent", 0.0),
            "today_pnl": Decimal(str(summary.get("today_pnl", "0"))),
        }
        await cache_set(cache_key, result, ttl_seconds=PORTFOLIO_CACHE_TTL)
        return result

    async def get_allocation(self, user_id: str) -> dict:
        """Get portfolio allocation by stock and sector."""
        cache_key = f"portfolio:allocation:{user_id}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        portfolio = await self.get_portfolio(user_id)
        holdings = portfolio["holdings"]
        
        result = calculate_allocation({h["symbol"]: h for h in holdings})
        await cache_set(cache_key, result, ttl_seconds=PORTFOLIO_CACHE_TTL)
        return result

    async def get_performance(
        self,
        user_id: str,
        period: Literal["1D", "1W", "1M", "3M", "6M", "1Y", "ALL"] = "1M",
    ) -> dict:
        """Get historical market value from persisted transaction and OHLC data."""
        cache_key = f"portfolio:performance:{user_id}:{period}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return cached

        period_days = {
            "1D": 1,
            "1W": 7,
            "1M": 30,
            "3M": 90,
            "6M": 180,
            "1Y": 365,
            "ALL": 3650,
        }
        
        days = period_days.get(period, 30)
        cutoff = date.today() - timedelta(days=days)
        
        txns = await self.repo.get_all_user_transactions(user_id)
        
        if not txns:
            empty_perf = {"period": period, "data": []}
            await cache_set(cache_key, empty_perf, ttl_seconds=PORTFOLIO_CACHE_TTL)
            return empty_perf
        
        symbols = sorted({transaction.symbol for transaction in txns})
        prices_result = await self.db.execute(
            select(Stock.symbol, StockPrice.date, StockPrice.adjusted_close)
            .join(Stock, StockPrice.stock_id == Stock.id)
            .where(Stock.symbol.in_(symbols), StockPrice.date >= cutoff)
            .order_by(StockPrice.date.asc())
        )
        historical_prices: dict[str, dict[date, Decimal]] = defaultdict(dict)
        for symbol, price_date, adjusted_close in prices_result.all():
            if adjusted_close is not None:
                historical_prices[symbol][price_date] = Decimal(str(adjusted_close))

        # Fallback to maintained local parquet history for symbols not yet populated in SQL database
        for sym in symbols:
            if not historical_prices.get(sym):
                try:
                    df = self.stock_service._get_ohlcv_from_file(sym, start=cutoff)
                    if df is not None and not df.empty:
                        for idx, row in df.iterrows():
                            close_val = row.get("CLOSE") or row.get("ADJUSTED_CLOSE")
                            if close_val is not None:
                                historical_prices[sym][idx.date()] = Decimal(str(close_val))
                except Exception:
                    pass
        
        data_series = calculate_performance_time_series(txns, historical_prices, period)
        result = {
            "period": period,
            "data": data_series,
        }
        await cache_set(cache_key, result, ttl_seconds=PORTFOLIO_CACHE_TTL)
        return result

    # ── Helper Methods ────────────────────────────────────────────────────────

    async def _get_stock(self, symbol: str) -> Stock | None:
        """Get stock by symbol, ensuring it exists in DB if valid PSX symbol."""
        symbol = symbol.upper()
        stock_info = await self.repo.get_stock_info([symbol])
        stock = stock_info.get(symbol)
        if stock:
            return stock

        # Check market quote and symbol universe. Unknown symbols often return a
        # synthetic zero-value placeholder quote, which must not be treated as a
        # valid listed stock.
        quote = self.stock_service.get_quote(symbol)
        is_valid = False
        name = symbol
        sector = "Other"

        placeholder_quote = (
            quote is not None
            and str(quote.get("symbol", "")).upper() == symbol
            and quote.get("current") in (None, 0, 0.0)
            and quote.get("ldcp") in (None, 0, 0.0)
            and quote.get("open") in (None, 0, 0.0)
            and quote.get("high") in (None, 0, 0.0)
            and quote.get("low") in (None, 0, 0.0)
            and not quote.get("sector")
        )

        if quote and not placeholder_quote and quote.get("symbol"):
            is_valid = True
            name = quote.get("name") or symbol
            sector = quote.get("sector") or "Other"
        else:
            try:
                from app.data.scraper.symbol_universe import get_active_symbols
                active_symbols = get_active_symbols()
                match = next((s for s in active_symbols if s.get("symbol", "").upper() == symbol), None)
                if match:
                    is_valid = True
                    name = match.get("company_name", symbol)
                    sector = match.get("sector", "Other")
            except Exception:
                pass

        if is_valid:
            from uuid import uuid4
            stock = Stock(
                id=uuid4().hex,
                symbol=symbol,
                name=name,
                sector=sector,
            )
            self.db.add(stock)
            await self.db.flush()
            await self.db.refresh(stock)
            return stock

        return None

    async def _get_prices_from_redis(self, symbols: list[str]) -> tuple[dict[str, Decimal], dict[str, datetime]]:
        """Fetch current prices for symbols directly from Redis market quotes cache."""
        current_prices: dict[str, Decimal] = {}
        price_dates: dict[str, datetime] = {}
        
        if not symbols:
            return current_prices, price_dates
        
        # Build cache keys for batch fetch - check both ETF and stock quote keys
        etf_symbols = {"MIIETF", "UBLPETF", "NITGETF", "MZNPETF", "JSGBETF", "HBLTETF"}
        quote_keys = []
        for sym in symbols:
            if sym in etf_symbols:
                quote_keys.append(f"etf:quote:v1:{sym}")
            else:
                quote_keys.append(f"stock:quote:v1:{sym}")
        
        # Try batch fetch from Redis using MGET
        client = get_redis_client()
        if client:
            try:
                cached_values = await client.mget(quote_keys)
                for sym, val in zip(symbols, cached_values):
                    if val is not None:
                        import json
                        quote_data = json.loads(val)
                        current = quote_data.get("current_price") or quote_data.get("current")
                        if current is not None:
                            current_prices[sym] = Decimal(str(current))
                            price_dates[sym] = datetime.now(timezone.utc)
            except Exception as exc:
                logger.debug("Redis batch quote fetch failed: %s", exc)
        
        # Fallback to stock_service for any missing symbols
        missing_symbols = [s for s in symbols if s not in current_prices]
        if missing_symbols:
            try:
                quotes = self.stock_service.get_quote_batch(missing_symbols)
                quote_list = list(quotes.values()) if isinstance(quotes, dict) else (quotes or [])
                for q in quote_list:
                    if isinstance(q, dict) and "symbol" in q:
                        cur = q.get("current") or q.get("current_price") or q.get("ldcp")
                        if cur is not None:
                            current_prices[q["symbol"].upper()] = Decimal(str(cur))
                            price_dates[q["symbol"].upper()] = datetime.now(timezone.utc)
            except Exception as exc:
                logger.debug("Stock service quote batch fallback failed: %s", exc)

        return current_prices, price_dates

    # ───────────────────────────────────────────────────────────────────
    # Precomputation methods for scheduled jobs
    # ───────────────────────────────────────────────────────────────────

    async def precompute_performance(self, user_id: str, period: str = "1M") -> dict:
        """Precompute portfolio performance and store in Redis (called from scheduled job)."""
        cache_key = f"portfolio:performance:{user_id}:{period}"
        
        period_days = {
            "1D": 1,
            "1W": 7,
            "1M": 30,
            "3M": 90,
            "6M": 180,
            "1Y": 365,
            "ALL": 3650,
        }
        
        days = period_days.get(period, 30)
        cutoff = date.today() - timedelta(days=days)
        
        txns = await self.repo.get_all_user_transactions(user_id)
        
        if not txns:
            empty_perf = {"period": period, "data": []}
            await cache_set(cache_key, empty_perf, ttl_seconds=PORTFOLIO_CACHE_TTL)
            return empty_perf
        
        symbols = sorted({transaction.symbol for transaction in txns})
        prices_result = await self.db.execute(
            select(Stock.symbol, StockPrice.date, StockPrice.adjusted_close)
            .join(Stock, StockPrice.stock_id == Stock.id)
            .where(Stock.symbol.in_(symbols), StockPrice.date >= cutoff)
            .order_by(StockPrice.date.asc())
        )
        historical_prices: dict[str, dict[date, Decimal]] = defaultdict(dict)
        for symbol, price_date, adjusted_close in prices_result.all():
            if adjusted_close is not None:
                historical_prices[symbol][price_date] = Decimal(str(adjusted_close))

        # Fallback to maintained local parquet history for symbols not yet populated in SQL database
        for sym in symbols:
            if not historical_prices.get(sym):
                try:
                    df = self.stock_service._get_ohlcv_from_file(sym, start=cutoff)
                    if df is not None and not df.empty:
                        for idx, row in df.iterrows():
                            close_val = row.get("CLOSE") or row.get("ADJUSTED_CLOSE")
                            if close_val is not None:
                                historical_prices[sym][idx.date()] = Decimal(str(close_val))
                except Exception:
                    pass
        
        data_series = calculate_performance_time_series(txns, historical_prices, period)
        result = {
            "period": period,
            "data": data_series,
        }
        await cache_set(cache_key, result, ttl_seconds=PORTFOLIO_CACHE_TTL)
        return result

    async def precompute_all_performance(self, user_id: str) -> dict:
        """Precompute performance for all periods for a user."""
        periods = ["1D", "1W", "1M", "3M", "6M", "1Y", "ALL"]
        results = {}
        for period in periods:
            try:
                results[period] = await self.precompute_performance(user_id, period)
            except Exception as exc:
                logger.warning("Precompute performance failed for user %s period %s: %s", user_id, period, exc)
        return results

    async def prewarm_portfolio_get_caches(self, user_id: str) -> dict:
        """Warm the standard portfolio GET responses before a user's first request."""
        payload = await self.refresh_portfolio_snapshot(user_id)
        warmed_details = 0
        for holding in payload["portfolio"]["holdings"]:
            await self.get_holding_detail(user_id, holding["symbol"])
            warmed_details += 1

        performance = await self.precompute_all_performance(user_id)
        transactions, total = await self.get_transactions(user_id, page=1, limit=20)
        transaction_payload = {
            "items": [
                {
                    "id": txn.id,
                    "symbol": txn.symbol,
                    "transaction_type": txn.transaction_type.value,
                    "quantity": str(txn.quantity),
                    "price": str(txn.price),
                    "fee": str(txn.fee),
                    "transaction_date": txn.transaction_date.isoformat(),
                    "created_at": txn.created_at.isoformat() if txn.created_at else None,
                    "updated_at": txn.updated_at.isoformat() if txn.updated_at else None,
                }
                for txn in transactions
            ],
            "total": total,
            "page": 1,
            "limit": 20,
        }
        await cache_set(
            f"portfolio:txns:{user_id}:1:20:None:None:None:None",
            transaction_payload,
            ttl_seconds=PORTFOLIO_CACHE_TTL,
        )
        return {
            "holding_details": warmed_details,
            "performance_periods": list(performance),
            "transactions": True,
        }
