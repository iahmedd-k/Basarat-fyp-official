"""Cached readers for the structured tables PSX renders on company pages.

This reads one symbol on demand. Successful results are cached for a day and
concurrent requests for the same symbol share one upstream fetch.
"""

from __future__ import annotations

import logging
import re
import threading
import time
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from app.core.redis import cache_get_sync, cache_set_sync

log = logging.getLogger(__name__)

_DAY_TTL = 24 * 60 * 60
_FAILURE_TTL = 60 * 60
_BASE = "https://dps.psx.com.pk"
_FINANCIALS_BASE = "https://financials.psx.com.pk/"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BasaratEducationalResearch/1.0)",
    "Accept": "text/html,application/json;q=0.9,*/*;q=0.8",
}
_local_cache: dict[str, tuple[object, float]] = {}
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()

_METRIC_KEYS = {
    "mark-up earned": "mark_up_earned",
    "markup earned": "mark_up_earned",
    "sales": "sales",
    "total income": "total_income",
    "profit after taxation": "profit_after_tax",
    "eps": "eps",
    "gross profit margin (%)": "gross_profit_margin_pct",
    "net profit margin (%)": "net_profit_margin_pct",
    "eps growth (%)": "eps_growth_pct",
    "peg": "peg_ratio",
}


def _get_lock(key: str) -> threading.Lock:
    with _guard:
        return _locks.setdefault(key, threading.Lock())


def _cached_fetch(key: str, loader):
    now = time.monotonic()
    local = _local_cache.get(key)
    if local and local[1] > now:
        return local[0]

    with _get_lock(key):
        now = time.monotonic()
        local = _local_cache.get(key)
        if local and local[1] > now:
            return local[0]
        shared = cache_get_sync(key)
        if isinstance(shared, dict):
            _local_cache[key] = (shared, now + _DAY_TTL)
            return shared

        value = loader()
        ttl = _DAY_TTL if value else _FAILURE_TTL
        if value:
            cache_set_sync(key, value, ttl)
        _local_cache[key] = (value or {}, now + ttl)
        return value or {}


def _number(text: str):
    raw = (text or "").strip().replace(",", "")
    if not raw or raw in {"-", "—", "N/A", "n/a"}:
        return None
    negative = raw.startswith("(") and raw.endswith(")")
    raw = raw.strip("()% ")
    try:
        value = float(raw)
    except ValueError:
        return text.strip()
    if negative:
        value = -value
    return int(value) if value.is_integer() else value


def _metric_key(label: str) -> str:
    normalized = re.sub(r"\s+", " ", label.strip()).casefold()
    return _METRIC_KEYS.get(normalized, re.sub(r"[^a-z0-9]+", "_", normalized).strip("_"))


def _parse_table(table) -> list[dict]:
    header = table.select_one("thead tr")
    if not header:
        return []
    periods = [cell.get_text(" ", strip=True) for cell in header.find_all(["th", "td"])]
    if len(periods) < 2:
        return []

    records = [{"period": period, "values": {}} for period in periods[1:]]
    for row in table.select("tbody tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) < 2:
            continue
        key = _metric_key(cells[0].get_text(" ", strip=True))
        for index, cell in enumerate(cells[1:]):
            if index < len(records):
                records[index]["values"][key] = _number(cell.get_text(" ", strip=True))
    return records


def _table_rows_as_source_dict(table) -> dict:
    rows = {}
    if not table:
        return rows
    for row in table.select("tbody tr"):
        cells = row.find_all(["td", "th"], recursive=False)
        if len(cells) > 1:
            rows[cells[0].get_text(" ", strip=True)] = " | ".join(
                cell.get_text(" ", strip=True) for cell in cells[1:]
            )
    return rows


def _page_source_info(soup, symbol: str) -> dict:
    profile_node = soup.select_one("#profile")
    profile = {}
    governance = {}
    if profile_node:
        description = profile_node.select_one(".profile__item--decription p")
        if description:
            profile["Business Description"] = description.get_text(" ", strip=True)
        for row in profile_node.select(".profile__item--people tr"):
            cells = row.find_all("td", recursive=False)
            if len(cells) >= 2:
                governance[cells[0].get_text(" ", strip=True)] = cells[1].get_text(" ", strip=True)
        for item in profile_node.select(".profile__item"):
            headings = item.find_all(class_="item__head")
            for heading in headings:
                label = heading.get_text(" ", strip=True).casefold()
                value_node = heading.find_next_sibling("p")
                if not value_node:
                    continue
                value = value_node.get_text(" ", strip=True)
                if label == "address":
                    profile["Address"] = value
                elif label == "website":
                    link = value_node.find("a", href=True)
                    profile["Website"] = link["href"] if link else value

    equity = {}
    raw_equity = {}
    for item in soup.select("#equity .stats_item"):
        label_node = item.select_one(".stats_label")
        value_node = item.select_one(".stats_value")
        if not label_node or not value_node:
            continue
        label = re.sub(r"\s+", " ", label_node.get_text(" ", strip=True))
        value = value_node.get_text(" ", strip=True)
        if label.startswith("Market Cap"):
            raw_equity["Market Cap (000's)"] = value
            market_cap_thousands = _number(value)
            if isinstance(market_cap_thousands, (int, float)):
                equity["market_cap"] = market_cap_thousands * 1000
        elif label == "Shares":
            raw_equity["Shares"] = value
            number = _number(value)
            if isinstance(number, (int, float)):
                equity["shares_outstanding"] = int(number)
        elif label == "Free Float":
            number = _number(value)
            if "%" in value:
                raw_equity["Free Float"] = value
                equity["free_float_pct"] = number
            else:
                raw_equity["Free Float Shares"] = value
                if isinstance(number, (int, float)):
                    equity["free_float_shares"] = int(number)

    financial_tables = soup.select("#financials table")
    ratio_tables = soup.select("#ratios table")
    annual = _table_rows_as_source_dict(financial_tables[0]) if financial_tables else {}
    quarterly = _table_rows_as_source_dict(financial_tables[1]) if len(financial_tables) > 1 else {}
    ratios = _table_rows_as_source_dict(ratio_tables[0]) if ratio_tables else {}

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    name_match = re.search(r"Stock quote for (.+?)(?:\s+-\s+Pakistan Stock Exchange|\s+-\s+PSX)", title, re.I)
    name = name_match.group(1).strip() if name_match else symbol
    return {
        "symbol": symbol,
        "name": name,
        "company_name": name,
        "Profile": profile,
        "Governance": governance,
        "Equity Profile": raw_equity,
        "Financials Annual": annual,
        "Financials Quarterly": quarterly,
        "Ratios": ratios,
        **equity,
    }


def _fetch_company_tables(symbol: str) -> dict:
    url = f"{_BASE}/company/{symbol}"
    try:
        response = httpx.get(
            url,
            headers={**_HEADERS, "Referer": f"{_BASE}/"},
            timeout=httpx.Timeout(12.0, connect=5.0),
            follow_redirects=True,
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        financial_tables = soup.select("#financials table")
        ratio_tables = soup.select("#ratios table")
        return {
            "source_url": str(response.url),
            "source_info": _page_source_info(soup, symbol),
            "financials_annual": _parse_table(financial_tables[0]) if financial_tables else [],
            "financials_quarterly": _parse_table(financial_tables[1]) if len(financial_tables) > 1 else [],
            "ratio_history": _parse_table(ratio_tables[0]) if ratio_tables else [],
        }
    except Exception as exc:
        log.warning("PSX company tables fetch failed for %s: %s", symbol, exc)
        return {}


def _fetch_financial_reports(symbol: str) -> dict:
    try:
        response = httpx.post(
            urljoin(_FINANCIALS_BASE, "annQtrStmts.php"),
            data={"name": "get_comp_data", "smbCode": symbol},
            headers={
                **_HEADERS,
                "Referer": _FINANCIALS_BASE,
                "Origin": "https://financials.psx.com.pk",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=httpx.Timeout(12.0, connect=5.0),
        )
        response.raise_for_status()
        rows = response.json()
        reports = []
        for row in rows if isinstance(rows, list) else []:
            html = BeautifulSoup(str(row.get("Reports", "")), "html.parser")
            link = html.find("a", href=True)
            if not link:
                continue
            reports.append({
                "report_type": link.get_text(" ", strip=True),
                "period_ended": row.get("period_ended"),
                "posting_date": row.get("posting_date"),
                "url": urljoin(_FINANCIALS_BASE, link["href"]),
            })
        def _date_key(value):
            text = str(value or "")
            parts = re.match(r"^(\d{4})(?:-(\d{2})-(\d{2}))?$", text)
            return tuple(int(part or 0) for part in parts.groups()) if parts else (0, 0, 0)

        reports.sort(
            key=lambda item: (
                _date_key(item.get("period_ended")),
                _date_key(item.get("posting_date")),
            ),
            reverse=True,
        )
        return {"financial_reports": reports}
    except Exception as exc:
        log.warning("PSX financial report index fetch failed for %s: %s", symbol, exc)
        return {}


def get_psx_company_table_data(symbol: str) -> dict:
    """Return normalized company-page statements, ratio history, and report links."""
    symbol = str(symbol).strip().upper()
    tables = _cached_fetch(f"psx:company-tables:v2:{symbol}", lambda: _fetch_company_tables(symbol))
    reports = _cached_fetch(f"psx:financial-report-index:v2:{symbol}", lambda: _fetch_financial_reports(symbol))
    return {**tables, **reports}
