"""StockAnalysis.com fundamentals fallback for PSX symbols.

pypsx_toolkit sources its company profile/equity/snapshot/quote data from
dps.psx.com.pk, which can be unreachable from cloud/datacenter IP ranges.
StockAnalysis.com (S&P Global data) is reachable from the same environments and
covers every PSX symbol with the full set of fundamentals the API returns, so it
acts as a zero-config fallback whenever an upstream PSX call comes back empty.
"""

import logging
import re
import time
from typing import Any

import httpx
from bs4 import BeautifulSoup

from app.core.redis import cache_get_sync, cache_set_sync

log = logging.getLogger(__name__)

_BASE = "https://stockanalysis.com"
_QUOTE_PATH = "/quote/psx/{symbol}/"
_STATS_PATH = "/quote/psx/{symbol}/statistics/"
_COMPANY_PATH = "/quote/psx/{symbol}/company/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}
_TIMEOUT = 20.0
_CACHE_TTL = 6 * 60 * 60  # 6 hours; fundamentals change slowly


def _parse_percent_change(value: str | None) -> float | None:
    """Parse the trailing percentage change with sign, e.g. 'EPS 50.88 +42.6%' -> 42.6."""
    if not value:
        return None
    text = str(value)
    match = re.search(r"([+\-]?[0-9]+(?:\.[0-9]+)?)\s*%", text)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _parse_number(value: str | None) -> float | None:
    """Parse StockAnalysis values like '4.30B', '1.37T', '16.90%', '5.67', '56.35 +42.6%'."""
    if not value:
        return None
    match = re.search(r"([0-9]+(?:[.,][0-9]+)?)", str(value))
    if not match:
        return None
    try:
        return float(match.group(1).replace(",", ""))
    except ValueError:
        return None


def _parse_money(value: str | None) -> float | None:
    """Parse suffixed quantities: 1.37T -> 1.37e12, 4.30B -> 4.3e9, 574.68M -> 574.68e6."""
    if not value:
        return None
    text = str(value).strip().replace(",", "")
    match = re.search(r"([0-9.\-+]+)\s*([TBMK])", text, re.IGNORECASE)
    if not match:
        return _parse_number(value)
    number = _parse_number(match.group(1))
    if number is None:
        return None
    scale = match.group(2).upper()
    if scale == "T":
        return number * 1e12
    if scale == "B":
        return number * 1e9
    if scale == "M":
        return number * 1e6
    return number * 1e3


def _table_rows(soup) -> dict[str, str]:
    """Extract the first label/value table on the page into a dict."""
    rows: dict[str, str] = {}
    for table in soup.select("table"):
        for tr in table.select("tr"):
            tds = tr.select("td")
            if len(tds) >= 2:
                key = tds[0].get_text(" ", strip=True)
                value = tds[1].get_text(" ", strip=True)
                if key and value:
                    rows.setdefault(key, value)
    return rows


def _fetch(path: str) -> httpx.Response | None:
    try:
        with httpx.Client(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            resp = client.get(path)
            if resp.status_code != 200:
                log.warning("StockAnalysis %s returned HTTP %s", path, resp.status_code)
                return None
            return resp
    except Exception as exc:
        log.warning("StockAnalysis fetch failed for %s: %s", path, exc)
        return None


def _text_of(soup, selector: str) -> str | None:
    el = soup.select_one(selector)
    if el is None:
        return None
    text = el.get_text(" ", strip=True)
    return text or None


def _parse_range(value: str | None) -> tuple[float | None, float | None]:
    """Parse 'low - high' ranges (StockAnalysis order) into (high, low)."""
    if not value:
        return None, None
    numbers = [n for part in re.split(r"\s*-\s*", str(value)) if (n := _parse_number(part)) is not None]
    if len(numbers) < 2:
        return None, None
    return numbers[1], numbers[0]


def _business_description(soup, symbol: str) -> str | None:
    """Descriptions live in the 'About' card on the overview page."""
    for heading in soup.select("h2"):
        if "About" in heading.get_text(" ", strip=True):
            para = heading.find_next("p")
            if para:
                text = para.get_text(" ", strip=True)
                return text or None
    return None


def fetch_stockanalysis_fundamentals(symbol: str) -> dict[str, Any]:
    """Fetch fundamentals for a PSX symbol from StockAnalysis, cached in Redis."""
    symbol = str(symbol).upper()
    cache_key = f"sa:fundamentals:{symbol}"

    cached = cache_get_sync(cache_key)
    if isinstance(cached, dict) and cached:
        return cached

    result: dict[str, Any] = {
        "company_profile": {},
        "equity_profile": {},
        "ratios": {},
        "trading_limits": {},
        "metrics": {},
        "business_description": None,
    }

    quote_resp = _fetch(_BASE + _QUOTE_PATH.format(symbol=symbol))
    if quote_resp is None:
        return result
    quote_soup = BeautifulSoup(quote_resp.text, "html.parser")
    quote_rows = _table_rows(quote_soup)

    market_cap = _parse_money(quote_rows.get("Market Cap"))
    shares_out = _parse_money(quote_rows.get("Shares Out"))
    pe_ratio = _parse_number(quote_rows.get("PE Ratio"))
    eps = _parse_number(quote_rows.get("EPS"))
    eps_growth = _parse_percent_change(quote_rows.get("EPS"))
    year_high, year_low = _parse_range(quote_rows.get("52-Week Range"))
    result["business_description"] = _business_description(quote_soup, symbol)

    result["company_profile"]["sector"] = None  # PSX sector via market watch preferred
    result["equity_profile"]["market_cap_pkr"] = market_cap
    result["equity_profile"]["market_cap_pkr_m"] = round(market_cap / 1e6, 2) if market_cap else None
    result["equity_profile"]["total_shares"] = int(shares_out) if shares_out else None
    result["ratios"]["pe_ratio"] = pe_ratio
    result["ratios"]["eps"] = eps
    result["ratios"]["eps_growth_pct"] = eps_growth
    result["trading_limits"]["year_high"] = year_high
    result["trading_limits"]["year_low"] = year_low
    result["metrics"]["market_cap_m"] = result["equity_profile"]["market_cap_pkr_m"]
    result["metrics"]["pe_ratio"] = pe_ratio
    result["metrics"]["eps"] = eps
    result["metrics"]["eps_growth_pct"] = eps_growth

    stats_resp = _fetch(_BASE + _STATS_PATH.format(symbol=symbol))
    if stats_resp is not None:
        stats_soup = BeautifulSoup(stats_resp.text, "html.parser")
        stats_rows = _table_rows(stats_soup)

        result["company_profile"]["sector"] = (
            stats_rows.get("Sector") if stats_rows.get("Sector") else None
        )
        result["equity_profile"]["free_float_shares"] = int(_parse_money(stats_rows.get("Float"))) if _parse_money(stats_rows.get("Float")) else None
        if result["equity_profile"]["total_shares"]:
            result["equity_profile"]["free_float_pct"] = round(
                result["equity_profile"]["free_float_shares"] / result["equity_profile"]["total_shares"] * 100, 2
            ) if result["equity_profile"]["free_float_shares"] else None
        result["ratios"]["peg_ratio"] = _parse_number(stats_rows.get("PEG Ratio"))
        result["ratios"]["net_profit_margin_pct"] = _parse_number(stats_rows.get("Profit Margin"))
        result["ratios"]["gross_profit_margin_pct"] = _parse_number(stats_rows.get("Gross Margin"))
        result["ratios"]["roe_pct"] = _parse_number(stats_rows.get("Return on Equity (ROE)"))
        result["ratios"]["dividend_yield_pct"] = _parse_number(stats_rows.get("Dividend Yield"))
        result["trading_limits"]["year_change_pct"] = _parse_number(stats_rows.get("52-Week Price Change"))
        result["metrics"]["roe_pct"] = result["ratios"]["roe_pct"]

    company_resp = _fetch(_BASE + _COMPANY_PATH.format(symbol=symbol))
    if company_resp is not None:
        company_soup = BeautifulSoup(company_resp.text, "html.parser")
        company_rows = _table_rows(company_soup)
        result["company_profile"]["ceo"] = company_rows.get("CEO")
        result["company_profile"]["website"] = company_rows.get("Website")
        result["company_profile"]["employees"] = company_rows.get("Employees")
        result["company_profile"]["founded"] = company_rows.get("Founded")

    if any(result.get("equity_profile", {}).values()) or any(result.get("ratios", {}).values()):
        cache_set_sync(cache_key, result, _CACHE_TTL)

    return result