import logging
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.portfolio import PriceCache, MarketStatus
from app.repository.portfolio_repository import PortfolioRepository
from app.services.portfolio.psx_client import PSXApiClient

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30  # 30-60s TTL as per spec


class PriceCacheService:
    """Manages PriceCache with TTL and PSX fallback."""

    def __init__(
        self,
        db: AsyncSession,
        psx_client: PSXApiClient,
        repo: Optional[PortfolioRepository] = None,
    ):
        self.db = db
        self.psx_client = psx_client
        self.repo = repo or PortfolioRepository(db)

    async def get_price(self, symbol: str) -> dict:
        """
        Get price for a symbol. Checks cache first (TTL ~30s).
        If stale, fetches from PSX, updates cache, returns price.
        If PSX fails, returns last cached price with stale=true.
        """
        symbol = symbol.upper()
        cache = await self.repo.get_price_cache(symbol)

        now = datetime.utcnow()
        is_stale = False

        if cache:
            age = (now - cache.last_updated).total_seconds()
            if age <= CACHE_TTL_SECONDS:
                # Cache is fresh
                return self._cache_to_dict(cache, stale=False)

        # Cache is stale or missing - try to fetch from PSX
        quote = self.psx_client.fetch_quote(symbol)

        if quote:
            # Update cache with fresh data
            market_status = self._determine_market_status(quote)
            updated_cache = await self.repo.upsert_price_cache(
                symbol=symbol,
                ldcp=quote.get("ldcp", 0),
                current_price=quote.get("current", quote.get("ldcp", 0)),
                change=quote.get("change", 0),
                change_percent=quote.get("change_pct", 0),
                market_status=market_status,
            )
            return self._cache_to_dict(updated_cache, stale=False)

        # PSX fetch failed - return stale cache if available
        if cache:
            logger.warning(f"PSX fetch failed for {symbol}, returning stale cache")
            return self._cache_to_dict(cache, stale=True)

        # No cache and PSX failed - return empty/default
        logger.error(f"No price data available for {symbol}")
        return {
            "symbol": symbol,
            "ldcp": 0.0,
            "current_price": 0.0,
            "change": 0.0,
            "change_percent": 0.0,
            "market_status": MarketStatus.CLOSED.value,
            "last_updated": now,
            "stale": True,
        }

    async def get_bulk_prices(self, symbols: list[str]) -> dict[str, dict]:
        """Get prices for multiple symbols. Uses batch fetch from PSX."""
        if not symbols:
            return {}

        upper_symbols = [s.upper() for s in symbols]

        # Check cache for all symbols
        cache_map = await self.repo.get_bulk_price_cache(upper_symbols)
        now = datetime.utcnow()

        fresh_results = {}
        stale_symbols = []

        for symbol in upper_symbols:
            cache = cache_map.get(symbol)
            if cache:
                age = (now - cache.last_updated).total_seconds()
                if age <= CACHE_TTL_SECONDS:
                    fresh_results[symbol] = self._cache_to_dict(cache, stale=False)
                    continue
            stale_symbols.append(symbol)

        # Fetch stale/missing symbols from PSX in batch
        if stale_symbols:
            quotes = self.psx_client.fetch_quote_batch(stale_symbols)
            for quote in quotes:
                symbol = quote["symbol"]
                market_status = self._determine_market_status(quote)
                await self.repo.upsert_price_cache(
                    symbol=symbol,
                    ldcp=quote.get("ldcp", 0),
                    current_price=quote.get("current", quote.get("ldcp", 0)),
                    change=quote.get("change", 0),
                    change_percent=quote.get("change_pct", 0),
                    market_status=market_status,
                )
                fresh_results[symbol] = {
                    "current_price": quote.get("current", 0),
                    "change_percent": quote.get("change_pct", 0),
                    "market_status": market_status,
                }

        return fresh_results

    def _determine_market_status(self, quote: dict) -> str:
        """Determine market status from quote data."""
        # PSX market hours: 9:30 AM - 3:30 PM PKT, Mon-Fri
        # For now, use volume as proxy - if volume > 0, likely open
        # In production, use proper market calendar
        volume = quote.get("volume", 0)
        if volume > 0:
            return MarketStatus.OPEN.value
        return MarketStatus.CLOSED.value

    def _cache_to_dict(self, cache: PriceCache, stale: bool = False) -> dict:
        return {
            "symbol": cache.symbol,
            "ldcp": float(cache.ldcp),
            "current_price": float(cache.current_price),
            "change": float(cache.change),
            "change_percent": float(cache.change_percent),
            "market_status": cache.market_status,
            "last_updated": cache.last_updated,
            "stale": stale,
        }