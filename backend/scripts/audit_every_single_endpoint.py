import asyncio
import sys
import time
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from httpx import ASGITransport

from app.main import app
from app.core.security import create_access_token
from app.db.session import async_session_factory
from sqlalchemy import select
from app.models.user import User
from app.ml.serving.model_loader import load_artifacts

async def get_real_auth():
    async with async_session_factory() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalars().first()
        if user:
            token = create_access_token(data={"sub": str(user.id), "email": user.email, "is_admin": getattr(user, "is_admin", False)})
            return token, str(user.id), user.email
    token = create_access_token(data={"sub": "demo-user-id", "email": "demo@basarat.pk", "is_admin": False})
    return token, "demo-user-id", "demo@basarat.pk"

async def run_full_audit():
    load_artifacts()
    token, user_id, email = await get_real_auth()
    auth_headers = {"Authorization": f"Bearer {token}", "Host": "localhost", "Content-Type": "application/json"}
    public_headers = {"Host": "localhost", "Content-Type": "application/json"}

    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000", timeout=30.0) as client:
        routes_to_test = [
            # System & Health
            ("System", "GET", "/health", False, None),
            ("System", "GET", "/api/v1/health", False, None),
            ("System", "GET", "/api/v1/health/ready", False, None),

            # Market Data
            ("Market", "GET", "/api/v1/market/live", False, None),
            ("Market", "GET", "/api/v1/market/quotes", False, None),
            ("Market", "GET", "/api/v1/market/indices", False, None),
            ("Market", "GET", "/api/v1/market/indices/kse-100", False, None),
            ("Market", "GET", "/api/v1/market/sectors/performance", False, None),
            ("Market", "GET", "/api/v1/market/gainers", False, None),
            ("Market", "GET", "/api/v1/market/losers", False, None),
            ("Market", "GET", "/api/v1/market/volume-spikes", False, None),

            # Stocks
            ("Stocks", "GET", "/api/v1/stocks/search?q=OGDC", False, None),
            ("Stocks", "GET", "/api/v1/stocks/OGDC/overview", False, None),
            ("Stocks", "GET", "/api/v1/stocks/OGDC/price-history?range=1M", False, None),
            ("Stocks", "GET", "/api/v1/stocks/OGDC/technical-indicators", False, None),
            ("Stocks", "GET", "/api/v1/stocks/OGDC/fundamentals", False, None),
            ("Stocks", "GET", "/api/v1/stocks/OGDC/news", False, None),

            # Forecast & Recommendations
            ("Forecast", "GET", "/api/v1/forecast/OGDC?horizon=1W", True, None),
            ("Forecast", "GET", "/api/v1/forecast/OGDC/history?horizon=1W&limit=10", True, None),
            ("Forecast", "GET", "/api/v1/recommendations?limit=10", True, None),
            ("Forecast", "GET", "/api/v1/recommendations/OGDC/target-stop", True, None),

            # Watchlists
            ("Watchlists", "GET", "/api/v1/watchlists", True, None),

            # Portfolio
            ("Portfolio", "GET", "/api/v1/portfolio", True, None),
            ("Portfolio", "GET", "/api/v1/portfolio/holdings", True, None),
            ("Portfolio", "GET", "/api/v1/portfolio/pnl", True, None),
            ("Portfolio", "GET", "/api/v1/portfolio/allocation", True, None),
            ("Portfolio", "GET", "/api/v1/portfolio/performance?period=1M", True, None),

            # Alerts
            ("Alerts", "GET", "/api/v1/alerts/rules", True, None),
            ("Alerts", "GET", "/api/v1/alerts/rules/check/OGDC", True, None),

            # Sentiment & News
            ("Sentiment", "GET", "/api/v1/sentiment/market", False, None),
            ("Sentiment", "GET", "/api/v1/sentiment/stock/OGDC", False, None),
            ("News", "GET", "/api/v1/news?limit=10", False, None),

            # Shariah
            ("Shariah", "GET", "/api/v1/shariah/compliant-stocks", False, None),
            ("Shariah", "GET", "/api/v1/shariah/OGDC", False, None),

            # Risk
            ("Risk", "GET", "/api/v1/risk/OGDC", True, None),

            # IPOs & ETFs
            ("IPOs", "GET", "/api/v1/ipos", False, None),
            ("IPOs", "GET", "/api/v1/ipos/calendar", False, None),
            ("IPOs", "GET", "/api/v1/ipos/performance", False, None),
            ("ETFs", "GET", "/api/v1/etfs", False, None),
            ("ETFs", "GET", "/api/v1/etfs/MIIETF", False, None),
            ("ETFs", "GET", "/api/v1/etfs/MIIETF/history?timeframe=1M", False, None),
            ("ETFs", "GET", "/api/v1/etfs/MIIETF/performance", False, None),

            # Events
            ("Events", "GET", "/api/v1/events?limit=10", False, None),

            # Community
            ("Community", "GET", "/api/v1/community/posts?limit=10", True, None),
            ("Community", "GET", "/api/v1/community/trending", True, None),
            ("Community", "GET", "/api/v1/community/notifications/unread-count", True, None),

            # Subscriptions & Users
            ("Subscriptions", "GET", "/api/v1/subscriptions/plans", False, None),
            ("Subscriptions", "GET", "/api/v1/subscriptions/usage", True, None),
            ("Users", "GET", "/api/v1/users/me", True, None),

            # Assistant
            ("Assistant", "GET", "/api/v1/assistant/quick-prompts", True, None),
            ("Assistant", "GET", "/api/v1/assistant/conversations", True, None),
        ]

        print("\n" + "="*85, flush=True)
        print("  FULL AUDIT: TESTING ALL READ ENDPOINTS ACROSS EVERY DOMAIN", flush=True)
        print(f"  Total Routes to Audit: {len(routes_to_test)}", flush=True)
        print("="*85 + "\n", flush=True)

        results = []
        for cat, method, path, is_auth, payload in routes_to_test:
            headers = auth_headers if is_auth else public_headers
            # Warm-up (Call 1)
            t0 = time.perf_counter()
            try:
                r0 = await client.request(method, path, headers=headers, json=payload)
                c_ms = (time.perf_counter() - t0) * 1000.0
                c_status = r0.status_code
            except Exception:
                c_ms = -1
                c_status = 500

            # Warm Measurement (Call 2)
            t1 = time.perf_counter()
            try:
                r1 = await client.request(method, path, headers=headers, json=payload)
                w_ms = (time.perf_counter() - t1) * 1000.0
                w_status = r1.status_code
            except Exception:
                w_ms = -1
                w_status = 500

            status_flag = "PASS" if w_status in (200, 201, 204) else f"CODE_{w_status}"
            entry = {
                "category": cat,
                "path": path,
                "method": method,
                "cold_ms": round(c_ms, 2),
                "warm_ms": round(w_ms, 2),
                "status": status_flag,
            }
            results.append(entry)
            flag_str = "[SLOW >1s]" if w_ms >= 1000 else "[FAST <100ms]" if w_ms < 100 else " "
            print(f"[{status_flag:<6}] | {cat:<14} | {path:<50} | Cold: {c_ms:7.2f}ms | Warm: {w_ms:7.2f}ms {flag_str}", flush=True)

        slow_endpoints = [r for r in results if r["warm_ms"] >= 1000]
        med_endpoints = [r for r in results if 300 <= r["warm_ms"] < 1000]

        print("\n" + "="*85, flush=True)
        print(f"  AUDIT SUMMARY: {len(results)} Routes Audited", flush=True)
        print(f"  Routes with Warm Latency >= 1000ms: {len(slow_endpoints)}", flush=True)
        print(f"  Routes with Warm Latency 300ms-1000ms: {len(med_endpoints)}", flush=True)
        print(f"  Routes with Warm Latency < 300ms: {len(results) - len(slow_endpoints) - len(med_endpoints)}", flush=True)
        print("="*85 + "\n", flush=True)

        with open("full_audit_warm_latency.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_full_audit())
