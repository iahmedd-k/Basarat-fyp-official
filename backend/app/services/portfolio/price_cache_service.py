"""Redis-backed live quote cache for portfolio / market price endpoints."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import cache_get, cache_set
from app.models.stock import Stock, StockPrice
from app.services.market_service import MarketService
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 30


class PriceCacheService:
    """Live PSX quote helper with short Redis TTL (no DB PriceCache table required)."""

    def __init__(
        self,
        stock_service: StockService | None = None,
        market_service: MarketService | None = None,
        db: AsyncSession | None = None,
    ):
        self.stock_service = stock_service or StockService()
        self.market_service = market_service or MarketService()
        self.db = db

    async def get_price(self, symbol: str) -> dict[str, Any]:
        symbol = symbol.strip().upper()
        cache_key = f"price:quote:v1:{symbol}"
        cached = await cache_get(cache_key)
        if cached:
            cached = dict(cached)
            cached["stale"] = False
            return cached

        stale_key = f"price:quote:stale:v1:{symbol}"

        # Prefer the shared market-watch snapshot. StockService's per-symbol
        # PSX endpoint can be unavailable even while the regular market refresh
        # has a valid quote for the same symbol.
        market_rows = await self.market_service.get_market_data(read_only=True)
        market_quote = next(
            (row for row in market_rows if str(row.get("symbol", "")).strip().upper() == symbol),
            None,
        )
        if market_quote and self._has_positive_price(market_quote.get("current")):
            freshness = self.market_service.quote_freshness()
            payload = self._quote_to_payload(market_quote, stale=bool(freshness.get("is_stale", True)))
            payload["last_updated"] = freshness.get("as_of") or payload["last_updated"]
            if payload["stale"]:
                await cache_set(
                    f"price:quote:stale:v1:{symbol}",
                    payload,
                    ttl_seconds=CACHE_TTL_SECONDS * 20,
                )
            else:
                await cache_set(cache_key, payload, ttl_seconds=CACHE_TTL_SECONDS)
                await cache_set(
                    f"price:quote:stale:v1:{symbol}",
                    payload,
                    ttl_seconds=CACHE_TTL_SECONDS * 20,
                )
            return payload

        quote = self.stock_service.get_quote(symbol)
        if quote and float(quote.get("current") or 0) > 0:
            payload = self._quote_to_payload(quote, stale=False)
            await cache_set(cache_key, payload, ttl_seconds=CACHE_TTL_SECONDS)
            await cache_set(
                stale_key,
                payload,
                ttl_seconds=CACHE_TTL_SECONDS * 20,
            )
            return payload

        # Soft stale: try longer-lived fallback key
        stale = await cache_get(stale_key)
        if stale:
            stale = dict(stale)
            stale["stale"] = True
            return stale

        historical = await self._historical_price(symbol)
        if historical:
            await cache_set(stale_key, historical, ttl_seconds=CACHE_TTL_SECONDS * 20)
            return historical

        logger.warning("No live price available for %s", symbol)
        return {
            "symbol": symbol,
            "ldcp": 0.0,
            "current_price": 0.0,
            "change": 0.0,
            "change_percent": 0.0,
            "volume": 0,
            "market_status": self._market_status(0),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "stale": True,
            "available": False,
        }

    async def _historical_price(self, symbol: str) -> dict[str, Any] | None:
        """Return a real last close, explicitly marked stale, when quotes fail."""
        if self.db is None:
            return None
        result = await self.db.execute(
            select(StockPrice.date, StockPrice.close, StockPrice.volume)
            .join(Stock, Stock.id == StockPrice.stock_id)
            .where(Stock.symbol == symbol, StockPrice.close.is_not(None), StockPrice.close > 0)
            .order_by(StockPrice.date.desc())
            .limit(2)
        )
        rows = result.all()
        if not rows:
            return None

        latest = rows[0]
        current = float(latest.close)
        ldcp = float(rows[1].close) if len(rows) > 1 and rows[1].close else 0.0
        change = round(current - ldcp, 4) if ldcp else 0.0
        change_percent = round(change / ldcp * 100, 4) if ldcp else 0.0
        return {
            "symbol": symbol,
            "ldcp": round(ldcp, 4),
            "current_price": round(current, 4),
            "change": change,
            "change_percent": change_percent,
            "volume": int(latest.volume or 0),
            "market_status": "CLOSED",
            "last_updated": latest.date.isoformat(),
            "stale": True,
            "available": True,
        }

    @staticmethod
    def _has_positive_price(value: Any) -> bool:
        try:
            return value is not None and float(value) > 0
        except (TypeError, ValueError):
            return False

    async def get_bulk_prices(self, symbols: list[str]) -> dict[str, dict[str, Any]]:
        if not symbols:
            return {}

        upper = [s.strip().upper() for s in symbols if s and str(s).strip()]
        results: dict[str, dict[str, Any]] = {}
        missing: list[str] = []

        for symbol in upper:
            cache_key = f"price:quote:v1:{symbol}"
            cached = await cache_get(cache_key)
            if cached:
                cached = dict(cached)
                cached["stale"] = False
                results[symbol] = cached
            else:
                missing.append(symbol)

        if missing:
            quotes = self.stock_service.get_quote_batch(missing)
            by_sym = {str(q.get("symbol", "")).upper(): q for q in quotes}
            for symbol in missing:
                quote = by_sym.get(symbol)
                if quote and float(quote.get("current") or 0) > 0:
                    payload = self._quote_to_payload(quote, stale=False)
                    await cache_set(f"price:quote:v1:{symbol}", payload, ttl_seconds=CACHE_TTL_SECONDS)
                    await cache_set(
                        f"price:quote:stale:v1:{symbol}",
                        payload,
                        ttl_seconds=CACHE_TTL_SECONDS * 20,
                    )
                    results[symbol] = payload
                else:
                    results[symbol] = await self.get_price(symbol)

        return results

    def _quote_to_payload(self, quote: dict, stale: bool = False) -> dict[str, Any]:
        volume = int(quote.get("volume") or 0)
        current = float(quote.get("current") or 0)
        ldcp = float(quote.get("ldcp") or 0)
        change = quote.get("change")
        if change is None and current and ldcp:
            change = current - ldcp
        change_pct = quote.get("change_pct")
        if change_pct is None and change is not None and ldcp:
            change_pct = (float(change) / ldcp) * 100.0
        return {
            "symbol": str(quote.get("symbol", "")).upper(),
            "ldcp": round(ldcp, 4),
            "current_price": round(current, 4),
            "change": round(float(change or 0), 4),
            "change_percent": round(float(change_pct or 0), 4),
            "volume": volume,
            "market_status": self._market_status(volume),
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "stale": stale,
            "available": current > 0,
        }

    @staticmethod
    def _market_status(volume: int) -> str:
        return "OPEN" if volume and volume > 0 else "CLOSED"
