import asyncio
import logging
import math
from collections import defaultdict

import pypsx_toolkit

from app.core.redis import (
    cache_get,
    cache_get_sync,
    cache_set,
    cache_set_sync,
)

log = logging.getLogger(__name__)

CACHE_TTL_SECONDS = 60
CONSTITUENTS_TTL_SECONDS = 300


class MarketService:
    MAIN_INDICES = {
        "KSE100": "KSE-100",
        "KSE30": "KSE-30",
        "KMI30": "KMI-30",
    }

    @staticmethod
    def _safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            v = float(value)
            return default if math.isnan(v) or math.isinf(v) else v
        except (TypeError, ValueError):
            return default

    @staticmethod
    def _safe_int(value, default=0):
        if value is None:
            return default
        try:
            v = float(value)
            return default if math.isnan(v) or math.isinf(v) else int(v)
        except (TypeError, ValueError):
            return default

    async def get_indices(self) -> list[dict]:
        cache_key = "market:indices"
        cached = await cache_get(cache_key)
        if cached is not None:
            log.debug("Indices cache hit from Redis")
            return cached

        log.info("Fetching indices from external API")
        raw = await asyncio.to_thread(pypsx_toolkit.get_indices)

        dropped = [
            code for code in raw.index
            if code not in self.MAIN_INDICES
        ]
        if dropped:
            log.warning("Dropping indices not in MAIN_INDICES: %s", dropped)

        results = [
            {
                "index": self.MAIN_INDICES.get(code, code),
                "code": code,
                "current": self._safe_float(row["CURRENT"]),
                "change": self._safe_float(row["CHANGE"]),
                "change_pct": self._safe_float(row["PERCENTAGE_CHANGE"]),
                "high": self._safe_float(row["HIGH"]),
                "low": self._safe_float(row["LOW"]),
            }
            for code, row in raw.iterrows()
            if code in self.MAIN_INDICES
        ]

        await cache_set(cache_key, results, CACHE_TTL_SECONDS)
        log.info("Stored %d indices in centralized cache", len(results))
        return results

    async def get_index_constituents(self, index_code: str) -> list[dict]:
        cache_key = f"market:constituents:{index_code}"
        cached = await cache_get(cache_key)
        if cached is not None:
            log.debug("Constituents cache hit from Redis for %s", index_code)
            return cached

        log.info("Fetching constituents for %s from external API", index_code)
        raw = await asyncio.to_thread(pypsx_toolkit.index_constituents, index_code)

        import pandas as pd
        if raw is None or (isinstance(raw, pd.DataFrame) and raw.empty):
            log.warning("Empty constituents data for %s", index_code)
            return []

        results = []
        for symbol, row in raw.iterrows():
            try:
                results.append({
                    "symbol": str(symbol),
                    "name": str(row.get("NAME", symbol)),
                    "ldcp": self._safe_float(row.get("LDCP")),
                    "current": self._safe_float(row.get("CURRENT")),
                    "change": self._safe_float(row.get("CHANGE")),
                    "change_pct": self._safe_float(row.get("CHANGE %")),
                    "weight_pct": self._safe_float(row.get("IDX WTG %")),
                    "index_points": self._safe_float(row.get("IDX POINT")),
                    "volume": self._safe_int(row.get("VOLUME")),
                    "freefloat_m": self._safe_float(row.get("FREEFLOAT (M)")),
                    "market_cap_m": self._safe_float(row.get("MARKET CAP (M)")),
                })
            except Exception:
                log.warning("Skipping malformed constituent row: %s", symbol, exc_info=True)
                continue

        await cache_set(cache_key, results, CONSTITUENTS_TTL_SECONDS)
        log.info("Stored %d constituents for %s in centralized cache", len(results), index_code)
        return results

    def get_market_data_sync(self, force_refresh: bool = False) -> list[dict]:
        """Synchronous market data fetch with centralized Redis caching."""
        cache_key = "market:quotes"
        if not force_refresh:
            cached = cache_get_sync(cache_key)
            if cached is not None:
                log.debug("Market data cache hit from Redis (sync)")
                return cached

        log.info("Fetching market watch from external API (sync)")
        raw = pypsx_toolkit.market_watch()

        rows = []
        for symbol, row in raw.iterrows():
            ldcp = self._safe_float(row.get("LDCP"))
            change = self._safe_float(row.get("Change"))
            change_pct = round((change / ldcp * 100) if ldcp else 0.0, 2)
            rows.append({
                "symbol": str(symbol),
                "sector": str(row.get("Sector", "")),
                "ldcp": ldcp,
                "open": self._safe_float(row.get("Open")),
                "high": self._safe_float(row.get("High")),
                "low": self._safe_float(row.get("Low")),
                "current": self._safe_float(row.get("Current")),
                "change": change,
                "change_pct": change_pct,
                "volume": self._safe_int(row.get("Volume")),
            })

        cache_set_sync(cache_key, rows, CACHE_TTL_SECONDS)
        log.info("Stored %d market quotes in centralized cache (sync)", len(rows))
        return rows

    async def get_market_data(self, force_refresh: bool = False) -> list[dict]:
        cache_key = "market:quotes"
        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached is not None:
                log.debug("Market data cache hit from Redis (async)")
                return cached

        log.info("Fetching market watch from external API")
        raw = await asyncio.to_thread(pypsx_toolkit.market_watch)

        rows = []
        for symbol, row in raw.iterrows():
            ldcp = self._safe_float(row.get("LDCP"))
            change = self._safe_float(row.get("Change"))
            change_pct = round((change / ldcp * 100) if ldcp else 0.0, 2)
            rows.append({
                "symbol": str(symbol),
                "sector": str(row.get("Sector", "")),
                "ldcp": ldcp,
                "open": self._safe_float(row.get("Open")),
                "high": self._safe_float(row.get("High")),
                "low": self._safe_float(row.get("Low")),
                "current": self._safe_float(row.get("Current")),
                "change": change,
                "change_pct": change_pct,
                "volume": self._safe_int(row.get("Volume")),
            })

        await cache_set(cache_key, rows, CACHE_TTL_SECONDS)
        log.info("Stored %d market quotes in centralized cache", len(rows))
        return rows

    async def get_top_gainers(self, limit: int = 10) -> list[dict]:
        data = await self.get_market_data()
        return sorted(data, key=lambda d: d["change_pct"], reverse=True)[:limit]

    async def get_top_losers(self, limit: int = 10) -> list[dict]:
        data = await self.get_market_data()
        return sorted(data, key=lambda d: d["change_pct"])[:limit]

    async def get_volume_spikes(self, limit: int = 10) -> list[dict]:
        data = await self.get_market_data()
        return sorted(data, key=lambda d: d["volume"], reverse=True)[:limit]

    async def get_sentiment_overview(self) -> dict:
        data = await self.get_market_data()
        advancing = sum(1 for d in data if d["change_pct"] > 0)
        declining = sum(1 for d in data if d["change_pct"] < 0)
        unchanged = len(data) - advancing - declining
        total = len(data)

        if declining == 0:
            ratio = float(advancing) if advancing > 0 else 1.0
        else:
            ratio = advancing / declining

        if ratio >= 2:
            market_mood = "strongly_bullish"
        elif ratio >= 1.5:
            market_mood = "bullish"
        elif ratio >= 1.1:
            market_mood = "slightly_bullish"
        elif ratio <= 0.5:
            market_mood = "strongly_bearish"
        elif ratio <= 0.67:
            market_mood = "bearish"
        elif ratio <= 0.9:
            market_mood = "slightly_bearish"
        else:
            market_mood = "neutral"

        sectors = defaultdict(lambda: {"total_change_pct": 0.0, "count": 0})
        for d in data:
            s = sectors[d["sector"]]
            s["total_change_pct"] += d["change_pct"]
            s["count"] += 1

        sector_performance = sorted(
            [
                {
                    "sector": sector,
                    "avg_change_pct": round(stats["total_change_pct"] / stats["count"], 2),
                    "companies": stats["count"],
                }
                for sector, stats in sectors.items()
            ],
            key=lambda x: x["avg_change_pct"],
            reverse=True,
        )

        top_movers = sorted(
            data,
            key=lambda d: abs(d["change_pct"]),
            reverse=True,
        )[:5]

        return {
            "market_mood": market_mood,
            "advancing": advancing,
            "declining": declining,
            "unchanged": unchanged,
            "advance_decline_ratio": round(ratio, 2),
            "gainers_pct": round(advancing / total * 100, 1) if total else 0,
            "losers_pct": round(declining / total * 100, 1) if total else 0,
            "sector_performance": sector_performance,
            "top_movers": top_movers,
        }
