import json
from datetime import datetime
from pathlib import Path
import sys

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE / "vendor-psxdata"))
from psxdata import PSXClient

client = PSXClient(cache_dir=str(BASE / "cache-psxdata"))
try:
    frame = client.fundamentals(cache=False)
    result = {
        "tested_at_local": datetime.now().astimezone().isoformat(),
        "ok": True,
        "count": len(frame),
        "columns": list(frame.columns),
        "HBL_count": int((frame["symbol"].astype(str).str.upper() == "HBL").sum()) if "symbol" in frame else None,
        "sample": frame.head(2).to_dict(orient="records"),
    }
except Exception as exc:
    result = {"tested_at_local": datetime.now().astimezone().isoformat(), "ok": False, "error_type": type(exc).__name__, "error": str(exc)}
out = BASE / "psxdata_all_fundamentals_result.json"
out.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
print(out.read_text(encoding="utf-8"))
