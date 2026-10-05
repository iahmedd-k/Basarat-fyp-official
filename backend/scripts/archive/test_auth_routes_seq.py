import json
import urllib.request
import urllib.error
import sys
from pathlib import Path
import subprocess
import base64

backend_dir = Path(__file__).resolve().parent.parent

SSH_KEY = r"d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key"
REMOTE_USER = "ubuntu"
REMOTE_HOST = "193.123.84.223"

# Fetch token
fetch_token_code = """
import json
from datetime import timedelta
from app.core.security import create_access_token
from app.db.base import get_sync_session_factory
from app.models.user import User

with get_sync_session_factory()() as s:
    u = s.query(User).filter(User.email == "admin@basarat.pk").first()
    if not u:
        u = s.query(User).first()
    token = create_access_token(
        data={"sub": str(u.id), "email": u.email, "role": getattr(u, "role", "admin")},
        expires_delta=timedelta(days=7)
    )
    print("JWT_TOKEN:" + token)
"""

b64 = base64.b64encode(fetch_token_code.encode("utf-8")).decode("ascii")
remote_cmd = f"echo '{b64}' | base64 -d | sudo docker exec -i basarat-app-1 python"
cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{REMOTE_USER}@{REMOTE_HOST}", remote_cmd]
res = subprocess.run(cmd, capture_output=True, text=True)

token = None
for line in res.stdout.splitlines():
    if line.startswith("JWT_TOKEN:"):
        token = line.split("JWT_TOKEN:")[1].strip()
        break

print("Token:", token[:20])

BASE_URL = "http://193.123.84.223:8000"

auth_routes = [
    "/api/v1/users/me",
    "/api/v1/users/profile",
    "/api/v1/watchlists",
    "/api/v1/watchlists/default",
    "/api/v1/watchlists/check/OGDC",
    "/api/v1/forecast/OGDC",
    "/api/v1/forecast/OGDC/history",
    "/api/v1/recommendations",
    "/api/v1/recommendations/engine-weights",
    "/api/v1/recommendations/OGDC",
    "/api/v1/recommendations/OGDC/target-stop",
    "/api/v1/portfolio",
    "/api/v1/portfolio/holdings",
    "/api/v1/portfolio/pnl",
    "/api/v1/portfolio/allocation",
    "/api/v1/portfolio/performance",
    "/api/v1/portfolio/transactions",
    "/api/v1/risk/var",
    "/api/v1/risk/stress-test",
    "/api/v1/sentiment/market-overview",
    "/api/v1/sentiment/OGDC",
    "/api/v1/sentiment/OGDC/history",
    "/api/v1/sentiment/OGDC/news",
    "/api/v1/events/calendar",
    "/api/v1/alerts",
    "/api/v1/alerts/rules",
    "/api/v1/alerts/rules/check/OGDC",
    "/api/v1/notifications",
    "/api/v1/community/feed",
    "/api/v1/community/posts/market",
    "/api/v1/community/posts/stock/OGDC",
    "/api/v1/community/me",
    "/api/v1/community/me/posts",
    "/api/v1/community/notifications",
    "/api/v1/community/notifications/unread-count",
    "/api/v1/assistant/quick-prompts",
    "/api/v1/assistant/conversations",
    "/api/v1/admin/community/reports",
]

for route in auth_routes:
    url = f"{BASE_URL}{route}"
    req = urllib.request.Request(url, headers={
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
        "User-Agent": "BasaratTest/1.0"
    })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            print(f"[SUCCESS {resp.status}] {route:40} -> {type(data).__name__} | {str(data)[:90]}", flush=True)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")[:100]
        print(f"[HTTP {e.code}] {route:40} -> {err_body}", flush=True)
    except Exception as e:
        print(f"[EXC]     {route:40} -> {str(e)}", flush=True)
