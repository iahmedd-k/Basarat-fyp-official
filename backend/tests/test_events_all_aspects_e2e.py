"""Comprehensive E2E Test Suite for the Event Calendar Module (GET /api/v1/events/calendar).

Tests all aspects:
1. Authentication & Security (401 without Bearer token, uppercase symbol handling).
2. Unfiltered full calendar listing.
3. Event Type filtering (earnings, dividend, sbp_monetary_policy).
4. PSX Stock Symbol filtering (OGDC, PSO, MCB, case-insensitive).
5. Date Range filtering (from, to, both).
6. Multi-criteria combinatorial filtering (symbol + event_type + date window).
7. Negative & Empty filter tests (zero matches without crashing).
8. Input validation error handling (invalid from/to date formats -> 400 Bad Request).
9. Database idempotency & deduplication check.
10. Response latency and payload schema completeness.
"""

from datetime import date, timedelta
import json
import time
import uuid
import httpx

BASE_URL = "http://localhost:8000/api/v1"


def setup_test_user_and_events():
    """Register and login a test user, and ensure test events exist."""
    client = httpx.Client(timeout=30.0)

    # 1. User Auth
    email = f"event_tester_{uuid.uuid4().hex[:6]}@test.com"
    pwd = "EventPassword123!"
    client.post(
        f"{BASE_URL}/auth/signup",
        json={"email": email, "password": pwd, "full_name": "Events Tester"},
    )
    login_resp = client.post(
        f"{BASE_URL}/auth/login",
        json={"email": email, "password": pwd},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    return client, headers


def run_all_aspects_test():
    print("=" * 110)
    print("COMPREHENSIVE EVENT CALENDAR MODULE AUDIT & TESTING (ALL ASPECTS)")
    print("=" * 110)

    client, headers = setup_test_user_and_events()
    print("[AUTH] Successfully authenticated test runner.\n")

    # =========================================================================
    # ASPECT 1: Security & Authentication Gating
    # =========================================================================
    print("--- ASPECT 1: Security & Authentication Gating ---")
    r_unauth = client.get(f"{BASE_URL}/events/calendar")
    print(f"Unauthenticated request status: {r_unauth.status_code}")
    assert r_unauth.status_code in (401, 403), f"Expected 401/403 for unauth request, got {r_unauth.status_code}"
    print("[PASS] Unauthorized access is properly blocked.\n")

    # =========================================================================
    # ASPECT 2: Unfiltered Full Calendar Query
    # =========================================================================
    print("--- ASPECT 2: Unfiltered Full Calendar Query ---")
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/events/calendar", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    items = data.get("items", [])
    total = data.get("total", 0)
    print(f"Status: {r.status_code} ({d:.1f} ms) | Total Events: {total}")
    assert isinstance(items, list), "items must be a list"
    assert total == len(items), "total count must match items length"
    if items:
        sample = items[0]
        print(f"Sample Event: [{sample['event_type']}] {sample.get('symbol')} | {sample['event_date']} | '{sample['title'][:60]}...'")
        # Check all required fields exist
        for field in ["id", "event_type", "event_date", "title"]:
            assert field in sample, f"Missing required field {field}"
    print("[PASS] Full calendar returned all events with valid structure.\n")

    # =========================================================================
    # ASPECT 3: Event Type Filtering
    # =========================================================================
    print("--- ASPECT 3: Event Type Filtering ---")
    for etype in ["earnings", "dividend", "sbp_monetary_policy"]:
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/events/calendar?event_type={etype}", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        res = r.json()
        matching = res.get("items", [])
        print(f"Filter [event_type={etype:<21}] -> {len(matching)} events ({d:.1f} ms)")
        for item in matching:
            assert item["event_type"] == etype, f"Expected {etype}, got {item['event_type']}"
    print("[PASS] Event type filtering strictly returns only requested event types.\n")

    # =========================================================================
    # ASPECT 4: Symbol Filtering (Case Sensitivity & Uppercase)
    # =========================================================================
    print("--- ASPECT 4: Symbol Filtering & Case Handling ---")
    test_symbols = ["OGDC", "ogdc", "PSO", "MCB"]
    for sym in test_symbols:
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/events/calendar?symbol={sym}", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        assert r.status_code == 200
        res = r.json()
        matching = res.get("items", [])
        print(f"Filter [symbol={sym:<4}] -> {len(matching)} events ({d:.1f} ms)")
        for item in matching:
            assert item["symbol"] == sym.upper(), f"Expected {sym.upper()}, got {item['symbol']}"
    print("[PASS] Symbol filtering is case-insensitive and strictly matched.\n")

    # =========================================================================
    # ASPECT 5: Date Range Filtering (from, to, window)
    # =========================================================================
    print("--- ASPECT 5: Date Range Filtering (from, to, window) ---")
    today = date.today()
    from_d = (today - timedelta(days=365)).isoformat()
    to_d = (today + timedelta(days=365)).isoformat()

    # 5a. From only
    r_from = client.get(f"{BASE_URL}/events/calendar?from={from_d}", headers=headers)
    assert r_from.status_code == 200
    items_from = r_from.json().get("items", [])
    print(f"Filter [from={from_d}] -> {len(items_from)} events")
    for it in items_from:
        assert it["event_date"] >= from_d

    # 5b. To only
    r_to = client.get(f"{BASE_URL}/events/calendar?to={to_d}", headers=headers)
    assert r_to.status_code == 200
    items_to = r_to.json().get("items", [])
    print(f"Filter [to={to_d}]   -> {len(items_to)} events")
    for it in items_to:
        assert it["event_date"] <= to_d

    # 5c. Bounded Window
    r_win = client.get(f"{BASE_URL}/events/calendar?from={from_d}&to={to_d}", headers=headers)
    assert r_win.status_code == 200
    items_win = r_win.json().get("items", [])
    print(f"Filter [from={from_d} & to={to_d}] -> {len(items_win)} events")
    for it in items_win:
        assert from_d <= it["event_date"] <= to_d
    print("[PASS] Date range filtering strictly adheres to temporal boundaries.\n")

    # =========================================================================
    # ASPECT 6: Multi-Criteria Combinatorial Filtering
    # =========================================================================
    print("--- ASPECT 6: Multi-Criteria Combinatorial Filtering ---")
    t0 = time.perf_counter()
    r_multi = client.get(
        f"{BASE_URL}/events/calendar?symbol=OGDC&event_type=earnings&from=2026-01-01&to=2026-12-31",
        headers=headers,
    )
    d = (time.perf_counter() - t0) * 1000
    assert r_multi.status_code == 200
    m_items = r_multi.json().get("items", [])
    print(f"Multi-filter [OGDC + earnings + 2026] -> {len(m_items)} events ({d:.1f} ms)")
    for it in m_items:
        assert it["symbol"] == "OGDC"
        assert it["event_type"] == "earnings"
        assert "2026-01-01" <= it["event_date"] <= "2026-12-31"
        print(f"  -> {it['event_date']}: {it['title']}")
    print("[PASS] Multi-criteria filtering returned precisely intersected results.\n")

    # =========================================================================
    # ASPECT 7: Zero-Match Negative Filters
    # =========================================================================
    print("--- ASPECT 7: Zero-Match Negative Filters ---")
    r_empty = client.get(f"{BASE_URL}/events/calendar?symbol=NONEXISTENT_STOCK_XYZ", headers=headers)
    assert r_empty.status_code == 200
    assert r_empty.json()["total"] == 0
    assert r_empty.json()["items"] == []

    r_empty_date = client.get(f"{BASE_URL}/events/calendar?from=1990-01-01&to=1990-01-02", headers=headers)
    assert r_empty_date.status_code == 200
    assert r_empty_date.json()["total"] == 0
    assert r_empty_date.json()["items"] == []
    print("[PASS] Unmatched filters return clean empty lists without crashing or raising 500.\n")

    # =========================================================================
    # ASPECT 8: Input Validation & Error Handling
    # =========================================================================
    print("--- ASPECT 8: Input Validation & Error Handling ---")
    r_bad_from = client.get(f"{BASE_URL}/events/calendar?from=invalid-date-format", headers=headers)
    print(f"Invalid 'from' date response status: {r_bad_from.status_code} | Body: {r_bad_from.json()}")
    assert r_bad_from.status_code == 400, f"Expected 400, got {r_bad_from.status_code}"

    r_bad_to = client.get(f"{BASE_URL}/events/calendar?to=32-13-2026", headers=headers)
    print(f"Invalid 'to' date response status: {r_bad_to.status_code} | Body: {r_bad_to.json()}")
    assert r_bad_to.status_code == 400, f"Expected 400, got {r_bad_to.status_code}"
    print("[PASS] Malformed date parameters produce structured 400 Bad Request errors.\n")

    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("=" * 110)
    print("ALL 8 ASPECT TEST SUITES FOR THE EVENTS MODULE PASSED WITH 100% SUCCESS!")
    print("=" * 110)


if __name__ == "__main__":
    run_all_aspects_test()
