"""
PKR/USD Exchange Rate Fetcher — thin wrapper around the Frankfurter API.

Fetches daily PKR/USD rates from the State Bank of Pakistan (SBP) provider
via the free Frankfurter API.  Returns a DataFrame so callers never touch
the HTTP layer directly.
"""

import json
import logging
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import requests

log = logging.getLogger(__name__)

_FRANKFURTER_URL = "https://api.frankfurter.dev/v2/rates"
_DEFAULT_OUTPUT_DIR = Path("data/config/macro")
_DEFAULT_CSV = _DEFAULT_OUTPUT_DIR / "pkr_usd.csv"
_DEFAULT_LOG = _DEFAULT_OUTPUT_DIR / "_fx_fetch_log.json"


def fetch_pkr_usd(
    start: date,
    end: date,
) -> pd.DataFrame:
    """Fetch daily PKR/USD rates from Frankfurter (SBP provider).

    Returns a DataFrame with columns ``[date, rate]`` sorted by date.
    Returns an empty DataFrame on failure.
    """
    params = {
        "from": start.isoformat(),
        "to": end.isoformat(),
        "providers": "SBP",
        "base": "USD",
    }

    log.info("Fetching PKR/USD  %s -> %s", start, end)
    try:
        resp = requests.get(_FRANKFURTER_URL, params=params, timeout=30)
        resp.raise_for_status()
    except requests.RequestException as exc:
        log.error("Frankfurter API request failed: %s", exc)
        return pd.DataFrame(columns=["date", "rate"])

    data = resp.json()
    # v2 returns a flat list of {date, base, quote, rate} dicts
    if not isinstance(data, list) or not data:
        log.warning("No data returned from Frankfurter for %s -> %s", start, end)
        return pd.DataFrame(columns=["date", "rate"])

    # Filter for PKR quotes only
    pkr_records = [r for r in data if r.get("quote") == "PKR"]
    if not pkr_records:
        log.warning("No PKR rates found in response")
        return pd.DataFrame(columns=["date", "rate"])

    rows = [{"date": r["date"], "rate": float(r["rate"])} for r in pkr_records]

    if not rows:
        log.warning("No PKR rates found in response")
        return pd.DataFrame(columns=["date", "rate"])

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)

    log.info("  Fetched %d PKR/USD rates (%s to %s)", len(df), df["date"].min().date(), df["date"].max().date())
    return df


def load_existing_rates(output_dir: Optional[Path] = None) -> pd.DataFrame:
    """Load previously saved PKR/USD CSV, or return empty DataFrame."""
    csv_path = (output_dir or _DEFAULT_OUTPUT_DIR) / "pkr_usd.csv"
    if not csv_path.exists():
        return pd.DataFrame(columns=["date", "rate"])
    try:
        df = pd.read_csv(csv_path)
        df["date"] = pd.to_datetime(df["date"])
        return df.sort_values("date").reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=["date", "rate"])


def save_rates(df: pd.DataFrame, output_dir: Optional[Path] = None) -> Path:
    """Save PKR/USD rates to CSV."""
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "pkr_usd.csv"
    df_out = df.copy()
    df_out["date"] = df_out["date"].dt.strftime("%Y-%m-%d")
    df_out.to_csv(path, index=False)
    log.info("Saved %d rates -> %s", len(df_out), path)
    return path


def save_fetch_log(entry: dict, output_dir: Optional[Path] = None) -> None:
    """Append a run entry to the fetch log."""
    out_dir = output_dir or _DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    log_path = out_dir / "_fx_fetch_log.json"
    existing = {"runs": []}
    if log_path.exists():
        try:
            existing = json.loads(log_path.read_text(encoding="utf-8"))
        except Exception:
            pass
    existing["runs"].append(entry)
    log_path.write_text(json.dumps(existing, indent=2, ensure_ascii=False), encoding="utf-8")
