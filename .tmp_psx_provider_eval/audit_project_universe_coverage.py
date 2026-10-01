import json
from pathlib import Path
import sys

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE / "venv-psx-dps" / "Lib" / "site-packages"))
from psx_dps import Client

universe_path = Path("backend/data/config/symbol_universe.json")
universe = json.loads(universe_path.read_text(encoding="utf-8-sig"))
expected = {
    str(item.get("symbol", "")).upper()
    for item in universe
    if "KSE100" in item.get("indices", [])
}
if not expected:
    expected = {str(item.get("symbol", "")).upper() for item in universe}
with Client(cache_dir=str(BASE / "cache-psx-dps"), timeout=15, retries=1, daily_budget=20) as psx:
    rows = psx.history_by_date("2026-09-30")
received = {str(row.get("symbol", "")).upper() for row in rows}
payload = {
    "project_analysis_universe_size": len(expected),
    "provider_eod_rows": len(rows),
    "universe_symbols_present": len(expected & received),
    "universe_symbols_missing": sorted(expected - received),
    "extra_provider_symbols": len(received - expected),
}
out = BASE / "project_universe_coverage.json"
out.write_text(json.dumps(payload, indent=2), encoding="utf-8")
print(out.read_text(encoding="utf-8"))
