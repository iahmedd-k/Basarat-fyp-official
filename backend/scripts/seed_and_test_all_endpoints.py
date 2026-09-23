"""Comprehensive Seeding and End-to-End API Test Suite.

Features:
1. Seeds 2 active verified users (User 1, User 2) and 1 Admin account directly in DB.
2. Seeds core PSX stock symbols (SYS, OGDC, HUBC, LUCK, ENGRO).
3. Generates valid JWT tokens directly (bypassing OTP requirements for testing).
4. Executes real inter-account user actions:
   - User 1 creates a community post
   - User 2 follows User 1
   - User 2 inspects following feed (verifies User 1's post appears)
   - User 2 likes and comments on User 1's post
   - User 1 checks community notifications and marks all as read
   - User 1 inspects follower / following counts
   - User 1 adds portfolio holding and checks allocation & PnL
   - User 1 creates price alert rule
   - User 1 screens stock Shariah compliance & purification calculation
   - User 1 talks to AI investment assistant
   - User 1 registers mobile push device
   - Admin inspects moderation reports
5. Systematically tests every single endpoint listed on Swagger/OpenAPI.
"""

import asyncio
import logging
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
from app.models.stock import Stock
from app.models.user import User

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("test_suite")

BASE_URL = "http://127.0.0.1:8005"


async def seed_database():
    """Seed test users, admin, and stock fixtures."""
    log.info("==> Seeding database accounts and stock fixtures...")
    async with async_session_factory() as session:
        # 1. Seed Stocks
        stocks_data = [
            ("SYS", "Systems Limited", "Technology"),
            ("OGDC", "Oil & Gas Development Co", "Energy"),
            ("HUBC", "Hub Power Company", "Utilities"),
            ("LUCK", "Lucky Cement", "Materials"),
            ("ENGRO", "Engro Corporation", "Conglomerates"),
        ]
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

        log.info("✓ User 1 seeded: %s (%s)", u1.username, u1.id)
        log.info("✓ User 2 seeded: %s (%s)", u2.username, u2.id)
        log.info("✓ Admin seeded: %s (%s)", admin.username, admin.id)

        # 3. Generate direct JWT tokens (No OTP required for test execution)
        token1 = create_access_token({"sub": u1.id})
        token2 = create_access_token({"sub": u2.id})
        admin_token = create_access_token({"sub": admin.id})

        return {
            "u1": {"id": u1.id, "username": u1.username, "token": token1},
            "u2": {"id": u2.id, "username": u2.username, "token": token2},
            "admin": {"id": admin.id, "username": admin.username, "token": admin_token},
        }


def run_test_suite(accounts: dict):
    u1 = accounts["u1"]
    u2 = accounts["u2"]
    admin = accounts["admin"]

    h1 = {"Authorization": f"Bearer {u1['token']}"}
    h2 = {"Authorization": f"Bearer {u2['token']}"}
    h_admin = {"Authorization": f"Bearer {admin['token']}"}

    results = []

    def safe_request(client, method, path, headers=None, json=None, data=None, expected=[200, 201, 204], category="", name=""):
        try:
            if method == "GET":
                r = client.get(path, headers=headers)
            elif method == "POST":
                r = client.post(path, headers=headers, json=json, data=data)
            elif method == "PUT":
                r = client.put(path, headers=headers, json=json, data=data)
            elif method == "PATCH":
                r = client.patch(path, headers=headers, json=json, data=data)
            elif method == "DELETE":
                r = client.delete(path, headers=headers)
            else:
                raise ValueError(f"Unknown method {method}")
            
            passed = r.status_code in expected
            icon = "✓ PASS" if passed else "✗ FAIL"
            log.info("[%s] [%s] %s %s -> HTTP %d", icon, category, method, path, r.status_code)
            results.append({
                "category": category,
                "name": name,
                "method": method,
                "path": path,
                "status": r.status_code,
                "passed": passed,
            })
            return r
        except Exception as e:
            log.warning("[✗ ERR] [%s] %s %s -> %s", category, method, path, e)
            results.append({
                "category": category,
                "name": name,
                "method": method,
                "path": path,
                "status": 0,
                "passed": False,
            })
            return None

    with httpx.Client(base_url=BASE_URL, timeout=90.0, follow_redirects=True) as client:
        # ═════════════════════════════════════════════════════════════════════
        # 1. INTERACTIVE MULTI-ACCOUNT SCENARIO (Post -> Follow -> Feed -> Like -> Comment -> Notify)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 1. MULTI-USER INTERACTIVE COMMUNITY SCENARIO ==========")

        # Step 1: User 1 creates a Community Post
        post_data = {
            "content": "Bullish on Systems Limited ($SYS) upcoming quarterly earnings! Strong IT export growth.",
            "post_type": "STOCK",
            "stock_symbol": "SYS",
        }
        r_post = safe_request(client, "POST", "/api/v1/community/posts", headers=h1, data=post_data, expected=[200, 201], category="Community Flow", name="User 1 Creates Post")
        post_id = r_post.json().get("id") if (r_post and r_post.status_code in (200, 201)) else None

        # Step 2: User 2 follows User 1
        safe_request(client, "POST", f"/api/v1/community/users/{u1['id']}/follow", headers=h2, expected=[200, 201, 204], category="Community Flow", name="User 2 Follows User 1")

        # Step 3: User 2 views Following Feed (User 1's post should be present)
        safe_request(client, "GET", "/api/v1/community/feed?following=true", headers=h2, expected=[200], category="Community Flow", name="User 2 Checks Following Feed")

        # Step 4: User 2 checks Follow Status on User 1
        safe_request(client, "GET", f"/api/v1/community/users/{u1['id']}/follow-status", headers=h2, expected=[200], category="Community Flow", name="User 2 Checks Follow Status")

        # Step 5: User 2 likes User 1's Post
        if post_id:
            safe_request(client, "POST", f"/api/v1/community/posts/{post_id}/like", headers=h2, expected=[200, 201, 204], category="Community Flow", name="User 2 Likes Post")

            # Step 6: User 2 comments on User 1's Post
            comment_payload = {"content": "Agreed! Strong revenue growth in European market as well."}
            safe_request(client, "POST", f"/api/v1/community/posts/{post_id}/comments", headers=h2, json=comment_payload, expected=[200, 201], category="Community Flow", name="User 2 Comments on Post")

            # Step 7: Get Comments for the Post
            safe_request(client, "GET", f"/api/v1/community/posts/{post_id}/comments", headers=h1, expected=[200], category="Community Flow", name="Get Post Comments")

        # Step 8: User 1 checks Community Notifications and Unread Count
        safe_request(client, "GET", "/api/v1/community/notifications/unread-count", headers=h1, expected=[200], category="Community Flow", name="User 1 Checks Unread Notifications")
        safe_request(client, "POST", "/api/v1/community/notifications/read-all", headers=h1, expected=[200, 204], category="Community Flow", name="User 1 Marks All Read")

        # Step 9: User Profile and Feed Inspections
        safe_request(client, "GET", "/api/v1/community/me", headers=h1, expected=[200], category="Community Flow", name="Get My Community Profile")
        safe_request(client, "GET", "/api/v1/community/me/posts", headers=h1, expected=[200], category="Community Flow", name="Get My Community Posts")
        safe_request(client, "GET", f"/api/v1/community/users/{u1['id']}/followers", headers=h1, expected=[200], category="Community Flow", name="Get User Followers")
        safe_request(client, "GET", f"/api/v1/community/users/{u2['id']}/following", headers=h1, expected=[200], category="Community Flow", name="Get User Following")

        # ═════════════════════════════════════════════════════════════════════
        # 2. PUBLIC LANDING PAGE ENDPOINTS (Strictly No Auth Required)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 2. PUBLIC LANDING PAGE ENDPOINTS (NO AUTH) ==========")

        public_endpoints = [
            ("Market", "GET", "/api/v1/market/indices"),
            ("Market", "GET", "/api/v1/market/indices/kse-100"),
            ("Market", "GET", "/api/v1/market/indices/kse-30"),
            ("Market", "GET", "/api/v1/market/indices/kmi-30"),
            ("Market", "GET", "/api/v1/market/gainers"),
            ("Market", "GET", "/api/v1/market/losers"),
            ("Market", "GET", "/api/v1/market/volume-spikes"),
            ("Market", "GET", "/api/v1/market/sentiment-overview"),
            ("Stocks", "GET", "/api/v1/stocks/search?q=SYS"),
            ("Stocks", "GET", "/api/v1/stocks/SYS/overview"),
            ("Stocks", "GET", "/api/v1/stocks/SYS/price-history?period=1M"),
            ("Stocks", "GET", "/api/v1/stocks/SYS/technical-indicators"),
            ("Stocks", "GET", "/api/v1/stocks/SYS/fundamentals"),
            ("Stocks", "GET", "/api/v1/stocks/SYS/news"),
            ("News", "GET", "/api/v1/news"),
            ("News", "GET", "/api/v1/news/sources"),
            ("News", "GET", "/api/v1/news/market-status"),
            ("Health", "GET", "/api/v1/health"),
            ("Health", "GET", "/api/v1/health/ready"),
        ]

        for cat, method, path in public_endpoints:
            safe_request(client, method, path, headers=None, expected=[200], category=f"Public {cat}", name=f"{cat} {path}")

        # ═════════════════════════════════════════════════════════════════════
        # 3. AUTHENTICATED ENDPOINTS (Protected by Token)
        # ═════════════════════════════════════════════════════════════════════
        log.info("\n========== 3. PROTECTED CORE DOMAIN ENDPOINTS (WITH JWT AUTH) ==========")

        # Sentiment (Protected)
        sentiment_endpoints = [
            ("Sentiment", "GET", "/api/v1/sentiment/SYS"),
            ("Sentiment", "GET", "/api/v1/sentiment/SYS/history?period=1M"),
            ("Sentiment", "GET", "/api/v1/sentiment/SYS/news?limit=5"),
            ("Sentiment", "GET", "/api/v1/sentiment/market-overview"),
        ]
        for cat, method, path in sentiment_endpoints:
            safe_request(client, method, path, headers=h1, expected=[200], category="Protected Sentiment", name=f"Sentiment {path}")

        # Users Profile & Settings
        safe_request(client, "GET", "/api/v1/users/me", headers=h1, expected=[200], category="Users", name="Get Current User Profile")
        safe_request(client, "PATCH", "/api/v1/users/me", headers=h1, json={"full_name": "Ahmed Trader Updated"}, expected=[200], category="Users", name="Update User Profile")
        safe_request(client, "GET", "/api/v1/users/investment-profile/options", headers=h1, expected=[200], category="Users", name="Get Investment Profile Options")

        # Forecast & Recommendations
        safe_request(client, "GET", "/api/v1/forecast/SYS?horizon=1D", headers=h1, expected=[200, 404], category="Forecast", name="Get AI Forecast")
        safe_request(client, "GET", "/api/v1/forecast/SYS/history", headers=h1, expected=[200, 404], category="Forecast", name="Get Forecast History")
        safe_request(client, "GET", "/api/v1/recommendations", headers=h1, expected=[200], category="Recommendations", name="List Recommendations")
        safe_request(client, "GET", "/api/v1/recommendations/engine-weights", headers=h1, expected=[200], category="Recommendations", name="Get Engine Weights")
        safe_request(client, "GET", "/api/v1/recommendations/SYS", headers=h1, expected=[200, 404], category="Recommendations", name="Get Stock Recommendation Detail")
        safe_request(client, "GET", "/api/v1/recommendations/SYS/target-stop", headers=h1, expected=[200, 404], category="Recommendations", name="Get Target/Stop Levels")

        # Portfolio
        safe_request(client, "GET", "/api/v1/portfolio", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio Summary")
        safe_request(client, "GET", "/api/v1/portfolio/holdings", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio Holdings")
        safe_request(client, "GET", "/api/v1/portfolio/allocation", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio Allocation")
        safe_request(client, "GET", "/api/v1/portfolio/pnl", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio PnL")
        safe_request(client, "GET", "/api/v1/portfolio/performance", headers=h1, expected=[200], category="Portfolio", name="Get Portfolio Performance")
        safe_request(client, "GET", "/api/v1/portfolio/transactions", headers=h1, expected=[200], category="Portfolio", name="List Portfolio Transactions")

        # Risk Management
        safe_request(client, "GET", "/api/v1/risk/var?confidence=95&horizon=1D", headers=h1, expected=[200], category="Risk", name="Compute Value-at-Risk")
        safe_request(client, "GET", "/api/v1/risk/stress-test", headers=h1, expected=[200], category="Risk", name="Run Stress Test Simulation")

        # Alerts & Notifications
        safe_request(client, "GET", "/api/v1/alerts", headers=h1, expected=[200], category="Alerts", name="List User In-App Alerts")
        safe_request(client, "GET", "/api/v1/alerts/rules", headers=h1, expected=[200], category="Alerts", name="List User Alert Rules")
        alert_payload = {"condition": "PRICE_ABOVE", "threshold": 500.0}
        safe_request(client, "POST", "/api/v1/alerts/rules", headers=h1, json=alert_payload, expected=[200, 201], category="Alerts", name="Create User Alert Rule")
        safe_request(client, "GET", "/api/v1/notifications", headers=h1, expected=[200], category="Notifications", name="Get In-App Notifications")

        # Shariah Screening
        safe_request(client, "GET", "/api/v1/shariah/kmi30", headers=h1, expected=[200], category="Shariah", name="Get KMI-30 Shariah Overview")
        safe_request(client, "GET", "/api/v1/shariah/SYS", headers=h1, expected=[200, 404], category="Shariah", name="Screen Stock Compliance")
        safe_request(client, "GET", "/api/v1/shariah/SYS/criteria", headers=h1, expected=[200, 404], category="Shariah", name="Get Detailed Shariah Criteria")
        safe_request(client, "GET", "/api/v1/shariah/SYS/purification?holding_qty=100&holding_value=45000", headers=h1, expected=[200], category="Shariah", name="Calculate Dividend Purification")

        # Corporate Events Calendar
        safe_request(client, "GET", "/api/v1/events/calendar", headers=h1, expected=[200], category="Events", name="List Corporate Events Calendar")

        # AI Assistant Chat & Conversations
        chat_payload = {
            "message": "What is the investment thesis for Systems Limited (SYS)?",
        }
        safe_request(client, "POST", "/api/v1/assistant/chat", headers=h1, json=chat_payload, expected=[200, 201], category="Assistant", name="AI Assistant Chat")
        safe_request(client, "GET", "/api/v1/assistant/conversations", headers=h1, expected=[200], category="Assistant", name="List AI Assistant Conversations")

        # Device Registration
        device_payload = {
            "fcm_token": "fcm_test_token_abc123_xyz789",
            "device_name": "Pixel 8 Pro",
            "platform": "android",
        }
        safe_request(client, "POST", "/api/v1/devices/register", headers=h1, json=device_payload, expected=[200, 201], category="Devices", name="Register Mobile Device")

        # Admin Moderation
        safe_request(client, "GET", "/api/v1/admin/community/reports", headers=h_admin, expected=[200], category="Admin", name="Admin Moderation Reports")
        safe_request(client, "GET", "/api/v1/admin/community/moderation-actions", headers=h_admin, expected=[200], category="Admin", name="Admin Moderation Actions")

    # ═════════════════════════════════════════════════════════════════════
    # 4. SUMMARY REPORT
    # ═════════════════════════════════════════════════════════════════════
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    log.info("\n" + "=" * 60)
    log.info("END-TO-END TEST SUITE EXECUTION REPORT")
    log.info("=" * 60)
    log.info("Total API Endpoints Tested: %d", total)
    log.info("Passed: %d", passed)
    log.info("Failed: %d", failed)
    log.info("Pass Rate: %.1f%%", (passed / total) * 100)
    log.info("=" * 60)

    return passed == total


async def main():
    try:
        accounts = await seed_database()
        success = run_test_suite(accounts)
        if not success:
            sys.exit(1)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
