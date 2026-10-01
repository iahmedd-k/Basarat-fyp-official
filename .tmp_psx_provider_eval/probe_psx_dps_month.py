import json
from datetime import datetime
from pathlib import Path

from psx_dps import Client

result = {"tested_at_local": datetime.now().astimezone().isoformat()}
with Client(cache_dir=str(Path(__file__).parent / "cache-psx-dps"), timeout=15, retries=1, daily_budget=20) as psx:
    try:
        rows = psx.history_by_month("HBL", 9, 2026, force_refresh=True)
        result["ok"] = True
        result["count"] = len(rows)
        result["columns"] = sorted(rows[0]) if rows else []
        result["first"] = rows[0] if rows else None
    except Exception as exc:
        result.update({"ok": False, "error_type": type(exc).__name__, "error": str(exc)})
out = Path(__file__).with_name("psx_dps_month_result.json")
out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
print(out.read_text(encoding="utf-8"))
