"""
Live Docker Route Verification Suite
Tests all core production API endpoints against the live Docker container:
  - System Health & Swagger Docs
  - Authentication (Login, Profile, 3-Step Forgot Password)
  - ML Price Forecasting & Sequence Engine
  - Recommendations & Stock Screening
  - FinBERT Sentiment & Live News
  - PSX Shariah Compliance
"""

import httpx

BASE_URL = "http://localhost:8000"

def run_verification():
    print("=" * 75)
    print("BASARAT BACKEND: LIVE DOCKER ROUTE VERIFICATION")
    print("=" * 75)

    client = httpx.Client(base_url=BASE_URL, timeout=30.0)
    results = []

    def check(name, method, url, expected_status=[200], headers=None, json_data=None):
        try:
            if method == "GET":
                resp = client.get(url, headers=headers)
            elif method == "POST":
                resp = client.post(url, headers=headers, json=json_data)
            
            passed = resp.status_code in expected_status
            tag = "[PASS]" if passed else "[FAIL]"
            status_text = f"HTTP {resp.status_code}"
            detail = ""
            if not passed:
                detail = f" | Detail: {resp.text[:120]}"
            print(f"  {tag:<6} {name:<50} {status_text:<10}{detail}")
            results.append((name, passed, resp))
            return resp
        except Exception as e:
            print(f"  [ERR]  {name:<50} CONN_ERROR | {e}")
            results.append((name, False, None))
            return None

    # 1. Health & OpenAPI Specification
    print("\n--- 1. Health & OpenAPI Specification ---")
    check("System Health Endpoint", "GET", "/api/v1/health")
    check("OpenAPI JSON Schema", "GET", "/api/v1/openapi.json")

    # 2. Authentication & Profile
    print("\n--- 2. Authentication & User Profile ---")
    email = "admin@basarat.pk"
    pwd = "AdminPassword123!"
    
    login_resp = check("Auth: Admin Login (/auth/login)", "POST", "/api/v1/auth/login",
                       json_data={"email": email, "password": pwd})
    
    auth_headers = {}
    if login_resp and login_resp.status_code == 200:
        token = login_resp.json()["access_token"]
        auth_headers = {"Authorization": f"Bearer {token}"}
        check("Auth: Get Current User (/auth/me)", "GET", "/api/v1/auth/me", headers=auth_headers)
        check("Users: Get Full Profile (/users/me)", "GET", "/api/v1/users/me", headers=auth_headers)

    # 3. 3-Step Password Reset Flow
    print("\n--- 3. 3-Step Password Reset Flow ---")
    check("Forgot Password: Step 1 (Request OTP)", "POST", "/api/v1/auth/forgot-password",
          json_data={"email": email})
    check("Forgot Password: Step 2 (Verify OTP invalid check)", "POST", "/api/v1/auth/verify-reset-code",
          expected_status=[400], json_data={"email": email, "code": "000000"})

    # 4. ML Forecasting Endpoints
    print("\n--- 4. ML Price Forecasting Engine ---")
    symbols = ["LUCK", "OGDC", "SYS", "ENGROH", "HUBC"]
    for sym in symbols:
        check(f"ML Forecast: {sym} (1D horizon)", "GET", f"/api/v1/forecast/{sym}?horizon=1D", headers=auth_headers)
        check(f"ML Forecast History: {sym}", "GET", f"/api/v1/forecast/{sym}/history", headers=auth_headers)

    # 5. Recommendations & Stocks
    print("\n--- 5. Alpha Recommendations & Stock Screener ---")
    check("AI Recommendations: Top Stocks", "GET", "/api/v1/recommendations", headers=auth_headers)
    check("Stocks: Search Ticker (LUCK)", "GET", "/api/v1/stocks/search?q=LUCK", headers=auth_headers)
    check("Stocks: Price History (LUCK)", "GET", "/api/v1/stocks/LUCK/price-history", headers=auth_headers)
    check("Stocks: Technical Indicators (LUCK)", "GET", "/api/v1/stocks/LUCK/technical-indicators", headers=auth_headers)

    # 6. Sentiment & News NLP
    print("\n--- 6. FinBERT Sentiment & Live News ---")
    check("Sentiment: Market Overview", "GET", "/api/v1/sentiment/market-overview", headers=auth_headers)
    check("Sentiment: Stock Sentiment (LUCK)", "GET", "/api/v1/sentiment/LUCK", headers=auth_headers)
    check("News: Live Feed & Analysis", "GET", "/api/v1/news", headers=auth_headers)

    # 7. Shariah Compliance
    print("\n--- 7. PSX Shariah Compliance Screener ---")
    check("Shariah: KMI-30 Index Constituents", "GET", "/api/v1/shariah/kmi30", headers=auth_headers)
    check("Shariah: Stock Screening (LUCK)", "GET", "/api/v1/shariah/LUCK", headers=auth_headers)

    # Summary
    passed_cnt = sum(1 for _, p, _ in results if p)
    total_cnt = len(results)
    print("\n" + "=" * 75)
    print(f"VERIFICATION RESULTS: {passed_cnt}/{total_cnt} CHECKS PASSED ({(passed_cnt/total_cnt)*100:.1f}%)")
    print("=" * 75)

if __name__ == "__main__":
    run_verification()
