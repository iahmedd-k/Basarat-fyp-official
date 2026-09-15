"""
OHLCV Fetcher — fetches daily OHLCV from PSX.

Uses ``psx-data-reader`` as the primary source, with a direct PSX scraper
as fallback (the library is broken since PSX renamed their TIME column to DATE).

Keeps the external library behind our own interface so it can be swapped
without touching calling code.
"""

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, timedelta
from calendar import monthrange
from typing import List, Tuple

import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup

log = logging.getLogger(__name__)

_PSX_HISTORY_URL = "https://dps.psx.com.pk/historical"
_SESSION_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; OHLCVScraper/1.0)"}


def _month_range(start: date, end: date) -> List[Tuple[int, int]]:
    """Return list of (year, month) tuples covering start..end."""
    months = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        months.append((y, m))
        m += 1
        if m > 12:
            m = 1
            y += 1
    return months


def _fetch_month(session: requests.Session, symbol: str, year: int, month: int) -> pd.DataFrame:
    """Fetch one month of daily data for *symbol* from PSX."""
    post = {"month": month, "year": year, "symbol": symbol}
    resp = session.post(_PSX_HISTORY_URL, data=post, timeout=30)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    headers = [th.get_text(strip=True).upper() for th in soup.select("th")]

    if not headers:
        return pd.DataFrame()

    rows_data = {h: [] for h in headers}
    for row in soup.select("tr"):
        cols = [td.get_text(strip=True) for td in row.select("td")]
        if not cols or len(cols) != len(headers):
            continue
        for key, value in zip(headers, cols):
            rows_data[key].append(value)

    if not rows_data.get(headers[0]):
        return pd.DataFrame()

    df = pd.DataFrame(rows_data, columns=headers)
    return df


def _fetch_symbol_direct(
    symbol: str,
    start: date,
    end: date,
    max_workers: int = 4,
) -> pd.DataFrame:
    """Fetch OHLCV by scraping PSX historical endpoint month-by-month."""
    months = _month_range(start, end)
    all_dfs: List[pd.DataFrame] = []

    session = requests.Session()
    session.headers.update(_SESSION_HEADERS)

    def _fetch_one(args):
        y, m = args
        try:
            return _fetch_month(session, symbol, y, m)
        except Exception as exc:
            log.debug("  %s %d-%02d fetch failed: %s", symbol, y, m, exc)
            return pd.DataFrame()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_fetch_one, args): args for args in months}
        for future in as_completed(futures):
            df = future.result()
            if not df.empty:
                all_dfs.append(df)

    if not all_dfs:
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    combined = pd.concat(all_dfs, ignore_index=True)

    # Map PSX column names to our snake_case names
    col_map = {
        "DATE": "date",
        "OPEN": "open",
        "HIGH": "high",
        "LOW": "low",
        "CLOSE": "close",
        "VOLUME": "volume",
    }
    combined = combined.rename(columns=col_map)
    desired = ["date", "open", "high", "low", "close", "volume"]
    combined = combined[[c for c in desired if c in combined.columns]]

    # Parse date
    combined["date"] = pd.to_datetime(combined["date"], format="%b %d, %Y")

    # Parse numeric columns
    for col in ["open", "high", "low", "close"]:
        if col in combined.columns:
            combined[col] = (
                combined[col]
                .str.replace(",", "", regex=False)
                .astype(np.float64)
            )
    if "volume" in combined.columns:
        combined["volume"] = (
            combined["volume"]
            .str.replace(",", "", regex=False)
            .astype(np.float64)
        )

    combined = combined.dropna(subset=["open", "high", "low", "close"], how="all")
    combined = combined.drop_duplicates(subset=["date"], keep="last")
    combined = combined.sort_values("date").reset_index(drop=True)
    return combined


def fetch_ohlcv(
    symbol: str,
    start: date | None = None,
    end: date | None = None,
) -> pd.DataFrame:
    """Fetch daily OHLCV for *symbol* between *start* and *end* (inclusive).

    Returns a DataFrame with columns ``[date, open, high, low, close, volume]``
    sorted by date ascending.  Returns an empty DataFrame if no data is found.
    """
    if end is None:
        end = date.today()
    if start is None:
        start = end - timedelta(days=5 * 365)

    log.info("Fetching OHLCV for %s  %s -> %s", symbol, start, end)

    # Try psx-data-reader first, fall back to direct scraping
    try:
        from psx import stocks
        df = stocks(symbol, start=start, end=end)
        if df is not None and not (hasattr(df, "empty") and df.empty):
            # Normalize column names
            col_map = {"Date": "date", "Open": "open", "High": "high",
                       "Low": "low", "Close": "close", "Volume": "volume"}
            df = df.rename(columns=col_map)
            desired = ["date", "open", "high", "low", "close", "volume"]
            df = df[[c for c in desired if c in df.columns]]
            if not pd.api.types.is_datetime64_any_dtype(df["date"]):
                df["date"] = pd.to_datetime(df["date"])
            df = df.dropna(subset=["open", "high", "low", "close"], how="all")
            df = df.sort_values("date").reset_index(drop=True)
            log.info("  %s: %d rows (%s to %s) [psx-data-reader]", symbol, len(df), df["date"].min(), df["date"].max())
            return df
    except Exception as exc:
        log.info("  psx-data-reader failed (%s), using direct scraper", exc)

    # Direct scraper fallback
    df = _fetch_symbol_direct(symbol, start, end)
    if df.empty:
        log.warning("No data returned for %s", symbol)
        return pd.DataFrame(columns=["date", "open", "high", "low", "close", "volume"])

    log.info("  %s: %d rows (%s to %s) [direct]", symbol, len(df), df["date"].min(), df["date"].max())
    return df
