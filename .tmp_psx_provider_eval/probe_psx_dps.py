import json
from datetime import datetime
from pathlib import Path

from psx_dps import Client

BASE = Path(__file__).parent
OUT = BASE / "psx_dps_result.json"


def summarize_rows(rows, date_keys=()):
    if not rows:
        return {"count": 0, "keys": [], "first": None, "last_date": None}
    rows = [dict(row) for row in rows]
    first = rows[0]
    last_date = None
    for row in reversed(rows):
        last_date = next((row.get(key) for key in date_keys if row.get(key)), None)
        if last_date:
            break
    return {"count": len(rows), "keys": sorted(first), "first": first, "last_date": last_date}


result = {"tested_at_local": datetime.now().astimezone().isoformat(), "calls": {}}
with Client(cache_dir=str(BASE / "cache-psx-dps"), timeout=15, retries=1, daily_budget=20) as psx:
    for name, call in (
        ("market_watch", lambda: psx.market_watch(force_refresh=True)),
        ("eod_HBL_since_2026-09-01", lambda: psx.eod("HBL", since="2026-09-01", force_refresh=True)),
        ("KSE100_constituents", lambda: psx.index_constituents("KSE100", force_refresh=True)),
        ("intraday_HBL", lambda: psx.intraday("HBL", force_refresh=True)),
    ):
        try:
            value = call()
            result["calls"][name] = {"ok": True, **summarize_rows(value, ("date", "time"))}
        except Exception as exc:
            result["calls"][name] = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}

result["client_features"] = sorted(name for name in dir(Client) if not name.startswith("_") and callable(getattr(Client, name)))
result["has_fundamentals_method"] = any("fundament" in name.lower() for name in result["client_features"])
OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
print(OUT.read_text(encoding="utf-8"))
