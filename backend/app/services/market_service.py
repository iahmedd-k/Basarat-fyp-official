import asyncio
import logging
import math
import re
from datetime import datetime, timezone
from collections import defaultdict
from typing import Any

import httpx
try:
    import pypsx_toolkit
except Exception:
    pypsx_toolkit = None
from bs4 import BeautifulSoup

from app.core.config import get_settings
from app.core.redis import (
    cache_get,
    cache_get_sync,
    cache_set,
    cache_set_sync,
)

log = logging.getLogger(__name__)


def _quotes_ttl() -> int:
    """Redis TTL for live board quotes (session Celery refresh + buffer)."""
    try:
        return max(30, int(get_settings().MARKET_QUOTES_TTL_SECONDS))
    except Exception:
        return 90


# Kept as module attribute for importers; prefer _quotes_ttl() at write time.
QUOTES_TTL_SECONDS = 90
INDICES_TTL_SECONDS = 28800  # 8 hours; refreshed with close/weekly jobs
CONSTITUENTS_TTL_SECONDS = 86400  # 24 hours; Celery refreshes weekly
FALLBACK_TTL_SECONDS = 86400 * 7  # 7 days persistent fallback
SECTOR_MAP_TTL_SECONDS = 86400  # PSX classifications rarely change; refresh daily
PSX_SCREENER_URL = "https://dps.psx.com.pk/screener"


_STATIC_SCREENER_CACHE: list[dict] = []
_STATIC_SCREENER_TIMESTAMP: float = 0.0

SECTOR_CODE_TO_NAME: dict[str, str] = {
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
    "0817": "MISCELLANEOUS",
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
    "0839": "FUTURE CONTRACTS",
}

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
    def _normalize_sector_code_or_name(val: Any) -> str | None:
        """Normalize sector names or numeric codes (e.g. '0807' -> 'COMMERCIAL BANKS')."""
        if val is None:
            return None
        s = str(val).strip()
        if not s or s.casefold() in {"none", "null", "nan", "unclassified", "unknown", "default"}:
            return None
        if s.isdigit():
            padded = s.zfill(4)
            if padded in SECTOR_CODE_TO_NAME:
                return SECTOR_CODE_TO_NAME[padded]
        if s.upper() in SECTOR_CODE_TO_NAME.values():
            return s.upper()
        for name in SECTOR_CODE_TO_NAME.values():
            if s.casefold() == name.casefold():
                return name
        return s.upper()

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

        sector_names: dict[str, str] = dict(SECTOR_CODE_TO_NAME)
        for option in soup.select("select option"):
            code = str(option.get("value") or "").strip()
            name = option.get_text(" ", strip=True)
            if re.fullmatch(r"08\d{2}", code) and name:
                sector_names[code] = name.upper()

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
                sector = sector_names.get(code) or MarketService._normalize_sector_code_or_name(code)
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
            return {"as_of": fetched_at, "is_stale": age > _quotes_ttl()}
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
        """Normalize cached quotes without presenting missing OHLC as real zero prices."""
        normalized = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            symbol = str(row.get("symbol") or "").strip()
            if not symbol or symbol.casefold() == "nan":
                continue
            row["symbol"] = symbol.upper()
            row["name"] = str(row.get("name") or symbol)
            sector = row.get("sector")
            norm_sec = MarketService._normalize_sector_code_or_name(sector)
            row["sector"] = norm_sec if norm_sec else None
            row["volume"] = MarketService._safe_int(row.get("volume"))
            market_cap = MarketService._positive_or_none(row.get("market_cap_m"))
            row["market_cap_m"] = market_cap
            for field in ("open", "high", "low"):
                value = MarketService._safe_float(row.get(field), default=None)
                row[field] = value if value is not None and value > 0 else None
            current = MarketService._positive_or_none(row.get("current"))
            ldcp = MarketService._positive_or_none(row.get("ldcp"))
            row["current"] = current
            row["ldcp"] = ldcp
            if current is not None and ldcp is not None:
                change = round(current - ldcp, 4)
                row["change"] = change
                row["change_pct"] = round(change / ldcp * 100, 2)
            else:
                row["change"] = None
                row["change_pct"] = None
            normalized.append(row)
        return normalized

    @staticmethod
    def _safe_float(value, default=0.0):
        if value is None:
            return default
        try:
            v = float(value)
            return default if math.isnan(v) or math.isinf(v) else v
        except (TypeError, ValueError):
            return default

    @classmethod
    def _positive_or_none(cls, value):
        number = cls._safe_float(value, default=None)
        return number if number is not None and number > 0 else None

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
        """Fetch quotes, falling back to PSX all-share constituents and direct screener if needed."""
        if pypsx_toolkit and hasattr(pypsx_toolkit, "market_watch"):
            try:
                raw = pypsx_toolkit.market_watch()
                if raw is not None and hasattr(raw, "iterrows") and not raw.empty:
                    frame = raw.copy()
                    frame.columns = [str(column).strip().upper() for column in frame.columns]
                    return frame
            except Exception as exc:
                log.warning("PSX market watch failed; trying all-share quotes: %s", exc)

        if pypsx_toolkit and hasattr(pypsx_toolkit, "index_constituents"):
            try:
                raw = pypsx_toolkit.index_constituents("ALLSHR")
                if raw is not None and hasattr(raw, "iterrows") and not raw.empty:
                    log.info("Loaded quote rows from PSX ALLSHR constituents fallback")
                    frame = raw.copy()
                    frame.columns = [str(column).strip().upper() for column in frame.columns]
                    return frame
            except Exception as exc:
                log.warning("PSX all-share quote fallback failed: %s", exc)

        try:
            r = httpx.get(
                PSX_SCREENER_URL,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=15.0,
                follow_redirects=True,
            )
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table")
                if table:
                    import pandas as pd
                    headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
                    sym_idx = headers.index("SYMBOL") if "SYMBOL" in headers else 0
                    price_idx = headers.index("PRICE") if "PRICE" in headers else -1
                    ch_idx = headers.index("CHANGE (%)") if "CHANGE (%)" in headers else -1
                    sector_idx = headers.index("SECTOR") if "SECTOR" in headers else -1
                    vol_idx = headers.index("30D VOLUME AVG.") if "30D VOLUME AVG." in headers else -1
                    rows = []
                    for tr in table.find_all("tr")[1:]:
                        tds = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                        if len(tds) <= max(sym_idx, price_idx):
                            continue
                        sym = tds[sym_idx].upper().strip()
                        if not sym or not sym.isalnum():
                            continue
                        try:
                            curr = float(tds[price_idx].replace(",", "").replace("%", "")) if price_idx >= 0 else None
                        except Exception:
                            curr = None
                        try:
                            ch_pct = float(tds[ch_idx].replace(",", "").replace("%", "")) if ch_idx >= 0 else 0.0
                        except Exception:
                            ch_pct = 0.0
                        try:
                            vol_str = tds[vol_idx].replace(",", "") if vol_idx >= 0 else "0"
                            vol = int(float(vol_str))
                        except Exception:
                            vol = 0
                        ldcp = round(curr / (1 + ch_pct / 100.0), 2) if (curr and ch_pct is not None and ch_pct != -100) else curr
                        change = round(curr - ldcp, 2) if (curr and ldcp) else 0.0
                        rows.append({
                            "SYMBOL": sym,
                            "NAME": sym,
                            "CURRENT": curr,
                            "LDCP": ldcp,
                            "OPEN": curr,
                            "HIGH": curr,
                            "LOW": curr,
                            "CHANGE": change,
                            "CHANGE_PCT": ch_pct,
                            "VOLUME": vol,
                            "SECTOR": MarketService._normalize_sector_code_or_name(tds[sector_idx]) if sector_idx >= 0 else None,
                        })
                    if rows:
                        frame = pd.DataFrame(rows).set_index("SYMBOL")
                        log.info("Loaded %d quote rows from PSX screener fallback", len(frame))
                        return frame
        except Exception as exc:
            log.warning("PSX screener quotes fallback failed: %s", exc)

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
            # When Redis is completely cold, continue down to fetch & populate cache

        log.info("Fetching indices from external API")
        raw = None
        if pypsx_toolkit and hasattr(pypsx_toolkit, "get_indices"):
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

            priority_order = {"KSE100": 0, "KSE30": 1, "KMI30": 2, "ALLSHR": 3, "KMIALLSHR": 4, "BKTI": 5, "OGTI": 6, "PSXDIV20": 7}
            results.sort(key=lambda x: priority_order.get(x["code"], 99))

            if results:
                await cache_set(cache_key, results, INDICES_TTL_SECONDS)
                await cache_set(fallback_key, results, FALLBACK_TTL_SECONDS)
                await cache_set("market:indices:fetched_at", datetime.now(timezone.utc).isoformat(), FALLBACK_TTL_SECONDS)
                log.info("Stored %d indices in centralized cache", len(results))
                return results

        # Fallback: direct HTTP scrape of PSX indices page
        try:
            r = await asyncio.to_thread(
                httpx.get,
                "https://dps.psx.com.pk/indices",
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=12.0,
                follow_redirects=True,
            )
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                results = []
                for table in soup.find_all("table"):
                    headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
                    if "INDEX" in headers and "CURRENT" in headers:
                        idx_i = headers.index("INDEX")
                        cur_i = headers.index("CURRENT")
                        ch_i = headers.index("CHANGE") if "CHANGE" in headers else -1
                        chp_i = headers.index("% CHANGE") if "% CHANGE" in headers else -1
                        h_i = headers.index("HIGH") if "HIGH" in headers else -1
                        l_i = headers.index("LOW") if "LOW" in headers else -1
                        for tr in table.find_all("tr")[1:]:
                            tds = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                            if len(tds) <= max(idx_i, cur_i):
                                continue
                            code_str = tds[idx_i].strip().upper()
                            if not code_str:
                                continue
                            def _clean_num(val_str):
                                try:
                                    return float(val_str.replace(",", "").replace("%", "").strip())
                                except Exception:
                                    return 0.0
                            results.append({
                                "index": self.MAIN_INDICES.get(code_str, code_str),
                                "code": code_str,
                                "current": _clean_num(tds[cur_i]),
                                "change": _clean_num(tds[ch_i]) if ch_i >= 0 else 0.0,
                                "change_pct": _clean_num(tds[chp_i]) if chp_i >= 0 else 0.0,
                                "high": _clean_num(tds[h_i]) if h_i >= 0 else 0.0,
                                "low": _clean_num(tds[l_i]) if l_i >= 0 else 0.0,
                            })
                        if results:
                            break
                if results:
                    priority_order = {"KSE100": 0, "KSE30": 1, "KMI30": 2, "ALLSHR": 3, "KMIALLSHR": 4, "BKTI": 5, "OGTI": 6, "PSXDIV20": 7}
                    results.sort(key=lambda x: priority_order.get(x["code"], 99))
                    await cache_set(cache_key, results, INDICES_TTL_SECONDS)
                    await cache_set(fallback_key, results, FALLBACK_TTL_SECONDS)
                    await cache_set("market:indices:fetched_at", datetime.now(timezone.utc).isoformat(), FALLBACK_TTL_SECONDS)
                    log.info("Stored %d indices from direct HTTP scrape", len(results))
                    return results
        except Exception as exc:
            log.warning("Direct HTTP scrape of indices failed: %s", exc)

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
            # When Redis is completely cold, continue down to fetch & populate cache

        log.info("Fetching constituents for %s from external API", index_code)
        raw = None
        if pypsx_toolkit and hasattr(pypsx_toolkit, "index_constituents"):
            try:
                raw = await asyncio.wait_for(
                    asyncio.to_thread(pypsx_toolkit.index_constituents, index_code),
                    timeout=15.0,
                )
            except Exception as e:
                log.warning("External fetch of constituents for %s failed: %s", index_code, e)

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

        # Fallback: direct HTTP scrape of PSX screener for index constituents
        try:
            r = await asyncio.to_thread(
                httpx.get,
                PSX_SCREENER_URL,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
                timeout=15.0,
                follow_redirects=True,
            )
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, "html.parser")
                table = soup.find("table")
                if table:
                    headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
                    sym_idx = headers.index("SYMBOL") if "SYMBOL" in headers else 0
                    listed_idx = headers.index("LISTED IN") if "LISTED IN" in headers else -1
                    price_idx = headers.index("PRICE") if "PRICE" in headers else -1
                    ch_idx = headers.index("CHANGE (%)") if "CHANGE (%)" in headers else -1
                    mcap_idx = headers.index("MARKET CAP.") if "MARKET CAP." in headers else -1
                    vol_idx = headers.index("30D VOLUME AVG.") if "30D VOLUME AVG." in headers else -1

                    target_code = index_code.upper().replace("-", "").strip()
                    results = []
                    for tr in table.find_all("tr")[1:]:
                        tds = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
                        if len(tds) <= max(sym_idx, price_idx):
                            continue
                        sym = tds[sym_idx].upper().strip()
                        if not sym or not sym.isalnum():
                            continue
                        listed = tds[listed_idx].upper() if listed_idx >= 0 else ""
                        if target_code not in listed and target_code != "ALLSHR":
                            continue
                        try:
                            curr = float(tds[price_idx].replace(",", "").replace("%", "")) if price_idx >= 0 else None
                        except Exception:
                            curr = None
                        try:
                            ch_pct = float(tds[ch_idx].replace(",", "").replace("%", "")) if ch_idx >= 0 else 0.0
                        except Exception:
                            ch_pct = 0.0
                        try:
                            vol = int(float(tds[vol_idx].replace(",", ""))) if vol_idx >= 0 else 0
                        except Exception:
                            vol = 0
                        ldcp = round(curr / (1 + ch_pct / 100.0), 2) if (curr and ch_pct is not None and ch_pct != -100) else curr
                        change = round(curr - ldcp, 2) if (curr and ldcp) else 0.0

                        results.append({
                            "symbol": sym,
                            "name": sym,
                            "ldcp": ldcp,
                            "current": curr,
                            "change": change,
                            "change_pct": ch_pct,
                            "weight_pct": 1.0,
                            "index_points": 0.0,
                            "volume": vol,
                            "freefloat_m": 0.0,
                            "market_cap_m": self._safe_float(tds[mcap_idx]) if mcap_idx >= 0 else None,
                        })
                    if results:
                        await cache_set(cache_key, results, CONSTITUENTS_TTL_SECONDS)
                        await cache_set(fallback_key, results, FALLBACK_TTL_SECONDS)
                        await cache_set(
                            f"market:constituents:{index_code}:fetched_at",
                            datetime.now(timezone.utc).isoformat(),
                            FALLBACK_TTL_SECONDS,
                        )
                        log.info("Stored %d constituents for %s from PSX screener fallback", len(results), index_code)
                        return results
        except Exception as exc:
            log.warning("PSX screener constituents fallback failed for %s: %s", index_code, exc)

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
                ldcp = self._positive_or_none(row.get("LDCP"))
                current = self._positive_or_none(row.get("CURRENT"))
                change = round(current - ldcp, 4) if current is not None and ldcp is not None else None
                change_pct = round(change / ldcp * 100, 2) if change is not None and ldcp else None
                raw_sector = (
                    row.get("SECTOR")
                    or previous_sectors.get(str(symbol).upper())
                    or sector_map.get(str(symbol).upper())
                )
                sector_val = MarketService._normalize_sector_code_or_name(raw_sector) or sector_map.get(str(symbol).upper())
                open_val = self._positive_or_none(row.get("OPEN"))
                high_val = self._positive_or_none(row.get("HIGH"))
                low_val = self._positive_or_none(row.get("LOW"))
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

            cache_set_sync(cache_key, rows, _quotes_ttl())
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
                ldcp = self._positive_or_none(row.get("LDCP"))
                current = self._positive_or_none(row.get("CURRENT"))
                change = round(current - ldcp, 4) if current is not None and ldcp is not None else None
                change_pct = round(change / ldcp * 100, 2) if change is not None and ldcp else None
                raw_sector = (
                    row.get("SECTOR")
                    or previous_sectors.get(str(symbol).upper())
                    or sector_map.get(str(symbol).upper())
                )
                sector_val = MarketService._normalize_sector_code_or_name(raw_sector) or sector_map.get(str(symbol).upper())
                open_val = self._positive_or_none(row.get("OPEN"))
                high_val = self._positive_or_none(row.get("HIGH"))
                low_val = self._positive_or_none(row.get("LOW"))
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
                ttl = _quotes_ttl()
                await cache_set(cache_key, rows, ttl)
                await cache_set(fallback_key, rows, FALLBACK_TTL_SECONDS)
                await cache_set("market:quotes:fetched_at", datetime.now(timezone.utc).isoformat(), FALLBACK_TTL_SECONDS)
                # Recommendations and StockService read market snapshots via
                # the synchronous Redis client. Mirror only this successful
                # upstream fetch so both API paths observe the same live quote
                # and freshness timestamp (never promote the stale fallback).
                await asyncio.to_thread(cache_set_sync, cache_key, rows, ttl)
                await asyncio.to_thread(cache_set_sync, fallback_key, rows, FALLBACK_TTL_SECONDS)
                await asyncio.to_thread(
                    cache_set_sync,
                    "market:quotes:fetched_at",
                    datetime.now(timezone.utc).isoformat(),
                    FALLBACK_TTL_SECONDS,
                )
                freshness = await asyncio.to_thread(self.quote_freshness)
                if freshness.get("is_stale"):
                    log.error("Market quote Redis mirror is not visible to sync readers: %s", freshness)
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
        traded = self._traded_quotes(data)
        return sorted(traded, key=lambda d: d["change_pct"], reverse=True)[:limit]

    async def get_top_losers(self, limit: int = 10) -> list[dict]:
        data = await self.get_market_data()
        traded = self._traded_quotes(data)
        return sorted(traded, key=lambda d: d["change_pct"])[:limit]

    @classmethod
    def _traded_quotes(cls, data: list[dict]) -> list[dict]:
        """Exclude no-trade rows from mover lists; their prices may be stale."""
        return [
            row for row in data
            if cls._safe_int(row.get("volume")) > 0
            and cls._safe_float(row.get("current")) > 0
            and cls._safe_float(row.get("ldcp")) > 0
        ]

    async def get_volume_spikes(self, limit: int = 10) -> list[dict]:
        data = await self.get_market_data()
        traded = [row for row in data if self._safe_int(row.get("volume")) > 0]
        return sorted(traded, key=lambda d: d["volume"], reverse=True)[:limit]

    async def get_sentiment_overview(self) -> dict:
        data = await self.get_market_data()
        traded = self._traded_quotes(data)
        advancing = sum(1 for d in traded if d["change_pct"] > 0)
        declining = sum(1 for d in traded if d["change_pct"] < 0)
        unchanged = len(traded) - advancing - declining
        total = len(traded)

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
        for quote in traded:
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
            traded,
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
        # Sector enrichment belongs to the scheduled market ingestion job.
        # A read endpoint must not fall back to scraping the PSX screener.

        grouped = defaultdict(list)
        for quote in data:
            raw_sec = quote.get("sector")
            sector = MarketService._normalize_sector_code_or_name(raw_sec)
            if not sector or sector.casefold() in {"unclassified", "unknown"}:
                continue
            grouped[sector].append(quote)

        sectors = []
        for sector, quotes in grouped.items():
            sector_with_change = [
                q for q in quotes
                if q.get("change_pct") is not None
                and not (isinstance(q.get("change_pct"), float) and math.isnan(q["change_pct"]))
            ]
            changes = [self._safe_float(quote.get("change_pct")) for quote in sector_with_change]
            gainers = [quote for quote, change in zip(sector_with_change, changes) if change > 0]
            losers = [quote for quote, change in zip(sector_with_change, changes) if change < 0]
            unchanged = len(quotes) - len(gainers) - len(losers)
            cap_values = [self._safe_float(quote.get("market_cap_m")) for quote in quotes]
            market_caps = [value for value in cap_values if value > 0]

            sorted_quotes = sorted(sector_with_change, key=lambda q: self._safe_float(q.get("change_pct")), reverse=True) if sector_with_change else quotes
            top_gainer = sorted_quotes[0] if sorted_quotes else None
            top_loser = sorted_quotes[-1] if sorted_quotes else None

            avg_chg = round(sum(changes) / len(changes), 2) if changes else 0.0
            tot_mcap = round(sum(market_caps), 2) if market_caps else 0.0

            sectors.append({
                "sector": sector,
                "name": sector,
                "avg_change_pct": avg_chg,
                "companies": len(quotes),
                "stock_count": len(quotes),
                "advancing": len(gainers),
                "declining": len(losers),
                "unchanged": max(0, unchanged),
                "total_volume": sum(self._safe_int(quote.get("volume")) for quote in quotes),
                "market_cap_m": tot_mcap,
                "top_gainer_symbol": top_gainer.get("symbol") if top_gainer else None,
                "top_loser_symbol": top_loser.get("symbol") if top_loser else None,
            })

        sectors.sort(key=lambda item: item["avg_change_pct"] if item["avg_change_pct"] is not None else 0.0, reverse=order.lower() != "asc")
        classified = sum(len(quotes) for quotes in grouped.values())
        return {
            "sectors": sectors,
            "total_sectors": len(sectors),
            "total_companies": len(data),
            "classified_companies": classified,
            "unclassified_companies": len(data) - classified,
            **self.quote_freshness(),
        }

    async def get_screener_data(self, force_refresh: bool = False) -> list[dict]:
        """Fetch and cache full 560-stock PSX screener metrics with 3-tier caching."""
        global _STATIC_SCREENER_CACHE, _STATIC_SCREENER_TIMESTAMP
        cache_key = "market:screener"
        fallback_key = "market:screener:last_known"
        
        # Tier 1: In-memory Process Cache (< 1ms)
        import time as _t
        now = _t.monotonic()
        if not force_refresh and _STATIC_SCREENER_CACHE and (now - _STATIC_SCREENER_TIMESTAMP) < 600:
            return _STATIC_SCREENER_CACHE

        # Tier 2: Redis Distributed Cache (< 15ms)
        if not force_refresh:
            cached = await cache_get(cache_key)
            if cached and isinstance(cached, list) and len(cached) > 10:
                _STATIC_SCREENER_CACHE = cached
                _STATIC_SCREENER_TIMESTAMP = now
                return cached

        def _scrape():
            import requests
            from bs4 import BeautifulSoup
            try:
                res = requests.get(PSX_SCREENER_URL, timeout=10.0, headers={"User-Agent": "Mozilla/5.0"})
                if res.status_code != 200:
                    return []
                soup = BeautifulSoup(res.text, "html.parser")
                table = soup.find("table")
                if not table:
                    return []
                rows = table.find_all("tr")
                items = []
                for tr in rows[1:]:
                    cols = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if len(cols) >= 11:
                        def _num(val):
                            try:
                                return float(val.replace("%", "").replace(",", "").strip())
                            except Exception:
                                return None
                        def _int(val):
                            try:
                                return int(val.replace(",", "").strip())
                            except Exception:
                                return 0
                        items.append({
                            "symbol": cols[0].upper(),
                            "sector_code": cols[1],
                            "market_cap": cols[3],
                            "price": _num(cols[4]),
                            "change_pct": _num(cols[5]),
                            "return_1y_pct": _num(cols[6]),
                            "pe_ratio": _num(cols[7]),
                            "dividend_yield_pct": _num(cols[8]),
                            "free_float": cols[9],
                            "volume_30d_avg": _int(cols[10]),
                        })
                return items
            except Exception as e:
                log.warning("Failed to scrape PSX screener: %s", e)
                return []

        screener_items = await asyncio.to_thread(_scrape)
        
        sector_map = await asyncio.to_thread(self._load_sector_map_sync)
        if screener_items:
            for it in screener_items:
                sym = it["symbol"]
                sec_code = it.get("sector_code")
                it["sector"] = (
                    sector_map.get(sym)
                    or MarketService._normalize_sector_code_or_name(sec_code)
                    or "Unclassified"
                )

        # Enrich company names and sectors from active quote catalog
        try:
            quotes = await self.get_market_data(read_only=True)
            quote_map = {str(q.get("symbol", "")).upper(): q for q in quotes if q.get("symbol")}
            for it in screener_items:
                sym = it["symbol"]
                q = quote_map.get(sym)
                if q:
                    it["name"] = q.get("name") or sym
                    if it.get("sector") in (None, "", "Unclassified", "unknown"):
                        it["sector"] = q.get("sector") or it.get("sector")
                else:
                    it["name"] = sym
        except Exception:
            for it in screener_items:
                it.setdefault("name", it["symbol"])
        
        if screener_items:
            _STATIC_SCREENER_CACHE = screener_items
            _STATIC_SCREENER_TIMESTAMP = now
            await cache_set(cache_key, screener_items, 3600)
            await cache_set(fallback_key, screener_items, FALLBACK_TTL_SECONDS)
            return screener_items
        
        # Tier 3: Persistent Fallback Cache
        fallback = await cache_get(fallback_key)
        if fallback and isinstance(fallback, list):
            _STATIC_SCREENER_CACHE = fallback
            _STATIC_SCREENER_TIMESTAMP = now
            return fallback
        return []

    async def get_curated_stocks(
        self,
        category: str = "high_dividend_yield",
        limit: int = 20,
        min_volume: int = 5000,
        sector: str | None = None,
    ) -> dict:
        """Return curated, ranked PSX stock leaderboards with full metrics."""
        raw_items = await self.get_screener_data()
        
        if sector:
            raw_items = [it for it in raw_items if str(it.get("sector", "")).casefold() == sector.casefold()]
            
        filtered = [it for it in raw_items if (it.get("volume_30d_avg") or 0) >= min_volume]
        if not filtered and raw_items:
            filtered = raw_items

        cat = category.lower().replace("-", "_")
        
        if cat in {"high_dividend_yield", "dividend", "dividends", "highest_yielding"}:
            title = "Highest Dividend Yielding Stocks"
            desc = "Top PSX companies delivering superior dividend yields to shareholders."
            # Exclude extreme statistical anomalies (> 100% liquidation yields) for realistic leaderboards
            valid = [it for it in filtered if 0 < (it.get("dividend_yield_pct") or 0) <= 100]
            valid.sort(key=lambda x: x.get("dividend_yield_pct") or 0, reverse=True)
            for it in valid:
                it["metric_label"] = "Dividend Yield"
                it["metric_value"] = it.get("dividend_yield_pct")
                
        elif cat in {"best_returning", "best_returning_1y", "top_performers", "highest_return"}:
            title = "Best 1-Year Returning Stocks"
            desc = "Leading PSX equities ranked by 1-year capital appreciation."
            valid = [it for it in filtered if it.get("return_1y_pct") is not None]
            valid.sort(key=lambda x: x.get("return_1y_pct") or -999, reverse=True)
            for it in valid:
                it["metric_label"] = "1-Year Return"
                it["metric_value"] = it.get("return_1y_pct")
                
        elif cat in {"value_investing", "value_stocks", "lowest_pe", "undervalued"}:
            title = "Undervalued Value Stocks"
            desc = "Profitable PSX companies trading at low P/E multiples with solid yield."
            valid = [it for it in filtered if (it.get("pe_ratio") or 0) > 0 and (it.get("dividend_yield_pct") or 0) >= 0]
            valid.sort(key=lambda x: x.get("pe_ratio") or 9999)
            for it in valid:
                it["metric_label"] = "P/E Ratio"
                it["metric_value"] = it.get("pe_ratio")
                
        elif cat in {"most_liquid", "high_volume", "most_active"}:
            title = "Most Liquid and Active Stocks"
            desc = "Equities with the highest 30-day average trading volume on the PSX."
            valid = list(filtered)
            valid.sort(key=lambda x: x.get("volume_30d_avg") or 0, reverse=True)
            for it in valid:
                it["metric_label"] = "30D Avg Volume"
                it["metric_value"] = float(it.get("volume_30d_avg") or 0)
                
        else:
            title = "Fast-Growing PSX Equities"
            desc = "High-momentum PSX equities with robust growth metrics."
            valid = [it for it in filtered if (it.get("return_1y_pct") or 0) > 0]
            valid.sort(key=lambda x: (x.get("return_1y_pct") or 0) + (x.get("dividend_yield_pct") or 0), reverse=True)
            for it in valid:
                it["metric_label"] = "1-Year Return"
                it["metric_value"] = it.get("return_1y_pct")

        results = valid[:limit]
        return {
            "category": cat,
            "title": title,
            "description": desc,
            "total_count": len(valid),
            "items": results,
            "as_of": datetime.now(timezone.utc).isoformat(),
            "is_stale": False,
        }
