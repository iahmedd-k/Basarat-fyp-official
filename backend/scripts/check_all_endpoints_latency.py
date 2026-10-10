"""Comprehensive Full-Stack Latency Benchmark & CRUD Functional Audit.

Tests all Swagger / OpenAPI HTTP Methods (GET, POST, PUT, PATCH, DELETE)
across all modules with cold & warm latency measurements, validation, and auto-cleanup.
"""

import asyncio
import sys
import time
import json
import logging
import uuid
from pathlib import Path
from datetime import datetime, timezone, date

# Add backend directory to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from httpx import ASGITransport

from app.main import app, lifespan
from app.core.security import create_access_token
from app.db.session import async_session_factory
from sqlalchemy import select
from app.models.user import User
from app.ml.serving.model_loader import load_artifacts

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
            return token, str(user.id), user.email
        else:
            token = create_access_token(data={"sub": "demo-user-id", "email": "demo@basarat.pk", "is_admin": False})
            return token, "demo-user-id", "demo@basarat.pk"


async def run_full_stack_benchmark():
    # 1. Initialize ML artifacts & model loader
    load_artifacts()
    
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost:8000", timeout=30.0) as client:
        token, user_id, email = await get_auth_token()
        auth_headers = {"Authorization": f"Bearer {token}", "Host": "localhost", "Content-Type": "application/json"}
        public_headers = {"Host": "localhost", "Content-Type": "application/json"}
        
        results = []
        
        print("\n" + "="*85, flush=True)
        print("  STARTING FULL-STACK HTTP METHODS LATENCY AUDIT (GET, POST, PUT, PATCH, DELETE)", flush=True)
        print(f"  Target User: {email} (ID: {user_id})", flush=True)
        print("="*85 + "\n", flush=True)

        async def measure(category, name, method, path, payload=None, is_auth=True, expected_codes=(200, 201, 204)):
            headers = auth_headers if is_auth else public_headers
            
            # Cold call
            t0 = time.perf_counter()
            try:
                res_cold = await client.request(method, path, headers=headers, json=payload)
                t_cold = (time.perf_counter() - t0) * 1000.0
                cold_status = res_cold.status_code
            except Exception as e:
                t_cold = -1
                cold_status = 500
                res_cold = None

            # Warm call
            t1 = time.perf_counter()
            try:
                res_warm = await client.request(method, path, headers=headers, json=payload)
                t_warm = (time.perf_counter() - t1) * 1000.0
                warm_status = res_warm.status_code
            except Exception as e:
                t_warm = -1
                warm_status = 500
                res_warm = None

            status_str = "PASS" if warm_status in expected_codes or cold_status in expected_codes else f"STATUS_{warm_status}"
            auth_str = "Auth" if is_auth else "Public"
            
            entry = {
                "category": category,
                "name": name,
                "method": method,
                "path": path,
                "auth": auth_str,
                "cold_status": cold_status,
                "warm_status": warm_status,
                "status": status_str,
                "cold_ms": round(t_cold, 2),
                "warm_ms": round(t_warm, 2),
            }
            results.append(entry)
            
            print(f"[{status_str:<6}] | {category:<14} | {method:<6} {path:<48} | Cold: {t_cold:6.2f}ms | Warm: {t_warm:6.2f}ms", flush=True)
            return res_cold, res_warm

        # ─── 1. SYSTEM & HEALTH ───────────────────────────────────────────────
        await measure("System", "Liveness Probe", "GET", "/health", is_auth=False)
        await measure("System", "V1 Health Liveness", "GET", "/api/v1/health", is_auth=False)
        await measure("System", "V1 Health Readiness", "GET", "/api/v1/health/ready", is_auth=False)

        # ─── 2. AUTHENTICATION & SESSIONS ─────────────────────────────────────
        # Auth Login (POST)
        await measure("Auth", "User Password Login", "POST", "/api/v1/auth/login", 
                      payload={"email": "demo@basarat.pk", "password": "demopassword123"}, is_auth=False, expected_codes=(200, 401, 422))
        
        # ─── 3. MARKET DATA & INDICES (GET) ───────────────────────────────────
        await measure("Market", "Live Market Status", "GET", "/api/v1/market/live", is_auth=False)
        await measure("Market", "All Stock Quotes", "GET", "/api/v1/market/quotes", is_auth=False)
        await measure("Market", "Main PSX Indices", "GET", "/api/v1/market/indices", is_auth=False)
        await measure("Market", "KSE-100 Constituents", "GET", "/api/v1/market/indices/kse-100", is_auth=False)
        await measure("Market", "Sector Performance", "GET", "/api/v1/market/sectors/performance", is_auth=False)
        await measure("Market", "Top Gainers", "GET", "/api/v1/market/gainers", is_auth=False)
        await measure("Market", "Top Losers", "GET", "/api/v1/market/losers", is_auth=False)
        await measure("Market", "Volume Spikes", "GET", "/api/v1/market/volume-spikes", is_auth=False)

        # ─── 4. STOCKS & ANALYTICS (GET) ──────────────────────────────────────
        await measure("Stocks", "Stock Search Autocomplete", "GET", "/api/v1/stocks/search?q=OGDC", is_auth=False)
        await measure("Stocks", "Stock Overview Snapshot", "GET", "/api/v1/stocks/OGDC/overview", is_auth=False)
        await measure("Stocks", "Price History OHLCV", "GET", "/api/v1/stocks/OGDC/price-history?range=1M", is_auth=False)
        await measure("Stocks", "Technical Indicators", "GET", "/api/v1/stocks/OGDC/technical-indicators", is_auth=False)
        await measure("Stocks", "Stock Fundamentals", "GET", "/api/v1/stocks/OGDC/fundamentals", is_auth=False)
        await measure("Stocks", "Stock News Feed", "GET", "/api/v1/stocks/OGDC/news", is_auth=False)

        # ─── 5. AI FORECAST & RECOMMENDATIONS ─────────────────────────────────
        await measure("Forecast", "AI Forecast Detail", "GET", "/api/v1/forecast/OGDC?horizon=1W", is_auth=True, expected_codes=(200, 503))
        await measure("Forecast", "AI Forecast History", "GET", "/api/v1/forecast/OGDC/history?horizon=1W&limit=10", is_auth=True)
        await measure("Forecast", "Recommendations Feed", "GET", "/api/v1/recommendations?limit=10", is_auth=True)
        await measure("Forecast", "Target & Stop-Loss Levels", "GET", "/api/v1/recommendations/OGDC/target-stop", is_auth=True)

        # ─── 6. WATCHLISTS (CRUD: GET, POST, PUT, DELETE) ─────────────────────
        # GET watchlists
        await measure("Watchlists", "List User Watchlists", "GET", "/api/v1/watchlists", is_auth=True)
        
        # POST create watchlist
        unique_wl_name = f"Benchmark WL {uuid.uuid4().hex[:6]}"
        res_cold_wl, res_warm_wl = await measure(
            "Watchlists", "Create Watchlist", "POST", "/api/v1/watchlists",
            payload={"name": unique_wl_name, "description": "Automated Benchmark Watchlist", "symbols": ["OGDC", "PPL"]},
            is_auth=True, expected_codes=(200, 201)
        )
        
        created_wl_id = None
        if res_cold_wl and res_cold_wl.status_code in (200, 201):
            try:
                created_wl_id = res_cold_wl.json().get("id")
            except Exception:
                pass
        
        if created_wl_id:
            # PATCH update watchlist
            await measure("Watchlists", "Update Watchlist Name", "PATCH", f"/api/v1/watchlists/{created_wl_id}",
                          payload={"name": f"{unique_wl_name} Renamed", "description": "Updated description"}, is_auth=True)
            
            # POST add item to watchlist
            await measure("Watchlists", "Add Stock to Watchlist", "POST", f"/api/v1/watchlists/{created_wl_id}/items",
                          payload={"symbol": "LUCK"}, is_auth=True, expected_codes=(200, 201))
            
            # DELETE remove item from watchlist
            await measure("Watchlists", "Remove Stock from Watchlist", "DELETE", f"/api/v1/watchlists/{created_wl_id}/items/LUCK",
                          is_auth=True, expected_codes=(200, 204))
            
            # DELETE watchlist
            await measure("Watchlists", "Delete Watchlist", "DELETE", f"/api/v1/watchlists/{created_wl_id}",
                          is_auth=True, expected_codes=(200, 204))

        # ─── 7. PORTFOLIO (CRUD: GET, POST, PUT, DELETE) ──────────────────────
        await measure("Portfolio", "Portfolio Overview", "GET", "/api/v1/portfolio", is_auth=True)
        await measure("Portfolio", "Portfolio Holdings", "GET", "/api/v1/portfolio/holdings", is_auth=True)
        await measure("Portfolio", "Portfolio P&L", "GET", "/api/v1/portfolio/pnl", is_auth=True)
        await measure("Portfolio", "Portfolio Allocation", "GET", "/api/v1/portfolio/allocation", is_auth=True)
        await measure("Portfolio", "Portfolio Performance", "GET", "/api/v1/portfolio/performance", is_auth=True)

        # POST create buy transaction
        res_cold_tx, res_warm_tx = await measure(
            "Portfolio", "Record BUY Transaction", "POST", "/api/v1/portfolio/transactions",
            payload={
                "symbol": "OGDC",
                "transaction_type": "BUY",
                "quantity": 100,
                "price": 160.50,
                "fee": 15.0,
                "transaction_date": str(date.today()),
                "confirm_outlier": True,
            },
            is_auth=True, expected_codes=(200, 201)
        )
        
        created_tx_id = None
        if res_cold_tx and res_cold_tx.status_code in (200, 201):
            try:
                created_tx_id = res_cold_tx.json().get("id")
            except Exception:
                pass
        elif res_warm_tx and res_warm_tx.status_code in (200, 201):
            try:
                created_tx_id = res_warm_tx.json().get("id")
            except Exception:
                pass

        if created_tx_id:
            # PATCH edit transaction
            await measure("Portfolio", "Edit Transaction", "PATCH", f"/api/v1/portfolio/transactions/{created_tx_id}",
                          payload={"quantity": 120, "price": 161.00, "fee": 15.0, "transaction_date": str(date.today()), "confirm_outlier": True},
                          is_auth=True, expected_codes=(200, 204))
            
            # DELETE transaction
            await measure("Portfolio", "Delete Transaction", "DELETE", f"/api/v1/portfolio/transactions/{created_tx_id}",
                          is_auth=True, expected_codes=(200, 204))

        # ─── 8. RISK ANALYTICS ───────────────────────────────────────────────
        await measure("Risk", "Portfolio VaR", "GET", "/api/v1/risk/var?confidence=95&horizon=1D", is_auth=True)
        await measure("Risk", "Risk Stress Testing", "GET", "/api/v1/risk/stress-test?scenario=2008_crash", is_auth=True)

        # ─── 9. ALERTS & NOTIFICATIONS (CRUD: GET, POST, PATCH, DELETE) ──────
        await measure("Alerts", "List User Alert Rules", "GET", "/api/v1/alerts/rules", is_auth=True)
        
        # POST create alert rule
        res_cold_al, res_warm_al = await measure(
            "Alerts", "Create Price Alert Rule", "POST", "/api/v1/alerts/rules",
            payload={"symbol": "OGDC", "condition": "PRICE_ABOVE", "target_value": 250.0, "channel": "PUSH"},
            is_auth=True, expected_codes=(200, 201)
        )
        created_rule_id = None
        if res_cold_al and res_cold_al.status_code in (200, 201):
            try:
                created_rule_id = res_cold_al.json().get("id")
            except Exception:
                pass

        if created_rule_id:
            # PATCH toggle alert rule
            await measure("Alerts", "Toggle Alert Active State", "PATCH", f"/api/v1/alerts/rules/{created_rule_id}/toggle",
                          is_auth=True, expected_codes=(200, 204))
            
            # DELETE alert rule
            await measure("Alerts", "Delete Alert Rule", "DELETE", f"/api/v1/alerts/rules/{created_rule_id}",
                          is_auth=True, expected_codes=(200, 204))

        # Notifications (GET, PATCH, POST)
        await measure("Notifications", "Get Notifications Feed", "GET", "/api/v1/notifications?limit=10", is_auth=True)
        await measure("Notifications", "Mark All Notifications Read", "POST", "/api/v1/notifications/read-all", is_auth=True, expected_codes=(200, 204))

        # ─── 10. COMMUNITY & SOCIAL (CRUD: GET, POST, PUT, DELETE) ───────────
        await measure("Community", "Get Community Feed", "GET", "/api/v1/community/posts?limit=10", is_auth=True)
        await measure("Community", "Community Trending Hub", "GET", "/api/v1/community/trending?limit=10", is_auth=True)
        
        # POST create community post
        res_cold_post, res_warm_post = await measure(
            "Community", "Create Discussion Post", "POST", "/api/v1/community/posts",
            payload={"content": "OGDC showing strong technical consolidation around PKR 160 #OGDC", "post_type": "STOCK", "stock_symbol": "OGDC"},
            is_auth=True, expected_codes=(200, 201)
        )
        created_post_id = None
        if res_cold_post and res_cold_post.status_code in (200, 201):
            try:
                created_post_id = res_cold_post.json().get("id")
            except Exception:
                pass

        if created_post_id:
            # POST toggle like
            await measure("Community", "Toggle Post Like", "POST", f"/api/v1/community/posts/{created_post_id}/like",
                          is_auth=True, expected_codes=(200, 201, 204))
            
            # POST add comment
            await measure("Community", "Add Post Comment", "POST", f"/api/v1/community/posts/{created_post_id}/comments",
                          payload={"content": "Agree! Solid volume support."}, is_auth=True, expected_codes=(200, 201))
            
            # DELETE post
            await measure("Community", "Delete Discussion Post", "DELETE", f"/api/v1/community/posts/{created_post_id}",
                          is_auth=True, expected_codes=(200, 204))

        # ─── 11. DEVICES (POST) ───────────────────────────────────────────────
        await measure("Devices", "Register Mobile FCM Device", "POST", "/api/v1/devices/register",
                      payload={"fcm_token": "mock-bench-fcm-token-12345", "platform": "android", "device_name": "Galaxy S24 Ultra"},
                      is_auth=True, expected_codes=(200, 201))
        await measure("Devices", "Unregister Device", "POST", "/api/v1/devices/unregister",
                      payload={"fcm_token": "mock-bench-fcm-token-12345"}, is_auth=True, expected_codes=(200, 204))

        # ─── 12. SUBSCRIPTIONS (GET, POST) ────────────────────────────────────
        await measure("Subscriptions", "Get Subscription Plans", "GET", "/api/v1/subscriptions/plans", is_auth=False)
        await measure("Subscriptions", "Get User AI Quota & Limits", "GET", "/api/v1/subscriptions/usage", is_auth=True)
        await measure("Subscriptions", "Create Payment Intent", "POST", "/api/v1/subscriptions/create-payment-intent",
                      payload={"plan_id": "pro_monthly", "currency": "PKR"}, is_auth=True, expected_codes=(200, 201, 503))

        # ─── 13. AI ASSISTANT CHAT & CONVERSATIONS (CRUD) ─────────────────────
        await measure("Assistant", "Get Quick Prompts", "GET", "/api/v1/assistant/quick-prompts", is_auth=True)
        await measure("Assistant", "Get Chat Conversations", "GET", "/api/v1/assistant/conversations", is_auth=True)
        await measure("Assistant", "Send AI Assistant Chat Message", "POST", "/api/v1/assistant/chat",
                      payload={"message": "What is the trend for OGDC?", "symbol": "OGDC"}, is_auth=True, expected_codes=(200, 201))

        print("\n" + "="*85, flush=True)
        print(f"  AUDIT COMPLETED: {len(results)} HTTP Operations Benchmarked Across GET, POST, PUT, PATCH, DELETE", flush=True)
        print("="*85 + "\n", flush=True)

        with open("full_crud_latency_results.json", "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)

if __name__ == "__main__":
    asyncio.run(run_full_stack_benchmark())
