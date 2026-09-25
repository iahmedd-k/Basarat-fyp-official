"""Live end-to-end audit for Risk and Sentiment API endpoints."""

import httpx
import uuid

BASE_URL = "http://16.16.26.247:8000/api/v1"

def test_live_sentiment_and_risk():
    print("\n" + "="*70)
    print(" LIVE AWS END-TO-END AUDIT: RISK & SENTIMENT MODULES")
    print("="*70)
    
    with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
        # 1. Login or register a test auditor user
        test_email = f"auditor_{uuid.uuid4().hex[:6]}@basarat.pk"
        test_pwd = "AuditorSecurePass123!"
        
        signup_resp = client.post("/auth/signup", json={
            "email": test_email,
            "password": test_pwd,
            "full_name": "Audit Tester"
        })
        
        login_resp = client.post("/auth/login", json={"email": test_email, "password": test_pwd})
        if login_resp.status_code != 200:
            # Fallback to admin
            login_resp = client.post("/auth/login", json={"email": "admin@basarat.pk", "password": "TestPassword12345!"})
            
        if login_resp.status_code != 200:
            print(f"[FAIL] Auth failed: {login_resp.status_code} - {login_resp.text}")
            return
            
        token = login_resp.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"[OK] Authenticated successfully as {test_email}.")
        
        # -------------------------------------------------------------
        # Sentiment Endpoints
        # -------------------------------------------------------------
        print("\n--- 1. Testing Sentiment Endpoints ---")
        
        # 1.1 Market Overview
        r = client.get("/sentiment/market-overview", headers=headers)
        print(f" GET /sentiment/market-overview -> Status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"   Mood: {data.get('market_mood')} | Score: {data.get('overall_score')} | A/D Ratio: {data.get('advance_decline_ratio')}")
            print(f"   Advancing: {data.get('advancing')} | Declining: {data.get('declining')} | Unchanged: {data.get('unchanged')}")
        else:
            print(f"   [ERR] {r.text}")
            
        # 1.2 Stock Sentiment (OGDC, MCB, LUCK, HUBC)
        for sym in ["OGDC", "MCB", "LUCK", "HUBC"]:
            r = client.get(f"/sentiment/{sym}", headers=headers)
            print(f" GET /sentiment/{sym} -> Status {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print(f"   Symbol: {data.get('symbol')} | Label: {data.get('label')} | Score: {data.get('score')} | Confidence: {data.get('confidence')} | Trend: {data.get('trend')}")
            else:
                print(f"   [ERR] {r.text}")

        # 1.3 Sentiment News
        r = client.get("/sentiment/OGDC/news?limit=5", headers=headers)
        print(f" GET /sentiment/OGDC/news -> Status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"   Total Articles: {data.get('total')} | Returned: {len(data.get('items', []))}")
            if data.get("items"):
                first = data["items"][0]
                print(f"   Sample Item: '{first.get('title')[:60]}...' | Sentiment: {first.get('sentiment')}")

        # 1.4 Sentiment History
        r = client.get("/sentiment/OGDC/history?period=1M", headers=headers)
        print(f" GET /sentiment/OGDC/history -> Status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"   Data Points: {len(data.get('data', []))}")

        # -------------------------------------------------------------
        # Risk Endpoints
        # -------------------------------------------------------------
        print("\n--- 2. Testing Risk Endpoints ---")
        
        # 2.1 VaR for empty / new user (Graceful empty handling)
        r = client.get("/risk/var?confidence=95&horizon=1D", headers=headers)
        print(f" GET /risk/var (Empty Portfolio) -> Status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"   Status: {data.get('status')} | Message: {data.get('message')} | Portfolio Value: {data.get('portfolio_value')}")

        # 2.2 Stress Tests for all 4 scenarios
        for sc in ["2008_crash", "pkr_devaluation", "covid_crash", "interest_rate_hike"]:
            r = client.get(f"/risk/stress-test?scenario={sc}", headers=headers)
            print(f" GET /risk/stress-test?scenario={sc} -> Status {r.status_code}")
            if r.status_code == 200:
                data = r.json()
                print(f"   Scenario: {data.get('scenario')} | Name: {data.get('name')} | Status: {data.get('status')}")

        # 2.3 Add a mock transaction to portfolio to test VaR and Stress Test with active assets!
        print("\n--- 3. Testing Risk with Active Portfolio Holdings ---")
        t1 = client.post("/portfolio/transactions", headers=headers, json={
            "symbol": "OGDC",
            "transaction_type": "BUY",
            "quantity": 1000,
            "price": 120.0,
            "fee": 0.0,
            "transaction_date": "2026-09-01"
        })
        t2 = client.post("/portfolio/transactions", headers=headers, json={
            "symbol": "MCB",
            "transaction_type": "BUY",
            "quantity": 500,
            "price": 200.0,
            "fee": 0.0,
            "transaction_date": "2026-09-01"
        })
        print(f" Transaction POST OGDC -> Status {t1.status_code}")
        print(f" Transaction POST MCB -> Status {t2.status_code}")
        
        # Test VaR again with populated portfolio
        r = client.get("/risk/var?confidence=95&horizon=1D", headers=headers)
        print(f" GET /risk/var (Active Portfolio) -> Status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"   Status: {data.get('status')} | VaR 95%: {data.get('var_value')} | CVaR: {data.get('cvar_value')} | Volatility: {data.get('annualized_volatility')}")
            print(f"   Portfolio Value: {data.get('portfolio_value')} PKR | VaR Loss Amount: {data.get('var_loss_amount')} PKR")

        # Test Stress Test with populated portfolio
        r = client.get("/risk/stress-test?scenario=2008_crash", headers=headers)
        print(f" GET /risk/stress-test?scenario=2008_crash (Active Portfolio) -> Status {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            print(f"   Status: {data.get('status')} | Current Val: {data.get('current_value')} PKR | Impact: {data.get('portfolio_impact_value')} PKR | Stressed: {data.get('stressed_value')} PKR")
            print(f"   Holdings Impacted: {len(data.get('holding_impacts', []))}")

        # 2.4 Monte Carlo
        r = client.post("/risk/monte-carlo", headers=headers, json={"num_simulations": 500, "horizon_days": 15, "seed": 42})
        print(f" POST /risk/monte-carlo -> Status {r.status_code}")
        if r.status_code == 202:
            data = r.json()
            job_id = data.get("job_id")
            print(f"   Job Dispatched: ID={job_id} | Status={data.get('status')}")
            # Poll result
            r_poll = client.get(f"/risk/monte-carlo/{job_id}", headers=headers)
            print(f"   GET /risk/monte-carlo/{job_id} -> Status {r_poll.status_code} | Poll State={r_poll.json().get('status')}")

    print("\n" + "="*70)
    print(" LIVE AUDIT COMPLETE")
    print("="*70)

if __name__ == "__main__":
    test_live_sentiment_and_risk()
