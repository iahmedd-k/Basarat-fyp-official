"""Comprehensive E2E Swagger API Audit & Benchmarking Suite.

Executes a complete, realistic user journey across all API modules:
1. System & Health Probes (Live & Ready)
2. Auth & Unified User Investment Profile (Signup, Login, Unified Options, POST profile, GET profile, PATCH profile)
3. Market Overview, Indices & Gainers/Losers
4. Stock Search, Price History, Technical Indicators, Fundamentals
5. Portfolio Management (BUY, SELL, Completed-Trade, Holdings, P&L, Allocation, Performance, Transactions)
6. Risk Analytics (VaR/CVaR, Monte Carlo Simulation with polling, Stress Testing)
7. ML Forecasting & Multi-Strategy Recommendations
8. Market & Stock Sentiment Analysis
9. News & Financial Events Calendar
10. Shariah Compliance Screening
11. Alert Creation, Monitoring & Notifications

Measures and records latency (ms), HTTP status codes, and payload correctness.
"""

import time
import uuid
import httpx
import json

BASE_URL = "http://localhost:8000/api/v1"
HEALTH_URL = "http://localhost:8000/health"
ROOT_URL = "http://localhost:8000/"

results = []

def record(module: str, endpoint: str, method: str, status_code: int, duration_ms: float, passed: bool, notes: str = "", error_body: str = ""):
    results.append({
        "module": module,
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "passed": passed,
        "notes": notes,
    })
    status_sym = "PASS" if passed else "FAIL"
    err_snippet = f" | ERR: {error_body[:100]}" if (not passed and error_body) else ""
    print(f"[{status_sym}] [{module:15}] {method:6} {endpoint:45} | {duration_ms:6.1f}ms | HTTP {status_code} | {notes}{err_snippet}")


def run_audit():
    print("=" * 110)
    print("STARTING FULL BASARAT API ENDPOINT AUDIT & LATENCY BENCHMARK")
    print("=" * 110)
    
    client = httpx.Client(timeout=60.0)
    
    # ── 0. System & Health ──────────────────────────────────────────────────
    t0 = time.perf_counter()
    r = client.get(ROOT_URL)
    d = (time.perf_counter() - t0) * 1000
    record("System", "/", "GET", r.status_code, d, r.status_code == 200, f"status={r.json().get('status')}", r.text)

    t0 = time.perf_counter()
    r = client.get(HEALTH_URL)
    d = (time.perf_counter() - t0) * 1000
    record("Health", "/health", "GET", r.status_code, d, r.status_code == 200, f"status={r.json().get('status')}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{HEALTH_URL}/ready")
    d = (time.perf_counter() - t0) * 1000
    record("Health", "/health/ready", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # ── 1. Auth & Unified User Investment Profile ───────────────────────────
    test_user_email = f"audit_user_{uuid.uuid4().hex[:6]}@test.com"
    test_user_password = "AuditPassword123!"
    
    # Signup
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/auth/signup", json={
        "email": test_user_email,
        "password": test_user_password,
        "full_name": "Swagger Audit Tester",
    })
    d = (time.perf_counter() - t0) * 1000
    record("Auth", "/auth/signup", "POST", r.status_code, d, r.status_code == 201, "", r.text)

    # Login
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/auth/login", json={
        "email": test_user_email,
        "password": test_user_password,
    })
    d = (time.perf_counter() - t0) * 1000
    login_data = r.json()
    token = login_data.get("access_token")
    headers = {"Authorization": f"Bearer {token}"}
    record("Auth", "/auth/login", "POST", r.status_code, d, r.status_code == 200 and bool(token), "", r.text)

    # Investment Profile Options
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/users/investment-profile/options", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Users", "/users/investment-profile/options", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # Update Profile (POST)
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/users/me", headers=headers, json={
        "full_name": "Audit Trader Pro",
        "risk_tolerance": "moderate",
        "sector_preferences": ["Technology", "Oil & Gas"],
        "investment_horizon": "medium_term",
    })
    d = (time.perf_counter() - t0) * 1000
    record("Users", "/users/me", "POST", r.status_code, d, r.status_code == 200, "", r.text)

    # Get Unified Profile (GET)
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/users/me", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Users", "/users/me", "GET", r.status_code, d, r.status_code == 200, f"name={r.json().get('full_name')}", r.text)

    # Patch Profile (PATCH)
    t0 = time.perf_counter()
    r = client.patch(f"{BASE_URL}/users/me", headers=headers, json={
        "risk_tolerance": "aggressive",
    })
    d = (time.perf_counter() - t0) * 1000
    record("Users", "/users/me", "PATCH", r.status_code, d, r.status_code == 200, "", r.text)

    # ── 2. Market Data ──────────────────────────────────────────────────────
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/market/indices", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Market", "/market/indices", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/market/indices/kse-100", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Market", "/market/indices/kse-100", "GET", r.status_code, d, r.status_code == 200, f"count={len(r.json().get('constituents', []))}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/market/indices/kse-30", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Market", "/market/indices/kse-30", "GET", r.status_code, d, r.status_code == 200, f"count={len(r.json().get('constituents', []))}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/market/indices/kmi-30", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Market", "/market/indices/kmi-30", "GET", r.status_code, d, r.status_code == 200, f"count={len(r.json().get('constituents', []))}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/market/gainers?limit=5", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Market", "/market/gainers", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/market/losers?limit=5", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Market", "/market/losers", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/market/volume-spikes?limit=5", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Market", "/market/volume-spikes", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/market/sentiment-overview", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Market", "/market/sentiment-overview", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # ── 3. Stocks ───────────────────────────────────────────────────────────
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/stocks/search?q=OGDC", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Stocks", "/stocks/search?q=OGDC", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/stocks/OGDC/overview", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Stocks", "/stocks/OGDC/overview", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/stocks/OGDC/price-history?range=1M", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Stocks", "/stocks/OGDC/price-history", "GET", r.status_code, d, r.status_code == 200, f"bars={len(r.json().get('history', []))}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/stocks/OGDC/technical-indicators?period=14&limit=30", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    tech_data = r.json() if r.status_code == 200 else {}
    record("Stocks", "/stocks/OGDC/technical-indicators", "GET", r.status_code, d, r.status_code == 200, f"signal={tech_data.get('overall_signal')}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/stocks/OGDC/fundamentals", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Stocks", "/stocks/OGDC/fundamentals", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # ── 4. Portfolio Workflow ───────────────────────────────────────────────
    # Step A: BUY OGDC
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/portfolio/transactions", headers=headers, json={
        "symbol": "OGDC",
        "transaction_type": "BUY",
        "quantity": 200,
        "price": 220.00,
        "fee": 15.00,
        "transaction_date": "2026-09-01",
    })
    d = (time.perf_counter() - t0) * 1000
    buy_txn_id = r.json().get("id") if r.status_code == 201 else None
    record("Portfolio", "/portfolio/transactions (BUY)", "POST", r.status_code, d, r.status_code == 201, "", r.text)

    # Step B: SELL part of OGDC
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/portfolio/transactions", headers=headers, json={
        "symbol": "OGDC",
        "transaction_type": "SELL",
        "quantity": 50,
        "price": 240.00,
        "fee": 10.00,
        "transaction_date": "2026-09-05",
    })
    d = (time.perf_counter() - t0) * 1000
    record("Portfolio", "/portfolio/transactions (SELL)", "POST", r.status_code, d, r.status_code == 201, "", r.text)

    # Step C: Completed (Round-Trip) Past Trade for SYS
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/portfolio/transactions/completed-trade", headers=headers, json={
        "symbol": "SYS",
        "quantity": 100,
        "buy_price": 400.00,
        "buy_date": "2026-09-02",
        "buy_fee": 20.00,
        "sell_price": 460.00,
        "sell_date": "2026-09-10",
        "sell_fee": 20.00,
    })
    d = (time.perf_counter() - t0) * 1000
    comp_data = r.json() if r.status_code == 201 else {}
    record("Portfolio", "/portfolio/transactions/completed-trade", "POST", r.status_code, d, r.status_code == 201, f"P&L=Rs {comp_data.get('realized_pnl')}", r.text)

    # Portfolio Overview
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/portfolio", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Portfolio", "/portfolio", "GET", r.status_code, d, r.status_code == 200, f"value={r.json().get('summary', {}).get('current_value')}", r.text)

    # Holdings
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/portfolio/holdings", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Portfolio", "/portfolio/holdings", "GET", r.status_code, d, r.status_code == 200, f"active_count={len(r.json())}", r.text)

    # Holding Detail
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/portfolio/holdings/OGDC", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Portfolio", "/portfolio/holdings/OGDC", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # PnL Breakdown
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/portfolio/pnl", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Portfolio", "/portfolio/pnl", "GET", r.status_code, d, r.status_code == 200, f"realized={r.json().get('realized_pnl')}", r.text)

    # Allocation
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/portfolio/allocation", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Portfolio", "/portfolio/allocation", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # Performance Time Series
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/portfolio/performance?period=1M", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Portfolio", "/portfolio/performance", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # Transaction History
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/portfolio/transactions", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Portfolio", "/portfolio/transactions", "GET", r.status_code, d, r.status_code == 200, f"total={r.json().get('total')}", r.text)

    # ── 5. Risk Analytics ───────────────────────────────────────────────────
    # VaR / CVaR
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/risk/var?confidence=95&horizon=1D", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Risk", "/risk/var", "GET", r.status_code, d, r.status_code == 200, f"VaR={r.json().get('var_value')}", r.text)

    # Monte Carlo Async Start
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/risk/monte-carlo", headers=headers, json={
        "num_simulations": 1000,
        "horizon_days": 30
    })
    d = (time.perf_counter() - t0) * 1000
    mc_data = r.json() if r.status_code == 202 else {}
    job_id = mc_data.get("job_id")
    record("Risk", "/risk/monte-carlo", "POST", r.status_code, d, r.status_code == 202 and bool(job_id), f"job_id={job_id}", r.text)

    # Poll Monte Carlo result
    if job_id:
        poll_passed = False
        poll_duration = 0
        for _ in range(15):
            time.sleep(0.5)
            t0 = time.perf_counter()
            r_poll = client.get(f"{BASE_URL}/risk/monte-carlo/{job_id}", headers=headers)
            poll_duration = (time.perf_counter() - t0) * 1000
            if r_poll.status_code == 200 and r_poll.json().get("status") == "completed":
                poll_passed = True
                break
        record("Risk", f"/risk/monte-carlo/{job_id}", "GET", r_poll.status_code, poll_duration, poll_passed, f"status={r_poll.json().get('status')}", r_poll.text)

    # Stress Test
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/risk/stress-test?scenario=2008_crash", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Risk", "/risk/stress-test", "GET", r.status_code, d, r.status_code == 200, f"impact={r.json().get('portfolio_impact')}", r.text)

    # ── 6. Forecast & Recommendations ───────────────────────────────────────
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/forecast/OGDC?horizon=1D", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Forecast", "/forecast/OGDC", "GET", r.status_code, d, r.status_code == 200, f"dir={r.json().get('direction')}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/recommendations?risk_profile=moderate", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Recommendations", "/recommendations", "GET", r.status_code, d, r.status_code == 200, f"count={r.json().get('count')}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/recommendations/OGDC", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Recommendations", "/recommendations/OGDC", "GET", r.status_code, d, r.status_code == 200, f"signal={r.json().get('signal')}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/recommendations/OGDC/target-stop", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Recommendations", "/recommendations/OGDC/target-stop", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/recommendations/engine-weights", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Recommendations", "/recommendations/engine-weights", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    # ── 7. Sentiment Analysis ───────────────────────────────────────────────
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/sentiment/market-overview", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Sentiment", "/sentiment/market-overview", "GET", r.status_code, d, r.status_code == 200, f"mood={r.json().get('market_mood')}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/sentiment/OGDC", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Sentiment", "/sentiment/OGDC", "GET", r.status_code, d, r.status_code == 200, f"score={r.json().get('score')}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/sentiment/OGDC/history?period=1M", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Sentiment", "/sentiment/OGDC/history", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/sentiment/OGDC/news", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Sentiment", "/sentiment/OGDC/news", "GET", r.status_code, d, r.status_code == 200, f"count={r.json().get('total')}", r.text)

    # ── 8. News & Events Calendar ───────────────────────────────────────────
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/news", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("News", "/news", "GET", r.status_code, d, r.status_code == 200, f"total={len(r.json().get('items', []))}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/events/calendar", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Events", "/events/calendar", "GET", r.status_code, d, r.status_code == 200, f"events_count={r.json().get('total')}", r.text)

    # ── 9. Shariah Compliance ───────────────────────────────────────────────
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/shariah/OGDC", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Shariah", "/shariah/OGDC", "GET", r.status_code, d, r.status_code == 200, f"status={r.json().get('status')}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/shariah/universe", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Shariah", "/shariah/universe", "GET", r.status_code, d, r.status_code == 200, f"compliant={r.json().get('compliant_count')}", r.text)

    # ── 10. Alerts & Notifications ──────────────────────────────────────────
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/alerts/rules", headers=headers, json={
        "condition": "PRICE_ABOVE",
        "threshold": 260.0,
    })
    d = (time.perf_counter() - t0) * 1000
    rule_id = r.json().get("id") if r.status_code == 201 else None
    record("Alerts", "/alerts/rules", "POST", r.status_code, d, r.status_code == 201, f"rule_id={rule_id}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/alerts/rules", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Alerts", "/alerts/rules", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/alerts", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Alerts", "/alerts", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/notifications", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("Notifications", "/notifications", "GET", r.status_code, d, r.status_code == 200, "", r.text)

    print("=" * 110)
    total_calls = len(results)
    passed_calls = sum(1 for x in results if x["passed"])
    avg_duration = sum(x["duration_ms"] for x in results) / total_calls if total_calls > 0 else 0
    print(f"AUDIT SUMMARY: {passed_calls}/{total_calls} ENDPOINTS PASSED | AVERAGE RESPONSE TIME: {avg_duration:.1f}ms")
    print("=" * 110)

    return results

if __name__ == "__main__":
    run_audit()
