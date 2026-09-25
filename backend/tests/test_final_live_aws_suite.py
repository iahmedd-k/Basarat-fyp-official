"""Master Final Live E2E URL Audit Suite for Basarat Backend on AWS.

Tests and benchmarks every endpoint on the live AWS deployment (http://16.16.26.247:8000/api/v1).
"""

import sys
import time
from pathlib import Path
import httpx

# Setup python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

BASE_URL = "http://16.16.26.247:8000/api/v1"
HEALTH_URL = "http://16.16.26.247:8000"

results = []

def record(module: str, method: str, endpoint: str, status_code: int, duration_ms: float, passed: bool, notes: str = ""):
    results.append({
        "module": module,
        "method": method,
        "endpoint": endpoint,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "passed": passed,
        "notes": notes,
    })
    status_icon = " PASS " if passed else " FAIL "
    print(f"[{status_icon}] {module:<18} | {method:<6} {endpoint:<45} | {duration_ms:6.1f}ms | HTTP {status_code} | {notes}")


def run_master_live_aws_audit():
    print("\n" + "="*115)
    print(f" BASARAT PRODUCTION LIVE AWS MASTER AUDIT — TARGET: {BASE_URL}")
    print("="*115 + "\n")

    with httpx.Client(timeout=45.0) as client:
        # -------------------------------------------------------------
        # 1. Health & System
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{HEALTH_URL}/health")
        d = (time.perf_counter() - t0) * 1000
        record("Health & System", "GET", "/health", r.status_code, d, r.status_code == 200, f"Status: {r.json().get('status')}")

        t0 = time.perf_counter()
        r = client.get(f"{HEALTH_URL}/health/ready")
        d = (time.perf_counter() - t0) * 1000
        record("Health & System", "GET", "/health/ready", r.status_code, d, r.status_code == 200)

        # -------------------------------------------------------------
        # 2. Authentication & User Profile
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r_login = client.post(f"{BASE_URL}/auth/login", json={"email": "admin@basarat.pk", "password": "TestPassword12345!"})
        d = (time.perf_counter() - t0) * 1000
        token_data = r_login.json() if r_login.status_code == 200 else {}
        token = token_data.get("access_token", "")
        refresh_token = token_data.get("refresh_token", "")
        headers = {"Authorization": f"Bearer {token}"}
        user_id = token_data.get("user", {}).get("id", "")
        record("Auth & Profile", "POST", "/auth/login", r_login.status_code, d, r_login.status_code == 200, f"User: {token_data.get('user', {}).get('email')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/users/me", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Auth & Profile", "GET", "/users/me", r.status_code, d, r.status_code == 200, f"Name: {r.json().get('full_name')}")

        t0 = time.perf_counter()
        r = client.patch(f"{BASE_URL}/users/me", headers=headers, json={"risk_tolerance": "moderate", "investment_horizon": "medium_term", "sector_preferences": ["Commercial Banks", "Oil & Gas"]})
        d = (time.perf_counter() - t0) * 1000
        record("Auth & Profile", "PATCH", "/users/me", r.status_code, d, r.status_code == 200, "Preferences Updated")

        t0 = time.perf_counter()
        r = client.patch(f"{BASE_URL}/users/me/notification-preferences", headers=headers, json={"channels": ["email", "push"], "categories": ["price_alerts", "daily_summary"]})
        d = (time.perf_counter() - t0) * 1000
        record("Auth & Profile", "PATCH", "/users/me/notification-preferences", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/users/investment-profile/options")
        d = (time.perf_counter() - t0) * 1000
        record("Auth & Profile", "GET", "/users/investment-profile/options", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.post(f"{BASE_URL}/auth/refresh", json={"refresh_token": refresh_token})
        d = (time.perf_counter() - t0) * 1000
        record("Auth & Profile", "POST", "/auth/refresh", r.status_code, d, r.status_code == 200, "Rotated Access Token")

        # -------------------------------------------------------------
        # 3. Market Overview & PSX Indices
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/indices")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/indices", r.status_code, d, r.status_code == 200, f"Indices count: {len(r.json().get('indices', []))}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/indices/kse-100")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/indices/kse-100", r.status_code, d, r.status_code == 200, f"Constituents: {len(r.json().get('constituents', []))}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/indices/kse-30")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/indices/kse-30", r.status_code, d, r.status_code == 200, f"Constituents: {len(r.json().get('constituents', []))}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/indices/kmi-30")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/indices/kmi-30", r.status_code, d, r.status_code == 200, f"Constituents: {len(r.json().get('constituents', []))}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/sectors/performance?order=desc")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/sectors/performance", r.status_code, d, r.status_code == 200, f"Sectors count: {len(r.json().get('sectors', []))}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/gainers?limit=5")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/gainers", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/losers?limit=5")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/losers", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/volume-spikes?limit=5")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/volume-spikes", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/sentiment-overview")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/sentiment-overview", r.status_code, d, r.status_code == 200, f"Mood: {r.json().get('market_mood')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/market/quotes?limit=10")
        d = (time.perf_counter() - t0) * 1000
        record("Market Overview", "GET", "/market/quotes", r.status_code, d, r.status_code == 200, f"Total PSX stocks: {r.json().get('total')}")

        # -------------------------------------------------------------
        # 4. Stocks & Fundamentals
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/stocks/search?q=OGDC")
        d = (time.perf_counter() - t0) * 1000
        record("Stocks Directory", "GET", "/stocks/search", r.status_code, d, r.status_code == 200, f"Results: {len(r.json().get('results', []))}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/stocks/OGDC/overview")
        d = (time.perf_counter() - t0) * 1000
        record("Stocks Directory", "GET", "/stocks/OGDC/overview", r.status_code, d, r.status_code == 200, f"Overview retrieved")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/stocks/OGDC/price-history?range=1M")
        d = (time.perf_counter() - t0) * 1000
        record("Stocks Directory", "GET", "/stocks/OGDC/price-history", r.status_code, d, r.status_code == 200, f"Bars: {len(r.json().get('bars', []))}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/stocks/OGDC/technical-indicators")
        d = (time.perf_counter() - t0) * 1000
        record("Stocks Directory", "GET", "/stocks/OGDC/technical-indicators", r.status_code, d, r.status_code == 200, f"Indicators: {list(r.json().get('indicators', {}).keys())}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/stocks/OGDC/fundamentals")
        d = (time.perf_counter() - t0) * 1000
        record("Stocks Directory", "GET", "/stocks/OGDC/fundamentals", r.status_code, d, r.status_code == 200, f"Reports: {len(r.json().get('financial_reports', []))}")

        # -------------------------------------------------------------
        # 5. Recommendations
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/recommendations?limit=5", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Recommendations", "GET", "/recommendations", r.status_code, d, r.status_code == 200, f"Count: {r.json().get('count')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/recommendations/OGDC", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Recommendations", "GET", "/recommendations/OGDC", r.status_code, d, r.status_code == 200, f"Decision: {r.json().get('decision', {}).get('signal')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/recommendations/weights", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Recommendations", "GET", "/recommendations/weights", r.status_code, d, r.status_code == 200)

        # -------------------------------------------------------------
        # 6. Risk Management
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/risk/var?confidence=95&horizon=1D", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Risk Engine", "GET", "/risk/var", r.status_code, d, r.status_code == 200, f"VaR 95%: {r.json().get('var_value')}")

        t0 = time.perf_counter()
        r = client.post(f"{BASE_URL}/risk/monte-carlo", headers=headers, json={"num_simulations": 500, "horizon_days": 30})
        d = (time.perf_counter() - t0) * 1000
        record("Risk Engine", "POST", "/risk/monte-carlo", r.status_code, d, r.status_code in (200, 202), f"Job ID: {r.json().get('job_id')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/risk/stress-test?scenario=2008_crash", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Risk Engine", "GET", "/risk/stress-test", r.status_code, d, r.status_code == 200, f"Impact: {r.json().get('portfolio_impact')}")

        # -------------------------------------------------------------
        # 7. Sentiment Analysis (Requires Auth)
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/sentiment/market-overview", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Sentiment Engine", "GET", "/sentiment/market-overview", r.status_code, d, r.status_code == 200, f"Mood: {r.json().get('market_mood')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/sentiment/OGDC", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Sentiment Engine", "GET", "/sentiment/OGDC", r.status_code, d, r.status_code == 200, f"Score: {r.json().get('score')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/sentiment/OGDC/history", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Sentiment Engine", "GET", "/sentiment/OGDC/history", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/sentiment/OGDC/news", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Sentiment Engine", "GET", "/sentiment/OGDC/news", r.status_code, d, r.status_code == 200)

        # -------------------------------------------------------------
        # 8. AI Price Forecasting
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/forecast/OGDC?horizon=1D", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("AI Forecast", "GET", "/forecast/OGDC?horizon=1D", r.status_code, d, r.status_code == 200, f"Direction: {r.json().get('direction')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/forecast/OGDC?horizon=1W", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("AI Forecast", "GET", "/forecast/OGDC?horizon=1W", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/forecast/OGDC?horizon=1M", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("AI Forecast", "GET", "/forecast/OGDC?horizon=1M", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/forecast/OGDC/history", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("AI Forecast", "GET", "/forecast/OGDC/history", r.status_code, d, r.status_code in (200, 404))

        # -------------------------------------------------------------
        # 9. Portfolio & Trades
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/portfolio", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Portfolio & Trades", "GET", "/portfolio", r.status_code, d, r.status_code == 200, f"Value: PKR {r.json().get('portfolio_value')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/portfolio/holdings", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Portfolio & Trades", "GET", "/portfolio/holdings", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/portfolio/pnl", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Portfolio & Trades", "GET", "/portfolio/pnl", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/portfolio/allocation", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Portfolio & Trades", "GET", "/portfolio/allocation", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/portfolio/performance", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Portfolio & Trades", "GET", "/portfolio/performance", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/portfolio/transactions", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Portfolio & Trades", "GET", "/portfolio/transactions", r.status_code, d, r.status_code == 200)

        # -------------------------------------------------------------
        # 10. Events Calendar
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/events/calendar", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Events Calendar", "GET", "/events/calendar", r.status_code, d, r.status_code == 200, f"Events: {len(r.json().get('events', []))}")

        # -------------------------------------------------------------
        # 11. Shariah Compliance Engine
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/shariah/kmi30")
        d = (time.perf_counter() - t0) * 1000
        record("Shariah Engine", "GET", "/shariah/kmi30", r.status_code, d, r.status_code == 200, f"Constituents: {r.json().get('total_constituents')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/shariah/OGDC")
        d = (time.perf_counter() - t0) * 1000
        record("Shariah Engine", "GET", "/shariah/OGDC", r.status_code, d, r.status_code == 200, f"Compliant: {r.json().get('is_shariah_compliant')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/shariah/OGDC/criteria")
        d = (time.perf_counter() - t0) * 1000
        record("Shariah Engine", "GET", "/shariah/OGDC/criteria", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/shariah/SYS/purification?dividend_income=10000")
        d = (time.perf_counter() - t0) * 1000
        record("Shariah Engine", "GET", "/shariah/SYS/purification", r.status_code, d, r.status_code == 200, f"Purification: PKR {r.json().get('purification_amount')}")

        # -------------------------------------------------------------
        # 12. Alerts, Notifications & Push Devices
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/alerts", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Alerts & Devices", "GET", "/alerts", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/alerts/rules", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Alerts & Devices", "GET", "/alerts/rules", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/notifications", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Alerts & Devices", "GET", "/notifications", r.status_code, d, r.status_code == 200)

        # -------------------------------------------------------------
        # 13. Community & Social Network
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/community/me", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Community & Feed", "GET", "/community/me", r.status_code, d, r.status_code == 200, f"Published posts: {r.json().get('published_post_count')}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/community/feed?limit=5", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("Community & Feed", "GET", "/community/feed", r.status_code, d, r.status_code == 200, f"Feed items: {len(r.json().get('posts', []))}")

        # -------------------------------------------------------------
        # 14. Financial News & Sources
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/news?limit=5")
        d = (time.perf_counter() - t0) * 1000
        record("Financial News", "GET", "/news", r.status_code, d, r.status_code == 200, f"Articles: {len(r.json().get('items', []))}")

        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/news/sources")
        d = (time.perf_counter() - t0) * 1000
        record("Financial News", "GET", "/news/sources", r.status_code, d, r.status_code == 200, f"Sources: {len(r.json().get('sources', []))}")

        # -------------------------------------------------------------
        # 15. AI Assistant & Conversations
        # -------------------------------------------------------------
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/assistant/conversations", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record("AI Assistant", "GET", "/assistant/conversations", r.status_code, d, r.status_code == 200)

        t0 = time.perf_counter()
        r_conv = client.post(f"{BASE_URL}/assistant/conversations", headers=headers, json={"title": "Live Master Audit Chat"})
        d = (time.perf_counter() - t0) * 1000
        conv_id = r_conv.json().get("id") if r_conv.status_code == 201 else None
        record("AI Assistant", "POST", "/assistant/conversations", r_conv.status_code, d, r_conv.status_code == 201, f"Conv ID: {conv_id}")

        if conv_id:
            # Cleanup conversation
            client.delete(f"{BASE_URL}/assistant/conversations/{conv_id}", headers=headers)


def print_summary():
    print("\n" + "="*115)
    print(" LIVE AWS MASTER AUDIT EXECUTION SUMMARY")
    print("="*115)
    total_endpoints = len(results)
    passed_endpoints = sum(1 for r in results if r["passed"])
    failed_endpoints = total_endpoints - passed_endpoints
    avg_latency = sum(r["duration_ms"] for r in results) / total_endpoints if total_endpoints else 0

    print(f" TOTAL ENDPOINTS TESTED : {total_endpoints}")
    print(f" PASSED                 : {passed_endpoints}  ({passed_endpoints/total_endpoints*100:.1f}%)")
    print(f" FAILED                 : {failed_endpoints}")
    print(f" AVERAGE LATENCY        : {avg_latency:.1f}ms")
    print("="*115 + "\n")

    if failed_endpoints == 0:
        print(" ALL ENDPOINTS PASSED ON LIVE AWS DEPLOYMENT WITH ZERO ERRORS!\n")
    else:
        print(f" {failed_endpoints} ENDPOINTS FAILED. PLEASE CHECK LOGS ABOVE.\n")


if __name__ == "__main__":
    run_master_live_aws_audit()
    print_summary()
