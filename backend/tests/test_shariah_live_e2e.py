import json
import time
import uuid
import httpx

BASE_URL = "http://localhost:8000/api/v1"


def test_shariah_endpoints():
    print("=" * 100)
    print("STARTING COMPREHENSIVE SHARIAH MODULE AUDIT (STEP BY STEP)")
    print("=" * 100)

    client = httpx.Client(timeout=30.0)

    # 1. User Registration & Login
    email = f"shariah_tester_{uuid.uuid4().hex[:6]}@test.com"
    pwd = "ShariahPassword123!"
    client.post(
        f"{BASE_URL}/auth/signup",
        json={"email": email, "password": pwd, "full_name": "Shariah Tester"},
    )
    login_resp = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": pwd},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    print(f"[AUTH OK] Logged in successfully: {email}")

    # 2. Test GET /shariah/kmi30
    print("\n" + "=" * 60)
    print("1. Testing GET /api/v1/shariah/kmi30")
    print("=" * 60)
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/shariah/kmi30", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    kmi_data = r.json()
    constituents = kmi_data.get("constituents", [])
    print(f"Status Code: {r.status_code} | Latency: {d:.1f}ms")
    print(f"Index Name:  {kmi_data.get('index')}")
    print(f"Total Constituents: {len(constituents)}")
    assert len(constituents) >= 30, f"Expected at least 30 constituents, got {len(constituents)}"
    
    symbols = [c.get("symbol") for c in constituents]
    print(f"Constituent Symbols: {symbols}")
    sample = constituents[0]
    print(f"Sample Constituent Record ({sample.get('symbol')}):")
    print(f"  -> Name: {sample.get('name')}")
    print(f"  -> Sector: {sample.get('sector')}")
    print(f"  -> Current Price: PKR {sample.get('current')}")
    print(f"  -> Is Shariah Compliant: {sample.get('is_shariah_compliant')}")
    print(f"  -> Purification Rate: {sample.get('purification_rate') * 100:.2f}%")

    # 3. Test GET /shariah/{symbol} for Compliant Stocks
    print("\n" + "=" * 60)
    print("2. Testing GET /api/v1/shariah/{symbol} for Compliant Stocks")
    print("=" * 60)
    compliant_test_stocks = ["OGDC", "SYS", "LUCK", "MEBL", "EFERT", "HUBC"]
    for sym in compliant_test_stocks:
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/shariah/{sym}", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200, f"Expected 200 for {sym}, got {r.status_code}: {r.text}"
        data = r.json()
        print(f"[{sym}] {d:5.1f}ms | Compliant: {data.get('is_shariah_compliant')} | Sector: {data.get('sector')} | Method: {data.get('screening_method')}")
        print(f"       Summary: {data.get('compliance_summary')}")
        assert data.get("is_shariah_compliant") is True
        assert data.get("screening_method") is not None

    # 4. Test GET /shariah/{symbol} for Non-Compliant Stocks
    print("\n" + "=" * 60)
    print("3. Testing GET /api/v1/shariah/{symbol} for Non-Compliant Stocks")
    print("=" * 60)
    non_compliant_test_stocks = ["HBL", "UBL", "MCB", "PAKT"]
    for sym in non_compliant_test_stocks:
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/shariah/{sym}", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200, f"Expected 200 for {sym}, got {r.status_code}: {r.text}"
        data = r.json()
        print(f"[{sym}] {d:5.1f}ms | Compliant: {data.get('is_shariah_compliant')} | Summary: {data.get('compliance_summary')}")
        assert data.get("is_shariah_compliant") is False

    # 5. Test GET /shariah/{symbol}/criteria (Criteria Breakdown)
    print("\n" + "=" * 60)
    print("4. Testing GET /api/v1/shariah/{symbol}/criteria")
    print("=" * 60)
    
    # Check OGDC Criteria
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/shariah/OGDC/criteria", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    data = r.json()
    print(f"[OGDC Criteria] {d:.1f}ms | Overall Compliant: {data.get('is_shariah_compliant')}")
    assert len(data.get("criteria", [])) == 6, f"Expected 6 criteria, got {len(data.get('criteria', []))}"
    for crit in data.get("criteria", []):
        mark = "PASS" if crit["passed"] else "FAIL"
        print(f"  [{mark}] {crit['name']:40} | Value: {crit['value']:<6} | Threshold: {crit['threshold']:<6} | {crit.get('description', '')}")
        assert crit["passed"] is True, f"OGDC should pass {crit['name']}"

    # Check HBL Criteria (Failing criteria)
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/shariah/HBL/criteria", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200
    data = r.json()
    print(f"\n[HBL Criteria] {d:.1f}ms | Overall Compliant: {data.get('is_shariah_compliant')}")
    assert data.get("is_shariah_compliant") is False
    for crit in data.get("criteria", []):
        mark = "PASS" if crit["passed"] else "FAIL"
        print(f"  [{mark}] {crit['name']:40} | Value: {crit['value']:<6} | Threshold: {crit['threshold']:<6}")

    # 6. Test GET /shariah/{symbol}/purification
    print("\n" + "=" * 60)
    print("5. Testing GET /api/v1/shariah/{symbol}/purification")
    print("=" * 60)
    
    purif_cases = [
        {"symbol": "OGDC", "qty": 1000, "val": 150000.0, "expected_rate": 0.012, "expected_amount": 1800.0},
        {"symbol": "SYS", "qty": 500, "val": 200000.0, "expected_rate": 0.015, "expected_amount": 3000.0},
        {"symbol": "LUCK", "qty": 200, "val": 160000.0, "expected_rate": 0.008, "expected_amount": 1280.0},
        {"symbol": "MEBL", "qty": 1000, "val": 250000.0, "expected_rate": 0.000, "expected_amount": 0.0},
    ]

    for case in purif_cases:
        sym = case["symbol"]
        qty = case["qty"]
        val = case["val"]
        t0 = time.perf_counter()
        r = client.get(
            f"{BASE_URL}/shariah/{sym}/purification?holding_qty={qty}&holding_value={val}",
            headers=headers,
        )
        d = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200, f"Expected 200 for {sym}, got {r.status_code}: {r.text}"
        pdata = r.json()
        print(f"[{sym}] {d:5.1f}ms | Value: PKR {pdata['holding_value']:,.2f} | Rate: {pdata['purification_rate']*100:.2f}% | Purification Amount: PKR {pdata['purification_amount']:,.2f}")
        print(f"       Advice: {pdata.get('notes')}")
        assert pdata["holding_qty"] == qty
        assert pdata["holding_value"] == val
        assert pdata["purification_amount"] == case["expected_amount"]
        assert pdata["purification_rate"] == case["expected_rate"]

    print("\n" + "=" * 100)
    print("ALL SHARIAH MODULE ENDPOINTS PASSED AUDIT WITH 100% SUCCESS!")
    print("=" * 100)


if __name__ == "__main__":
    test_shariah_endpoints()
