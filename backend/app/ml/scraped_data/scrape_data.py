"""
Market Indices Router — KSE-100 / KSE-30 / KMI-30 constituents
=================================================================
Drop this file into your FastAPI project and include the router:

    from app.routers.market_indices import router as market_router
    app.include_router(market_router)

Endpoints (match your existing OpenAPI paths exactly):
    GET /api/v1/market/indices/kse-100
    GET /api/v1/market/indices/kse-30
    GET /api/v1/market/indices/kmi-30

Data source: PSX Data Portal's live index page
    https://dps.psx.com.pk/indices/{INDEX_CODE}
This is the same page PSX itself renders for index constituents — it's
scraped (PSX doesn't offer a JSON API for this), so a short in-memory
cache is used to avoid re-fetching on every request.

Install deps (if not already present):
    pip install fastapi httpx beautifulsoup4
"""

import argparse
import asyncio
import datetime
import json
import time
import logging
from pathlib import Path
from threading import Lock
from typing import List, Optional

import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

log = logging.getLogger("market_indices")

router = APIRouter(prefix="/api/v1/market/indices", tags=["Market"])

PSX_INDEX_URL = "https://dps.psx.com.pk/indices/{code}"
CACHE_TTL_SECONDS = 60  # index composition/prices don't need to be re-scraped every request

# Column order on the PSX index page, after the SYMBOL/NAME lead columns
VALUE_COLUMNS = [
    "name", "ldcp", "current", "change", "change_pct",
    "index_weight_pct", "index_points", "volume", "freefloat_m", "market_cap_m",
]


class IndexConstituent(BaseModel):
    symbol: str
    name: str
    ldcp: Optional[float] = Field(None, description="Last day closing price")
    current: Optional[float] = Field(None, description="Current/last traded price")
    change: Optional[float] = None
    change_pct: Optional[float] = None
    index_weight_pct: Optional[float] = Field(None, description="Weight in the index, %")
    index_points: Optional[float] = None
    volume: Optional[int] = None
    freefloat_m: Optional[float] = Field(None, description="Free float shares, millions")
    market_cap_m: Optional[float] = Field(None, description="Market cap, PKR millions")
    is_ex_dividend: bool = False


class IndexConstituentsResponse(BaseModel):
    index: str
    count: int
    constituents: List[IndexConstituent]
    cached: bool


# ---------------- scraper + cache ----------------

class _IndexCache:
    def __init__(self):
        self._lock = Lock()
        self._store: dict[str, tuple[float, List[IndexConstituent]]] = {}

    def get(self, key: str) -> Optional[List[IndexConstituent]]:
        with self._lock:
            entry = self._store.get(key)
            if not entry:
                return None
            fetched_at, data = entry
            if time.time() - fetched_at > CACHE_TTL_SECONDS:
                return None
            return data

    def set(self, key: str, data: List[IndexConstituent]) -> None:
        with self._lock:
            self._store[key] = (time.time(), data)


_cache = _IndexCache()


def _clean_number(text: str) -> Optional[float]:
    text = text.strip().replace(",", "").replace("%", "")
    if text in ("", "-", "N/A"):
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _parse_index_page(html: str) -> List[IndexConstituent]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if table is None:
        return []

    rows = table.find_all("tr")
    constituents: List[IndexConstituent] = []

    for row in rows:
        cells = row.find_all("td")
        if len(cells) < len(VALUE_COLUMNS) + 1:
            continue  # header row or malformed row

        # Last N cells are the fixed value columns; everything before that
        # is the symbol cell (which sometimes contains an "XD" ex-dividend flag).
        value_cells = cells[-len(VALUE_COLUMNS):]
        symbol_cell = cells[0]

        anchor = symbol_cell.find("a")
        symbol_text = (anchor.get_text(strip=True) if anchor else symbol_cell.get_text(strip=True))
        is_ex_dividend = "XD" in symbol_cell.get_text()

        values = [c.get_text(strip=True) for c in value_cells]
        record = dict(zip(VALUE_COLUMNS, values))

        try:
            constituents.append(IndexConstituent(
                symbol=symbol_text,
                name=record.get("name", ""),
                ldcp=_clean_number(record.get("ldcp", "")),
                current=_clean_number(record.get("current", "")),
                change=_clean_number(record.get("change", "")),
                change_pct=_clean_number(record.get("change_pct", "")),
                index_weight_pct=_clean_number(record.get("index_weight_pct", "")),
                index_points=_clean_number(record.get("index_points", "")),
                volume=int(_clean_number(record.get("volume", "")) or 0) or None,
                freefloat_m=_clean_number(record.get("freefloat_m", "")),
                market_cap_m=_clean_number(record.get("market_cap_m", "")),
                is_ex_dividend=is_ex_dividend,
            ))
        except Exception as exc:
            log.warning(f"Skipping malformed row for symbol {symbol_text!r}: {exc}")
            continue

    return constituents


async def _get_constituents(index_code: str) -> tuple[List[IndexConstituent], bool]:
    """Returns (constituents, was_cached)."""
    cached = _cache.get(index_code)
    if cached is not None:
        return cached, True

    url = PSX_INDEX_URL.format(code=index_code)
    try:
        async with httpx.AsyncClient(timeout=10.0, headers={
            "User-Agent": "Mozilla/5.0 (compatible; MarketIndicesService/1.0)"
        }) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        log.error(f"Failed to fetch {index_code} constituents from PSX: {exc}")
        raise HTTPException(
            status_code=502,
            detail=f"Could not reach PSX Data Portal for {index_code} constituents",
        )

    constituents = _parse_index_page(resp.text)
    if not constituents:
        raise HTTPException(
            status_code=502,
            detail=f"PSX returned no parseable data for {index_code} — page layout may have changed",
        )

    _cache.set(index_code, constituents)
    return constituents, False


# ---------------- endpoints ----------------

@router.get("/kse-100", response_model=IndexConstituentsResponse, summary="Get Kse 100 Constituents")
async def get_kse_100_constituents():
    constituents, cached = await _get_constituents("KSE100")
    return IndexConstituentsResponse(
        index="KSE-100", count=len(constituents), constituents=constituents, cached=cached
    )


@router.get("/kse-30", response_model=IndexConstituentsResponse, summary="Get Kse 30 Constituents")
async def get_kse_30_constituents():
    constituents, cached = await _get_constituents("KSE30")
    return IndexConstituentsResponse(
        index="KSE-30", count=len(constituents), constituents=constituents, cached=cached
    )


@router.get("/kmi-30", response_model=IndexConstituentsResponse, summary="Get Kmi 30 Constituents")
async def get_kmi_30_constituents():
    constituents, cached = await _get_constituents("KMI30")
    return IndexConstituentsResponse(
        index="KMI-30", count=len(constituents), constituents=constituents, cached=cached
    )


# ---------------- standalone download ----------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrape_data.py",
        description=(
            "Download PSX index constituents and their historical OHLCV.\n"
            "Without --symbols, saves a current constituent snapshot JSON per index.\n"
            "With --symbols (e.g. KSE100 KSE30 KMI30), saves a CSV per constituent "
            "with N years of daily history."
        ),
    )
    parser.add_argument("--symbols", nargs="+", default=None,
                        help="Index codes: KSE100, KSE30, KMI30, ...")
    parser.add_argument("--years", type=int, default=5,
                        help="Years of history to fetch back from today (default: 5)")
    parser.add_argument("--output-dir", default="psx_data",
                        help="Directory for output files (default: psx_data)")
    parser.add_argument("--delay", type=float, default=0.4,
                        help="Seconds to wait between symbol requests (default: 0.4)")
    return parser


async def _download_snapshots(output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for index_code, file_name in (("KSE100", "kse-100.json"), ("KSE30", "kse-30.json"), ("KMI30", "kmi-30.json")):
        constituents, _ = await _get_constituents(index_code)
        payload = IndexConstituentsResponse(
            index=index_code, count=len(constituents), constituents=constituents, cached=False
        )
        path = output_dir / file_name
        path.write_text(json.dumps(payload.model_dump(), indent=2), encoding="utf-8")
        print(f"Saved {len(constituents)} constituents to {path}")


def _download_history(index_codes: List[str], years: int, output_dir: Path, delay: float) -> None:
    import psxdata

    output_dir.mkdir(parents=True, exist_ok=True)
    cutoff = datetime.date.today() - datetime.timedelta(days=int(years * 365.25))
    total_rows = 0
    total_failed = 0

    for index_code in index_codes:
        constituents, _ = asyncio.run(_get_constituents(index_code))
        symbols = [c.symbol for c in constituents]
        print(f"[{index_code}] {len(symbols)} constituents — fetching {years}y history (from {cutoff})")
        for i, symbol in enumerate(symbols, 1):
            try:
                df = psxdata.stocks(symbol, start=cutoff.isoformat(), end=None)
            except Exception as exc:
                total_failed += 1
                print(f"[{index_code}] {i}/{len(symbols)} FAILED {symbol}: {exc}")
                continue
            if df is None or df.empty:
                total_failed += 1
                print(f"[{index_code}] {i}/{len(symbols)} no data {symbol}")
                continue
            df = df.sort_values("date").reset_index(drop=True)
            csv_path = output_dir / f"{symbol}.csv"
            df.to_csv(csv_path, index=False)
            total_rows += len(df)
            print(f"[{index_code}] {i}/{len(symbols)} {symbol} -> {csv_path.name} ({len(df)} rows)")
            time.sleep(delay)

    print(f"Done. {total_rows} rows written to {output_dir}; {total_failed} symbol(s) failed.")


if __name__ == "__main__":
    args = _build_parser().parse_args()
    out = Path(args.output_dir)
    if args.symbols:
        _download_history(args.symbols, args.years, out, args.delay)
    else:
        asyncio.run(_download_snapshots(out))