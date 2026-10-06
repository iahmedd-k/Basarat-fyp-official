import subprocess
import os
from pathlib import Path

SSH_KEY = r"d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key"
REMOTE_USER = "ubuntu"
REMOTE_HOST = "193.123.84.223"

LOCAL_BACKEND = Path(__file__).resolve().parent.parent

FILES_TO_SYNC = [
    ("app/services/stock_service.py", "/app/app/services/stock_service.py"),
    ("app/tasks/refresh_fundamentals.py", "/app/app/tasks/refresh_fundamentals.py"),
    ("app/schemas/stock.py", "/app/app/schemas/stock.py"),
    ("data/config/symbol_universe.json", "/app/data/config/symbol_universe.json"),
]

CONTAINERS = [
    "basarat-app-1",
    "basarat-celery-worker-1",
    "basarat-celery-beat-1",
]

def run_ssh(cmd_str):
    cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{REMOTE_USER}@{REMOTE_HOST}", cmd_str]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout, res.stderr

def scp_file(local_path, remote_temp_path):
    cmd = ["scp", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", str(local_path), f"{REMOTE_USER}@{REMOTE_HOST}:{remote_temp_path}"]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(f"SCP failed for {local_path}: {res.stderr}")
    return res.returncode == 0

if __name__ == "__main__":
    print("Uploading updated files to remote host...")
    for rel_path, dest_in_container in FILES_TO_SYNC:
        local_file = LOCAL_BACKEND / rel_path
        filename = local_file.name
        remote_tmp = f"/tmp/{filename}"
        
        print(f"Transferring {rel_path} -> {remote_tmp}...")
        if scp_file(local_file, remote_tmp):
            for container in CONTAINERS:
                cp_cmd = f"sudo docker cp {remote_tmp} {container}:{dest_in_container}"
                out, err = run_ssh(cp_cmd)
                if err:
                    print(f"  [{container}] docker cp warning: {err.strip()}")
                else:
                    print(f"  [{container}] Updated {dest_in_container}")

    print("\nRestarting Celery Worker, Celery Beat, and FastAPI containers to load latest code...")
    for container in ["basarat-celery-worker-1", "basarat-celery-beat-1", "basarat-app-1"]:
        out, err = run_ssh(f"sudo docker restart {container}")
        print(f"Restarted {container}: {out.strip()} {err.strip()}")

    print("\nVerifying container status...")
    out, _ = run_ssh("sudo docker ps --format 'table {{.Names}}\t{{.Status}}'")
    print(out)
