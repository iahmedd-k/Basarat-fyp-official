import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / "archive"))
from remote_exec import run_remote_python

code = """
import json
import traceback
from app.services.stock_service import StockService

service = StockService()
targets = ["BML", "IMAGE", "NCPL", "THCCL"]
for sym in targets:
    try:
        p = service._fetch_fundamentals_upstream(sym, allow_synthetic=True, force_refresh=True)
        print(f"{sym} SUCCESS: data_status={p.get('data_status')}, keys={len(p)}")
        print(f"  profile: {p.get('company_profile', {}).get('name')}")
        print(f"  ratios: {p.get('ratios')}")
    except Exception as e:
        print(f"{sym} ERROR: {e}")
        traceback.print_exc()
"""

if __name__ == "__main__":
    run_remote_python(code)
