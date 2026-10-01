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
    "User-Agent": "Basarat PSX public-page collector/1.0 (daily company reference refresh)",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
}
_http_client: httpx.Client | None = None
_local_cache: dict[str, tuple[object, float]] = {}
_locks: dict[str, threading.Lock] = {}
_guard = threading.Lock()
_PSX_ACCESS_DENIED = False
_PSX_SOURCE_FAILURE: str | None = None


def psx_access_denied() -> bool:
    return _PSX_ACCESS_DENIED


def reset_psx_access_denied() -> None:
    global _PSX_ACCESS_DENIED, _PSX_SOURCE_FAILURE
    _PSX_ACCESS_DENIED = False
    _PSX_SOURCE_FAILURE = None


def psx_source_failure() -> str | None:
    return _PSX_SOURCE_FAILURE


def clear_psx_source_failure() -> None:
    global _PSX_SOURCE_FAILURE
    _PSX_SOURCE_FAILURE = None


def _get_http_client() -> httpx.Client:
    global _http_client
    with _guard:
        if _http_client is None or _http_client.is_closed:
            _http_client = httpx.Client(
                headers=_HEADERS,
                timeout=httpx.Timeout(12.0, connect=5.0),
                follow_redirects=True,
            )
        return _http_client


def close_psx_connection_batch() -> None:
    """Close pooled sockets at a symbol-batch boundary; next request reconnects."""
    global _http_client
    with _guard:
        if _http_client is not None:
            _http_client.close()
            _http_client = None


def _request_with_retry(method: str, url: str, **kwargs) -> httpx.Response:
    """Retry transient source failures with a fresh connection and backoff."""
    global _http_client
    attempts = 4
    for attempt in range(attempts):
        try:
            response = _get_http_client().request(method, url, **kwargs)
            if response.status_code < 500 or attempt == attempts - 1:
                return response
            last_error = RuntimeError(f"upstream HTTP {response.status_code}")
        except (httpx.TimeoutException, httpx.TransportError) as exc:
            last_error = exc
            if attempt == attempts - 1:
                raise
        close_psx_connection_batch()
        delay = min(2 ** (attempt + 1), 16)
        log.warning("PSX transient request failure (%s); reconnecting in %ss (%d/%d)",
                    last_error, delay, attempt + 1, attempts)
        time.sleep(delay)
    raise last_error

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
    "p/e ratio": "pe_ratio",
    "p/e ratio (ttm)": "pe_ratio",
    "dividend yield (%)": "dividend_yield_pct",
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


def cache_company_tables(symbol: str, payload: dict) -> None:
    """Share a successful daily scrape with API readers for the same day."""
    key = f"psx:company-tables:v5:{str(symbol).strip().upper()}"
    _local_cache[key] = (payload, time.monotonic() + _DAY_TTL)
    cache_set_sync(key, payload, _DAY_TTL)


def cache_financial_reports(symbol: str, payload: dict) -> None:
    """Share report-index results with API readers for the same day."""
    key = f"psx:financial-report-index:v5:{str(symbol).strip().upper()}"
    _local_cache[key] = (payload, time.monotonic() + _DAY_TTL)
    cache_set_sync(key, payload, _DAY_TTL)


def _number(text: str):
    raw = re.sub(r"^rs\.?\s*", "", (text or "").strip(), flags=re.I).replace(",", "")
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


def _record_tables(tables) -> list[dict]:
    records = []
    for table in tables:
        header = [cell.get_text(" ", strip=True) for cell in table.select("thead th, thead td")]
        for row in table.select("tbody tr"):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["td", "th"], recursive=False)]
            if not cells:
                continue
            if header and len(header) == len(cells):
                records.append({key: value for key, value in zip(header, cells) if key and value})
            else:
                records.append({f"column_{index + 1}": value for index, value in enumerate(cells) if value})
    return records


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

        # The public company page also exposes additional profile fields in
        # item-head blocks. Keep them in the durable raw profile, even when a
        # particular company has no value for one of them.
        profile_labels = {
            "registrar": "Registrar",
            "auditor": "Auditor",
            "fiscal year end": "Fiscal Year End",
        }
        for heading in profile_node.select(".item__head"):
            label = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).casefold()
            key = profile_labels.get(label)
            value_node = heading.find_next_sibling()
            if key and value_node:
                value = value_node.get_text(" ", strip=True)
                if value:
                    profile[key] = value

    equity = {}
    raw_equity = {}
    for item in soup.select("#equity .stats_item, .section[data-name='Equity Profile'] .stats_item"):
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

    def first_text(*selectors):
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                value = node.get_text(" ", strip=True)
                if value:
                    return value
        return None

    quote = {
        "price": _number(first_text(".company__quote .quote__close", ".quote__close")),
        "price_as_of": re.sub(r"^[\s^]*As of\s*", "", first_text(".company__quote .quote__date", ".quote__date") or "") or None,
        "name": first_text(".company__quote .quote__name", ".quote__name"),
        "sector": first_text(".company__quote .quote__sector", ".quote__sector"),
    }
    market_stats = {}
    for scope in (soup.select_one('.tabs__panel[data-name="REG"]'), soup):
        if not scope:
            continue
        for label_node, value_node in zip(scope.select(".stats_label"), scope.select(".stats_value")):
            label = re.sub(r"[\s*^]+$", "", " ".join(label_node.get_text(" ", strip=True).split()))
            value = value_node.get_text(" ", strip=True)
            if label and value:
                market_stats.setdefault(label, value)
        if market_stats:
            break
    quote.update({
        "ldcp": _number(market_stats.get("LDCP")),
        "pe_ratio_ttm": _number(market_stats.get("P/E Ratio (TTM)")),
        "year_change_pct": _number(market_stats.get("1-Year Change")),
        "ytd_change_pct": _number(market_stats.get("YTD Change")),
    })
    range_match = re.findall(r"\d[\d,]*\.?\d*", market_stats.get("52-WEEK RANGE", ""))
    quote["week52_low"] = _number(range_match[0]) if len(range_match) > 0 else None
    quote["week52_high"] = _number(range_match[1]) if len(range_match) > 1 else None

    # Also inspect the titled profile section used by the current DPS page
    # layout; this preserves the extra fields if they sit outside #profile.
    extra_profile_labels = {
        "registrar": "Registrar",
        "auditor": "Auditor",
        "fiscal year end": "Fiscal Year End",
    }
    for title in soup.select(".section__title"):
        if title.get_text(" ", strip=True).casefold() != "company profile":
            continue
        section = title.find_parent(class_="section")
        if not section:
            continue
        for heading in section.select(".item__head"):
            label = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).casefold()
            key = extra_profile_labels.get(label)
            content = []
            for sibling in heading.next_siblings:
                if getattr(sibling, "name", None) and "item__head" in (sibling.get("class") or []):
                    break
                if getattr(sibling, "get_text", None):
                    content.append(sibling.get_text(" ", strip=True))
            value = " ".join(part for part in content if part).strip()
            if key and value:
                profile[key] = value

    financial_tables = soup.select("#financials table")
    ratio_tables = soup.select("#ratios table")
    annual = _table_rows_as_source_dict(financial_tables[0]) if financial_tables else {}
    quarterly = _table_rows_as_source_dict(financial_tables[1]) if len(financial_tables) > 1 else {}
    ratios = _table_rows_as_source_dict(ratio_tables[0]) if ratio_tables else {}
    payouts = _record_tables(soup.select("#payouts table"))

    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    name_match = re.search(r"Stock quote for (.+?)(?:\s+-\s+Pakistan Stock Exchange|\s+-\s+PSX)", title, re.I)
    name = name_match.group(1).strip() if name_match else symbol
    return {
        "symbol": symbol,
        "name": name,
        "company_name": name,
        "sector": quote.get("sector"),
        "Profile": profile,
        "Governance": governance,
        "Equity Profile": raw_equity,
        "Financials Annual": annual,
        "Financials Quarterly": quarterly,
        "Ratios": ratios,
        "Market Data": quote,
        "Payouts": payouts,
        **equity,
    }


def _parse_pipe_dict_to_records(pipe_dict: dict, prefix: str = "Y") -> list[dict]:
    if not isinstance(pipe_dict, dict) or not pipe_dict:
        return []
    cols = {}
    max_len = 0
    for label, val in pipe_dict.items():
        if val is None:
            continue
        parts = [p.strip() for p in str(val).split("|")]
        cols[_metric_key(label)] = parts
        max_len = max(max_len, len(parts))
    records = []
    for i in range(max_len):
        rec = {"period": f"{prefix}-{i+1}", "values": {}}
        for mk, parts in cols.items():
            if i < len(parts):
                rec["values"][mk] = _number(parts[i])
        records.append(rec)
    return records


def _fetch_company_tables(symbol: str, *, allow_fallback: bool = True) -> dict:
    global _PSX_ACCESS_DENIED, _PSX_SOURCE_FAILURE
    url = f"{_BASE}/company/{symbol}"
    soup = None
    try:
        response = _request_with_retry("GET", url, headers={"Referer": f"{_BASE}/"})
        if response.status_code in (403, 429):
            _PSX_ACCESS_DENIED = True
            log.warning("PSX denied company-page access for %s (HTTP %d)", symbol, response.status_code)
            return {}
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
        elif response.status_code == 404 or response.status_code >= 500:
            _PSX_SOURCE_FAILURE = f"HTTP {response.status_code}"
            log.error("PSX company-page source failed for %s (%s); stopping the daily run", symbol, _PSX_SOURCE_FAILURE)
            return {}
    except Exception as exc:
        log.warning("PSX direct page fetch failed for %s: %s", symbol, exc)
        _PSX_SOURCE_FAILURE = type(exc).__name__
        return {}

    if soup:
        financial_tables = soup.select("#financials table")
        ratio_tables = soup.select("#ratios table")
        payload = {
            "source_url": url,
            "source_info": _page_source_info(soup, symbol),
            "financials_annual": _parse_table(financial_tables[0]) if financial_tables else [],
            "financials_quarterly": _parse_table(financial_tables[1]) if len(financial_tables) > 1 else [],
            "ratio_history": _parse_table(ratio_tables[0]) if ratio_tables else [],
        }
        info = payload["source_info"]
        profile = info.get("Profile") or {}
        equity = info.get("Equity Profile") or {}
        has_profile = any(value not in (None, "", [], {}) for value in profile.values())
        has_equity = any(value not in (None, "", [], {}) for value in equity.values())
        has_market_data = any(value not in (None, "", [], {}) for value in (info.get("Market Data") or {}).values())
        has_table_data = any(payload[key] for key in ("financials_annual", "financials_quarterly", "ratio_history"))
        if has_profile or has_equity or has_market_data or has_table_data:
            return payload

    # Daily durable ingestion uses only the official public DPS company page.
    # A denied, missing, or changed page must not trigger a second client or
    # alternate request pattern against the same upstream service.
    if not allow_fallback:
        return {}

    # Fallback retained for existing interactive callers only.
    try:
        import pypsx_toolkit
        t = pypsx_toolkit.Ticker(symbol)
        info = getattr(t, "info", None)
        if isinstance(info, dict) and info:
            ann_raw = info.get("Financials Annual") or {}
            qtr_raw = info.get("Financials Quarterly") or {}
            rat_raw = info.get("Ratios") or {}
            ann_records = _parse_pipe_dict_to_records(ann_raw, prefix="Y")
            qtr_records = _parse_pipe_dict_to_records(qtr_raw, prefix="Q")
            rat_records = _parse_pipe_dict_to_records(rat_raw, prefix="R")

            eq_raw = info.get("Equity Profile") or {}
            equity = {}
            if "Market Cap (000's)" in eq_raw:
                mc_k = _number(eq_raw["Market Cap (000's)"])
                if isinstance(mc_k, (int, float)):
                    equity["market_cap"] = mc_k * 1000
            if "Shares" in eq_raw:
                sh = _number(eq_raw["Shares"])
                if isinstance(sh, (int, float)):
                    equity["shares_outstanding"] = int(sh)
            if "Free Float" in eq_raw:
                ff = _number(eq_raw["Free Float"])
                if isinstance(ff, (int, float)):
                    equity["free_float_pct"] = ff

            source_info = {
                "symbol": symbol,
                "name": info.get("name") or symbol,
                "company_name": info.get("company_name") or symbol,
                "Profile": info.get("Profile") or {},
                "Governance": info.get("Governance") or {},
                "Equity Profile": eq_raw,
                "Financials Annual": ann_raw,
                "Financials Quarterly": qtr_raw,
                "Ratios": rat_raw,
                **equity,
            }
            return {
                "source_url": url,
                "source_info": source_info,
                "financials_annual": ann_records,
                "financials_quarterly": qtr_records,
                "ratio_history": rat_records,
            }
    except Exception as exc:
        log.warning("pypsx_toolkit fallback failed for %s: %s", symbol, exc)

    return {}


def _fetch_financial_reports(symbol: str) -> dict:
    global _PSX_ACCESS_DENIED, _PSX_SOURCE_FAILURE
    try:
        response = _request_with_retry(
            "POST",
            urljoin(_FINANCIALS_BASE, "annQtrStmts.php"),
            data={"name": "get_comp_data", "smbCode": symbol},
            headers={
                **_HEADERS,
                "Referer": _FINANCIALS_BASE,
                "Origin": "https://financials.psx.com.pk",
                "X-Requested-With": "XMLHttpRequest",
            },
        )
        if response.status_code in (403, 429):
            _PSX_ACCESS_DENIED = True
            log.warning("PSX financial-report index denied for %s (HTTP %d)", symbol, response.status_code)
            return {"financial_reports": [], "total_reports_count": 0,
                    "psx_reports_url": f"{_BASE}/company/{symbol}"}
        if response.status_code == 404 or response.status_code >= 500:
            _PSX_SOURCE_FAILURE = f"financial_reports_http_{response.status_code}"
            log.error("PSX financial-report source failed for %s (%s)", symbol, _PSX_SOURCE_FAILURE)
            return {"financial_reports": [], "total_reports_count": 0,
                    "psx_reports_url": f"{_BASE}/company/{symbol}"}
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
        # Top 6 most recent reports as requested
        return {
            "financial_reports": reports[:6],
            "total_reports_count": len(reports),
            "psx_reports_url": f"{_BASE}/company/{symbol}",
        }
    except Exception as exc:
        log.warning("PSX financial report index fetch failed for %s: %s", symbol, exc)
        _PSX_SOURCE_FAILURE = f"financial_reports_{type(exc).__name__}"
        return {
            "financial_reports": [],
            "total_reports_count": 0,
            "psx_reports_url": f"{_BASE}/company/{symbol}",
        }


def get_psx_company_table_data(symbol: str) -> dict:
    """Return normalized company-page statements, ratio history, and report links."""
    symbol = str(symbol).strip().upper()
    tables = _cached_fetch(f"psx:company-tables:v5:{symbol}", lambda: _fetch_company_tables(symbol))
    reports = _cached_fetch(f"psx:financial-report-index:v5:{symbol}", lambda: _fetch_financial_reports(symbol))
    return {**tables, **reports}
