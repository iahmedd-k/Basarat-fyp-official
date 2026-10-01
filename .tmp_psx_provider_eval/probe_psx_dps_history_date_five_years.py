import json
from datetime import datetime
from pathlib import Path

from psx_dps import Client

result = {"tested_at_local": datetime.now().astimezone().isoformat(), "requested_date": "2021-10-01"}
with Client(cache_dir=str(Path(__file__).parent / "cache-psx-dps"), timeout=15, retries=1, daily_budget=20) as psx:
    try:
        rows = psx.history_by_date("2021-10-01", force_refresh=True)
        result.update({
            "ok": True,
            "count": len(rows),
            "columns": sorted(rows[0]) if rows else [],
            "HBL": next((row for row in rows if str(row.get("symbol", "")).upper() == "HBL"), None),
        })
    except Exception as exc:
        result.update({"ok": False, "error_type": type(exc).__name__, "error": str(exc)})
out = Path(__file__).with_name("psx_dps_history_date_five_years_result.json")
out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
print(out.read_text(encoding="utf-8"))
