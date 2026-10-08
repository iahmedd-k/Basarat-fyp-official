import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete, desc, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession
import numpy as np
import pandas as pd

from app.core.exceptions import NotFoundError
from app.core.redis import cache_get, cache_get_many, cache_set
from app.models.etf import ETF
from app.schemas.etf import (
    ETFQuote,
    ETFResponse,
    ETFListResponse,
    ETFHistoryItem,
    ETFHistoryResponse,
    ETFPerformanceResponse,
)

log = logging.getLogger(__name__)
OHLCV_DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "raw" / "ohlcv"

INITIAL_PSX_ETFS = [
    {
        "symbol": "MIIETF",
        "name": "Meezan Islamic ETF",
        "fund_manager": "Al Meezan Investment Management Limited",
        "category": "Islamic Equity ETF",
        "benchmark_index": "Meezan Pakistan Index (MII-30)",
        "is_shariah_compliant": True,
        "expense_ratio": 0.75,
        "inception_date": date(2020, 10, 6),
        "total_assets_pkr": 1450000000,
        "description": "Tracks the performance of Shariah-compliant high-market-cap equities in Pakistan.",
        "is_active": True,
    },
    {
        "symbol": "UBLPETF",
        "name": "UBL Pakistan Enterprise ETF",
        "fund_manager": "UBL Fund Managers Limited",
        "category": "Broad Market Equity ETF",
        "benchmark_index": "Pakistan Enterprise Index",
        "is_shariah_compliant": False,
        "expense_ratio": 0.65,
        "inception_date": date(2020, 3, 24),
        "total_assets_pkr": 980000000,
        "description": "Tracks top 9 fundamental companies representing Pakistan's core economy.",
        "is_active": True,
    },
    {
        "symbol": "NITGETF",
        "name": "NIT Pakistan Gateway ETF",
        "fund_manager": "National Investment Trust Limited (NIT)",
        "category": "Broad Market Equity ETF",
        "benchmark_index": "NIT Pakistan Gateway Index",
        "is_shariah_compliant": False,
        "expense_ratio": 0.70,
        "inception_date": date(2020, 3, 24),
        "total_assets_pkr": 1200000000,
        "description": "Represents the top 50% market cap weight of KSE-100 index.",
        "is_active": True,
    },
    {
        "symbol": "MZNPETF",
        "name": "Meezan Pakistan ETF",
        "fund_manager": "Al Meezan Investment Management Limited",
        "category": "Islamic Equity ETF",
        "benchmark_index": "Meezan Pakistan Index",
        "is_shariah_compliant": True,
        "expense_ratio": 0.75,
        "inception_date": date(2022, 9, 15),
        "total_assets_pkr": 850000000,
        "description": "Shariah-compliant equity basket focusing on dividend yield and growth.",
        "is_active": True,
    },
    {
        "symbol": "JSGBETF",
        "name": "JS Global Banking Sector ETF",
        "fund_manager": "JS Investments Limited",
        "category": "Sector Equity ETF",
        "benchmark_index": "PSX Banking Index",
        "is_shariah_compliant": False,
        "expense_ratio": 0.80,
        "inception_date": date(2022, 1, 14),
        "total_assets_pkr": 620000000,
        "description": "Focused thematic ETF tracking top commercial banks in Pakistan.",
        "is_active": True,
    },
    {
        "symbol": "HBLTETF",
        "name": "HBL Total Treasury ETF",
        "fund_manager": "HBL Asset Management Limited",
        "category": "Treasury / Debt ETF",
        "benchmark_index": "PSX Government Debt Index",
        "is_shariah_compliant": False,
        "expense_ratio": 0.50,
        "inception_date": date(2023, 2, 20),
        "total_assets_pkr": 1800000000,
        "description": "First sovereign debt ETF tracking high-yield Pakistan Treasury Bills and PIBs.",
        "is_active": True,
    },
]

# Reliable baseline fallbacks for live metrics if scraper is temporarily down
DEFAULT_ETF_PRICES = {
    "MIIETF": {"price": 16.24, "change": 0.19, "change_pct": 1.18, "open": 16.05, "high": 16.24, "low": 16.05, "volume": 125000},
    "UBLPETF": {"price": 28.52, "change": -0.15, "change_pct": -0.52, "open": 28.52, "high": 28.52, "low": 28.30, "volume": 84000},
    "NITGETF": {"price": 32.83, "change": 0.35, "change_pct": 1.08, "open": 32.83, "high": 33.09, "low": 32.83, "volume": 92000},
    "MZNPETF": {"price": 17.49, "change": 0.11, "change_pct": 0.63, "open": 17.49, "high": 17.60, "low": 17.30, "volume": 68000},
    "JSGBETF": {"price": 38.92, "change": -0.22, "change_pct": -0.56, "open": 38.92, "high": 38.95, "low": 38.92, "volume": 45000},
    "HBLTETF": {"price": 105.40, "change": 0.08, "change_pct": 0.08, "open": 105.32, "high": 105.45, "low": 105.30, "volume": 310000},
}


class ETFService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_seed_data(self) -> None:
        """Seed initial active PSX ETF directory if the table is empty."""
        try:
            count_res = await self.db.execute(select(func.count(ETF.id)))
            if (count_res.scalar() or 0) == 0:
                for item in INITIAL_PSX_ETFS:
                    self.db.add(ETF(**item))
                await self.db.commit()
                log.info("Initialized %d default PSX ETF records", len(INITIAL_PSX_ETFS))
        except Exception as exc:
            log.warning("Could not verify/seed ETF initial data: %s", exc)
            await self.db.rollback()

    # ───────────────────────────────────────────────────────────────────
    # Resilient Scraper / Quote Fetching with Redis
    # ───────────────────────────────────────────────────────────────────

    @staticmethod
    def _quote_data_from_live_snapshot(symbol: str, live_quotes: Any) -> dict[str, Any] | None:
        if not isinstance(live_quotes, dict):
            return None
        row = live_quotes.get(symbol)
        if not isinstance(row, dict):
            return None

        try:
            close = float(row.get("current") or row.get("close") or row.get("price") or 0.0)
            if close <= 0:
                return None
            open_price = float(row.get("open") or close)
            change = float(row.get("change") or (close - open_price))
            return {
                "current_price": round(close, 2),
                "change": round(change, 2),
                "change_percent": round(float(row.get("change_percent") or 0.0), 2),
                "open_price": round(open_price, 2),
                "high_price": round(float(row.get("high") or close), 2),
                "low_price": round(float(row.get("low") or close), 2),
                "close_price": round(close, 2),
                "volume": int(row.get("volume") or 0),
                "bid_price": round(close, 2),
                "ask_price": round(close, 2),
                "data_as_of": datetime.utcnow().isoformat(),
                "quote_source": "redis_live_bus",
            }
        except (TypeError, ValueError, OverflowError):
            return None

    @staticmethod
    def _fallback_quote_data(symbol: str) -> dict[str, Any]:
        fallback = DEFAULT_ETF_PRICES.get(
            symbol,
            {"price": 25.0, "change": 0.0, "change_pct": 0.0, "open": 25.0, "high": 25.0, "low": 25.0, "volume": 10000},
        )
        return {
            "current_price": fallback["price"],
            "change": fallback["change"],
            "change_percent": fallback["change_pct"],
            "open_price": fallback["open"],
            "high_price": fallback["high"],
            "low_price": fallback["low"],
            "close_price": fallback["price"],
            "volume": fallback["volume"],
            "bid_price": fallback["price"],
            "ask_price": fallback["price"],
            "data_as_of": datetime.utcnow().isoformat(),
            "quote_source": "cached_fallback",
        }

    async def get_live_quote(self, symbol: str) -> ETFQuote:
        """Read a live ETF quote from Redis, falling back to the configured quote."""
        sym = symbol.strip().upper()
        cache_key = f"etf:quote:v1:{sym}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFQuote(**cached)

        live_quotes = await cache_get("market:quotes:live")
        quote_data = self._quote_data_from_live_snapshot(sym, live_quotes)
        if quote_data is None:
            quote_data = self._fallback_quote_data(sym)

        await cache_set(cache_key, quote_data, ttl_seconds=120)
        return ETFQuote(**quote_data)

    async def _format_etf_response(
        self,
        etf: ETF,
        quote: ETFQuote | None = None,
    ) -> ETFResponse:
        if quote is None:
            quote = await self.get_live_quote(etf.symbol)
        return ETFResponse(
            id=etf.id,
            symbol=etf.symbol,
            name=etf.name,
            fund_manager=etf.fund_manager,
            category=etf.category,
            benchmark_index=etf.benchmark_index,
            is_shariah_compliant=etf.is_shariah_compliant,
            expense_ratio=etf.expense_ratio,
            inception_date=etf.inception_date,
            total_assets_pkr=etf.total_assets_pkr,
            description=etf.description,
            is_active=etf.is_active,
            quote=quote,
            current_price=quote.current_price,
            change=quote.change,
            change_percent=quote.change_percent,
            volume=quote.volume,
            created_at=etf.created_at,
            updated_at=etf.updated_at,
        )

    # ───────────────────────────────────────────────────────────────────
    # Public Read Endpoints
    # ───────────────────────────────────────────────────────────────────

    async def get_etfs(
        self,
        category: Optional[str] = None,
        is_shariah_compliant: Optional[bool] = None,
        search: Optional[str] = None,
    ) -> ETFListResponse:
        cache_key = f"etf:list:v1:{category}:{is_shariah_compliant}:{search}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFListResponse(**cached)

        await self.ensure_seed_data()
        query = select(ETF).where(ETF.is_active == True)
        if category and category.strip():
            query = query.where(ETF.category.ilike(f"%{category.strip()}%"))
        if is_shariah_compliant is not None:
            query = query.where(ETF.is_shariah_compliant == is_shariah_compliant)
        if search and search.strip():
            q = search.strip()
            query = query.where(
                or_(
                    ETF.symbol.ilike(f"%{q}%"),
                    ETF.name.ilike(f"%{q}%"),
                    ETF.fund_manager.ilike(f"%{q}%"),
                    ETF.benchmark_index.ilike(f"%{q}%"),
                )
            )

        query = query.order_by(ETF.symbol.asc())
        res = await self.db.execute(query)
        etfs = res.scalars().all()

        quote_keys = [f"etf:quote:v1:{etf.symbol.strip().upper()}" for etf in etfs]
        cached_quotes = await cache_get_many(quote_keys)
        live_quotes = await cache_get("market:quotes:live")
        formatted = []
        for etf, quote_key in zip(etfs, quote_keys):
            quote_data = cached_quotes.get(quote_key)
            if not quote_data:
                quote_data = self._quote_data_from_live_snapshot(
                    etf.symbol.strip().upper(),
                    live_quotes,
                )
            if not quote_data:
                quote_data = self._fallback_quote_data(etf.symbol.strip().upper())
            formatted.append(
                await self._format_etf_response(etf, quote=ETFQuote(**quote_data))
            )
        shariah_count = sum(1 for e in formatted if e.is_shariah_compliant)
        conventional_count = len(formatted) - shariah_count

        response = ETFListResponse(
            total=len(formatted),
            shariah_count=shariah_count,
            conventional_count=conventional_count,
            etfs=list(formatted),
        )
        # Cache list response for 120 seconds
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=120)
        return response

    async def get_etf_by_symbol(self, symbol: str) -> ETFResponse:
        sym = symbol.strip().upper()
        cache_key = f"etf:detail:v1:{sym}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFResponse(**cached)

        await self.ensure_seed_data()
        res = await self.db.execute(select(ETF).where(ETF.symbol == sym))
        etf = res.scalars().first()
        if not etf:
            raise NotFoundError(f"ETF '{sym}' not found.")
        response = await self._format_etf_response(etf)
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=120)
        return response


    async def get_history(self, symbol: str, timeframe: str = "1M") -> ETFHistoryResponse:
        """Read historical timeseries from the maintained OHLCV data files.

        Historical data is published by the daily ingestion pipeline. API
        requests must not contact PSX directly when a cache is cold.
        Returns empty history with data_available=False if no OHLCV file exists.
        """
        sym = symbol.strip().upper()
        cache_key = f"etf:hist:v1:{sym}:{timeframe}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFHistoryResponse(**cached)

        history_items: List[ETFHistoryItem] = []
        data_available = False
        try:
            path = OHLCV_DATA_DIR / f"{sym}.parquet"
            if path.is_file():
                df = pd.read_parquet(path)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date")
                if not df.empty:
                    df.index = pd.to_datetime(df.index)
                    df.columns = [str(column).upper() for column in df.columns]
                    df = df.sort_index(ascending=True)
                if hasattr(df, "iloc") and len(df) > 0:
                    df = df.sort_index(ascending=True)
                    limit = 30 if timeframe == "1M" else 90 if timeframe == "3M" else 250
                    for idx, row in df.tail(limit).iterrows():
                        d_str = str(idx.date()) if hasattr(idx, "date") else str(idx)[:10]
                        history_items.append(
                            ETFHistoryItem(
                                date=d_str,
                                open=float(row.get("OPEN") or row.get("CLOSE", 0)),
                                high=float(row.get("HIGH") or row.get("CLOSE", 0)),
                                low=float(row.get("LOW") or row.get("CLOSE", 0)),
                                close=float(row.get("CLOSE") or 0),
                                volume=int(row.get("VOLUME") or 0),
                            )
                        )
                    data_available = len(history_items) > 0
        except Exception as exc:
            log.warning("Persisted ETF history read failed for %s: %s", sym, exc)

        # Do NOT generate synthetic data - return empty history with data_available flag
        if not data_available:
            log.info("No OHLCV data available for ETF %s (%s)", sym, timeframe)

        response = ETFHistoryResponse(
            symbol=sym,
            timeframe=timeframe,
            count=len(history_items),
            history=history_items,
            data_available=data_available,
        )
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response

    async def get_performance(self, symbol: str) -> ETFPerformanceResponse:
        """Calculate returns across standard holding periods from actual OHLCV data."""
        sym = symbol.strip().upper()
        cache_key = f"etf:perf:v1:{sym}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFPerformanceResponse(**cached)

        etf = await self.get_etf_by_symbol(symbol)
        sym = etf.symbol

        # Try to calculate from actual OHLCV data
        returns = {}
        is_estimated = False
        try:
            path = OHLCV_DATA_DIR / f"{sym}.parquet"
            if path.is_file():
                df = pd.read_parquet(path)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.set_index("date")
                if not df.empty:
                    df.index = pd.to_datetime(df.index)
                    df.columns = [str(column).upper() for column in df.columns]
                    df = df.sort_index(ascending=True)
                    if "CLOSE" in df.columns and len(df) > 1:
                        close = df["CLOSE"]
                        last_price = close.iloc[-1]
                        periods = {
                            "1D": 1,
                            "1W": 5,
                            "1M": 21,
                            "3M": 63,
                            "1Y": 252,
                        }
                        for period, days in periods.items():
                            if len(close) > days:
                                past_price = close.iloc[-(days + 1)]
                                if past_price > 0:
                                    returns[period] = round(((last_price - past_price) / past_price) * 100, 2)
                        # YTD
                        current_year = pd.Timestamp.now().year
                        ytd_data = close[close.index.year == current_year]
                        if len(ytd_data) > 1:
                            ytd_start = ytd_data.iloc[0]
                            if ytd_start > 0:
                                returns["YTD"] = round(((last_price - ytd_start) / ytd_start) * 100, 2)
        except Exception as exc:
            log.warning("Failed to calculate ETF performance from OHLCV for %s: %s", sym, exc)

        if not returns:
            # Fallback to estimated - clearly marked
            is_estimated = True
            returns = {
                "1D": 0.0, "1W": 0.0, "1M": 0.0, "3M": 0.0, "1Y": 0.0, "YTD": 0.0
            }

        # Benchmark returns (estimated as 98% of ETF returns when no benchmark data)
        bench_ret = {k: round(v * 0.98, 2) for k, v in returns.items()}

        response = ETFPerformanceResponse(
            symbol=sym,
            name=etf.name,
            benchmark_index=etf.benchmark_index,
            returns=returns,
            benchmark_returns=bench_ret,
            tracking_difference_1m=round(returns.get("1M", 0) - bench_ret.get("1M", 0), 2),
            volatility_annualized=None,
            is_estimated=is_estimated,
        )
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response
