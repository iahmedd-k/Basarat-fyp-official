"""Comprehensive Seeding and End-to-End API Test Suite (Excluding Auth & Community Modules).

Features:
1. Seeds 2 active verified users (User 1, User 2) and 1 Admin account directly in DB.
2. Seeds core PSX stock symbols (SYS, OGDC, HUBC, LUCK, ENGRO).
3. Generates valid JWT tokens directly (bypassing OTP / auth endpoints).
4. Systematically tests every single endpoint across:
   - System & Health Probes
   - Market Data & Quotes
   - Stock Overview, Fundamentals & Technicals
   - News Feed, Sources & Market Status
   - PSX Corporate Events Calendar
   - Protected Sentiment Analysis
   - User Profiles, Investment Preferences & Notification Settings
   - ML Forecasting & Prediction History
   - Multi-Strategy Quantitative Recommendations & Target Stops
   - Portfolio Summary, Holdings, Allocations, PnL, Performance & Transactions
   - Risk Analytics (VaR, CVaR, Monte Carlo, Stress Tests)
   - In-App Alerts & Notification Inbox
   - Shariah Compliance Screening & Dividend Purification
   - AI Investment Assistant Chat & Conversations
   - FCM Device Push Registration
(Auth and Community modules are excluded as requested).
"""

import asyncio
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import or_, select

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import create_access_token, hash_password
from app.db.base import async_session_factory, engine
from app.main import app
from app.ml.serving.model_loader import load_artifacts
from app.models.portfolio import PortfolioTransaction, TransactionType
from app.models.stock import Stock
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("test_suite")


async def seed_database():
    """Seed test users, admin, and stock fixtures."""
    log.info("==> Seeding database accounts, stock fixtures, and initial holdings...")
    async with async_session_factory() as session:
        # 1. Seed Stocks
        stocks_data = [
            ("SYS", "Systems Limited", "Technology"),
            ("OGDC", "Oil & Gas Development Co", "Energy"),
            ("HUBC", "Hub Power Company", "Utilities"),
            ("LUCK", "Lucky Cement", "Materials"),
            ("ENGRO", "Engro Corporation", "Conglomerates"),
        ]
        stock_map = {}
        for sym, name, sec in stocks_data:
            stk_res = await session.execute(select(Stock).where(Stock.symbol == sym))
            stk = stk_res.scalars().first()
            if not stk:
                stk = Stock(
                    symbol=sym,
                    name=name,
                    sector=sec,
                    market="PSX",
                    is_active=True,
                )
                session.add(stk)
                await session.flush()
                await session.refresh(stk)
            stock_map[sym] = stk

        # 2. Seed Accounts
        async def upsert_user(email, username, full_name, is_admin=False):
            res = await session.execute(
                select(User).where(or_(User.email == email, User.username == username))
            )
            u = res.scalars().first()
            if not u:
                u = User(email=email, username=username)
                session.add(u)
            u.email = email
            u.username = username
            u.full_name = full_name
            u.hashed_password = hash_password("TestPassword12345!")
            u.is_active = True
            u.is_verified = True
            u.is_admin = is_admin
            u.risk_tolerance = "moderate"
            return u

        u1 = await upsert_user("trader1@basarat.pk", "trader_one", "Ahmed Trader 1", is_admin=False)
        u2 = await upsert_user("trader2@basarat.pk", "trader_two", "Ali Trader 2", is_admin=False)
        admin = await upsert_user("admin@basarat.pk", "admin_master", "System Admin", is_admin=True)

        await session.commit()
        await session.refresh(u1)
        await session.refresh(u2)
        await session.refresh(admin)

        # 3. Seed sample portfolio transaction for u1 so Portfolio & Risk endpoints have data
        tx_check = await session.execute(
            select(PortfolioTransaction).where(PortfolioTransaction.user_id == u1.id)
        )
        if not tx_check.scalars().first():
            sys_stock = stock_map.get("SYS")
            if sys_stock:
                from datetime import date
                from decimal import Decimal
                sample_tx = PortfolioTransaction(
                    user_id=u1.id,
                    symbol="SYS",
                    transaction_type=TransactionType.BUY,
                    quantity=Decimal("100.0"),
                    price=Decimal("450.0"),
                    fee=Decimal("0.0"),
                    transaction_date=date.today(),
                )
                session.add(sample_tx)
                await session.commit()

        log.info("✓ User 1 seeded: %s (%s)", u1.username, u1.id)
        log.info("✓ User 2 seeded: %s (%s)", u2.username, u2.id)
        log.info("✓ Admin seeded: %s (%s)", admin.username, admin.id)

        # 4. Generate direct JWT tokens (Bypassing OTP/auth endpoints)
        token1 = create_access_token({"sub": u1.id})
        token2 = create_access_token({"sub": u2.id})
        admin_token = create_access_token({"sub": admin.id})

        return {
            "u1": {"id": u1.id, "username": u1.username, "token": token1},
            "u2": {"id": u2.id, "username": u2.username, "token": token2},
            "admin": {"id": admin.id, "username": admin.username, "token": admin_token},
        }


async def run_test_suite_async(accounts: dict):
    u1 = accounts["u1"]
    h1 = {"Authorization": f"Bearer {u1['token']}"}

    results = []

    def response_data_issue(method, path, response):
        """Return a useful-data failure reason, independent of HTTP status."""
        if response.status_code == 204:
            return None
        try:
            payload = response.json()
        except ValueError:
            return "response is not valid JSON"
        if payload is None:
            return "response body is null"

        def has_value(value):
            if value is None:
                return False
            if isinstance(value, str):
                return bool(value.strip())
            if isinstance(value, (int, float, bool)):
                return True
            if isinstance(value, list):
                return any(has_value(item) for item in value)
            if isinstance(value, dict):
                return any(has_value(item) for item in value.values())
            return False

        if not has_value(payload):
            return "response contains only null/empty values"

        # These collection responses are specifically expected to return useful
        # application data in this seeded local audit, not just a valid wrapper.
        if isinstance(payload, dict):
            data_keys = {
                "items", "results", "bars", "history", "indices", "constituents",
                "quotes", "events", "recommendations", "holdings", "transactions",
                "rules", "sources", "conversations", "notifications", "indicators",
            }
            for key in data_keys.intersection(payload):
                value = payload[key]
                if isinstance(value, list) and not value:
                    return f"{key} is empty"
        elif method == "GET" and isinstance(payload, list) and not payload:
            return "response list is empty"
        return None

    async def safe_request(client, method, path, headers=None, json=None, data=None, expected=[200, 201, 204], category="", name=""):
        try:
            if method == "GET":
                r = await client.get(path, headers=headers)
            elif method == "POST":
                r = await client.post(path, headers=headers, json=json, data=data)
            elif method == "PUT":
                r = await client.put(path, headers=headers, json=json, data=data)
            elif method == "PATCH":
                r = await client.patch(path, headers=headers, json=json, data=data)
            elif method == "DELETE":
                r = await client.delete(path, headers=headers)
            else:
                raise ValueError(f"Unknown method {method}")

            passed = r.status_code in expected
            issue = response_data_issue(method, path, r) if passed else None
            passed = passed and issue is None
            icon = "✓ PASS" if passed else "✗ FAIL"
            log.info("[%s] [%s] %s %s -> HTTP %d%s", icon, category, method, path, r.status_code, f" | {issue}" if issue else "")
            results.append({
                "category": category,
                "name": name or path,
                "method": method,
                "path": path,
                "status": r.status_code,
                "passed": passed,
                "data_issue": issue,
                "body_snippet": r.text[:300],
            })
            return r
        except Exception as e:
            log.warning("[✗ ERR] [%s] %s %s -> %s", category, method, path, e)
            results.append({
                "category": category,
                "name": name or path,
                "method": method,
                "path": path,
                "status": 0,
                "passed": False,
                "body_snippet": str(e),
            })
            return None

    # Use ASGITransport for direct FastAPI in-process execution
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test", timeout=90.0) as client:
        # ═════════════════════════════════════════════════════════════════════
        # 1. SYSTEM & HEALTH PROBES (PUBLIC)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 1. SYSTEM & HEALTH PROBES (PUBLIC) ==========")
        health_endpoints = [
            ("Root API", "GET", "/"),
            ("Health Live", "GET", "/health"),
            ("Health Ready", "GET", "/health/ready"),
            ("API v1 Health", "GET", "/api/v1/health"),
            ("API v1 Health Ready", "GET", "/api/v1/health/ready"),
            ("API v1 Ready (Compat)", "GET", "/api/v1/ready"),
        ]
        for cat, method, path in health_endpoints:
            await safe_request(client, method, path, expected=[200], category="Health", name=f"{cat} {path}")

        # ═════════════════════════════════════════════════════════════════════
        # 2. MARKET DATA & QUOTES (PUBLIC)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 2. MARKET DATA & QUOTES (PUBLIC) ==========")
        market_endpoints = [
            ("Indices Summary", "GET", "/api/v1/market/indices"),
            ("KSE-100 Constituents", "GET", "/api/v1/market/indices/kse-100"),
            ("KSE-30 Constituents", "GET", "/api/v1/market/indices/kse-30"),
            ("KMI-30 Constituents", "GET", "/api/v1/market/indices/kmi-30"),
            ("Top Gainers", "GET", "/api/v1/market/gainers"),
            ("Top Losers", "GET", "/api/v1/market/losers"),
            ("Volume Spikes", "GET", "/api/v1/market/volume-spikes"),
            ("Sentiment Overview", "GET", "/api/v1/market/sentiment-overview"),
            ("Market Quotes (Paginated)", "GET", "/api/v1/market/quotes?limit=10"),
            ("Market All-Stocks (Alias)", "GET", "/api/v1/market/all-stocks?limit=10"),
        ]
        for cat, method, path in market_endpoints:
            await safe_request(client, method, path, expected=[200], category="Market", name=f"{cat} {path}")

        # ═════════════════════════════════════════════════════════════════════
        # 3. STOCKS METRICS & DETAILS (PUBLIC)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 3. STOCKS METRICS & DETAILS (PUBLIC) ==========")
        stocks_endpoints = [
            ("Search Stocks", "GET", "/api/v1/stocks/search?q=SYS"),
            ("Stock Overview", "GET", "/api/v1/stocks/SYS/overview"),
            ("Price History (1M)", "GET", "/api/v1/stocks/SYS/price-history?period=1M"),
            ("Technical Indicators", "GET", "/api/v1/stocks/SYS/technical-indicators"),
            ("Stock Fundamentals", "GET", "/api/v1/stocks/SYS/fundamentals"),
            ("Stock News", "GET", "/api/v1/stocks/SYS/news"),
        ]
        for cat, method, path in stocks_endpoints:
            await safe_request(client, method, path, expected=[200], category="Stocks", name=f"{cat} {path}")

        # ═════════════════════════════════════════════════════════════════════
        # 4. NEWS & CORPORATE EVENTS
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 4. NEWS & CORPORATE EVENTS ==========")
        news_endpoints = [
            ("News Feed (Public)", "GET", "/api/v1/news"),
            ("News Filtered by Symbol (Public)", "GET", "/api/v1/news?symbol=SYS"),
            ("News Sources (Public)", "GET", "/api/v1/news/sources"),
            ("Market Schedule Status (Public)", "GET", "/api/v1/news/market-status"),
            ("News Refresh Status (Public)", "GET", "/api/v1/news/refresh/status"),
        ]
        for cat, method, path in news_endpoints:
            await safe_request(client, method, path, expected=[200], category="News", name=f"{cat} {path}")

        # Corporate Events Calendar (Protected)
        await safe_request(client, "GET", "/api/v1/events/calendar", headers=h1, expected=[200], category="Events", name="Events Calendar")

        # ═════════════════════════════════════════════════════════════════════
        # 5. PROTECTED SENTIMENT ANALYSIS (WITH JWT)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 5. PROTECTED SENTIMENT ANALYSIS ==========")
        sentiment_endpoints = [
            ("Stock Sentiment", "GET", "/api/v1/sentiment/SYS"),
            ("Sentiment History", "GET", "/api/v1/sentiment/SYS/history?period=1M"),
            ("Sentiment Tagged News", "GET", "/api/v1/sentiment/SYS/news?limit=5"),
            ("Market Sentiment Overview", "GET", "/api/v1/sentiment/market-overview"),
        ]
        for cat, method, path in sentiment_endpoints:
            await safe_request(client, method, path, headers=h1, expected=[200], category="Sentiment", name=f"{cat} {path}")

        # ═════════════════════════════════════════════════════════════════════
        # 6. USERS PROFILE & SETTINGS (PROTECTED)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 6. USERS PROFILE & SETTINGS ==========")
        await safe_request(client, "GET", "/api/v1/users/me", headers=h1, expected=[200], category="Users", name="Get Current User Profile")
        await safe_request(client, "PATCH", "/api/v1/users/me", headers=h1, json={"full_name": "Ahmed Trader Updated", "risk_tolerance": "moderate"}, expected=[200], category="Users", name="Update User Profile")
        await safe_request(client, "GET", "/api/v1/users/investment-profile/options", headers=h1, expected=[200], category="Users", name="Get Investment Profile Options")
        await safe_request(client, "PATCH", "/api/v1/users/me/notification-preferences", headers=h1, json={"channels": ["in_app"], "categories": ["alerts", "news"]}, expected=[200], category="Users", name="Update Notification Preferences")

        # ═════════════════════════════════════════════════════════════════════
        # 7. FORECAST & RECOMMENDATIONS (PROTECTED)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 7. FORECAST & RECOMMENDATIONS ==========")
        await safe_request(client, "GET", "/api/v1/forecast/SYS?horizon=1D", headers=h1, expected=[200], category="Forecast", name="Get AI Forecast")
        await safe_request(client, "GET", "/api/v1/forecast/SYS/history", headers=h1, expected=[200], category="Forecast", name="Get Forecast History")
        await safe_request(client, "GET", "/api/v1/recommendations", headers=h1, expected=[200], category="Recommendations", name="List Recommendations")
        await safe_request(client, "GET", "/api/v1/recommendations/engine-weights", headers=h1, expected=[200], category="Recommendations", name="Get Engine Weights")
        await safe_request(client, "GET", "/api/v1/recommendations/SYS", headers=h1, expected=[200], category="Recommendations", name="Get Stock Recommendation Detail")
        await safe_request(client, "GET", "/api/v1/recommendations/SYS/target-stop", headers=h1, expected=[200], category="Recommendations", name="Get Target/Stop Levels")
        await safe_request(client, "GET", "/api/v1/recommendations/top-picks", headers=h1, expected=[200], category="Recommendations", name="Get Top Recommendations Picks")

        # ═════════════════════════════════════════════════════════════════════
        # 8. PORTFOLIO & RISK ANALYTICS (PROTECTED)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 8. PORTFOLIO & RISK ANALYTICS ==========")
        await safe_request(client, "GET", "/api/v1/portfolio", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio Summary")
        await safe_request(client, "GET", "/api/v1/portfolio/holdings", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio Holdings")
        await safe_request(client, "GET", "/api/v1/portfolio/allocation", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio Allocation")
        await safe_request(client, "GET", "/api/v1/portfolio/pnl", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio PnL")
        await safe_request(client, "GET", "/api/v1/portfolio/performance", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio Performance")
        await safe_request(client, "GET", "/api/v1/portfolio/transactions", headers=h1, expected=[200], category="Portfolio", name="List Portfolio Transactions")

        await safe_request(client, "GET", "/api/v1/risk/var?confidence=95&horizon=1D", headers=h1, expected=[200], category="Risk", name="Compute Value-at-Risk")
        await safe_request(client, "GET", "/api/v1/risk/stress-test", headers=h1, expected=[200], category="Risk", name="Run Stress Test Simulation")
        mc_payload = {"num_simulations": 100, "horizon_days": 30, "seed": 42}
        await safe_request(client, "POST", "/api/v1/risk/monte-carlo", headers=h1, json=mc_payload, expected=[200, 201, 202], category="Risk", name="Start Monte Carlo Simulation")

        # ═════════════════════════════════════════════════════════════════════
        # 9. ALERTS & NOTIFICATIONS (PROTECTED)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 9. ALERTS & NOTIFICATIONS ==========")
        await safe_request(client, "GET", "/api/v1/alerts", headers=h1, expected=[200], category="Alerts", name="List User Alerts")
        await safe_request(client, "GET", "/api/v1/alerts/rules", headers=h1, expected=[200], category="Alerts", name="List User Alert Rules")
        alert_payload = {"condition": "price_above", "threshold": 500.0}
        r_rule = await safe_request(client, "POST", "/api/v1/alerts/rules", headers=h1, json=alert_payload, expected=[200, 201], category="Alerts", name="Create User Alert Rule")
        rule_id = r_rule.json().get("id") if (r_rule and r_rule.status_code in (200, 201)) else None
        if rule_id:
            await safe_request(client, "PATCH", f"/api/v1/alerts/rules/{rule_id}", headers=h1, json={"threshold": 550.0}, expected=[200], category="Alerts", name="Update Alert Rule")
            await safe_request(client, "DELETE", f"/api/v1/alerts/rules/{rule_id}", headers=h1, expected=[200, 204], category="Alerts", name="Delete Alert Rule")

        await safe_request(client, "GET", "/api/v1/notifications", headers=h1, expected=[200], category="Notifications", name="Get User Notification Inbox")

        # ═════════════════════════════════════════════════════════════════════
        # 10. SHARIAH COMPLIANCE SCREENING & DIVIDEND PURIFICATION (PROTECTED)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 10. SHARIAH COMPLIANCE & PURIFICATION ==========")
        await safe_request(client, "GET", "/api/v1/shariah/kmi30", headers=h1, expected=[200], category="Shariah", name="Get KMI-30 Shariah Overview")
        await safe_request(client, "GET", "/api/v1/shariah/SYS", headers=h1, expected=[200], category="Shariah", name="Screen Stock Compliance")
        await safe_request(client, "GET", "/api/v1/shariah/SYS/criteria", headers=h1, expected=[200], category="Shariah", name="Get Detailed Shariah Criteria")
        await safe_request(client, "GET", "/api/v1/shariah/SYS/purification?holding_qty=100&holding_value=45000", headers=h1, expected=[200], category="Shariah", name="Calculate Dividend Purification")

        # ═════════════════════════════════════════════════════════════════════
        # 11. AI INVESTMENT ASSISTANT & DEVICES (PROTECTED)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 11. AI ASSISTANT & DEVICES ==========")
        chat_payload = {"message": "What is the investment thesis for Systems Limited (SYS)?"}
        await safe_request(client, "POST", "/api/v1/assistant/chat", headers=h1, json=chat_payload, expected=[200, 201], category="Assistant", name="AI Assistant Chat")
        await safe_request(client, "GET", "/api/v1/assistant/conversations", headers=h1, expected=[200], category="Assistant", name="List AI Assistant Conversations")

        device_payload = {
            "fcm_token": "fcm_test_token_abc123_xyz789",
            "device_name": "Pixel 8 Pro",
            "platform": "android",
        }
        await safe_request(client, "POST", "/api/v1/devices/register", headers=h1, json=device_payload, expected=[200, 201], category="Devices", name="Register Mobile Device")

    # ═════════════════════════════════════════════════════════════════════
    # SUMMARY REPORT
    # ═════════════════════════════════════════════════════════════════════
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    log.info("\n" + "=" * 75)
    log.info("END-TO-END TEST SUITE EXECUTION REPORT (EXCLUDING AUTH & COMMUNITY)")
    log.info("=" * 75)
    for r in results:
        sym = "PASS" if r["passed"] else "FAIL"
        err = f" -> {r['body_snippet']}" if not r["passed"] else ""
        log.info("[%4s] %-15s %-6s %-45s (HTTP %d)%s", sym, r["category"], r["method"], r["name"], r["status"], err)

    log.info("=" * 75)
    log.info("Total API Endpoints Tested: %d", total)
    log.info("Passed: %d", passed)
    log.info("Failed: %d", failed)
    log.info("Pass Rate: %.1f%%", (passed / total) * 100)
    log.info("=" * 75)

    return passed == total


async def main():
    try:
        # 1. Preload ML Model Artifacts
        load_artifacts()
        # 2. Seed Database
        accounts = await seed_database()
        # 3. Run Async Test Suite
        success = await run_test_suite_async(accounts)
        if not success:
            sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
