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

# 1. Fetch JWT token for seeded admin user
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
    print("Failed to get token!")
    sys.exit(1)

routes = [
    # Category, Method, Path, IsAuth, Description
    ("Health", "GET", "/health", False, "Service health check"),
    ("Health", "GET", "/api/v1/health/ready", False, "System readiness probe"),
    ("Market", "GET", "/api/v1/market/live", False, "Live PSX market status & metrics"),
    ("Market", "GET", "/api/v1/market/indices", False, "PSX Benchmark Indices"),
    ("Market", "GET", "/api/v1/market/indices/kse-100", False, "KSE-100 index constituents & prices"),
    ("Market", "GET", "/api/v1/market/indices/kse-30", False, "KSE-30 index constituents"),
    ("Market", "GET", "/api/v1/market/indices/kmi-30", False, "KMI-30 Islamic index constituents"),
    ("Market", "GET", "/api/v1/market/gainers", False, "Top market gainers"),
    ("Market", "GET", "/api/v1/market/losers", False, "Top market losers"),
    ("Market", "GET", "/api/v1/market/volume-spikes", False, "High volume activity"),
    ("Market", "GET", "/api/v1/market/sentiment-overview", False, "Market-wide sentiment summary"),
    ("Market", "GET", "/api/v1/market/all-stocks", False, "747+ active PSX stocks"),
    ("Market", "GET", "/api/v1/market/quotes", False, "Cached PSX stock quotes"),
    ("Market", "GET", "/api/v1/market/curated", False, "Curated stock picks"),
    
    # Stocks
    ("Stocks", "GET", "/api/v1/stocks/search?q=OGDC", False, "Stock search by symbol/name"),
    ("Stocks", "GET", "/api/v1/stocks/OGDC/overview", False, "OGDC Stock overview"),
    ("Stocks", "GET", "/api/v1/stocks/OGDC/price-history?range=1M", False, "OGDC 1-month daily OHLCV bars"),
    ("Stocks", "GET", "/api/v1/stocks/OGDC/technical-indicators", False, "OGDC RSI, MACD, Bollinger Bands"),
    ("Stocks", "GET", "/api/v1/stocks/OGDC/fundamentals", False, "OGDC Financials & Ratios"),
    ("Stocks", "GET", "/api/v1/stocks/HBL/fundamentals", False, "HBL Financials & Ratios"),
    ("Stocks", "GET", "/api/v1/stocks/SYS/fundamentals", False, "SYS Financials & Ratios"),
    ("Stocks", "GET", "/api/v1/stocks/ENGRO/fundamentals", False, "ENGRO Financials & Ratios"),
    ("Stocks", "GET", "/api/v1/stocks/OGDC/news", False, "OGDC Stock news"),
    
    # News & Events
    ("News", "GET", "/api/v1/news", False, "PSX Market & Corporate News"),
    ("News", "GET", "/api/v1/news/sources", False, "Registered news providers"),
    ("News", "GET", "/api/v1/news/market-status", False, "Market trading hours status"),
    ("Events", "GET", "/api/v1/events/calendar", True, "Corporate events (earnings/AGM)"),
    
    # Shariah
    ("Shariah", "GET", "/api/v1/shariah/kmi30", False, "KMI-30 Shariah Compliant index"),
    ("Shariah", "GET", "/api/v1/shariah/OGDC", False, "OGDC Shariah compliance status"),
    ("Shariah", "GET", "/api/v1/shariah/OGDC/criteria", False, "OGDC AAOIFI Shariah screening breakdown"),
    
    # ETFs & IPOs
    ("ETFs", "GET", "/api/v1/etfs", False, "PSX ETF directory & performance"),
    ("IPOs", "GET", "/api/v1/ipos", False, "PSX IPOs directory"),
    ("IPOs", "GET", "/api/v1/ipos/calendar", False, "Upcoming IPO calendar"),
    ("IPOs", "GET", "/api/v1/ipos/performance", False, "Historical IPO listing performance"),
    
    # WebSockets & System
    ("WS", "GET", "/api/v1/ws/protocol", False, "WebSocket protocol specification"),
    ("WS", "GET", "/api/v1/ws/stats", False, "WebSocket server metrics"),
    
    # Auth & User Profile
    ("Auth/User", "GET", "/api/v1/users/me", True, "Current user profile & preferences"),
    
    # Watchlists
    ("Watchlist", "GET", "/api/v1/watchlists", True, "User watchlists list"),
    ("Watchlist", "GET", "/api/v1/watchlists/default", True, "User default watchlist"),
    ("Watchlist", "GET", "/api/v1/watchlists/check/OGDC", True, "Check if OGDC in watchlist"),
    
    # Forecasts & Recommendations
    ("Forecast", "GET", "/api/v1/forecast/OGDC/history", True, "OGDC Historical ML predictions"),
    ("Recommendations", "GET", "/api/v1/recommendations", True, "Algorithmic stock recommendations"),
    ("Recommendations", "GET", "/api/v1/recommendations/engine-weights", True, "Quant engine model weights"),
    
    # Portfolio & Risk
    ("Portfolio", "GET", "/api/v1/portfolio", True, "User portfolio summary & holdings"),
    ("Portfolio", "GET", "/api/v1/portfolio/performance", True, "Portfolio historical PnL performance"),
    ("Portfolio", "GET", "/api/v1/portfolio/transactions", True, "Portfolio transaction ledger"),
    ("Risk", "GET", "/api/v1/risk/stress-test", True, "Historical stress test scenarios"),
    
    # Sentiment
    ("Sentiment", "GET", "/api/v1/sentiment/market-overview", True, "Market sentiment mood & score"),
    ("Sentiment", "GET", "/api/v1/sentiment/OGDC", True, "OGDC Stock sentiment score & label"),
    ("Sentiment", "GET", "/api/v1/sentiment/OGDC/news", True, "OGDC News sentiment items"),
    
    # Alerts & Notifications
    ("Alerts", "GET", "/api/v1/alerts", True, "Active user price alerts"),
    ("Alerts", "GET", "/api/v1/alerts/rules/check/OGDC", True, "Check active alert rules for OGDC"),
    ("Notifications", "GET", "/api/v1/notifications", True, "In-app notifications inbox"),
    
    # Community & Social
    ("Community", "GET", "/api/v1/community/me", True, "User social profile & stats"),
    ("Community", "GET", "/api/v1/community/posts/market", True, "Market-wide community posts"),
    ("Community", "GET", "/api/v1/community/notifications/unread-count", True, "Community notifications badge"),
    ("Admin", "GET", "/api/v1/admin/community/reports", True, "Moderation reported posts queue"),
    
    # AI Assistant
    ("Assistant", "GET", "/api/v1/assistant/quick-prompts", True, "Quick prompt starters"),
    ("Assistant", "GET", "/api/v1/assistant/conversations", True, "Chat conversation history"),
]

results = []
print(f"Testing {len(routes)} endpoints on Oracle VM: {BASE_URL}\n")

for cat, method, path, is_auth, desc in routes:
    url = f"{BASE_URL}{path}"
    headers = {
        "User-Agent": "BasaratAuditor/1.0",
        "Accept": "application/json",
    }
    if is_auth:
        headers["Authorization"] = f"Bearer {token}"
    
    req = urllib.request.Request(url, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = resp.read().decode("utf-8")
            data = json.loads(raw)
            
            # Content verification
            is_empty = False
            summary_info = ""
            if isinstance(data, list):
                summary_info = f"{len(data)} items"
                is_empty = len(data) == 0
            elif isinstance(data, dict):
                keys = list(data.keys())
                for list_k in ["constituents", "items", "data", "posts", "alerts", "prompts", "conversations", "results"]:
                    if list_k in data and isinstance(data[list_k], list):
                        summary_info = f"{list_k}: {len(data[list_k])} items"
                        if len(data[list_k]) == 0 and list_k not in ["alerts", "conversations"]:
                            is_empty = True
                        break
                if not summary_info:
                    summary_info = f"keys: {', '.join(keys[:4])}"
            
            status_tag = "EMPTY" if is_empty else "POPULATED"
            print(f"[{resp.status}] [{status_tag:9}] {cat:15} | {path:46} -> {summary_info}")
            results.append({
                "category": cat,
                "path": path,
                "auth": is_auth,
                "status": resp.status,
                "empty": is_empty,
                "summary": summary_info,
                "data_sample": data if not isinstance(data, (list, dict)) else (data[:1] if isinstance(data, list) else {k: data[k] for k in list(data.keys())[:3]}),
                "description": desc
            })
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")[:100]
        print(f"[{e.code}] [ERROR    ] {cat:15} | {path:46} -> HTTP {e.code}: {err_body}")
        results.append({
            "category": cat,
            "path": path,
            "auth": is_auth,
            "status": e.code,
            "empty": True,
            "summary": f"HTTP {e.code}",
            "data_sample": err_body,
            "description": desc
        })
    except Exception as e:
        print(f"[EXC] [FAILED   ] {cat:15} | {path:46} -> {str(e)[:60]}")
        results.append({
            "category": cat,
            "path": path,
            "auth": is_auth,
            "status": "EXC",
            "empty": True,
            "summary": str(e),
            "data_sample": None,
            "description": desc
        })

# Summary
passed = sum(1 for r in results if r["status"] == 200 and not r["empty"])
empty = sum(1 for r in results if r["status"] == 200 and r["empty"])
failed = sum(1 for r in results if r["status"] != 200)

print("\n" + "="*80)
print(f"VERIFICATION RESULTS: Total Tested: {len(results)} | Verified Populated: {passed} | Empty: {empty} | Failed: {failed}")
print("="*80)

with open(Path(__file__).resolve().parent.parent / "full_verification_report.json", "w", encoding="utf-8") as f:
    json.dump(results, f, indent=2)
