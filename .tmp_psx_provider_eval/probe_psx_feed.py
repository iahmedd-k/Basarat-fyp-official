import json
from datetime import date, datetime
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent / "vendor-psx-feed"))
from psx import stocks, tickers

result = {"tested_at_local": datetime.now().astimezone().isoformat(), "calls": {}}
for name, call in (
    ("tickers", tickers),
    ("stocks_HBL_September_2026", lambda: stocks("HBL", start=date(2026, 9, 1), end=date(2026, 9, 30))),
):
    try:
        value = call()
        if hasattr(value, "empty"):
            rows = value.reset_index().to_dict(orient="records") if not value.empty else []
            result["calls"][name] = {"ok": True, "rows": len(rows), "columns": list(value.reset_index().columns), "first": rows[0] if rows else None, "last": rows[-1] if rows else None}
        else:
            result["calls"][name] = {"ok": True, "rows": len(value), "type": type(value).__name__, "first": value[:1]}
    except Exception as exc:
        result["calls"][name] = {"ok": False, "error_type": type(exc).__name__, "error": str(exc)}

result["exports"] = [name for name in dir(sys.modules["psx"]) if not name.startswith("_")]
result["has_live_quote"] = any("quote" in name.lower() for name in result["exports"])
Path(__file__).with_name("psx_feed_result.json").write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
print(json.dumps(result, indent=2, default=str))
