import subprocess
import sys

SSH_KEY = r"d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key"
REMOTE_USER = "ubuntu"
REMOTE_HOST = "193.123.84.223"

def run_remote_python(code: str, container: str = "basarat-app-1"):
    import base64
    b64 = base64.b64encode(code.encode("utf-8")).decode("ascii")
    remote_cmd = f"echo '{b64}' | base64 -d | sudo docker exec -i {container} python"
    
    cmd = [
        "ssh",
        "-i", SSH_KEY,
        "-o", "StrictHostKeyChecking=no",
        f"{REMOTE_USER}@{REMOTE_HOST}",
        remote_cmd
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    print("STDOUT:")
    print(res.stdout)
    if res.stderr:
        print("STDERR:")
        print(res.stderr)
    return res.returncode

if __name__ == "__main__":
    test_code = """
import json
from app.db.base import get_sync_session_factory
from app.models.fundamentals import StockFundamentals
from app.models.stock import Stock

with get_sync_session_factory()() as s:
    stocks_count = s.query(Stock).count()
    funds_count = s.query(StockFundamentals).count()
    print(json.dumps({'stocks_count': stocks_count, 'fundamentals_count': funds_count}))
"""
    run_remote_python(test_code)
