import json
from pathlib import Path

from psx_dps import Client

BASE = Path(__file__).parent
with Client(cache_dir=str(BASE / "cache-psx-dps"), timeout=15, retries=1, daily_budget=20) as psx:
    rows = psx.history_by_date("2026-09-30")

required = ("symbol", "open", "high", "low", "close", "volume")
missing = {key: sum(not row.get(key) for row in rows) for key in required}
unique_symbols = {str(row.get("symbol", "")).upper() for row in rows}
payload = {
    "rows": len(rows),
    "unique_symbols": len(unique_symbols),
    "duplicate_symbol_rows": len(rows) - len(unique_symbols),
    "missing_or_empty": missing,
    "HBL": next((row for row in rows if str(row.get("symbol", "")).upper() == "HBL"), None),
}
out = BASE / "psx_dps_history_date_audit.json"
out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
print(out.read_text(encoding="utf-8"))
