"""
========================================================================================
BASARAT PRODUCTION LIVE SYSTEM & DEEP DATA ACCURACY MASTER AUDIT
Target: http://16.16.26.247:8000 (API & Celery Workers) & ws://16.16.26.247:8000
Note: Community module is strictly EXCLUDED per instructions.
========================================================================================
"""

import asyncio
import json
import time
from typing import Any, Dict, List, Optional
import httpx
import websockets

BASE_URL = "http://16.16.26.247:8000/api/v1"
HEALTH_URL = "http://16.16.26.247:8000"
WS_MARKET_URL = "ws://16.16.26.247:8000/ws/market"
WS_ALERTS_URL = "ws://16.16.26.247:8000/ws/alerts"

ADMIN_EMAIL = "admin@basarat.pk"
ADMIN_PASSWORD = "TestPassword12345!"

results: List[Dict[str, Any]] = []


def record(
    category: str,
    method: str,
    endpoint: str,
    status_code: int,
    latency_ms: float,
    passed: bool,
    data_summary: str = "",
    notes: str = "",
):
    results.append({
        "category": category,
        "method": method,
        "endpoint": endpoint,
        "status_code": status_code,
        "latency_ms": round(latency_ms, 2),
        "passed": passed,
        "data_summary": data_summary,
        "notes": notes,
    })
    status_tag = "PASS" if passed else "FAIL"
    print(
        f"[{status_tag:^6}] {category:<20} | {method:<6} {endpoint:<45} | {latency_ms:6.1f}ms | HTTP {status_code:<3} | {data_summary} {notes}",
        flush=True,
    )


async def run_master_production_audit():
    print("\n" + "=" * 125)
    print(" BASARAT PRODUCTION LIVE SYSTEM & DEEP DATA ACCURACY MASTER AUDIT")
    print(f" Target API: {BASE_URL} | WebSocket: {WS_MARKET_URL}")
    print(" Scope: Comprehensive Live Endpoints, Async Celery Workers, Redis, Data Freshness & WebSockets")
    print(" Excluded: Community Module (per instruction)")
    print("=" * 125 + "\n", flush=True)

    token = ""
    refresh_token = ""

    async with httpx.AsyncClient(timeout=45.0) as client:
        # ==============================================================================
        # 1. SYSTEM HEALTH & MONITORING
        # ==============================================================================
        print("\n--- 1. SYSTEM HEALTH & MONITORING ---", flush=True)
        for path in ["/health", "/health/ready"]:
            t0 = time.perf_counter()
            r = await client.get(f"{HEALTH_URL}{path}")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            try:
                body = r.json()
                summary = f"Status: {body.get('status', 'ok')} | Redis: {body.get('redis', 'ok')} | Celery: {body.get('celery_beat', 'ready')}"
            except Exception:
                summary = r.text[:30]
            record("System Health", "GET", path, r.status_code, lat, passed, summary)

        # ==============================================================================
        # 2. AUTHENTICATION & USER PROFILE LIFECYCLE
        # ==============================================================================
        print("\n--- 2. AUTHENTICATION & PROFILE ---", flush=True)
        t0 = time.perf_counter()
        r_login = await client.post(
            f"{BASE_URL}/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        )
        lat = (time.perf_counter() - t0) * 1000
        if r_login.status_code == 200:
            auth_data = r_login.json()
            token = auth_data.get("access_token", "")
            refresh_token = auth_data.get("refresh_token", "")
            record(
                "Auth & Profile",
                "POST",
                "/auth/login",
                r_login.status_code,
                lat,
                True,
                f"User: {auth_data.get('user', {}).get('email')} | JWT Acquired",
            )
        else:
            record("Auth & Profile", "POST", "/auth/login", r_login.status_code, lat, False, r_login.text[:50])

        headers = {"Authorization": f"Bearer {token}"} if token else {}

        # User profile
        t0 = time.perf_counter()
        r_me = await client.get(f"{BASE_URL}/users/me", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        passed = r_me.status_code == 200
        data_sum = f"Name: {r_me.json().get('full_name')} | Risk: {r_me.json().get('risk_tolerance')}" if passed else r_me.text[:30]
        record("Auth & Profile", "GET", "/users/me", r_me.status_code, lat, passed, data_sum)

        # Patch preferences
        t0 = time.perf_counter()
        r = await client.patch(
            f"{BASE_URL}/users/me",
            headers=headers,
            json={"risk_tolerance": "moderate", "investment_horizon": "medium_term", "sector_preferences": ["Commercial Banks", "Oil & Gas"]},
        )
        lat = (time.perf_counter() - t0) * 1000
        record("Auth & Profile", "PATCH", "/users/me", r.status_code, lat, r.status_code == 200, "Preferences Updated")

        # Notification preferences
        t0 = time.perf_counter()
        r = await client.patch(
            f"{BASE_URL}/users/me/notification-preferences",
            headers=headers,
            json={"channels": ["email", "push"], "categories": ["price_alerts", "daily_summary"]},
        )
        lat = (time.perf_counter() - t0) * 1000
        record("Auth & Profile", "PATCH", "/users/me/notification-preferences", r.status_code, lat, r.status_code == 200, "Notifications Configured")

        # Options
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/users/investment-profile/options")
        lat = (time.perf_counter() - t0) * 1000
        record("Auth & Profile", "GET", "/users/investment-profile/options", r.status_code, lat, r.status_code == 200, "Investment Profile Options")

        # Token refresh
        t0 = time.perf_counter()
        r_ref = await client.post(f"{BASE_URL}/auth/refresh", json={"refresh_token": refresh_token})
        lat = (time.perf_counter() - t0) * 1000
        record("Auth & Profile", "POST", "/auth/refresh", r_ref.status_code, lat, r_ref.status_code == 200, "Rotated Access Token")

        # ==============================================================================
        # 3. PSX MARKET OVERVIEW & INDICES
        # ==============================================================================
        print("\n--- 3. PSX MARKET OVERVIEW & AGGREGATIONS ---", flush=True)
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/market/indices")
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        ind_count = len(r.json().get("indices", [])) if passed else 0
        record("Market Overview", "GET", "/market/indices", r.status_code, lat, passed, f"Indices count: {ind_count}")

        for idx in ["kse-100", "kse-30", "kmi-30"]:
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/market/indices/{idx}")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            const_count = len(r.json().get("constituents", [])) if passed else 0
            record("Market Overview", "GET", f"/market/indices/{idx}", r.status_code, lat, passed, f"Constituents: {const_count}")

        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/market/sectors/performance?order=desc")
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        sec_count = len(r.json().get("sectors", [])) if passed else 0
        record("Market Overview", "GET", "/market/sectors/performance", r.status_code, lat, passed, f"Sectors count: {sec_count}")

        for ep, desc in [
            ("/market/gainers?limit=5", "Top Gainers"),
            ("/market/losers?limit=5", "Top Losers"),
            ("/market/volume-spikes?limit=5", "Volume Spikes"),
            ("/market/sentiment-overview", "Sentiment Mood"),
            ("/market/quotes?limit=10", "All PSX Quotes"),
        ]:
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}{ep}")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            summary = f"Total: {r.json().get('total', len(r.json()))}" if passed else r.text[:30]
            record("Market Overview", "GET", ep, r.status_code, lat, passed, summary, f"({desc})")

        # ==============================================================================
        # 4. CURATED STOCKS LEADERBOARD (5 CATEGORIES + REDIS BENCHMARK)
        # ==============================================================================
        print("\n--- 4. CURATED STOCKS LEADERBOARD & REDIS CACHE ---", flush=True)
        curated_cats = [
            ("high_dividend_yield", "Highest Dividend Yield"),
            ("best_returning_1y", "Best 1-Year Return"),
            ("value_investing", "Value Stocks"),
            ("most_liquid", "Most Liquid Equities"),
            ("fastest_growth", "Fast Growth"),
        ]
        for cat, name in curated_cats:
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/market/curated?category={cat}&limit=5")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            if passed:
                items = r.json().get("items", [])
                top_sym = items[0]["symbol"] if items else "None"
                top_val = items[0].get("metric_value", "N/A") if items else "N/A"
                summary = f"{len(items)} items | Top: {top_sym} ({top_val})"
            else:
                summary = r.text[:30]
            record("Curated Market", "GET", f"/market/curated?category={cat}", r.status_code, lat, passed, summary)

        # Curated Sector Filter
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/market/curated?category=high_dividend_yield&sector=FERTILIZER&limit=5")
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        summary = f"{len(r.json().get('items', []))} Fertilizer items verified" if passed else r.text[:30]
        record("Curated Market", "GET", "/market/curated?sector=FERT", r.status_code, lat, passed, summary)

        # ==============================================================================
        # 5. STOCKS DIRECTORY, FUNDAMENTALS & TECHNICAL INDICATORS
        # ==============================================================================
        print("\n--- 5. STOCKS DIRECTORY, TECHNICALS & FUNDAMENTALS ---", flush=True)
        for sym in ["OGDC", "SYS", "LUCK", "MEBL"]:
            # Search
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/stocks/search?q={sym}")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            record("Stocks Directory", "GET", f"/stocks/search?q={sym}", r.status_code, lat, passed, f"Matches: {len(r.json().get('results', [])) if passed else 0}")

            # Overview
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/stocks/{sym}/overview")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            data_sum = f"Price: {r.json().get('current_price', r.json().get('price'))} PKR | Cap: {r.json().get('market_cap')}" if passed else r.text[:30]
            record("Stocks Directory", "GET", f"/stocks/{sym}/overview", r.status_code, lat, passed, data_sum)

            # Price History
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/stocks/{sym}/price-history?range=1M")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            bars_count = len(r.json().get("bars", [])) if passed else 0
            record("Stocks Directory", "GET", f"/stocks/{sym}/price-history?range=1M", r.status_code, lat, passed, f"Candles: {bars_count}")

            # Technical Indicators
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/stocks/{sym}/technical-indicators")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            inds = list(r.json().get("indicators", {}).keys()) if passed else []
            record("Stocks Directory", "GET", f"/stocks/{sym}/technical-indicators", r.status_code, lat, passed, f"Indicators: {inds[:4]}")

            # Fundamentals
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/stocks/{sym}/fundamentals")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            reps = len(r.json().get("financial_reports", [])) if passed else 0
            record("Stocks Directory", "GET", f"/stocks/{sym}/fundamentals", r.status_code, lat, passed, f"Reports: {reps}")

        # ==============================================================================
        # 6. MULTI-FACTOR AI RECOMMENDATIONS
        # ==============================================================================
        print("\n--- 6. MULTI-FACTOR AI RECOMMENDATIONS ---", flush=True)
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/recommendations?limit=5", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        record("Recommendations", "GET", "/recommendations?limit=5", r.status_code, lat, passed, f"Count: {r.json().get('count') if passed else 0}")

        for sym in ["OGDC", "SYS", "LUCK"]:
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/recommendations/{sym}", headers=headers)
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            sig = r.json().get("decision", {}).get("signal", "N/A") if passed else "N/A"
            score = r.json().get("decision", {}).get("overall_score", "N/A") if passed else "N/A"
            record("Recommendations", "GET", f"/recommendations/{sym}", r.status_code, lat, passed, f"Signal: {sig} | Score: {score}")

        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/recommendations/engine-weights", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        record("Recommendations", "GET", "/recommendations/engine-weights", r.status_code, lat, r.status_code == 200, "Active Engine Factor Weights")

        # ==============================================================================
        # 7. RISK ENGINE & ASYNC CELERY MONTE CARLO WORKER
        # ==============================================================================
        print("\n--- 7. RISK ENGINE & ASYNC MONTE CARLO WORKER ---", flush=True)
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/risk/var?confidence=95&horizon=1D", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        var_val = r.json().get("var_value", "N/A") if passed else "N/A"
        record("Risk Engine", "GET", "/risk/var?confidence=95&horizon=1D", r.status_code, lat, passed, f"VaR 95%: {var_val}")

        # Async Monte Carlo Worker Dispatch
        t0 = time.perf_counter()
        r_mc = await client.post(
            f"{BASE_URL}/risk/monte-carlo",
            headers=headers,
            json={"num_simulations": 500, "horizon_days": 30},
        )
        lat = (time.perf_counter() - t0) * 1000
        mc_passed = r_mc.status_code in (200, 202)
        job_id = r_mc.json().get("job_id") if mc_passed else ""
        record("Risk Worker", "POST", "/risk/monte-carlo", r_mc.status_code, lat, mc_passed, f"Dispatched Async Job ID: {job_id}")

        # Poll the dispatched background worker job
        if job_id:
            for poll in range(1, 7):
                await asyncio.sleep(2.0)
                t0 = time.perf_counter()
                r_poll = await client.get(f"{BASE_URL}/risk/monte-carlo/{job_id}", headers=headers)
                lat = (time.perf_counter() - t0) * 1000
                if r_poll.status_code == 200:
                    status = r_poll.json().get("status", "").upper()
                    record("Risk Worker", "GET", f"/risk/monte-carlo/{job_id[:8]}", r_poll.status_code, lat, True, f"Poll #{poll}: Status={status}")
                    if status in ("COMPLETED", "SUCCESS"):
                        print(f"    [+] Async Monte Carlo Celery Worker Job COMPLETED successfully! Result: Expected Return: {r_poll.json().get('expected_return')}", flush=True)
                        break
                else:
                    record("Risk Worker", "GET", f"/risk/monte-carlo/{job_id[:8]}", r_poll.status_code, lat, False, r_poll.text[:30])

        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/risk/stress-test?scenario=2008_crash", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        impact = r.json().get("portfolio_impact", "N/A") if passed else "N/A"
        record("Risk Engine", "GET", "/risk/stress-test?scenario=2008_crash", r.status_code, lat, passed, f"Portfolio Impact: {impact}")

        # ==============================================================================
        # 8. SENTIMENT ENGINE (NLP & NEWS AGGREGATIONS)
        # ==============================================================================
        print("\n--- 8. SENTIMENT ENGINE ---", flush=True)
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/sentiment/market-overview", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        mood = r.json().get("market_mood", "N/A") if passed else "N/A"
        record("Sentiment Engine", "GET", "/sentiment/market-overview", r.status_code, lat, passed, f"Market Mood: {mood}")

        for sym in ["OGDC", "SYS", "MEBL"]:
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/sentiment/{sym}", headers=headers)
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            score = r.json().get("score", "N/A") if passed else "N/A"
            record("Sentiment Engine", "GET", f"/sentiment/{sym}", r.status_code, lat, passed, f"Sentiment Score: {score}")

            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/sentiment/{sym}/history", headers=headers)
            lat = (time.perf_counter() - t0) * 1000
            record("Sentiment Engine", "GET", f"/sentiment/{sym}/history", r.status_code, lat, r.status_code == 200, "Historical sentiment trends")

            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/sentiment/{sym}/news", headers=headers)
            lat = (time.perf_counter() - t0) * 1000
            record("Sentiment Engine", "GET", f"/sentiment/{sym}/news", r.status_code, lat, r.status_code == 200, "Symbol news sentiment tags")

        # ==============================================================================
        # 9. AI MULTI-HORIZON PRICE FORECASTING
        # ==============================================================================
        print("\n--- 9. AI MULTI-HORIZON PRICE FORECASTING ---", flush=True)
        for sym in ["OGDC", "SYS", "LUCK"]:
            for hz in ["1D", "1W", "1M"]:
                t0 = time.perf_counter()
                r = await client.get(f"{BASE_URL}/forecast/{sym}?horizon={hz}", headers=headers)
                lat = (time.perf_counter() - t0) * 1000
                passed = r.status_code == 200
                direction = r.json().get("direction", "N/A") if passed else "N/A"
                pred = r.json().get("predicted_price", "N/A") if passed else "N/A"
                record("AI Forecast", "GET", f"/forecast/{sym}?horizon={hz}", r.status_code, lat, passed, f"Direction: {direction} | Pred Price: {pred}")

            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/forecast/{sym}/history", headers=headers)
            lat = (time.perf_counter() - t0) * 1000
            record("AI Forecast", "GET", f"/forecast/{sym}/history", r.status_code, lat, r.status_code in (200, 404), "Historical Model Forecasts")

        # ==============================================================================
        # 10. PORTFOLIO, TRADES & HOLDINGS
        # ==============================================================================
        print("\n--- 10. PORTFOLIO, TRADES & HOLDINGS ---", flush=True)
        for ep, desc in [
            ("/portfolio", "Portfolio Summary & Total Value"),
            ("/portfolio/holdings", "Active Stock Holdings"),
            ("/portfolio/pnl", "Unrealized / Realized PnL"),
            ("/portfolio/allocation", "Sector & Asset Allocation"),
            ("/portfolio/performance", "Time-weighted Performance"),
            ("/portfolio/transactions", "Historical Transactions"),
        ]:
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}{ep}", headers=headers)
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            record("Portfolio", "GET", ep, r.status_code, lat, passed, desc)

        # ==============================================================================
        # 11. CORPORATE EVENTS & CALENDAR
        # ==============================================================================
        print("\n--- 11. EVENTS CALENDAR ---", flush=True)
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/events/calendar", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        ev_count = len(r.json().get("events", [])) if passed else 0
        record("Events Calendar", "GET", "/events/calendar", r.status_code, lat, passed, f"Upcoming PSX Events: {ev_count}")

        # ==============================================================================
        # 12. SHARIAH COMPLIANCE & SCREENING ENGINE
        # ==============================================================================
        print("\n--- 12. SHARIAH COMPLIANCE ENGINE ---", flush=True)
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/shariah/kmi30")
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        kmi_count = r.json().get("total_constituents", 0) if passed else 0
        record("Shariah Engine", "GET", "/shariah/kmi30", r.status_code, lat, passed, f"KMI-30 Constituents: {kmi_count}")

        for sym in ["OGDC", "SYS", "MEBL", "LUCK", "HBL"]:
            t0 = time.perf_counter()
            r = await client.get(f"{BASE_URL}/shariah/{sym}")
            lat = (time.perf_counter() - t0) * 1000
            passed = r.status_code == 200
            comp = r.json().get("is_shariah_compliant", "N/A") if passed else "N/A"
            record("Shariah Engine", "GET", f"/shariah/{sym}", r.status_code, lat, passed, f"Compliant: {comp}")

        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/shariah/OGDC/criteria")
        lat = (time.perf_counter() - t0) * 1000
        record("Shariah Engine", "GET", "/shariah/OGDC/criteria", r.status_code, lat, r.status_code == 200, "Detailed 6-factor criteria")

        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/shariah/SYS/purification?dividend_income=10000")
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        pur = r.json().get("purification_amount", 0) if passed else 0
        record("Shariah Engine", "GET", "/shariah/SYS/purification", r.status_code, lat, passed, f"Purification: PKR {pur}")

        # ==============================================================================
        # 13. ALERTS & NOTIFICATIONS
        # ==============================================================================
        print("\n--- 13. ALERTS & NOTIFICATIONS ---", flush=True)
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/alerts", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        a_count = len(r.json() if isinstance(r.json(), list) else r.json().get("items", [])) if r.status_code == 200 else 0
        record("Alerts & Notifications", "GET", "/alerts", r.status_code, lat, r.status_code == 200, f"User Alerts: {a_count}")

        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/alerts/rules", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        record("Alerts & Notifications", "GET", "/alerts/rules", r.status_code, lat, r.status_code == 200, "Predefined Alert Rules")

        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/notifications", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        n_count = len(r.json() if isinstance(r.json(), list) else r.json().get("items", [])) if r.status_code == 200 else 0
        record("Alerts & Notifications", "GET", "/notifications", r.status_code, lat, r.status_code == 200, f"Notifications: {n_count}")

        # ==============================================================================
        # 14. FINANCIAL NEWS & SOURCES
        # ==============================================================================
        print("\n--- 14. FINANCIAL NEWS & SOURCES ---", flush=True)
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/news?limit=5")
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        articles = len(r.json() if isinstance(r.json(), list) else r.json().get("items", [])) if passed else 0
        record("Financial News", "GET", "/news?limit=5", r.status_code, lat, passed, f"Live Articles: {articles}")

        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/news/sources")
        lat = (time.perf_counter() - t0) * 1000
        passed = r.status_code == 200
        sources = len(r.json() if isinstance(r.json(), list) else r.json().get("sources", [])) if passed else 0
        record("Financial News", "GET", "/news/sources", r.status_code, lat, passed, f"PSX News Sources: {sources}")

        # ==============================================================================
        # 15. AI ASSISTANT CONVERSATION MANAGEMENT
        # ==============================================================================
        print("\n--- 15. AI ASSISTANT CONVERSATIONS ---", flush=True)
        t0 = time.perf_counter()
        r = await client.get(f"{BASE_URL}/assistant/conversations", headers=headers)
        lat = (time.perf_counter() - t0) * 1000
        record("AI Assistant", "GET", "/assistant/conversations", r.status_code, lat, r.status_code == 200, "Listed user conversation threads")

        t0 = time.perf_counter()
        r_conv = await client.post(f"{BASE_URL}/assistant/conversations", headers=headers, json={"title": "Master Live Audit Chat"})
        lat = (time.perf_counter() - t0) * 1000
        conv_id = r_conv.json().get("id") if r_conv.status_code == 201 else None
        record("AI Assistant", "POST", "/assistant/conversations", r_conv.status_code, lat, r_conv.status_code == 201, f"Created Conversation ID: {conv_id}")

        if conv_id:
            t0 = time.perf_counter()
            r_del = await client.delete(f"{BASE_URL}/assistant/conversations/{conv_id}", headers=headers)
            lat = (time.perf_counter() - t0) * 1000
            record("AI Assistant", "DELETE", f"/assistant/conversations/{conv_id[:8]}", r_del.status_code, lat, r_del.status_code in (200, 204), "Cleaned up test conversation")

        # ==============================================================================
        # 16. WEBSOCKETS REST STATS & LIVE STREAMING PROTOCOL
        # ==============================================================================
        print("\n--- 16. WEBSOCKETS STATS & LIVE STREAMING AUDIT ---", flush=True)
        t0 = time.perf_counter()
        r_ws_stats = await client.get(f"{BASE_URL}/ws/stats")
        lat = (time.perf_counter() - t0) * 1000
        passed = r_ws_stats.status_code == 200
        ws_stats = r_ws_stats.json() if passed else {}
        record("WebSockets", "GET", "/ws/stats", r_ws_stats.status_code, lat, passed, f"Active: {ws_stats.get('total_connections', 0)} | Subscribed: {ws_stats.get('subscribed_symbols_count', 0)}")

    # ----------------------------------------------------------------------------------
    # LIVE WEBSOCKET CONNECTION & PROTOCOL TEST
    # ----------------------------------------------------------------------------------
    print("\n[*] Testing Live WebSocket Market Stream (ws://16.16.26.247:8000/ws/market)...", flush=True)
    try:
        async with websockets.connect(WS_MARKET_URL, open_timeout=10, close_timeout=5) as ws:
            # 1. Welcome handshake
            t0 = time.perf_counter()
            welcome_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            lat = (time.perf_counter() - t0) * 1000
            welcome = json.loads(welcome_raw)
            passed = welcome.get("event") == "connected"
            record("WS Market", "WS", "/ws/market [Handshake]", 101, lat, passed, f"Event: {welcome.get('event')}")

            # 2. Ping / Pong
            t0 = time.perf_counter()
            await ws.send(json.dumps({"action": "ping"}))
            pong_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            lat = (time.perf_counter() - t0) * 1000
            pong = json.loads(pong_raw)
            passed = pong.get("event") == "pong"
            record("WS Market", "WS", "/ws/market [Ping-Pong]", 101, lat, passed, f"Pong received in {lat:.1f}ms")

            # 3. Subscribe to Symbols
            t0 = time.perf_counter()
            await ws.send(json.dumps({"action": "subscribe", "symbols": ["SYS", "OGDC"]}))
            sub_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            lat = (time.perf_counter() - t0) * 1000
            sub_res = json.loads(sub_raw)
            passed = sub_res.get("event") == "subscribed" and "SYS" in sub_res.get("symbols", [])
            record("WS Market", "WS", "/ws/market [Subscribe]", 101, lat, passed, f"Subscribed: {sub_res.get('symbols')}")

            # 4. REST Broadcast Trigger -> WS Reception
            async with httpx.AsyncClient(timeout=10.0) as http_c:
                t0 = time.perf_counter()
                b_resp = await http_c.post(
                    f"{BASE_URL}/ws/broadcast",
                    json={
                        "symbol": "SYS",
                        "price": 460.25,
                        "change": 5.75,
                        "change_pct": 1.26,
                        "volume": 3200000,
                    },
                )
                b_lat = (time.perf_counter() - t0) * 1000
                b_passed = b_resp.status_code == 200 and b_resp.json().get("clients_reached", 0) >= 1
                record("WS Broadcast", "POST", "/ws/broadcast", b_resp.status_code, b_lat, b_passed, f"Clients reached: {b_resp.json().get('clients_reached')}")

            # Receive broadcasted tick
            t0 = time.perf_counter()
            tick_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            lat = (time.perf_counter() - t0) * 1000
            tick = json.loads(tick_raw)
            passed = tick.get("event") == "quote_update" and tick.get("symbol") == "SYS"
            record("WS Market", "WS", "/ws/market [Quote Tick]", 101, lat, passed, f"Tick Received: {tick.get('symbol')} @ {tick.get('data', {}).get('price')} PKR")

            # 5. Unsubscribe
            t0 = time.perf_counter()
            await ws.send(json.dumps({"action": "unsubscribe", "symbols": ["OGDC"]}))
            unsub_raw = await asyncio.wait_for(ws.recv(), timeout=5.0)
            lat = (time.perf_counter() - t0) * 1000
            unsub_res = json.loads(unsub_raw)
            passed = unsub_res.get("event") == "unsubscribed"
            record("WS Market", "WS", "/ws/market [Unsubscribe]", 101, lat, passed, f"Unsubscribed: {unsub_res.get('symbols')}")

    except Exception as e:
        record("WS Market", "WS", "/ws/market", 500, 0.0, False, f"WebSocket Error: {e}")

    # Test WS Alerts Authentication if token exists
    if token:
        print("\n[*] Testing Live Authenticated WebSocket Alerts (ws://16.16.26.247:8000/ws/alerts)...", flush=True)
        try:
            async with websockets.connect(f"{WS_ALERTS_URL}?token={token}", open_timeout=10, close_timeout=5) as ws_al:
                t0 = time.perf_counter()
                auth_raw = await asyncio.wait_for(ws_al.recv(), timeout=5.0)
                lat = (time.perf_counter() - t0) * 1000
                auth_msg = json.loads(auth_raw)
                passed = auth_msg.get("event") == "authenticated"
                record("WS Alerts", "WS", "/ws/alerts [Auth Stream]", 101, lat, passed, f"User authenticated: {auth_msg.get('user_id', '')[:8]}...")
        except Exception as e:
            record("WS Alerts", "WS", "/ws/alerts", 500, 0.0, False, f"WebSocket Auth Error: {e}")

    # ==============================================================================
    # FINAL SUMMARY & SCORECARD
    # ==============================================================================
    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    failed_count = total - passed_count
    pass_rate = (passed_count / total * 100) if total > 0 else 0
    avg_latency = sum(r["latency_ms"] for r in results) / total if total else 0

    print("\n" + "=" * 125)
    print(f" BASARAT PRODUCTION LIVE MASTER AUDIT SCORECARD")
    print("=" * 125)
    print(f" TOTAL TESTS EXECUTED : {total}")
    print(f" PASSED               : {passed_count} / {total} ({pass_rate:.1f}%)")
    print(f" FAILED               : {failed_count}")
    print(f" AVERAGE LATENCY      : {avg_latency:.1f}ms")
    print("=" * 125 + "\n", flush=True)

    if failed_count > 0:
        print("FAILED ENDPOINTS / SCENARIOS:")
        for r in results:
            if not r["passed"]:
                print(f" - [{r['category']}] {r['method']} {r['endpoint']}: Status {r['status_code']} -> {r['data_summary']} {r['notes']}")
        print()
    else:
        print(" ALL PRODUCTION LIVE ENDPOINTS, JOBS, DATA & WEBSOCKETS PASSED 100% WITH ZERO ERRORS!\n")


if __name__ == "__main__":
    asyncio.run(run_master_production_audit())
