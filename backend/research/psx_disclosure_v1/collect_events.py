"""Backfill PSX company announcement rows into the isolated event dataset.

The PSX DPS announcements endpoint is an HTML portal endpoint, not a documented
stable public API. Validate response layout before using this for research.
This collector preserves the raw announcement rows and never marks coverage
verified automatically.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
import time
from datetime import date, datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
import requests
from bs4 import BeautifulSoup

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
DATA_DIR = HERE / "data"
RAW_PATH = DATA_DIR / "psx_announcements_raw.csv"
EVENTS_PATH = DATA_DIR / "events.csv"
COVERAGE_PATH = DATA_DIR / "events_coverage.json"
URL = "https://dps.psx.com.pk/announcements"
PAGE_URL = "https://dps.psx.com.pk/announcements/companies"
BASE = "https://dps.psx.com.pk"
PKT = timezone(timedelta(hours=5))
HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; BasaratResearch/1.0)",
    "Referer": PAGE_URL,
    "Origin": BASE,
    "X-Requested-With": "XMLHttpRequest",
}
LOG = logging.getLogger("psx_disclosure_v1.collect_events")
RAW_COLUMNS = ["date", "time", "symbol", "company", "title", "document_url", "published_at", "source_id"]
EVENT_COLUMNS = [
    "symbol", "published_at", "title", "document_url", "event_type", "meeting_date",
    "dividend_pkr_per_share", "dividend_face_value_pct", "face_value_pkr", "ex_date",
    "eps_current", "eps_comparison", "eps_period", "eps_basis", "source_id",
]


def _event_type(title: str) -> str:
    text = (title or "").lower()
    if "board meeting" in text or "meeting of the board" in text:
        return "board_meeting"
    if any(x in text for x in ["bonus", "right issue", "rights issue"]):
        return "bonus_or_rights"
    if any(x in text for x in ["dividend", "payout"]):
        return "dividend"
    if any(x in text for x in ["financial result", "financial statement", "earnings", "profit after tax", "eps"]):
        return "earnings"
    if any(x in text for x in ["material information", "material fact", "discovery", "agreement", "commissioning", "acquisition"]):
        return "material_information"
    return "other"


def _parse_table(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    parsed = []
    for row in soup.select("tr"):
        cols = row.find_all(["td", "th"])
        texts = [c.get_text(" ", strip=True) for c in cols]
        if len(texts) < 5 or texts[0].strip().upper() == "DATE":
            continue
        raw_date, raw_time, symbol, company, title = texts[:5]
        if not symbol or not title:
            continue
        published = None
        for fmt in ["%b %d, %Y %I:%M %p", "%b %d, %Y %H:%M", "%d-%b-%Y %I:%M %p"]:
            try:
                published = datetime.strptime(f"{raw_date} {raw_time}", fmt).replace(tzinfo=PKT)
                break
            except ValueError:
                pass
        if published is None:
            LOG.warning("Could not parse publication date/time: %r %r", raw_date, raw_time)
            continue
        doc_url = ""
        for a in row.find_all("a"):
            href = a.get("href", "")
            if "/download/" in href or href.lower().endswith(".pdf"):
                doc_url = urljoin(BASE, href)
                break
        identity = "|".join([symbol.upper(), published.isoformat(), " ".join(title.lower().split()), doc_url])
        source_id = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        parsed.append({"date": raw_date, "time": raw_time, "symbol": symbol.upper().strip(),
                       "company": company, "title": title, "document_url": doc_url,
                       "published_at": published.isoformat(), "source_id": source_id})
    return parsed


def _month_ranges(start: date, end: date):
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        if cursor.month == 12:
            next_month = date(cursor.year + 1, 1, 1)
        else:
            next_month = date(cursor.year, cursor.month + 1, 1)
        lo = max(start, cursor)
        hi = min(end, next_month - timedelta(days=1))
        yield lo, hi
        cursor = next_month


def _fetch_range(client: requests.Session, start: date, end: date, page_size: int, pause: float) -> tuple[list[dict], int]:
    found: list[dict] = []
    offset = 0
    pages = 0
    while True:
        payload = {
            "type": "C", "symbol": "", "query": "", "count": str(page_size),
            "offset": str(offset), "date_from": start.isoformat(), "date_to": end.isoformat(),
            "page": "annc",
        }
        last_error = None
        for attempt in range(3):
            try:
                response = client.post(URL, data=payload, headers=HEADERS, timeout=45)
                response.raise_for_status()
                html = response.text
                rows = _parse_table(html)
                # A non-empty response without either parsed records or a table
                # is treated as a source/layout failure, never as an empty month.
                if html.strip() and not rows and "<tr" not in html.lower():
                    raise RuntimeError("PSX response did not contain an announcement table")
                break
            except Exception as exc:
                last_error = exc
                time.sleep(1.5 * (attempt + 1))
        else:
            raise RuntimeError(f"PSX request failed for {start}..{end}: {last_error}")
        pages += 1
        found.extend(rows)
        LOG.info("%s..%s offset=%d parsed=%d", start, end, offset, len(rows))
        if len(rows) < page_size:
            break
        offset += len(rows)
        time.sleep(pause)
    return found, pages


def _save(rows: pd.DataFrame, start: date, end: date, completed: list[str], failures: list[str], pages: int) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_PATH.exists():
        old = pd.read_csv(RAW_PATH).reindex(columns=RAW_COLUMNS)
        rows = pd.concat([old, rows], ignore_index=True)
    rows = rows.reindex(columns=RAW_COLUMNS).drop_duplicates("source_id", keep="last")
    rows.to_csv(RAW_PATH, index=False, encoding="utf-8-sig")
    canonical = pd.DataFrame({
        "symbol": rows.symbol,
        "published_at": rows.published_at,
        "title": rows.title,
        "document_url": rows.document_url,
        "event_type": rows.title.map(_event_type),
        "meeting_date": "",
        "dividend_pkr_per_share": "",
        "dividend_face_value_pct": "",
        "face_value_pkr": "",
        "ex_date": "",
        "eps_current": "",
        "eps_comparison": "",
        "eps_period": "",
        "eps_basis": "",
        "source_id": rows.source_id,
    }).reindex(columns=EVENT_COLUMNS)
    canonical.to_csv(EVENTS_PATH, index=False, encoding="utf-8-sig")
    manifest = {
        "requested_start": start.isoformat(), "requested_end": end.isoformat(),
        "coverage_start": start.isoformat(), "coverage_end": end.isoformat(),
        "coverage_verified": False,
        "verification_note": "Collector output only. Confirm every date range paginated successfully, inspect symbol/date coverage and parser output, and verify PSX returned all rows before changing coverage_verified to true.",
        "completed_months": completed, "failed_months": failures,
        "pages_fetched": pages, "raw_rows_deduplicated": int(len(rows)),
        "numeric_facts": "Not extracted; enrich fields from linked PSX documents before model training.",
        "source": PAGE_URL,
    }
    COVERAGE_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def backfill(start: date, end: date, page_size: int = 100, pause: float = 0.4) -> dict:
    if start > end:
        raise ValueError("--from must be on or before --to")
    completed: list[str] = []
    failed: list[str] = []
    all_rows: list[dict] = []
    total_pages = 0
    with requests.Session() as client:
        for lo, hi in _month_ranges(start, end):
            key = f"{lo.isoformat()}..{hi.isoformat()}"
            try:
                rows, pages = _fetch_range(client, lo, hi, page_size, pause)
                all_rows.extend(rows)
                total_pages += pages
                completed.append(key)
                LOG.info("Completed %s: %d announcements", key, len(rows))
                # Persist after every month so a later failure does not lose the backfill.
                current = pd.DataFrame(all_rows)
                if current.empty:
                    current = pd.DataFrame(columns=RAW_COLUMNS)
                _save(current, start, end, completed, failed, total_pages)
            except Exception as exc:
                failed.append(key)
                LOG.exception("Failed range %s: %s", key, exc)
                current = pd.DataFrame(all_rows) if all_rows else pd.DataFrame(columns=RAW_COLUMNS)
                _save(current, start, end, completed, failed, total_pages)
                raise
    final = pd.read_csv(RAW_PATH)
    return {"rows": len(final), "completed_months": len(completed), "pages": total_pages,
            "failed_months": failed, "events_csv": str(EVENTS_PATH), "coverage_verified": False}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", type=date.fromisoformat, required=True, help="First announcement date YYYY-MM-DD")
    parser.add_argument("--to", dest="end", type=date.fromisoformat, required=True, help="Last announcement date YYYY-MM-DD")
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--pause", type=float, default=0.4, help="Seconds between paginated requests")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(backfill(args.start, args.end, args.page_size, args.pause), indent=2))


if __name__ == "__main__":
    main()
