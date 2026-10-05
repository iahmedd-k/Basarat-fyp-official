import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import json
import urllib.request
from datetime import timedelta
from app.core.security import create_access_token
from app.db.base import get_sync_session_factory
from app.models.user import User

# 1. Generate auth token for test user
token = None
with get_sync_session_factory()() as s:
    u = s.query(User).filter(User.email == "admin@basarat.pk").first()
    if not u:
        u = s.query(User).first()
    token = create_access_token(
        data={"sub": str(u.id), "email": u.email, "role": "admin"},
        expires_delta=timedelta(days=7)
    )

headers = {
    "User-Agent": "BasaratAuditor/1.0",
    "Authorization": f"Bearer {token}",
    "Accept": "application/json",
}

base = "http://127.0.0.1:8000"

test_routes = [
    # Health Probe
    ("PUBLIC", "/health"),
    ("PUBLIC", "/api/v1/health/ready"),
    # Market & Quotes
    ("PUBLIC", "/api/v1/market/live"),
    ("PUBLIC", "/api/v1/market/indices"),
    ("PUBLIC", "/api/v1/market/indices/kse-100"),
    ("PUBLIC", "/api/v1/market/indices/kse-30"),
    ("PUBLIC", "/api/v1/market/indices/kmi-30"),
    ("PUBLIC", "/api/v1/market/gainers"),
    ("PUBLIC", "/api/v1/market/losers"),
    ("PUBLIC", "/api/v1/market/volume-spikes"),
    ("PUBLIC", "/api/v1/market/sentiment-overview"),
    ("PUBLIC", "/api/v1/market/all-stocks"),
    ("PUBLIC", "/api/v1/market/quotes"),
    ("PUBLIC", "/api/v1/market/curated"),
    # Stocks
    ("PUBLIC", "/api/v1/stocks/search?q=OGDC"),
    ("PUBLIC", "/api/v1/stocks/OGDC/overview"),
    ("PUBLIC", "/api/v1/stocks/OGDC/price-history?range=1M"),
    ("PUBLIC", "/api/v1/stocks/OGDC/technical-indicators"),
    ("PUBLIC", "/api/v1/stocks/OGDC/fundamentals"),
    ("PUBLIC", "/api/v1/stocks/HBL/fundamentals"),
    ("PUBLIC", "/api/v1/stocks/SYS/fundamentals"),
    ("PUBLIC", "/api/v1/stocks/OGDC/news"),
    # News
    ("PUBLIC", "/api/v1/news"),
    ("PUBLIC", "/api/v1/news/sources"),
    ("PUBLIC", "/api/v1/news/market-status"),
    # Shariah
    ("PUBLIC", "/api/v1/shariah/kmi30"),
    ("PUBLIC", "/api/v1/shariah/OGDC"),
    ("PUBLIC", "/api/v1/shariah/OGDC/criteria"),
    # ETFs & IPOs
    ("PUBLIC", "/api/v1/etfs"),
    ("PUBLIC", "/api/v1/ipos"),
    ("PUBLIC", "/api/v1/ipos/calendar"),
    ("PUBLIC", "/api/v1/ipos/performance"),
    # WebSockets stats
    ("PUBLIC", "/api/v1/ws/protocol"),
    ("PUBLIC", "/api/v1/ws/stats"),
    # Authenticated Routes
    ("AUTH",   "/api/v1/users/me"),
    ("AUTH",   "/api/v1/users/profile"),
    ("AUTH",   "/api/v1/watchlists"),
    ("AUTH",   "/api/v1/watchlists/default"),
    ("AUTH",   "/api/v1/watchlists/check/OGDC"),
    ("AUTH",   "/api/v1/forecast/OGDC"),
    ("AUTH",   "/api/v1/forecast/OGDC/history"),
    ("AUTH",   "/api/v1/recommendations"),
    ("AUTH",   "/api/v1/recommendations/engine-weights"),
    ("AUTH",   "/api/v1/recommendations/OGDC"),
    ("AUTH",   "/api/v1/recommendations/OGDC/target-stop"),
    ("AUTH",   "/api/v1/portfolio"),
    ("AUTH",   "/api/v1/portfolio/holdings"),
    ("AUTH",   "/api/v1/portfolio/pnl"),
    ("AUTH",   "/api/v1/portfolio/allocation"),
    ("AUTH",   "/api/v1/portfolio/performance"),
    ("AUTH",   "/api/v1/portfolio/transactions"),
    ("AUTH",   "/api/v1/risk/var"),
    ("AUTH",   "/api/v1/risk/stress-test"),
    ("AUTH",   "/api/v1/sentiment/market-overview"),
    ("AUTH",   "/api/v1/sentiment/OGDC"),
    ("AUTH",   "/api/v1/sentiment/OGDC/history"),
    ("AUTH",   "/api/v1/sentiment/OGDC/news"),
    ("AUTH",   "/api/v1/events/calendar"),
    ("AUTH",   "/api/v1/alerts"),
    ("AUTH",   "/api/v1/alerts/rules"),
    ("AUTH",   "/api/v1/alerts/rules/check/OGDC"),
    ("AUTH",   "/api/v1/notifications"),
    ("AUTH",   "/api/v1/community/feed"),
    ("AUTH",   "/api/v1/community/posts/market"),
    ("AUTH",   "/api/v1/community/posts/stock/OGDC"),
    ("AUTH",   "/api/v1/community/me"),
    ("AUTH",   "/api/v1/community/me/posts"),
    ("AUTH",   "/api/v1/community/notifications"),
    ("AUTH",   "/api/v1/community/notifications/unread-count"),
    ("AUTH",   "/api/v1/assistant/quick-prompts"),
    ("AUTH",   "/api/v1/assistant/conversations"),
    ("AUTH",   "/api/v1/admin/community/reports"),
]

results = []
for access_type, path in test_routes:
    req_headers = headers if access_type == "AUTH" else {"User-Agent": "BasaratAuditor/1.0", "Accept": "application/json"}
    url = f"{base}{path}"
    try:
        req = urllib.request.Request(url, headers=req_headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            results.append({
                "path": path,
                "status": resp.status,
                "access": access_type,
                "data_type": type(body).__name__,
                "keys_or_len": len(body) if isinstance(body, list) else list(body.keys())[:5],
                "sample": body if not isinstance(body, (list, dict)) else (body[:1] if isinstance(body, list) else {k: body[k] for k in list(body.keys())[:3]}),
            })
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8")[:100]
        results.append({
            "path": path,
            "status": e.code,
            "access": access_type,
            "error": f"HTTP {e.code}: {err_msg}",
        })
    except Exception as e:
        results.append({
            "path": path,
            "status": "ERR",
            "access": access_type,
            "error": str(e),
        })

print(json.dumps(results, indent=2))
"""

run_remote_python(code)
