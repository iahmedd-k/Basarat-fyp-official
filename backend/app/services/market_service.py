import asyncio
import logging
import math
from datetime import datetime, timezone
from collections import defaultdict

import pypsx_toolkit

from app.core.redis import (
    cache_get,
    cache_get_sync,
    cache_set,
    cache_set_sync,
)

log = logging.getLogger(__name__)

QUOTES_TTL_SECONDS = 600  # refreshed by Celery every 5 minutes
INDICES_TTL_SECONDS = 28800  # 8 hours; Celery refreshes every 6 hours
CONSTITUENTS_TTL_SECONDS = 86400  # 24 hours; Celery refreshes daily
FALLBACK_TTL_SECONDS = 86400 * 7  # 7 days persistent fallback


class MarketService:
    MAIN_INDICES = {
        "KSE100": "KSE-100",
        "KSE30": "KSE-30",
        "KMI30": "KMI-30",
    }

    @staticmethod
    def quote_freshness() -> dict:
        """Return the timestamp of the last successful live market-watch fetch."""
        fetched_at = cache_get_sync("market:quotes:fetched_at")
        if not fetched_at:
            return {"as_of": None, "is_stale": True}
        try:
            stamp = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
            return {"as_of": fetched_at, "is_stale": age > QUOTES_TTL_SECONDS}
        except (TypeError, ValueError):
            return {"as_of": None, "is_stale": True}

    @staticmethod
    def _normalize_quotes(rows: list[dict]) -> list[dict]:
        """Reconcile provider change fields with the actual current and LDCP prices."""
        for row in rows:
            current = MarketService._safe_float(row.get("current"))
            ldcp = MarketService._safe_float(row.get("ldcp"))
            if current > 0 and ldcp > 0:
                change = round(current - ldcp, 4)
                row["change"] = change
                row["change_pct"] = round(change / ldcp * 100, 2)
        return rows

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

    async def get_indices(self, force_refresh: bool = False, read_only: bool = True) -> list[dict]:
        cache_key = "market:indices"
        fallback_key = "market:indices:last_known"
        cached = None if force_refresh else await cache_get(cache_key)
        if cached is not None and len(cached) > 0:
            log.debug("Indices cache hit from Redis")
            return cached

        if read_only and not force_refresh:
            last_known = await cache_get(fallback_key)
            if last_known:
                log.info("Serving %d indices from stale fallback cache", len(last_known))
                return last_known
            return []

        log.info("Fetching indices from external API")
        raw = None
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(pypsx_toolkit.get_indices),
                timeout=12.0,
            )
        except Exception as e:
            log.warning("External fetch of indices failed: %s", e)

        if raw is not None and hasattr(raw, "iterrows") and not raw.empty:
            results = []
            for code, row in raw.iterrows():
                code_str = str(code).strip()
                results.append({
                    "index": self.MAIN_INDICES.get(code_str, code_str),
                    "code": code_str,
                    "current": self._safe_float(row.get("CURRENT")),
                    "change": self._safe_float(row.get("CHANGE")),
                    "change_pct": self._safe_float(row.get("PERCENTAGE_CHANGE")),
                    "high": self._safe_float(row.get("HIGH")),
                    "low": self._safe_float(row.get("LOW")),
                })

            # Prioritize core benchmark indices first (KSE100, KSE30, KMI30, ALLSHR)
            priority_order = {"KSE100": 0, "KSE30": 1, "KMI30": 2, "ALLSHR": 3, "KMIALLSHR": 4, "BKTI": 5, "OGTI": 6, "PSXDIV20": 7}
            results.sort(key=lambda x: priority_order.get(x["code"], 99))

            if results:
                await cache_set(cache_key, results, INDICES_TTL_SECONDS)
                await cache_set(fallback_key, results, FALLBACK_TTL_SECONDS)
                log.info("Stored %d indices in centralized cache", len(results))
                return results

        # Fallback to last known indices if external call failed or timed out
        last_known = await cache_get(fallback_key)
        if last_known and len(last_known) > 0:
            log.info("Serving %d indices from fallback cache", len(last_known))
            return last_known

        return []

    async def get_index_constituents(
        self, index_code: str, force_refresh: bool = False, read_only: bool = True
    ) -> list[dict]:
        cache_key = f"market:constituents:{index_code}"
        fallback_key = f"market:constituents:last_known:{index_code}"
        cached = None if force_refresh else await cache_get(cache_key)
        if cached is not None and len(cached) > 0:
            log.debug("Constituents cache hit from Redis for %s", index_code)
            return cached

        if read_only and not force_refresh:
            last_known = await cache_get(fallback_key)
            if last_known:
                log.info("Serving %d stale constituents for %s", len(last_known), index_code)
                return last_known
            return []

        log.info("Fetching constituents for %s from external API", index_code)
        raw = None
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(pypsx_toolkit.index_constituents, index_code),
                timeout=15.0,
            )
        except Exception as e:
            log.warning("External fetch of constituents for %s failed: %s", index_code, e)

        import pandas as pd
        if raw is not None and isinstance(raw, pd.DataFrame) and not raw.empty:
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

            if results:
                await cache_set(cache_key, results, CONSTITUENTS_TTL_SECONDS)
                await cache_set(fallback_key, results, FALLBACK_TTL_SECONDS)
                log.info("Stored %d constituents for %s in centralized cache", len(results), index_code)
                return results

        # Fallback to persistent last-known snapshot if external PSX request timed out or was empty
        last_known = await cache_get(fallback_key)
        if last_known and len(last_known) > 0:
            log.info("Serving %d constituents for %s from persistent fallback cache", len(last_known), index_code)
            return last_known

        log.warning("No constituents data available for %s", index_code)
        return []

    def get_market_data_sync(self, force_refresh: bool = False, read_only: bool = True) -> list[dict]:
        """Synchronous market data fetch with centralized Redis caching."""
        cache_key = "market:quotes"
        fallback_key = "market:quotes:last_known"
        if not force_refresh:
            cached = cache_get_sync(cache_key)
            if cached is not None and len(cached) > 0:
                log.debug("Market data cache hit from Redis (sync)")
                return self._normalize_quotes(cached)

        if read_only and not force_refresh:
            last_known = cache_get_sync(fallback_key)
            if last_known:
                log.info("Serving %d market quotes from sync stale fallback", len(last_known))
                return self._normalize_quotes(last_known)
            return []

        log.info("Fetching market watch from external API (sync)")
        raw = None
        try:
            raw = pypsx_toolkit.market_watch()
        except Exception as exc:
            log.warning("External fetch of market watch failed (sync): %s", exc)

        if raw is not None and hasattr(raw, "iterrows") and not raw.empty:
            rows = []
            for symbol, row in raw.iterrows():
                ldcp = self._safe_float(row.get("LDCP"))
                current = self._safe_float(row.get("Current"))
                reported_change = self._safe_float(row.get("Change"))
                change = round(current - ldcp, 4) if current is not None and current > 0 and ldcp is not None and ldcp > 0 else reported_change
                change_pct = round((change / ldcp * 100) if ldcp else 0.0, 2)
                rows.append({
                    "symbol": str(symbol),
                    "sector": str(row.get("Sector", "")),
                    "ldcp": ldcp,
                    "open": self._safe_float(row.get("Open")),
                    "high": self._safe_float(row.get("High")),
                    "low": self._safe_float(row.get("Low")),
                    "current": current,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": self._safe_int(row.get("Volume")),
                })

            cache_set_sync(cache_key, rows, QUOTES_TTL_SECONDS)
            cache_set_sync(fallback_key, rows, FALLBACK_TTL_SECONDS)
            cache_set_sync("market:quotes:fetched_at", datetime.now(timezone.utc).isoformat(), FALLBACK_TTL_SECONDS)
            log.info("Stored %d market quotes in centralized cache (sync)", len(rows))
            return rows

        # Fallback to last known if available
        last_known = cache_get_sync(fallback_key)
        if last_known and len(last_known) > 0:
            log.info("Serving %d market quotes from sync fallback cache", len(last_known))
            return self._normalize_quotes(last_known)

        return []

    async def get_market_data(self, force_refresh: bool = False, read_only: bool = True) -> list[dict]:
        cache_key = "market:quotes"
        fallback_key = "market:quotes:last_known"
        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached is not None and len(cached) > 0:
                log.debug("Market data cache hit from Redis (async)")
                return self._normalize_quotes(cached)

        if read_only and not force_refresh:
            last_known = await cache_get(fallback_key)
            if last_known:
                log.info("Serving %d market quotes from stale fallback", len(last_known))
                return self._normalize_quotes(last_known)
            return []

        log.info("Fetching market watch from external API")
        raw = None
        try:
            raw = await asyncio.wait_for(
                asyncio.to_thread(pypsx_toolkit.market_watch),
                timeout=15.0,
            )
        except Exception as e:
            log.warning("External fetch of market watch failed: %s", e)

        if raw is not None and hasattr(raw, "iterrows") and not raw.empty:
            rows = []
            for symbol, row in raw.iterrows():
                ldcp = self._safe_float(row.get("LDCP"))
                current = self._safe_float(row.get("Current"))
                reported_change = self._safe_float(row.get("Change"))
                change = round(current - ldcp, 4) if current is not None and current > 0 and ldcp is not None and ldcp > 0 else reported_change
                change_pct = round((change / ldcp * 100) if ldcp else 0.0, 2)
                rows.append({
                    "symbol": str(symbol),
                    "sector": str(row.get("Sector", "")),
                    "ldcp": ldcp,
                    "open": self._safe_float(row.get("Open")),
                    "high": self._safe_float(row.get("High")),
                    "low": self._safe_float(row.get("Low")),
                    "current": current,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": self._safe_int(row.get("Volume")),
                })

            if rows:
                await cache_set(cache_key, rows, QUOTES_TTL_SECONDS)
                await cache_set(fallback_key, rows, FALLBACK_TTL_SECONDS)
                await cache_set("market:quotes:fetched_at", datetime.now(timezone.utc).isoformat(), FALLBACK_TTL_SECONDS)
                log.info("Stored %d market quotes in centralized cache", len(rows))
                return rows

        # Fallback to persistent last-known market quotes
        last_known = await cache_get(fallback_key)
        if last_known and len(last_known) > 0:
            log.info("Serving %d market quotes from persistent fallback cache", len(last_known))
            return self._normalize_quotes(last_known)

        return []

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
