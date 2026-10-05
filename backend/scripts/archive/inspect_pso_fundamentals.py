import subprocess
import base64
import json

SSH_KEY = r"d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key"
REMOTE_USER = "ubuntu"
REMOTE_HOST = "193.123.84.223"

def main():
    py_code = """
import json
from app.db.base import get_sync_session_factory
from app.models.fundamentals import StockFundamentals

with get_sync_session_factory()() as s:
    f = s.query(StockFundamentals).filter(StockFundamentals.symbol == 'PSO').first()
    if f:
        print("=== PSO DB PAYLOAD ===")
        print("Keys:", list(f.payload.keys()))
        print("Company Profile:", json.dumps(f.payload.get("company_profile"), indent=2))
        print("Trading Limits:", json.dumps(f.payload.get("trading_limits"), indent=2))
        print("Sector Overview:", json.dumps(f.payload.get("sector_overview"), indent=2))
        print("Ratios:", json.dumps(f.payload.get("ratios"), indent=2))
    else:
        print("No DB row for PSO")
"""
    b64 = base64.b64encode(py_code.encode("utf-8")).decode("ascii")
    remote_cmd = f"echo '{b64}' | base64 -d | sudo docker exec -i basarat-app-1 python"
    cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{REMOTE_USER}@{REMOTE_HOST}", remote_cmd]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:\n", res.stdout)
    if res.stderr:
        print("STDERR:\n", res.stderr)

if __name__ == "__main__":
    main()
