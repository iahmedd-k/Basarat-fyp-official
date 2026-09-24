import asyncio
import logging
import math
import re
from datetime import datetime, timezone
from collections import defaultdict

import httpx
import pypsx_toolkit
from bs4 import BeautifulSoup

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
SECTOR_MAP_TTL_SECONDS = 86400  # PSX classifications rarely change; refresh daily
PSX_SCREENER_URL = "https://dps.psx.com.pk/screener"


_STATIC_SECTOR_MAP: dict[str, str] = {
    "ABL": "COMMERCIAL BANKS",
    "AKBL": "COMMERCIAL BANKS",
    "BAFL": "COMMERCIAL BANKS",
    "BAHL": "COMMERCIAL BANKS",
    "BOP": "COMMERCIAL BANKS",
    "FABL": "COMMERCIAL BANKS",
    "HBL": "COMMERCIAL BANKS",
    "HMB": "COMMERCIAL BANKS",
    "MCB": "COMMERCIAL BANKS",
    "MEBL": "COMMERCIAL BANKS",
    "NBP": "COMMERCIAL BANKS",
    "SCBPL": "COMMERCIAL BANKS",
    "UBL": "COMMERCIAL BANKS",
    "OGDC": "OIL & GAS EXPLORATION COMPANIES",
    "PPL": "OIL & GAS EXPLORATION COMPANIES",
    "MARI": "OIL & GAS EXPLORATION COMPANIES",
    "POL": "OIL & GAS EXPLORATION COMPANIES",
    "APL": "OIL & GAS MARKETING COMPANIES",
    "PSO": "OIL & GAS MARKETING COMPANIES",
    "SNGP": "OIL & GAS MARKETING COMPANIES",
    "SSGC": "OIL & GAS MARKETING COMPANIES",
    "ATRL": "REFINERY",
    "CNERGY": "REFINERY",
    "NRL": "REFINERY",
    "PRL": "REFINERY",
    "EFERT": "FERTILIZER",
    "ENGROH": "FERTILIZER",
    "FATIMA": "FERTILIZER",
    "FFC": "FERTILIZER",
    "BWCL": "CEMENT",
    "CHCC": "CEMENT",
    "DGKC": "CEMENT",
    "FCCL": "CEMENT",
    "KOHC": "CEMENT",
    "LUCK": "CEMENT",
    "MLCF": "CEMENT",
    "PIOC": "CEMENT",
    "POWER": "CEMENT",
    "HUBC": "POWER GENERATION & DISTRIBUTION",
    "KAPCO": "POWER GENERATION & DISTRIBUTION",
    "KEL": "POWER GENERATION & DISTRIBUTION",
    "NPL": "POWER GENERATION & DISTRIBUTION",
    "AIRLINK": "TECHNOLOGY & COMMUNICATION",
    "HUMNL": "TECHNOLOGY & COMMUNICATION",
    "PTC": "TECHNOLOGY & COMMUNICATION",
    "SYS": "TECHNOLOGY & COMMUNICATION",
    "TRG": "TECHNOLOGY & COMMUNICATION",
    "ABOT": "PHARMACEUTICALS",
    "AGP": "PHARMACEUTICALS",
    "CPHL": "PHARMACEUTICALS",
    "GLAXO": "PHARMACEUTICALS",
    "HALEON": "PHARMACEUTICALS",
    "HINOON": "PHARMACEUTICALS",
    "SEARL": "PHARMACEUTICALS",
    "SHFA": "PHARMACEUTICALS",
    "ATLH": "AUTOMOBILE ASSEMBLER",
    "HCAR": "AUTOMOBILE ASSEMBLER",
    "INDU": "AUTOMOBILE ASSEMBLER",
    "MTL": "AUTOMOBILE ASSEMBLER",
    "SAZEW": "AUTOMOBILE ASSEMBLER",
    "THALL": "AUTOMOBILE ASSEMBLER",
    "BNWM": "TEXTILE COMPOSITE",
    "GADT": "TEXTILE COMPOSITE",
    "IBFL": "TEXTILE COMPOSITE",
    "ILP": "TEXTILE COMPOSITE",
    "KTML": "TEXTILE COMPOSITE",
    "MEHT": "TEXTILE COMPOSITE",
    "NML": "TEXTILE COMPOSITE",
    "YOUW": "TEXTILE COMPOSITE",
    "GAL": "CHEMICAL",
    "GHGL": "CHEMICAL",
    "GHNI": "CHEMICAL",
    "LCI": "CHEMICAL",
    "LOTCHEM": "CHEMICAL",
    "TGL": "CHEMICAL",
    "INIL": "ENGINEERING",
    "ISL": "ENGINEERING",
    "PAEL": "ENGINEERING",
    "PABC": "ENGINEERING",
    "COLG": "FOOD & PERSONAL CARE PRODUCTS",
    "FFL": "FOOD & PERSONAL CARE PRODUCTS",
    "JDWS": "FOOD & PERSONAL CARE PRODUCTS",
    "MUREB": "FOOD & PERSONAL CARE PRODUCTS",
    "NATF": "FOOD & PERSONAL CARE PRODUCTS",
    "NESTLE": "FOOD & PERSONAL CARE PRODUCTS",
    "PAKT": "FOOD & PERSONAL CARE PRODUCTS",
    "RMPL": "FOOD & PERSONAL CARE PRODUCTS",
    "TREET": "FOOD & PERSONAL CARE PRODUCTS",
    "UPFL": "FOOD & PERSONAL CARE PRODUCTS",
    "AHCL": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "AICL": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "DCR": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "FHAM": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "HGFA": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "JVDC": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "PGLC": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "PIBTL": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "PKGS": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "PSEL": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "PSX": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "SRVI": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "SSOM": "INV. BANKS / INV. COS. / SECURITIES COS.",
    "TPLRF1": "INV. BANKS / INV. COS. / SECURITIES COS.",
}


class MarketService:
    MAIN_INDICES = {
        "KSE100": "KSE-100",
        "KSE30": "KSE-30",
        "KMI30": "KMI-30",
    }

    @staticmethod
    def _fetch_sector_map_sync() -> dict[str, str]:
        """Read PSX's public screener once to map symbols to sector names.

        The ALLSHR quote feed contains prices but omits sector labels. PSX's
        screener includes each symbol's sector code and the sector filter's
        code-to-name options, so combine those two fields here.
        """
        response = httpx.get(
            PSX_SCREENER_URL,
            headers={"User-Agent": "Mozilla/5.0 (compatible; BasaratMarketData/1.0)"},
            timeout=12.0,
            follow_redirects=True,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        sector_names: dict[str, str] = {}
        for option in soup.select("select option"):
            code = str(option.get("value") or "").strip()
            name = option.get_text(" ", strip=True)
            if re.fullmatch(r"08\d{2}", code) and name:
                sector_names[code] = name.upper()

        # PSX's current sector codes are stable; this table lets the screener
        # still classify rows if its sector select is rendered client-side.
        sector_names.update({
            "0801": "AUTOMOBILE ASSEMBLER",
            "0802": "AUTOMOBILE PARTS & ACCESSORIES",
            "0803": "CABLE & ELECTRICAL GOODS",
            "0804": "CEMENT",
            "0805": "CHEMICAL",
            "0806": "CLOSE - END MUTUAL FUND",
            "0807": "COMMERCIAL BANKS",
            "0808": "ENGINEERING",
            "0809": "FERTILIZER",
            "0810": "FOOD & PERSONAL CARE PRODUCTS",
            "0811": "GLASS & CERAMICS",
            "0812": "INSURANCE",
            "0813": "INV. BANKS / INV. COS. / SECURITIES COS.",
            "0814": "JUTE",
            "0815": "LEASING COMPANIES",
            "0816": "LEATHER & TANNERIES",
            "0818": "MISCELLANEOUS",
            "0819": "MODARABAS",
            "0820": "OIL & GAS EXPLORATION COMPANIES",
            "0821": "OIL & GAS MARKETING COMPANIES",
            "0822": "PAPER, BOARD & PACKAGING",
            "0823": "PHARMACEUTICALS",
            "0824": "POWER GENERATION & DISTRIBUTION",
            "0825": "REFINERY",
            "0826": "SUGAR & ALLIED INDUSTRIES",
            "0827": "SYNTHETIC & RAYON",
            "0828": "TECHNOLOGY & COMMUNICATION",
            "0829": "TEXTILE COMPOSITE",
            "0830": "TEXTILE SPINNING",
            "0831": "TEXTILE WEAVING",
            "0832": "TOBACCO",
            "0833": "TRANSPORT",
            "0834": "VANASPATI & ALLIED INDUSTRIES",
            "0835": "WOOLLEN",
            "0836": "REAL ESTATE INVESTMENT TRUST",
            "0837": "EXCHANGE TRADED FUNDS",
            "0838": "PROPERTY",
            })

        sector_map: dict[str, str] = {}
        for table in soup.find_all("table"):
            headers = [cell.get_text(" ", strip=True).upper() for cell in table.select("thead th")]
            if not headers:
                first_row = table.find("tr")
                headers = [cell.get_text(" ", strip=True).upper() for cell in first_row.find_all(["th", "td"])] if first_row else []
            if "SYMBOL" not in headers or "SECTOR" not in headers:
                continue
            symbol_index, sector_index = headers.index("SYMBOL"), headers.index("SECTOR")
            for row in table.select("tbody tr") or table.find_all("tr")[1:]:
                cells = row.find_all("td")
                if max(symbol_index, sector_index) >= len(cells):
                    continue
                symbol = cells[symbol_index].get_text(" ", strip=True).upper().split()[0]
                code = cells[sector_index].get_text(" ", strip=True)
                sector = sector_names.get(code)
                if symbol and sector:
                    sector_map[symbol] = sector
            if sector_map:
                break
        return sector_map

    @staticmethod
    def _load_sector_map_sync() -> dict[str, str]:
        """Use the daily cached PSX symbol-sector map, refreshing when absent."""
        cache_key = "market:sectors:symbol_map"
        cached = cache_get_sync(cache_key)
        if isinstance(cached, dict):
            return cached
        try:
            sector_map = MarketService._fetch_sector_map_sync()
            if sector_map:
                cache_set_sync(cache_key, sector_map, SECTOR_MAP_TTL_SECONDS)
                log.info("Loaded PSX sectors for %d symbols", len(sector_map))
                return sector_map
            cache_set_sync(cache_key, {}, 300)
        except Exception as exc:
            log.warning("PSX screener sector map unavailable: %s", exc)
            cache_set_sync(cache_key, {}, 300)

        # Fallback to static sector map when PSX screener is unreachable
        log.info("Using static sector map fallback with %d symbols", len(_STATIC_SECTOR_MAP))
        return _STATIC_SECTOR_MAP.copy()

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
    def _cache_freshness(timestamp_key: str, ttl_seconds: int) -> dict:
        fetched_at = cache_get_sync(timestamp_key)
        if not fetched_at:
            return {"as_of": None, "is_stale": True}
        try:
            stamp = datetime.fromisoformat(fetched_at.replace("Z", "+00:00"))
            age = (datetime.now(timezone.utc) - stamp.astimezone(timezone.utc)).total_seconds()
            return {"as_of": fetched_at, "is_stale": age > ttl_seconds}
        except (TypeError, ValueError):
            return {"as_of": None, "is_stale": True}

    @classmethod
    def indices_freshness(cls) -> dict:
        return cls._cache_freshness("market:indices:fetched_at", INDICES_TTL_SECONDS)

    @classmethod
    def constituents_freshness(cls, index_code: str) -> dict:
        return cls._cache_freshness(
            f"market:constituents:{index_code}:fetched_at", CONSTITUENTS_TTL_SECONDS
        )

    @staticmethod
    def _normalize_quotes(rows: list[dict]) -> list[dict]:
        """Reconcile provider change fields with the actual current and LDCP prices."""
        for row in rows:
            row.setdefault("name", row.get("symbol"))
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

    @staticmethod
    def _fetch_market_watch_frame():
        """Fetch quotes, falling back to PSX all-share constituents if needed."""
        try:
            raw = pypsx_toolkit.market_watch()
            if raw is not None and hasattr(raw, "iterrows") and not raw.empty:
                frame = raw.copy()
                frame.columns = [str(column).strip().upper() for column in frame.columns]
                return frame
        except Exception as exc:
            log.warning("PSX market watch failed; trying all-share quotes: %s", exc)

        try:
            raw = pypsx_toolkit.index_constituents("ALLSHR")
            if raw is not None and hasattr(raw, "iterrows") and not raw.empty:
                log.info("Loaded quote rows from PSX ALLSHR constituents fallback")
                frame = raw.copy()
                frame.columns = [str(column).strip().upper() for column in frame.columns]
                return frame
        except Exception as exc:
            log.warning("PSX all-share quote fallback failed: %s", exc)
        return None

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
                await cache_set("market:indices:fetched_at", datetime.now(timezone.utc).isoformat(), FALLBACK_TTL_SECONDS)
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
                await cache_set(
                    f"market:constituents:{index_code}:fetched_at",
                    datetime.now(timezone.utc).isoformat(),
                    FALLBACK_TTL_SECONDS,
                )
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
        raw = self._fetch_market_watch_frame()

        if raw is not None and hasattr(raw, "iterrows") and not raw.empty:
            previous_rows = cache_get_sync(fallback_key) or []
            previous_sectors = {
                str(item.get("symbol", "")).upper(): item.get("sector")
                for item in previous_rows
                if isinstance(item, dict) and item.get("sector")
            }
            sector_map = self._load_sector_map_sync()
            rows = []
            for symbol, row in raw.iterrows():
                ldcp = self._safe_float(row.get("LDCP"))
                current = self._safe_float(row.get("CURRENT"))
                reported_change = self._safe_float(row.get("CHANGE"))
                change = round(current - ldcp, 4) if current is not None and current > 0 and ldcp is not None and ldcp > 0 else reported_change
                change_pct = round((change / ldcp * 100) if ldcp else 0.0, 2)
                sector_val = (
                    row.get("SECTOR")
                    or previous_sectors.get(str(symbol).upper())
                    or sector_map.get(str(symbol).upper())
                )
                open_val = self._safe_float(row.get("OPEN"))
                high_val = self._safe_float(row.get("HIGH"))
                low_val = self._safe_float(row.get("LOW"))
                if open_val == 0.0:
                    open_val = ldcp
                if high_val == 0.0:
                    high_val = max(ldcp, current)
                if low_val == 0.0:
                    low_val = min(ldcp, current)
                rows.append({
                    "symbol": str(symbol),
                    "name": str(row.get("NAME") or row.get("COMPANY NAME") or symbol),
                    "sector": sector_val if sector_val else "Unclassified",
                    "ldcp": ldcp,
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "current": current,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": self._safe_int(row.get("VOLUME")),
                    "market_cap_m": self._safe_float(row.get("MARKET CAP (M)")),
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
                asyncio.to_thread(self._fetch_market_watch_frame),
                timeout=20.0,
            )
        except Exception as e:
            log.warning("External fetch of market watch and ALLSHR fallback failed: %s", e)

        if raw is not None and hasattr(raw, "iterrows") and not raw.empty:
            previous_rows = await cache_get(fallback_key) or []
            previous_sectors = {
                str(item.get("symbol", "")).upper(): item.get("sector")
                for item in previous_rows
                if isinstance(item, dict) and item.get("sector")
            }
            sector_map = await asyncio.to_thread(self._load_sector_map_sync)
            rows = []
            for symbol, row in raw.iterrows():
                ldcp = self._safe_float(row.get("LDCP"))
                current = self._safe_float(row.get("CURRENT"))
                reported_change = self._safe_float(row.get("CHANGE"))
                change = round(current - ldcp, 4) if current is not None and current > 0 and ldcp is not None and ldcp > 0 else reported_change
                change_pct = round((change / ldcp * 100) if ldcp else 0.0, 2)
                sector_val = (
                    row.get("SECTOR")
                    or previous_sectors.get(str(symbol).upper())
                    or sector_map.get(str(symbol).upper())
                )
                open_val = self._safe_float(row.get("OPEN"))
                high_val = self._safe_float(row.get("HIGH"))
                low_val = self._safe_float(row.get("LOW"))
                if open_val == 0.0:
                    open_val = ldcp
                if high_val == 0.0:
                    high_val = max(ldcp, current)
                if low_val == 0.0:
                    low_val = min(ldcp, current)
                rows.append({
                    "symbol": str(symbol),
                    "name": str(row.get("NAME") or row.get("COMPANY NAME") or symbol),
                    "sector": sector_val if sector_val else "Unclassified",
                    "ldcp": ldcp,
                    "open": open_val,
                    "high": high_val,
                    "low": low_val,
                    "current": current,
                    "change": change,
                    "change_pct": change_pct,
                    "volume": self._safe_int(row.get("VOLUME")),
                    "market_cap_m": self._safe_float(row.get("MARKET CAP (M)")),
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

        grouped = defaultdict(list)
        for quote in data:
            sector = str(quote.get("sector") or "").strip()
            if not sector or sector.casefold() in {"unclassified", "unknown"}:
                continue
            grouped[sector].append(quote)

        sector_performance = []
        for sector, quotes in grouped.items():
            changes = [self._safe_float(quote.get("change_pct")) for quote in quotes]
            gainers = [quote for quote, change in zip(quotes, changes) if change > 0]
            losers = [quote for quote, change in zip(quotes, changes) if change < 0]
            unchanged_count = len(quotes) - len(gainers) - len(losers)
            cap_values = [self._safe_float(quote.get("market_cap_m")) for quote in quotes]
            market_caps = [value for value in cap_values if value > 0]
            top_gainer = max(quotes, key=lambda quote: self._safe_float(quote.get("change_pct")))
            top_loser = min(quotes, key=lambda quote: self._safe_float(quote.get("change_pct")))
            sector_performance.append({
                "sector": sector,
                "avg_change_pct": round(sum(changes) / len(changes), 2),
                "companies": len(quotes),
                "advancing": len(gainers),
                "declining": len(losers),
                "unchanged": unchanged_count,
                "total_volume": sum(self._safe_int(quote.get("volume")) for quote in quotes),
                "market_cap_m": round(sum(market_caps), 2) if market_caps else None,
                "top_gainer_symbol": top_gainer.get("symbol"),
                "top_loser_symbol": top_loser.get("symbol"),
            })

        sector_performance.sort(key=lambda x: x["avg_change_pct"], reverse=True)

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
            **self.quote_freshness(),
        }

    async def get_sector_performance(self, order: str = "desc") -> dict:
        """Aggregate daily price performance and breadth for each classified sector."""
        data = await self.get_market_data()
        # Existing quote caches may predate sector enrichment. Fill them from
        # the bulk PSX screener in one request instead of leaving every group
        # empty until a scheduled quote refresh occurs.
        if data and not any(
            str(quote.get("sector") or "").strip().casefold() not in {"", "unclassified", "unknown"}
            for quote in data
        ):
            sector_map = await asyncio.to_thread(self._load_sector_map_sync)
            if sector_map:
                for quote in data:
                    quote["sector"] = sector_map.get(str(quote.get("symbol", "")).upper(), "Unclassified")
                await cache_set("market:quotes", data, QUOTES_TTL_SECONDS)
                await cache_set("market:quotes:last_known", data, FALLBACK_TTL_SECONDS)

        grouped = defaultdict(list)
        for quote in data:
            sector = str(quote.get("sector") or "").strip()
            if not sector or sector.casefold() in {"unclassified", "unknown"}:
                continue
            grouped[sector].append(quote)

        sectors = []
        for sector, quotes in grouped.items():
            changes = [self._safe_float(quote.get("change_pct")) for quote in quotes]
            gainers = [quote for quote, change in zip(quotes, changes) if change > 0]
            losers = [quote for quote, change in zip(quotes, changes) if change < 0]
            unchanged = len(quotes) - len(gainers) - len(losers)
            cap_values = [self._safe_float(quote.get("market_cap_m")) for quote in quotes]
            market_caps = [value for value in cap_values if value > 0]
            top_gainer = max(quotes, key=lambda quote: self._safe_float(quote.get("change_pct")))
            top_loser = min(quotes, key=lambda quote: self._safe_float(quote.get("change_pct")))
            sectors.append({
                "sector": sector,
                "avg_change_pct": round(sum(changes) / len(changes), 2),
                "companies": len(quotes),
                "advancing": len(gainers),
                "declining": len(losers),
                "unchanged": unchanged,
                "total_volume": sum(self._safe_int(quote.get("volume")) for quote in quotes),
                "market_cap_m": round(sum(market_caps), 2) if market_caps else None,
                "top_gainer_symbol": top_gainer.get("symbol"),
                "top_loser_symbol": top_loser.get("symbol"),
            })

        sectors.sort(key=lambda item: item["avg_change_pct"], reverse=order.lower() != "asc")
        classified = sum(len(quotes) for quotes in grouped.values())
        return {
            "sectors": sectors,
            "total_sectors": len(sectors),
            "total_companies": len(data),
            "classified_companies": classified,
            "unclassified_companies": len(data) - classified,
            **self.quote_freshness(),
        }
