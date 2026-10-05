"""Cashtag extraction and stock price snapshot service for Community posts."""

import re
from typing import List, Optional, Set
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock
from app.core.redis import cache_get

# Match $SYMBOL or #SYMBOL with 1-10 uppercase alphanumeric chars, avoiding pure digits like $50
CASHTAG_REGEX = re.compile(r"[$#]([A-Za-z][A-Za-z0-9\-_]{0,9})\b")


class CashtagService:
    @staticmethod
    def extract_cashtags(content: str) -> List[str]:
        """Extract unique cashtag / ticker candidate strings from post content."""
        if not content:
            return []
        matches = CASHTAG_REGEX.findall(content)
        # Normalize uppercase and remove duplicate while preserving order
        seen: Set[str] = set()
        tickers: List[str] = []
        for m in matches:
            sym = m.upper().strip()
            # Ignore purely numeric or trivial strings
            if sym and not sym.isdigit() and sym not in seen:
                seen.add(sym)
                tickers.append(sym)
        return tickers[:5]  # Limit to max 5 tickers per post to prevent spam

    @staticmethod
    async def validate_tickers(db: AsyncSession, candidates: List[str]) -> List[str]:
        """Validate candidate symbols against the active stocks in the database."""
        if not candidates:
            return []
        
        # Check database
        result = await db.execute(
            select(Stock.symbol).where(
                Stock.symbol.in_(candidates),
                Stock.is_active == True,
            )
        )
        valid_symbols = {row[0] for row in result.all()}
        return [c for c in candidates if c in valid_symbols]

    @staticmethod
    async def get_price_snapshot(symbol: Optional[str]) -> Optional[float]:
        """Fetch current or last closing price snapshot from Redis market quote cache."""
        if not symbol:
            return None
        sym = symbol.upper().strip()
        try:
            # Check market quote in Redis cache
            quote_key = f"market:quote:{sym}"
            quote = await cache_get(quote_key)
            if quote and isinstance(quote, dict):
                price = quote.get("current_price") or quote.get("price") or quote.get("close")
                if price is not None:
                    return float(price)
        except Exception:
            pass
        return None
