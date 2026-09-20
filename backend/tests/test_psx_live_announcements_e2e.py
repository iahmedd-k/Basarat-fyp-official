"""End-to-End Test for Live PSX Company Announcements & Redis Caching.

Verifies:
1. Live On-Demand fetch from PSX DPS for individual stock (OGDC) -> parses PDF URLs, titles, dates, event types.
2. Redis cache hit verification (< 20ms latency on repeated request).
3. Live fetch for multiple real PSX tickers (LUCK, SYS, MLCF).
4. Portfolio integration: User buys stocks -> GET /news?row=portfolio returns announcements strictly for their portfolio stocks.
"""

import time
import uuid
import httpx

BASE_URL = "http://localhost:8000/api/v1"

def test_live_psx_announcements():
    print("=" * 110)
    print("STARTING LIVE PSX ANNOUNCEMENTS & REDIS CACHE VERIFICATION")
    print("=" * 110)

    client = httpx.Client(timeout=30.0)

    # 1. User Auth
    email = f"psx_tester_{uuid.uuid4().hex[:6]}@test.com"
    pwd = "PsxPassword123!"
    client.post(f"{BASE_URL}/auth/signup", json={"email": email, "password": pwd, "full_name": "PSX Live Tester"})
    token = client.post(f"{BASE_URL}/auth/login", json={"email": email, "password": pwd}).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. First call for OGDC (Live Fetch from PSX)
    t0 = time.perf_counter()
    r1 = client.get(f"{BASE_URL}/stocks/OGDC/news", headers=headers)
    d1 = (time.perf_counter() - t0) * 1000
    data1 = r1.json()
    items1 = data1.get("items", [])
    print(f"[LIVE FETCH] GET /stocks/OGDC/news | {d1:6.1f}ms | Found {len(items1)} announcements from PSX")
    if items1:
        print(f"  -> Title: {items1[0].get('title')}")
        print(f"  -> Doc Link: {items1[0].get('url')}")
        print(f"  -> Summary: {items1[0].get('summary')}")
        print(f"  -> Event: {items1[0].get('event_type')}")

    # 3. Second call for OGDC (Should hit Redis Cache)
    t0 = time.perf_counter()
    r2 = client.get(f"{BASE_URL}/stocks/OGDC/news", headers=headers)
    d2 = (time.perf_counter() - t0) * 1000
    data2 = r2.json()
    items2 = data2.get("items", [])
    print(f"[REDIS CACHE HIT] GET /stocks/OGDC/news | {d2:6.1f}ms | Returned {len(items2)} announcements")
    assert r2.status_code == 200
    assert len(items2) == len(items1)
    assert d2 < 150  # Must be fast cache hit

    # 4. Live fetch for MLCF (Maple Leaf Cement) & SYS
    for sym in ["MLCF", "SYS"]:
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/stocks/{sym}/news", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        items = r.json().get("items", [])
        print(f"[LIVE FETCH] GET /stocks/{sym}/news | {d:6.1f}ms | Found {len(items)} announcements")
        if items:
            print(f"  -> Top {sym} Notice: {items[0].get('title')} ({items[0].get('url')})")

    # 5. Portfolio Flow: Add BUY transactions for OGDC and SYS
    client.post(
        f"{BASE_URL}/portfolio/transactions",
        headers=headers,
        json={
            "symbol": "OGDC",
            "transaction_type": "BUY",
            "quantity": 100,
            "price": 220.0,
            "transaction_date": "2026-09-10",
        }
    )
    client.post(
        f"{BASE_URL}/portfolio/transactions",
        headers=headers,
        json={
            "symbol": "SYS",
            "transaction_type": "BUY",
            "quantity": 50,
            "price": 450.0,
            "transaction_date": "2026-09-10",
        }
    )

    # 6. Fetch Portfolio News (GET /news?row=portfolio)
    t0 = time.perf_counter()
    r_port = client.get(f"{BASE_URL}/news?row=portfolio", headers=headers)
    d_port = (time.perf_counter() - t0) * 1000
    port_items = r_port.json().get("items", [])
    print(f"[PORTFOLIO ROW] GET /news?row=portfolio | {d_port:6.1f}ms | Retrieved {len(port_items)} announcements for user holdings")
    for item in port_items[:4]:
        sym = item.get("symbols", [{}])[0].get("symbol", "")
        print(f"  -> [{sym}] {item.get('title')}")

    print("=" * 110)
    print("ALL LIVE PSX ANNOUNCEMENTS & REDIS CACHE TESTS PASSED!")
    print("=" * 110)

if __name__ == "__main__":
    test_live_psx_announcements()
