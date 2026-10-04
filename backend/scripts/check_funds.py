import subprocess
import json

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
    return res.stdout, res.stderr

if __name__ == "__main__":
    code = """
import json
from app.db.base import get_sync_session_factory
from app.models.fundamentals import StockFundamentals

with get_sync_session_factory()() as s:
    rows = s.query(StockFundamentals).all()
    print("FUNDAMENTALS SYMBOLS:", [r.symbol for r in rows])
    if rows:
        print("SAMPLE PAYLOAD FOR", rows[0].symbol, ":", json.dumps(rows[0].payload)[:300])
"""
    out, err = run_remote_python(code)
    print("STDOUT:", out)
    if err:
        print("STDERR:", err)
