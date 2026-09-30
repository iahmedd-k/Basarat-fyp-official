import logging
from datetime import datetime, date
from typing import Optional, List
from sqlalchemy import select, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError
from app.core.redis import cache_get, cache_set
from app.models.etf import ETF
from app.schemas.etf import (
    ETFQuote,
    ETFCreate,
    ETFUpdate,
    ETFResponse,
    ETFListResponse,
    ETFHistoryItem,
    ETFHistoryResponse,
    ETFPerformanceResponse,
)

log = logging.getLogger(__name__)

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

# Hardcoded price/performance maps removed — never invent live market data.
# Quotes/history/performance return unavailable/null when scraper data is missing.


class ETFService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_seed_data(self) -> None:
        """Seed initial active PSX ETF directory if the table is empty."""
        try:
            count_res = await self.db.execute(select(func.count(ETF.id)))
            if count_res.scalar() == 0:
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

    async def get_live_quote(self, symbol: str) -> ETFQuote:
        """Fetch live ETF quote with Redis caching. Never invents prices."""
        sym = symbol.strip().upper()
        cache_key = f"etf:quote:v1:{sym}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFQuote(**cached)

        quote_data = None
        try:
            import pypsx_toolkit
            import asyncio
            frame = await asyncio.wait_for(
                asyncio.to_thread(pypsx_toolkit.get_quote, sym),
                timeout=2.0,
            )
            if hasattr(frame, "iloc") and len(frame) > 0:
                row = frame.iloc[-1]
                close = float(row.get("CURRENT") or row.get("CLOSE") or row.get("PRICE") or row.get("LDCP") or 0.0)
                if close > 0.0:
                    open_p = float(row.get("OPEN") or close)
                    high_p = float(row.get("HIGH") or close)
                    low_p = float(row.get("LOW") or close)
                    vol = int(row.get("VOLUME") or 0)
                    change = float(row.get("CHANGE") or (close - open_p))
                    change_pct = float(
                        row.get("CHANGE_PERCENT")
                        or (change / open_p * 100 if open_p > 0 else 0.0)
                    )

                    quote_data = {
                        "current_price": round(close, 2),
                        "change": round(change, 2),
                        "change_percent": round(change_pct, 2),
                        "open_price": round(open_p, 2),
                        "high_price": round(high_p, 2),
                        "low_price": round(low_p, 2),
                        "close_price": round(close, 2),
                        "volume": vol,
                        "bid_price": float(row.get("BID_PRICE") or close),
                        "ask_price": float(row.get("ASK_PRICE") or close),
                        "data_as_of": datetime.utcnow().isoformat(),
                        "quote_source": "psx_live",
                    }
        except Exception as exc:
            log.debug("Live scraper quote fetch timed out/failed for ETF %s: %s", sym, exc)

        if not quote_data:
            quote_data = {
                "current_price": None,
                "change": None,
                "change_percent": None,
                "open_price": None,
                "high_price": None,
                "low_price": None,
                "close_price": None,
                "volume": None,
                "bid_price": None,
                "ask_price": None,
                "data_as_of": None,
                "quote_source": "unavailable",
            }
            # Short negative-cache so clients see unavailable quickly without hammering scraper
            await cache_set(cache_key, quote_data, ttl_seconds=30)
            return ETFQuote(**quote_data)

        await cache_set(cache_key, quote_data, ttl_seconds=60)
        return ETFQuote(**quote_data)

    async def _format_etf_response(self, etf: ETF) -> ETFResponse:
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
        await self.ensure_seed_data()
        cache_key = f"etf:list:v1:{category}:{is_shariah_compliant}:{search}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFListResponse(**cached)

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

        formatted = [await self._format_etf_response(e) for e in etfs]
        shariah_count = sum(1 for e in formatted if e.is_shariah_compliant)
        conventional_count = len(formatted) - shariah_count

        response = ETFListResponse(
            total=len(formatted),
            shariah_count=shariah_count,
            conventional_count=conventional_count,
            etfs=formatted,
        )
        # Cache list response for 60 seconds
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=60)
        return response

    async def get_etf_by_symbol(self, symbol: str) -> ETFResponse:
        await self.ensure_seed_data()
        sym = symbol.strip().upper()
        res = await self.db.execute(select(ETF).where(ETF.symbol == sym))
        etf = res.scalars().first()
        if not etf:
            raise NotFoundError(f"ETF '{sym}' not found.")
        return await self._format_etf_response(etf)

    async def get_history(self, symbol: str, timeframe: str = "1M") -> ETFHistoryResponse:
        """Fetch historical timeseries with cache."""
        sym = symbol.strip().upper()
        cache_key = f"etf:hist:v1:{sym}:{timeframe}"
        cached = await cache_get(cache_key)
        if cached:
            return ETFHistoryResponse(**cached)

        history_items: List[ETFHistoryItem] = []
        try:
            import pypsx_toolkit
            import asyncio
            df = await asyncio.wait_for(
                asyncio.to_thread(pypsx_toolkit.get_historical, sym),
                timeout=3.0,
            )
            if hasattr(df, "iloc") and len(df) > 0:
                df = df.sort_index(ascending=True)
                for idx, row in df.tail(30 if timeframe == "1M" else 90 if timeframe == "3M" else 250).iterrows():
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
        except Exception as exc:
            log.debug("Historical fetch failed for ETF %s: %s", sym, exc)

        if not history_items:
            # Do not invent OHLCV — return empty history when scraper has no data
            response = ETFHistoryResponse(
                symbol=sym,
                timeframe=timeframe,
                count=0,
                history=[],
            )
            await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=60)
            return response

        response = ETFHistoryResponse(
            symbol=sym,
            timeframe=timeframe,
            count=len(history_items),
            history=history_items,
        )
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response

    async def get_performance(self, symbol: str) -> ETFPerformanceResponse:
        """Calculate returns from real history when available; otherwise nulls."""
        etf = await self.get_etf_by_symbol(symbol)
        sym = etf.symbol

        history = await self.get_history(sym, timeframe="1Y")
        closes = [h.close for h in history.history if h.close and h.close > 0]
        periods = ("1D", "1W", "1M", "3M", "1Y", "YTD")
        empty_ret = {k: None for k in periods}

        if len(closes) < 2:
            return ETFPerformanceResponse(
                symbol=sym,
                name=etf.name,
                benchmark_index=etf.benchmark_index,
                returns=empty_ret,
                benchmark_returns=empty_ret,
                tracking_difference_1m=None,
                volatility_annualized=None,
            )

        def _pct(lookback: int) -> float | None:
            if len(closes) <= lookback:
                return None
            base = closes[-(lookback + 1)]
            if not base:
                return None
            return round((closes[-1] / base - 1.0) * 100.0, 2)

        ret = {
            "1D": _pct(1),
            "1W": _pct(5),
            "1M": _pct(21),
            "3M": _pct(63),
            "1Y": _pct(min(250, len(closes) - 1)),
            "YTD": None,
        }

        # Approximate YTD using calendar filter when dates exist
        try:
            year = date.today().year
            ytd_items = [h for h in history.history if h.date.startswith(str(year))]
            if len(ytd_items) >= 2 and ytd_items[0].close:
                ret["YTD"] = round((ytd_items[-1].close / ytd_items[0].close - 1.0) * 100.0, 2)
        except Exception:
            ret["YTD"] = None

        return ETFPerformanceResponse(
            symbol=sym,
            name=etf.name,
            benchmark_index=etf.benchmark_index,
            returns=ret,
            benchmark_returns=empty_ret,
            tracking_difference_1m=None,
            volatility_annualized=None,
        )

    # ───────────────────────────────────────────────────────────────────
    # Admin CRUD
    # ───────────────────────────────────────────────────────────────────

    async def create_etf(self, data: ETFCreate) -> ETFResponse:
        sym = data.symbol.strip().upper()
        existing = await self.db.execute(select(ETF).where(ETF.symbol == sym))
        if existing.scalars().first():
            raise ConflictError(f"ETF '{sym}' already exists.")
        etf = ETF(
            symbol=sym,
            name=data.name.strip(),
            fund_manager=data.fund_manager.strip(),
            category=data.category.strip(),
            benchmark_index=data.benchmark_index.strip(),
            is_shariah_compliant=data.is_shariah_compliant,
            expense_ratio=data.expense_ratio,
            inception_date=data.inception_date,
            total_assets_pkr=data.total_assets_pkr,
            description=data.description,
            is_active=data.is_active,
        )
        self.db.add(etf)
        await self.db.flush()
        await self.db.refresh(etf)
        return await self._format_etf_response(etf)

    async def update_etf(self, symbol: str, data: ETFUpdate) -> ETFResponse:
        sym = symbol.strip().upper()
        res = await self.db.execute(select(ETF).where(ETF.symbol == sym))
        etf = res.scalars().first()
        if not etf:
            raise NotFoundError(f"ETF '{sym}' not found.")
        updates = data.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(etf, key, value.strip() if isinstance(value, str) else value)
        await self.db.flush()
        await self.db.refresh(etf)
        return await self._format_etf_response(etf)

    async def delete_etf(self, symbol: str) -> None:
        sym = symbol.strip().upper()
        res = await self.db.execute(select(ETF).where(ETF.symbol == sym))
        etf = res.scalars().first()
        if not etf:
            raise NotFoundError(f"ETF '{sym}' not found.")
        await self.db.delete(etf)
        await self.db.flush()
