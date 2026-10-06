"""
Assistant context cache on top of existing Basarat Redis.

Reuses market:* / stock:* / fund:* keys. Adds a thin universe profile bundle
for KSE100 + KSE30 + KMI30. Chat paths always fall back to MarketService /
StockService / DB when cache misses.
"""

from __future__ import annotations

import logging
import time as _py_time
from datetime import datetime, timezone
from typing import Any, Optional

from app.core.redis import cache_get, cache_set
from app.services.assistant_freshness import cache_age_seconds, is_fresh_enough
from app.services.market_service import MarketService, QUOTES_TTL_SECONDS
from app.services.stock_service import StockService

log = logging.getLogger(__name__)

UNIVERSE_KEY = "assistant:universe:v1"
UNIVERSE_TTL_SECONDS = 86400  # 24h profiles
INDEX_CODES = ("KSE100", "KSE30", "KMI30")

# Soft-live: reuse Redis quotes if younger than this
SOFT_LIVE_MAX_AGE_SECONDS = 180
# Hard-live: force refresh if cache older than this
HARD_LIVE_MAX_AGE_SECONDS = 60

# Process-level L1 memory caches for ultra-fast context resolution (sub-millisecond)
_L1_UNIVERSE: Optional[dict] = None
_L1_UNIVERSE_TS: float = 0.0
_L1_QUOTES_MAP: Optional[dict[str, dict]] = None
_L1_QUOTES_TS: float = 0.0


class AssistantContextCache:
    """Tiered assistant data access with cache → service → last_known fallbacks."""

    def __init__(
        self,
        market_service: Optional[MarketService] = None,
        stock_service: Optional[StockService] = None,
    ):
        self.market_service = market_service or MarketService()
        self.stock_service = stock_service or StockService()

    # ── Universe profiles (Tier A) ─────────────────────────────────────

    async def get_universe(self) -> dict:
        global _L1_UNIVERSE, _L1_UNIVERSE_TS
        now = _py_time.perf_counter()
        if _L1_UNIVERSE and (now - _L1_UNIVERSE_TS < 300.0):
            return _L1_UNIVERSE

        cached = await cache_get(UNIVERSE_KEY)
        if isinstance(cached, dict) and cached.get("symbols"):
            _L1_UNIVERSE = cached
            _L1_UNIVERSE_TS = now
            return cached
        return {"symbols": {}, "as_of": None, "indexes": {}}

    async def get_profile(self, symbol: str) -> Optional[dict]:
        sym = symbol.upper().strip()
        universe = await self.get_universe()
        profile = (universe.get("symbols") or {}).get(sym)
        if profile:
            return {**profile, "source": "assistant_universe"}

        # Fallback: pull from market quotes row / constituents maps
        row = await self._quote_row_from_market_cache(sym)
        if row:
            return {
                "symbol": sym,
                "name": row.get("name") or sym,
                "sector": row.get("sector"),
                "indexes": [],
                "source": "market_quotes_cache",
            }
        return None

    async def warm_universe(self, force_refresh_constituents: bool = False) -> dict:
        """Build/refresh assistant:universe:v1 from index constituents + quote catalog."""
        symbols: dict[str, dict] = {}
        indexes: dict[str, list[str]] = {}

        # Prefer existing quote catalog for name/sector (fast)
        quote_map: dict[str, dict] = {}
        try:
            rows = await self.market_service.get_market_data(read_only=True)
            for row in rows or []:
                if isinstance(row, dict) and row.get("symbol"):
                    quote_map[str(row["symbol"]).upper()] = row
        except Exception as e:
            log.warning("Universe warm: market quotes unavailable: %s", e)

        for code in INDEX_CODES:
            try:
                members = await self.market_service.get_index_constituents(
                    code,
                    force_refresh=force_refresh_constituents,
                    read_only=not force_refresh_constituents,
                )
            except Exception as e:
                log.warning("Universe warm: constituents %s failed: %s", code, e)
                members = []

            member_syms: list[str] = []
            for item in members or []:
                if isinstance(item, str):
                    sym = item.upper().strip()
                elif isinstance(item, dict):
                    sym = str(item.get("symbol") or item.get("Symbol") or "").upper().strip()
                else:
                    continue
                if not sym:
                    continue
                member_syms.append(sym)
                q = quote_map.get(sym) or {}
                existing = symbols.get(sym) or {
                    "symbol": sym,
                    "name": q.get("name") or sym,
                    "sector": q.get("sector"),
                    "indexes": [],
                }
                idxs = list(existing.get("indexes") or [])
                if code not in idxs:
                    idxs.append(code)
                existing["indexes"] = idxs
                if q.get("name"):
                    existing["name"] = q.get("name")
                if q.get("sector"):
                    existing["sector"] = q.get("sector")
                # Lean fundamentals from Redis fund cache if present (no scrape)
                fund = await cache_get(f"fund:v21:{sym}")
                if isinstance(fund, dict):
                    ratios = fund.get("ratios") or {}
                    existing["fundamentals"] = {
                        k: v
                        for k, v in {
                            "pe": ratios.get("pe") or ratios.get("pe_ratio") or fund.get("pe_ratio"),
                            "eps": ratios.get("eps"),
                            "dividend_yield": ratios.get("dividend_yield") or ratios.get("div_yield"),
                            "pb": ratios.get("pb") or ratios.get("pb_ratio"),
                            "market_cap_m": fund.get("market_cap_m") or q.get("market_cap_m"),
                        }.items()
                        if v is not None
                    }
                symbols[sym] = existing
            indexes[code] = member_syms

        payload = {
            "symbols": symbols,
            "indexes": indexes,
            "symbol_count": len(symbols),
            "as_of": datetime.now(timezone.utc).isoformat(),
        }
        await cache_set(UNIVERSE_KEY, payload, UNIVERSE_TTL_SECONDS)
        log.info(
            "Assistant universe warmed: %d symbols across %s",
            len(symbols),
            ", ".join(INDEX_CODES),
        )
        return payload

    # ── Quotes / market (Tier B / C) ───────────────────────────────────

    async def resolve_quote(
        self,
        symbol: str,
        *,
        hard_live: bool = False,
    ) -> dict:
        """
        Resolve a quote with ultra-fast L1/Redis lookup first, falling back to service.
        """
        sym = symbol.upper().strip()
        sources_tried: list[str] = ["market_quotes_cache"]
        as_of: Optional[str] = None
        refreshed: bool = False

        # Fast L1/Redis check
        row = await self._quote_row_from_market_cache(sym)
        if row and (row.get("current") not in (None, 0, 0.0) or row.get("ltp") not in (None, 0, 0.0)):
            as_of = row.get("as_of") or row.get("quote_as_of")
            age = cache_age_seconds(as_of)
            return self._normalize_quote(
                sym,
                row,
                as_of=as_of,
                age=age,
                stale=bool((age or 0) > SOFT_LIVE_MAX_AGE_SECONDS),
                source="market_quotes_cache",
                refreshed=False,
                hard_live=hard_live,
                sources_tried=sources_tried,
            )

        # Fallback to StockService quote
        sources_tried.append("stock_service.get_quote")
        try:
            import asyncio
            quote = await asyncio.wait_for(_to_thread(self.stock_service.get_quote, sym), timeout=1.5)
            if quote and (quote.get("current") not in (None, 0, 0.0) or quote.get("ltp") not in (None, 0, 0.0)):
                as_of = quote.get("as_of") or quote.get("quote_as_of")
                age = cache_age_seconds(as_of)
                return self._normalize_quote(
                    sym,
                    quote,
                    as_of=as_of,
                    age=age,
                    stale=bool((age or 0) > SOFT_LIVE_MAX_AGE_SECONDS),
                    source="stock_service_quote",
                    refreshed=False,
                    hard_live=hard_live,
                    sources_tried=sources_tried,
                )
        except Exception as e:
            log.info("Stock quote fallback failed for %s: %s", sym, e)

        # Overview last resort (slower)
        sources_tried.append("stock_service.get_overview")
        try:
            overview = await _to_thread(self.stock_service.get_overview, sym)
            if overview and overview.get("message") != "no data" and overview.get("ltp") not in (None, 0, 0.0):
                return {
                    "symbol": sym,
                    "name": overview.get("name") or sym,
                    "sector": overview.get("sector"),
                    "current_price": overview.get("ltp"),
                    "change": overview.get("change"),
                    "change_pct": overview.get("change_pct"),
                    "volume": overview.get("volume"),
                    "day_range": overview.get("day_range"),
                    "pe_ratio": overview.get("pe_ratio"),
                    "market_cap_m": overview.get("market_cap_m"),
                    "quote_as_of": overview.get("quote_as_of") or as_of,
                    "quote_is_stale": overview.get("quote_is_stale", True),
                    "source": "stock_service_overview",
                    "refreshed": refreshed,
                    "hard_live_requested": hard_live,
                    "sources_tried": sources_tried,
                }
        except Exception as e:
            log.info("Overview fallback failed for %s: %s", sym, e)

        return {
            "symbol": sym,
            "current_price": None,
            "quote_is_stale": True,
            "quote_as_of": as_of,
            "source": "unavailable",
            "refreshed": refreshed,
            "hard_live_requested": hard_live,
            "sources_tried": sources_tried,
            "unavailable_reason": "No quote found in Redis market cache, StockService quote, or overview",
        }

    async def resolve_market_snapshot(self, *, hard_live: bool = False) -> dict:
        """Indices + breadth + gainers/losers with soft/hard live policy and caching."""
        cache_key = "assistant:market_snapshot"
        if not hard_live:
            cached = await cache_get(cache_key)
            if isinstance(cached, dict) and cached.get("breadth"):
                return cached

        sources_tried: list[str] = ["market_quotes_cache"]
        refreshed = False

        try:
            indices = await self.market_service.get_indices(
                force_refresh=False,
                read_only=True,
            )
        except Exception as e:
            log.warning("Indices fetch failed: %s", e)
            indices = []
            sources_tried.append("indices_failed")

        try:
            rows = await cache_get("market:quotes")
            if not rows:
                rows = await self.market_service.get_market_data(read_only=True)
        except Exception as e:
            log.warning("Market rows fetch failed: %s", e)
            rows = []
            sources_tried.append("quotes_failed")

        rows = [r for r in (rows or []) if isinstance(r, dict)]
        market: dict[str, Any] = {
            "quote_freshness": {"is_stale": False},
            "refreshed": refreshed,
            "hard_live_requested": hard_live,
            "sources_tried": sources_tried,
            "data_mode": "hard_live" if hard_live else "soft_live",
        }
        if indices:
            market["indices"] = indices
        if rows:
            advancing = sum(1 for r in rows if (r.get("change_pct") or 0) > 0)
            declining = sum(1 for r in rows if (r.get("change_pct") or 0) < 0)
            market["breadth"] = {
                "symbols_count": len(rows),
                "advancing": advancing,
                "declining": declining,
                "unchanged": len(rows) - advancing - declining,
            }
            market["top_gainers"] = sorted(
                rows, key=lambda r: r.get("change_pct") or 0, reverse=True
            )[:5]
            market["top_losers"] = sorted(
                rows, key=lambda r: r.get("change_pct") or 0
            )[:5]
            await cache_set(cache_key, market, ttl_seconds=30)
        else:
            market["unavailable_reason"] = "Market quote catalog empty after cache and refresh attempts"
        return market

    async def resolve_fundamentals(self, symbol: str) -> Optional[dict]:
        """Lean fundamentals: fund Redis → StockService (timeout-friendly caller)."""
        sym = symbol.upper().strip()
        for key in (f"fund:v21:{sym}", f"stock:raw_fundamentals:v4:{sym}"):
            cached = await cache_get(key)
            if isinstance(cached, dict) and cached:
                ratios = cached.get("ratios") or cached
                compact = {
                    k: v
                    for k, v in {
                        "pe": ratios.get("pe") or ratios.get("pe_ratio") or cached.get("pe_ratio"),
                        "eps": ratios.get("eps") or cached.get("eps"),
                        "dividend_yield": ratios.get("dividend_yield") or ratios.get("div_yield"),
                        "pb": ratios.get("pb") or ratios.get("pb_ratio"),
                        "market_cap_m": cached.get("market_cap_m"),
                    }.items()
                    if v is not None
                }
                if compact:
                    compact["source"] = key
                    return compact

        try:
            import asyncio

            fundamentals = await asyncio.wait_for(
                _to_thread(self.stock_service.get_fundamentals, sym),
                timeout=4.0,
            )
            if isinstance(fundamentals, dict):
                ratios = fundamentals.get("ratios") or {}
                profile = fundamentals.get("equity_profile") or fundamentals.get("company_profile") or {}
                compact = {
                    k: v
                    for k, v in {
                        "pe": ratios.get("pe") or ratios.get("pe_ratio"),
                        "eps": ratios.get("eps") or profile.get("eps"),
                        "dividend_yield": ratios.get("dividend_yield") or ratios.get("div_yield"),
                        "pb": ratios.get("pb") or ratios.get("pb_ratio"),
                    }.items()
                    if v is not None
                }
                if compact:
                    compact["source"] = "stock_service_fundamentals"
                    return compact
        except Exception as e:
            log.info("Fundamentals resolve failed for %s: %s", sym, e)
        return None

    async def _quote_row_from_market_cache(self, symbol: str) -> Optional[dict]:
        global _L1_QUOTES_MAP, _L1_QUOTES_TS
        sym = symbol.upper().strip()
        now = _py_time.perf_counter()

        if _L1_QUOTES_MAP and (now - _L1_QUOTES_TS < 15.0):
            return _L1_QUOTES_MAP.get(sym)

        # Primary redis key
        rows = await cache_get("market:quotes")
        if not rows:
            rows = await cache_get("market:quotes:last_known")
        if not isinstance(rows, list):
            # Service path (read_only) as another fallback
            try:
                rows = await self.market_service.get_market_data(read_only=True)
            except Exception:
                rows = []

        q_map: dict[str, dict] = {}
        for row in rows or []:
            if isinstance(row, dict) and row.get("symbol"):
                q_map[str(row["symbol"]).upper().strip()] = row

        _L1_QUOTES_MAP = q_map
        _L1_QUOTES_TS = now
        return q_map.get(sym)

    @staticmethod
    def _normalize_quote(
        symbol: str,
        row: dict,
        *,
        as_of: Optional[str],
        age: Optional[float],
        stale: bool,
        source: str,
        refreshed: bool,
        hard_live: bool,
        sources_tried: list[str],
    ) -> dict:
        current = row.get("current") if row.get("current") is not None else row.get("ltp")
        return {
            "symbol": symbol,
            "name": row.get("name") or symbol,
            "sector": row.get("sector"),
            "current_price": current,
            "change": row.get("change"),
            "change_pct": row.get("change_pct"),
            "volume": row.get("volume"),
            "market_cap_m": row.get("market_cap_m"),
            "quote_as_of": as_of or row.get("as_of") or row.get("quote_as_of"),
            "quote_age_seconds": age,
            "quote_is_stale": stale,
            "source": source,
            "refreshed": refreshed,
            "hard_live_requested": hard_live,
            "sources_tried": sources_tried,
            "quotes_ttl_seconds": QUOTES_TTL_SECONDS,
        }


async def _to_thread(fn, *args):
    import asyncio

    return await asyncio.to_thread(fn, *args)


# Module-level helper for Celery warm task
async def warm_assistant_universe(force_refresh_constituents: bool = False) -> dict:
    return await AssistantContextCache().warm_universe(
        force_refresh_constituents=force_refresh_constituents
    )
