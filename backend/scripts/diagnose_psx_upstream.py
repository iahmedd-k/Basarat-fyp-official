"""Diagnose which pypsx_toolkit upstream sources work from the current runtime.

Runs inside the deployed container (or locally) to see which PSX/upstream data
sources resolve and which are blocked. Run with:
    docker compose -f docker-compose.production.yml exec app python scripts/diagnose_psx_upstream.py
"""

import socket
import time
import warnings

warnings.filterwarnings("ignore")

import pypsx_toolkit

SYMBOL = "UBL"


def describe(value):
    if hasattr(value, "empty"):
        return f"DataFrame rows={len(value)} cols={list(value.columns)[:6]}"
    if isinstance(value, dict):
        nonnull = {k: v for k, v in value.items() if v not in (None, "", [], {})}
        return f"dict keys={list(value.keys())[:8]} nonnull={list(nonnull.keys())[:8]}"
    if value is None:
        return "None"
    return f"{type(value).__name__} {str(value)[:120]}"


def run(label, fn):
    start = time.time()
    try:
        result = fn()
        elapsed = round(time.time() - start, 2)
        print(f"[OK ] {label} ({elapsed}s) -> {describe(result)}")
        return result
    except Exception as exc:
        elapsed = round(time.time() - start, 2)
        print(f"[ERR] {label} ({elapsed}s) -> {type(exc).__name__}: {str(exc)[:200]}")
        return None


def main():
    print(f"pypsx_toolkit version: {getattr(pypsx_toolkit, '__version__', '?')}")
    print(f"hostname: {socket.gethostname()}")
    print("---")

    run("market_watch", lambda: pypsx_toolkit.market_watch())
    run("Ticker.info", lambda: pypsx_toolkit.Ticker(SYMBOL).info)
    run("get_company_fundamentals", lambda: pypsx_toolkit.get_company_fundamentals(SYMBOL, format="dataframe"))
    run("get_snapshot", lambda: pypsx_toolkit.get_snapshot(SYMBOL))
    run("get_quote", lambda: pypsx_toolkit.get_quote(SYMBOL, format="dataframe"))
    run("get_dividend_info", lambda: pypsx_toolkit.get_dividend_info(SYMBOL, format="dataframe"))
    run("get_business_description", lambda: pypsx_toolkit.get_business_description(SYMBOL))
    run("get_indices", lambda: pypsx_toolkit.get_indices())


if __name__ == "__main__":
    main()