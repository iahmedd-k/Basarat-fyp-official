import json
from datetime import date, datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "vendor-psxdata"))
from psxdata import PSXClient

BASE = Path(__file__).parent
OUT = BASE / "psxdata_result.json"


def summarize(value, sample_count=1):
    if hasattr(value, "empty"):
        rows = value.to_dict(orient="records") if not value.empty else []
        return {"count": len(rows), "columns": list(value.columns), "samples": rows[:sample_count], "last": rows[-1] if rows else None}
    if isinstance(value, dict):
        return {"keys": sorted(value), "counts": {str(k): len(v) if hasattr(v, "__len__") else None for k, v in value.items()}}
    return {"count": len(value) if hasattr(value, "__len__") else None, "type": type(value).__name__, "sample": list(value[:sample_count]) if isinstance(value, (list, tuple)) else str(value)}


result = {"tested_at_local": datetime.now().astimezone().isoformat(), "calls": {}}
client = PSXClient(cache_dir=str(BASE / "cache-psxdata"))
for name, call in (
    ("quote_HBL", lambda: client.quote("HBL", cache=False)),
    ("stocks_HBL_since_2026-09-01", lambda: client.stocks("HBL", start="2026-09-01", end=date.today(), cache=False)),
    ("symbols", lambda: client.symbols(cache=False)),
    ("KSE100", lambda: client.indices("KSE100", cache=False)),
    ("fundamentals_HBL", lambda: client.fundamentals("HBL", cache=False)),
):
    try:
        value = call()
        result["calls"][name] = {"ok": True, **summarize(value)}
    except Exception as exc:
        result["calls"][name] = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}

result["has_dividends_method"] = hasattr(client, "dividends")
OUT.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
print(OUT.read_text(encoding="utf-8"))
