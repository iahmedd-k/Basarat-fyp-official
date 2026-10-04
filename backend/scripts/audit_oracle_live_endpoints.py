import json
import urllib.request
import urllib.error
import sys
import concurrent.futures
from pathlib import Path
import subprocess
import base64

backend_dir = Path(__file__).resolve().parent.parent

SSH_KEY = r"d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key"
REMOTE_USER = "ubuntu"
REMOTE_HOST = "193.123.84.223"

# 1. Fetch live JWT token
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

if not token:
    print("Failed to obtain token:", res.stdout, res.stderr, flush=True)
    sys.exit(1)

print(f"Obtained Auth Token: {token[:15]}...{token[-10:]}", flush=True)

BASE_URL = "http://193.123.84.223:8000"

endpoints = [
    # Health & System
    ("GET", "/health", False),
    ("GET", "/api/v1/health/ready", False),
    ("GET", "/api/v1/health/live", False),
    
    # Market & Indices
    ("GET", "/api/v1/market/live", False),
    ("GET", "/api/v1/market/indices", False),
    ("GET", "/api/v1/market/indices/kse-100", False),
    ("GET", "/api/v1/market/indices/kse-30", False),
    ("GET", "/api/v1/market/indices/kmi-30", False),
    ("GET", "/api/v1/market/gainers", False),
    ("GET", "/api/v1/market/losers", False),
    ("GET", "/api/v1/market/volume-spikes", False),
    ("GET", "/api/v1/market/sentiment-overview", False),
    ("GET", "/api/v1/market/all-stocks", False),
    ("GET", "/api/v1/market/quotes", False),
    ("GET", "/api/v1/market/curated", False),
    
    # Stocks
    ("GET", "/api/v1/stocks/search?q=OGDC", False),
    ("GET", "/api/v1/stocks/OGDC/overview", False),
    ("GET", "/api/v1/stocks/OGDC/price-history?range=1M", False),
    ("GET", "/api/v1/stocks/OGDC/technical-indicators", False),
    ("GET", "/api/v1/stocks/OGDC/fundamentals", False),
    ("GET", "/api/v1/stocks/HBL/fundamentals", False),
    ("GET", "/api/v1/stocks/SYS/fundamentals", False),
    ("GET", "/api/v1/stocks/ENGRO/fundamentals", False),
    ("GET", "/api/v1/stocks/OGDC/news", False),
    
    # News
    ("GET", "/api/v1/news", False),
    ("GET", "/api/v1/news/sources", False),
    ("GET", "/api/v1/news/market-status", False),
    
    # Shariah
    ("GET", "/api/v1/shariah/kmi30", False),
    ("GET", "/api/v1/shariah/OGDC", False),
    ("GET", "/api/v1/shariah/OGDC/criteria", False),
    
    # ETFs & IPOs
    ("GET", "/api/v1/etfs", False),
    ("GET", "/api/v1/ipos", False),
    ("GET", "/api/v1/ipos/calendar", False),
    ("GET", "/api/v1/ipos/performance", False),
    
    # WebSockets
    ("GET", "/api/v1/ws/protocol", False),
    ("GET", "/api/v1/ws/stats", False),
    
    # Authenticated User & Profile
    ("GET", "/api/v1/users/me", True),
    ("GET", "/api/v1/users/profile", True),
    
    # Watchlists
    ("GET", "/api/v1/watchlists", True),
    ("GET", "/api/v1/watchlists/default", True),
    ("GET", "/api/v1/watchlists/check/OGDC", True),
    
    # Forecasts & ML
    ("GET", "/api/v1/forecast/OGDC", True),
    ("GET", "/api/v1/forecast/OGDC/history", True),
    ("GET", "/api/v1/recommendations", True),
    ("GET", "/api/v1/recommendations/engine-weights", True),
    ("GET", "/api/v1/recommendations/OGDC", True),
    ("GET", "/api/v1/recommendations/OGDC/target-stop", True),
    
    # Portfolio & Risk
    ("GET", "/api/v1/portfolio", True),
    ("GET", "/api/v1/portfolio/holdings", True),
    ("GET", "/api/v1/portfolio/pnl", True),
    ("GET", "/api/v1/portfolio/allocation", True),
    ("GET", "/api/v1/portfolio/performance", True),
    ("GET", "/api/v1/portfolio/transactions", True),
    ("GET", "/api/v1/risk/var", True),
    ("GET", "/api/v1/risk/stress-test", True),
    
    # Sentiment & Events
    ("GET", "/api/v1/sentiment/market-overview", True),
    ("GET", "/api/v1/sentiment/OGDC", True),
    ("GET", "/api/v1/sentiment/OGDC/history", True),
    ("GET", "/api/v1/sentiment/OGDC/news", True),
    ("GET", "/api/v1/events/calendar", True),
    
    # Alerts & Notifications
    ("GET", "/api/v1/alerts", True),
    ("GET", "/api/v1/alerts/rules", True),
    ("GET", "/api/v1/alerts/rules/check/OGDC", True),
    ("GET", "/api/v1/notifications", True),
    
    # Community
    ("GET", "/api/v1/community/feed", True),
    ("GET", "/api/v1/community/posts/market", True),
    ("GET", "/api/v1/community/posts/stock/OGDC", True),
    ("GET", "/api/v1/community/me", True),
    ("GET", "/api/v1/community/me/posts", True),
    ("GET", "/api/v1/community/notifications", True),
    ("GET", "/api/v1/community/notifications/unread-count", True),
    
    # Assistant
    ("GET", "/api/v1/assistant/quick-prompts", True),
    ("GET", "/api/v1/assistant/conversations", True),
    
    # Admin
    ("GET", "/api/v1/admin/community/reports", True),
]

def check_empty(val):
    if val is None:
        return True, "Null/None"
    if isinstance(val, (list, dict, str)) and len(val) == 0:
        return True, f"Empty {type(val).__name__}"
    return False, "Populated"

def test_endpoint(item):
    method, path, is_auth = item
    url = f"{BASE_URL}{path}"
    headers = {
        "User-Agent": "BasaratLiveAuditor/1.0",
        "Accept": "application/json",
    }
    if is_auth:
        headers["Authorization"] = f"Bearer {token}"
    
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            status_code = response.status
            raw = response.read().decode("utf-8")
            try:
                data = json.loads(raw)
            except Exception:
                data = raw
            
            is_empty, empty_reason = check_empty(data)
            items_count = None
            if isinstance(data, list):
                items_count = len(data)
                if len(data) == 0:
                    is_empty = True
                    empty_reason = "Empty list []"
            elif isinstance(data, dict):
                # check if primary list inside dict is empty
                for k in ["constituents", "items", "data", "posts", "alerts", "holdings", "results", "quotes"]:
                    if k in data and isinstance(data[k], list):
                        items_count = f"{k}: {len(data[k])}"
                        if len(data[k]) == 0:
                            is_empty = True
                            empty_reason = f"Empty list in '{k}'"
            
            res_entry = {
                "route": path,
                "auth": is_auth,
                "status": status_code,
                "empty": is_empty,
                "reason": empty_reason,
                "count_or_type": items_count or type(data).__name__,
                "preview": str(data)[:120]
            }
            status_symbol = "[EMPTY]" if is_empty else "[OK]"
            print(f"[{status_code}] {status_symbol:8} {path:45} -> {empty_reason} | {items_count or type(data).__name__}", flush=True)
            return res_entry
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8")[:100]
        res_entry = {
            "route": path,
            "auth": is_auth,
            "status": e.code,
            "empty": True,
            "reason": f"HTTPError {e.code}",
            "count_or_type": "Error",
            "preview": body
        }
        print(f"[{e.code}] [ERROR]  {path:45} -> {body}", flush=True)
        return res_entry
    except Exception as e:
        res_entry = {
            "route": path,
            "auth": is_auth,
            "status": "EXC",
            "empty": True,
            "reason": str(e),
            "count_or_type": "Exception",
            "preview": ""
        }
        print(f"[EXC] [FAILED] {path:45} -> {str(e)[:60]}", flush=True)
        return res_entry

print(f"\nAuditing {len(endpoints)} endpoints concurrently on {BASE_URL}...\n", flush=True)

with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
    audit_results = list(executor.map(test_endpoint, endpoints))

# Summary
success_count = sum(1 for r in audit_results if not r["empty"] and r["status"] == 200)
empty_count = sum(1 for r in audit_results if r["empty"] and r["status"] == 200)
err_count = sum(1 for r in audit_results if r["status"] != 200)

print("\n" + "="*70, flush=True)
print(f"AUDIT SUMMARY: Total: {len(audit_results)} | Populated: {success_count} | Empty/Null: {empty_count} | Errors: {err_count}", flush=True)
print("="*70, flush=True)

with open(backend_dir / "audit_live_report.json", "w", encoding="utf-8") as f:
    json.dump(audit_results, f, indent=2)
