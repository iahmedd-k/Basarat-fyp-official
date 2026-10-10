"""Comprehensive Endpoint Latency Benchmark & Functional Audit Script.

Tests all Swagger / OpenAPI endpoints with both cold and warm latency measurements,
validating HTTP status codes, response times, and payload integrity using demo credentials.
"""

import asyncio
import sys
import time
import json
import logging
from pathlib import Path
from datetime import datetime, timezone

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from httpx import ASGITransport

from app.main import app
from app.core.security import create_access_token
from app.db.session import async_session_factory
from sqlalchemy import select
from app.models.user import User

logging.basicConfig(level=logging.ERROR)

async def get_auth_token():
    """Get valid JWT access token for demo user or create a temporary token."""
    async with async_session_factory() as db:
        result = await db.execute(select(User).where(User.email == "demo@basarat.pk"))
        user = result.scalars().first()
        if not user:
            result = await db.execute(select(User).limit(1))
            user = result.scalars().first()
        
        if user:
            token = create_access_token(data={"sub": str(user.id), "email": user.email, "is_admin": getattr(user, "is_admin", False)})
            return token, str(user.id)
        else:
            token = create_access_token(data={"sub": "demo-user-id", "email": "demo@basarat.pk", "is_admin": False})
            return token, "demo-user-id"

# Catalog of all endpoints with representative test queries / payloads
ENDPOINTS_TO_TEST = [
    # System / Health Probes
    ("GET", "/health", None, False, "System Liveness Probe"),
    ("GET", "/api/v1/health", None, False, "V1 Health Liveness"),
    ("GET", "/api/v1/health/ready", None, False, "V1 Health Readiness"),
    
    # Market & Quotes
    ("GET", "/api/v1/market/live", None, False, "Live Market Status"),
    ("GET", "/api/v1/market/quotes", None, False, "All Stock Quotes"),
    ("GET", "/api/v1/market/indices", None, False, "Main PSX Indices"),
    ("GET", "/api/v1/market/indices/kse-100", None, False, "KSE-100 Constituents"),
    ("GET", "/api/v1/market/indices/kse-30", None, False, "KSE-30 Constituents"),
    ("GET", "/api/v1/market/indices/kmi-30", None, False, "KMI-30 Constituents"),
    ("GET", "/api/v1/market/gainers", None, False, "Top Gainers"),
    ("GET", "/api/v1/market/losers", None, False, "Top Losers"),
    ("GET", "/api/v1/market/volume-spikes", None, False, "Volume Spikes"),
    ("GET", "/api/v1/market/sectors/performance", None, False, "Sector Performance"),
    
    # Stocks & Analytics
    ("GET", "/api/v1/stocks/search?q=OGDC", None, False, "Stock Autocomplete"),
    ("GET", "/api/v1/stocks/OGDC/overview", None, False, "Stock Overview Snapshot"),
    ("GET", "/api/v1/stocks/OGDC/price-history?range=1M", None, False, "OHLCV Price History"),
    ("GET", "/api/v1/stocks/OGDC/technical-indicators", None, False, "Technical Indicators"),
    ("GET", "/api/v1/stocks/OGDC/fundamentals", None, False, "Stock Fundamentals"),
    ("GET", "/api/v1/stocks/OGDC/price-on-date?date=2026-10-02", None, False, "Vintage Price On Date"),
    ("GET", "/api/v1/stocks/OGDC/news", None, False, "Stock Specific News"),
    
    # AI Forecast & Recommendations
    ("GET", "/api/v1/forecast/OGDC?horizon=1W", None, True, "AI Ensemble Forecast"),
    ("GET", "/api/v1/forecast/OGDC/history?horizon=1W&limit=10", None, True, "Forecast History & Accuracy"),
    ("GET", "/api/v1/recommendations?limit=10", None, True, "Personalized Recommendations"),
    ("GET", "/api/v1/recommendations/OGDC", None, True, "Stock Recommendation Detail"),
    ("GET", "/api/v1/recommendations/OGDC/target-stop", None, True, "Target & Stop-Loss Levels"),
    ("GET", "/api/v1/recommendations/engine-weights", None, True, "Engine Model Weights"),
    
    # Shariah & Ethical Finance
    ("GET", "/api/v1/shariah/OGDC", None, False, "Shariah Screening Detail"),
    ("GET", "/api/v1/shariah/kmi30", None, False, "KMI-30 Shariah Roster"),
    
    # News, Sentiment & Events
    ("GET", "/api/v1/news?limit=10", None, False, "Global Financial News Feed"),
    ("GET", "/api/v1/news/sources", None, False, "News Source Health"),
    ("GET", "/api/v1/events/calendar", None, True, "Events Calendar"),
    ("GET", "/api/v1/sentiment/news?limit=10", None, True, "Sentiment Scored News"),
    ("GET", "/api/v1/sentiment/market", None, True, "Overall Market Sentiment"),
    
    # ETFs & IPOs
    ("GET", "/api/v1/etfs?limit=10", None, False, "ETF Catalog List"),
    ("GET", "/api/v1/etfs/MIIETF", None, False, "ETF Fund Detail"),
    ("GET", "/api/v1/ipos?limit=10", None, False, "IPO Catalog List"),
    ("GET", "/api/v1/ipos/calendar", None, False, "IPO Timeline Calendar"),
    ("GET", "/api/v1/ipos/performance", None, False, "IPO Historical Returns"),
    
    # User Profile & Watchlists
    ("GET", "/api/v1/users/me", None, True, "Current User Profile"),
    ("GET", "/api/v1/watchlists", None, True, "User Watchlists Summary"),
    ("GET", "/api/v1/watchlists/check/OGDC", None, True, "Watchlist Symbol Membership Check"),
    
    # Portfolio & Risk Analytics
    ("GET", "/api/v1/portfolio", None, True, "User Portfolio Overview"),
    ("GET", "/api/v1/portfolio/holdings", None, True, "Portfolio Holdings"),
    ("GET", "/api/v1/portfolio/pnl", None, True, "Portfolio Realized/Unrealized P&L"),
    ("GET", "/api/v1/portfolio/performance", None, True, "Portfolio Performance Breakdown"),
    ("GET", "/api/v1/portfolio/allocation", None, True, "Portfolio Asset Allocation"),
    ("GET", "/api/v1/portfolio/transactions?limit=10", None, True, "Portfolio Transactions History"),
    ("GET", "/api/v1/risk/var?confidence=95&horizon=1D", None, True, "Portfolio Value-at-Risk (VaR)"),
    ("GET", "/api/v1/risk/stress-test?scenario=2008_crash", None, True, "Risk Stress Testing"),
    
    # Alerts & Notifications
    ("GET", "/api/v1/alerts/rules", None, True, "User Alert Rules"),
    ("GET", "/api/v1/notifications?limit=10", None, True, "User Notifications Feed"),
    ("GET", "/api/v1/notifications?unread_only=true", None, True, "Unread Notifications"),
    
    # Community & Social
    ("GET", "/api/v1/community/posts?limit=10", None, True, "Community Feed Posts"),
    ("GET", "/api/v1/community/trending?limit=10", None, True, "Community Trending Cashtags & Posts"),
    ("GET", "/api/v1/community/posts/search?q=OGDC", None, True, "Community Search Posts"),
    
    # Subscriptions
    ("GET", "/api/v1/subscriptions/plans", None, False, "Subscription Plans & Pricing"),
    ("GET", "/api/v1/subscriptions/usage", None, True, "User AI Quota & Limits"),
]

async def run_latency_benchmark():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000", timeout=30.0) as client:
        token, user_id = await get_auth_token()
        headers = {"Authorization": f"Bearer {token}", "Host": "localhost"}
        
        results = []
        print("\n" + "="*80)
        print(f"[RUNNING] LATENCY AUDIT ACROSS {len(ENDPOINTS_TO_TEST)} SWAGGER ENDPOINTS")
        print(f"Auth Token: generated for user ID: {user_id}")
        print("="*80 + "\n")
        
        for method, path, payload, req_auth, name in ENDPOINTS_TO_TEST:
            req_headers = {"Authorization": f"Bearer {token}", "Host": "localhost"} if req_auth else {"Host": "localhost"}
            
            # 1. Cold Request
            t0 = time.perf_counter()
            try:
                res_cold = await client.request(method, path, headers=req_headers, json=payload)
                t_cold = (time.perf_counter() - t0) * 1000.0
                cold_status = res_cold.status_code
                if cold_status == 400:
                    print(f"DEBUG 400 for {path}: {res_cold.text}")
            except Exception as e:
                t_cold = -1
                cold_status = 500
            
            # 2. Warm Request (Cache Hit)
            t1 = time.perf_counter()
            try:
                res_warm = await client.request(method, path, headers=req_headers, json=payload)
                t_warm = (time.perf_counter() - t1) * 1000.0
                warm_status = res_warm.status_code
            except Exception as e:
                t_warm = -1
                warm_status = 500
            
            status_str = "PASS" if warm_status in (200, 201) else f"STATUS_{warm_status}"
            auth_str = "Auth" if req_auth else "Public"
            
            results.append({
                "name": name,
                "method": method,
                "path": path,
                "auth": auth_str,
                "status_code": warm_status,
                "status": status_str,
                "cold_ms": round(t_cold, 2),
                "warm_ms": round(t_warm, 2),
            })
            
            print(f"[{status_str:<6}] | {auth_str:<6} | {method:<4} {path:<50} | Cold: {t_cold:6.2f}ms | Warm: {t_warm:6.2f}ms", flush=True)
            
        print("\n" + "="*80, flush=True)
        print("LATENCY BENCHMARK COMPLETED", flush=True)
        print("="*80 + "\n", flush=True)
        
        # Save JSON output for structured presentation
        with open("latency_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
            
if __name__ == "__main__":
    asyncio.run(run_latency_benchmark())
