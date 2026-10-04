import json
import urllib.request
import urllib.error
import sys
import subprocess
import base64
from pathlib import Path

SSH_KEY = r"d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key"
REMOTE_USER = "ubuntu"
REMOTE_HOST = "193.123.84.223"
BASE_URL = "http://193.123.84.223:8000"

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

if not token:
    print("Failed to get token!", flush=True)
    sys.exit(1)

def api_call(method, path, body=None):
    url = f"{BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "BasaratCRUDTester/1.0",
    }
    data = json.dumps(body).encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            raw = resp.read().decode("utf-8")
            try:
                res_json = json.loads(raw)
            except Exception:
                res_json = raw
            return resp.status, res_json
    except urllib.error.HTTPError as e:
        err_raw = e.read().decode("utf-8")
        try:
            return e.code, json.loads(err_raw)
        except Exception:
            return e.code, err_raw
    except Exception as e:
        return "EXC", str(e)

crud_log = []

def record(action, method, path, status, success, details):
    crud_log.append({
        "action": action,
        "method": method,
        "path": path,
        "status": status,
        "success": success,
        "details": details
    })
    status_icon = "[PASS]" if success else "[FAIL]"
    print(f"{status_icon:8} {method:6} {path:48} | Status: {status} | {details}", flush=True)

print("\n" + "="*80, flush=True)
print("STARTING FULL CRUD LIFECYCLE TESTS ON ORACLE CLOUD...", flush=True)
print("="*80 + "\n", flush=True)

# ── 1. USER PROFILE CRUD ──────────────────────────────────────────────────
print("\n--- 1. Testing User Profile CRUD ---", flush=True)
st, body = api_call("PATCH", "/api/v1/users/me", {
    "full_name": "Senior PSX Portfolio Manager",
    "risk_tolerance": "aggressive",
    "investment_horizon": "long_term"
})
record("User Profile Update", "PATCH", "/api/v1/users/me", st, st == 200, f"Updated Name: {body.get('full_name') if isinstance(body, dict) else body}")

st, body = api_call("GET", "/api/v1/users/me")
record("User Profile Verify", "GET", "/api/v1/users/me", st, st == 200 and isinstance(body, dict) and body.get("risk_tolerance") == "aggressive", f"Risk: {body.get('risk_tolerance') if isinstance(body, dict) else body}")

# ── 2. WATCHLIST CRUD ─────────────────────────────────────────────────────
print("\n--- 2. Testing Watchlist CRUD Lifecycle ---", flush=True)
st, body = api_call("POST", "/api/v1/watchlists", {
    "name": "Energy & Tech Focus",
    "description": "High momentum portfolio tracking",
    "symbols": ["OGDC", "SYS", "TRG"]
})
created_wl_id = body.get("id") if isinstance(body, dict) else None
record("Watchlist Create", "POST", "/api/v1/watchlists", st, st in [200, 201] and bool(created_wl_id), f"ID: {created_wl_id}")

if created_wl_id:
    # Add item
    st, body = api_call("POST", f"/api/v1/watchlists/{created_wl_id}/items", {"symbol": "ENGRO"})
    record("Watchlist Add Item", "POST", f"/api/v1/watchlists/{created_wl_id}/items", st, st in [200, 201], f"Added ENGRO -> {body.get('symbol') if isinstance(body, dict) else body}")
    
    # Get details
    st, body = api_call("GET", f"/api/v1/watchlists/{created_wl_id}")
    items_count = len(body.get("items", [])) if isinstance(body, dict) else 0
    record("Watchlist Get Details", "GET", f"/api/v1/watchlists/{created_wl_id}", st, st == 200 and items_count > 0, f"Items: {items_count}")
    
    # Delete item
    st, body = api_call("DELETE", f"/api/v1/watchlists/{created_wl_id}/items/TRG")
    record("Watchlist Remove Item", "DELETE", f"/api/v1/watchlists/{created_wl_id}/items/TRG", st, st in [200, 204], "Removed TRG")
    
    # Delete watchlist
    st, body = api_call("DELETE", f"/api/v1/watchlists/{created_wl_id}")
    record("Watchlist Delete", "DELETE", f"/api/v1/watchlists/{created_wl_id}", st, st in [200, 204], "Deleted test watchlist")

# ── 3. PORTFOLIO TRANSACTION CRUD ─────────────────────────────────────────
print("\n--- 3. Testing Portfolio Transaction CRUD Lifecycle ---", flush=True)
st, body = api_call("POST", "/api/v1/portfolio/transactions", {
    "symbol": "HUBC",
    "transaction_type": "BUY",
    "quantity": 500,
    "price": 125.50,
    "fee": 10.0,
    "transaction_date": "2026-10-02"
})
created_txn_id = body.get("id") if isinstance(body, dict) else None
record("Portfolio Transaction Create", "POST", "/api/v1/portfolio/transactions", st, st in [200, 201] and bool(created_txn_id), f"ID: {created_txn_id}")

if created_txn_id:
    # Verify portfolio summary
    st, body = api_call("GET", "/api/v1/portfolio")
    total_val = body.get("summary", {}).get("current_value") if isinstance(body, dict) else None
    record("Portfolio Summary Verify", "GET", "/api/v1/portfolio", st, st == 200 and total_val is not None, f"Current Value: {total_val}")
    
    # Delete test transaction
    st, body = api_call("DELETE", f"/api/v1/portfolio/transactions/{created_txn_id}")
    record("Portfolio Transaction Delete", "DELETE", f"/api/v1/portfolio/transactions/{created_txn_id}", st, st in [200, 204], "Deleted test transaction")

# ── 4. ALERTS CRUD ────────────────────────────────────────────────────────
print("\n--- 4. Testing Alerts Rules CRUD Lifecycle ---", flush=True)
st, body = api_call("POST", "/api/v1/alerts/rules", {
    "symbol": "OGDC",
    "condition": "PRICE_ABOVE",
    "threshold": 250.0
})
created_alert_id = body.get("id") if isinstance(body, dict) else None
record("Alert Rule Create", "POST", "/api/v1/alerts/rules", st, st in [200, 201] and bool(created_alert_id), f"ID: {created_alert_id}")

if created_alert_id:
    # List rules
    st, body = api_call("GET", "/api/v1/alerts/rules")
    record("Alert Rules List", "GET", "/api/v1/alerts/rules", st, st == 200, f"Total Rules: {len(body) if isinstance(body, list) else body}")
    
    # Delete alert rule
    st, body = api_call("DELETE", f"/api/v1/alerts/rules/{created_alert_id}")
    record("Alert Rule Delete", "DELETE", f"/api/v1/alerts/rules/{created_alert_id}", st, st in [200, 204], "Deleted test alert rule")

# ── 5. COMMUNITY POSTS & COMMENTS CRUD ────────────────────────────────────
print("\n--- 5. Testing Community Posts & Comments CRUD Lifecycle ---", flush=True)
st, body = api_call("POST", "/api/v1/community/posts", {
    "content": "KSE-100 demonstrating strong resistance level. Tracking institutional volumes.",
    "post_type": "GENERAL_MARKET"
})
created_post_id = body.get("id") if isinstance(body, dict) else None
record("Community Post Create", "POST", "/api/v1/community/posts", st, st in [200, 201] and bool(created_post_id), f"ID: {created_post_id}")

if created_post_id:
    # Add comment
    st, body = api_call("POST", f"/api/v1/community/posts/{created_post_id}/comments", {
        "content": "Agreed. High volume accumulation in tech sector today."
    })
    created_comment_id = body.get("id") if isinstance(body, dict) else None
    record("Community Post Add Comment", "POST", f"/api/v1/community/posts/{created_post_id}/comments", st, st in [200, 201], f"Comment ID: {created_comment_id}")
    
    # Like post
    st, body = api_call("POST", f"/api/v1/community/posts/{created_post_id}/like")
    record("Community Post Like", "POST", f"/api/v1/community/posts/{created_post_id}/like", st, st in [200, 201], f"Liked: {body}")
    
    # Delete comment
    if created_comment_id:
        st, body = api_call("DELETE", f"/api/v1/community/comments/{created_comment_id}")
        record("Community Delete Comment", "DELETE", f"/api/v1/community/comments/{created_comment_id}", st, st in [200, 204], "Deleted test comment")
    
    # Delete post
    st, body = api_call("DELETE", f"/api/v1/community/posts/{created_post_id}")
    record("Community Delete Post", "DELETE", f"/api/v1/community/posts/{created_post_id}", st, st in [200, 204], "Deleted test post")

# ── 6. ASSISTANT CHAT ─────────────────────────────────────────────────────
print("\n--- 6. Testing AI Investment Assistant ---", flush=True)
st, body = api_call("POST", "/api/v1/assistant/chat", {
    "message": "What is the current technical outlook for OGDC on PSX?",
    "conversation_id": None
})
reply_preview = body.get("reply", "")[:80] if isinstance(body, dict) else str(body)[:80]
record("AI Assistant Chat", "POST", "/api/v1/assistant/chat", st, st == 200, f"Reply: {reply_preview}")

# Save full results
print("\n" + "="*80, flush=True)
passed = sum(1 for r in crud_log if r["success"])
failed = sum(1 for r in crud_log if not r["success"])
print(f"CRUD TEST SUMMARY: Total Operations: {len(crud_log)} | Passed: {passed} | Failed: {failed}", flush=True)
print("="*80, flush=True)

with open(Path(__file__).resolve().parent.parent / "crud_verification_report.json", "w", encoding="utf-8") as f:
    json.dump(crud_log, f, indent=2)
