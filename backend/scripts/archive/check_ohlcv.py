import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import os
from pathlib import Path

ohlcv_dir = Path("/app/data/raw/ohlcv")
print("OHLCV Dir exists:", ohlcv_dir.exists())
if ohlcv_dir.exists():
    files = list(ohlcv_dir.glob("*.parquet")) + list(ohlcv_dir.glob("*.csv"))
    print("Files in OHLCV dir:", len(files))
    if files:
        print("Sample files:", [f.name for f in files[:5]])
else:
    print("Listing /app/data:")
    if Path("/app/data").exists():
        for p in Path("/app/data").rglob("*"):
            if p.is_file():
                print(" ", p)
"""

out, err = run_remote_python(code)
print("OUTPUT:")
print(out)
if err:
    print("ERR:", err)
