import json
from pathlib import Path
import sys

import pandas as pd

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE / "vendor-psxdata"))
from psxdata import PSXClient

client = PSXClient(cache_dir=str(BASE / "cache-psxdata"))
frame = client.screener(cache=True)
payload = {
    "rows": len(frame),
    "columns": list(frame.columns),
    "null_counts": {str(col): int(frame[col].isna().sum()) for col in frame.columns},
    "null_percent": {str(col): round(float(frame[col].isna().mean() * 100), 2) for col in frame.columns},
    "HBL": frame[frame["symbol"].astype(str).str.upper() == "HBL"].head(1).to_dict(orient="records") if "symbol" in frame else [],
}
out = BASE / "psxdata_screener_audit.json"
out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
print(out.read_text(encoding="utf-8"))
