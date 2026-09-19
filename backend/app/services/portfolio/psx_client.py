import logging
from typing import Optional

from app.services.stock_service import StockService

logger = logging.getLogger(__name__)


class PSXApiClient:
    """Wrapper around StockService for PSX live data fetching."""

    def __init__(self, stock_service: StockService):
        self.stock_service = stock_service

    def fetch_quote(self, symbol: str) -> Optional[dict]:
        """Fetch a single quote from PSX."""
        try:
            quote = self.stock_service.get_quote(symbol)
            if quote and quote.get("current", 0) > 0:
                return quote
            return None
        except Exception as e:
            logger.warning(f"Failed to fetch quote for {symbol}: {e}")
            return None

    def fetch_quote_batch(self, symbols: list[str]) -> list[dict]:
        """Fetch multiple quotes from PSX."""
        if not symbols:
            return []
        try:
            quotes = self.stock_service.get_quote_batch(symbols)
            return quotes
        except Exception as e:
            logger.warning(f"Failed to fetch batch quotes: {e}")
            return []

    def is_symbol_valid(self, symbol: str) -> bool:
        """Check if a symbol exists on PSX."""
        quote = self.fetch_quote(symbol)
        return quote is not None