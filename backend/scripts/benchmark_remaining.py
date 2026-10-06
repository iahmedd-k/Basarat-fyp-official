import time
import requests
import json
import uuid

BASE_URL = "http://193.123.84.223:8000/api/v1"
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjMmI4YjAxMDQwYTA0NmM1OWNhNzA3MTc5YjZjYTljOSIsImV4cCI6MTc5MTI1Njk4MywidHlwZSI6ImFjY2VzcyIsImp0aSI6ImE3YTViZDYzMzZlNTRhZjM4YzMxMjA1NmQwMjUzMzE0In0.Hpp8WtgSf48PJhtyjSL-iyMTRxE7YePDByArzy2NVCI"

headers = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "Content-Type": "application/json",
}

def benchmark(name, method, url, data=None, req_headers=None):
    if req_headers is None:
        req_headers = headers
    
    # Run 1: Cold
    t0 = time.perf_counter()
    try:
        if method == "GET":
            r1 = requests.get(url, headers=req_headers, timeout=12)
        elif method == "POST":
            r1 = requests.post(url, headers=req_headers, json=data, timeout=12)
        elif method == "PATCH":
            r1 = requests.patch(url, headers=req_headers, json=data, timeout=12)
        elif method == "DELETE":
            r1 = requests.delete(url, headers=req_headers, timeout=12)
        t1 = time.perf_counter()
        cold_lat = (t1 - t0) * 1000
        s1 = r1.status_code
    except Exception as e:
        print(f"{name:50} | Cold: FAILED ({e})")
        return

    # Run 2: Warm
    t0 = time.perf_counter()
    try:
        if method == "GET":
            r2 = requests.get(url, headers=req_headers, timeout=12)
        elif method == "POST":
            r2 = requests.post(url, headers=req_headers, json=data, timeout=12)
        elif method == "PATCH":
            r2 = requests.patch(url, headers=req_headers, json=data, timeout=12)
        elif method == "DELETE":
            r2 = requests.delete(url, headers=req_headers, timeout=12)
        t1 = time.perf_counter()
        warm_lat = (t1 - t0) * 1000
        s2 = r2.status_code
    except Exception as e:
        print(f"{name:50} | Cold: {cold_lat:6.1f} ms ({s1}) | Warm: FAILED ({e})")
        return

    print(f"{name:50} | Cold: {cold_lat:6.1f} ms ({s1}) | Warm: {warm_lat:6.1f} ms ({s2})", flush=True)

print("=" * 90)
print(f"BENCHMARKING REMAINING ENDPOINTS ON LIVE ORACLE SERVER ({BASE_URL})")
print("=" * 90)

# 1. System & Health
print("\n--- [1] SYSTEM & HEALTH ---")
benchmark("GET /health", "GET", f"{BASE_URL}/health", req_headers={})

# 2. Market APIs
print("\n--- [2] MARKET APIS ---")
benchmark("GET /market/live", "GET", f"{BASE_URL}/market/live", req_headers={})
benchmark("GET /market/quotes", "GET", f"{BASE_URL}/market/quotes", req_headers={})
benchmark("GET /market/all-stocks", "GET", f"{BASE_URL}/market/all-stocks", req_headers={})
benchmark("GET /market/curated", "GET", f"{BASE_URL}/market/curated", req_headers={})
benchmark("GET /market/sectors/performance", "GET", f"{BASE_URL}/market/sectors/performance", req_headers={})
benchmark("GET /market/indices", "GET", f"{BASE_URL}/market/indices", req_headers={})
benchmark("GET /market/indices/kse-100", "GET", f"{BASE_URL}/market/indices/kse-100", req_headers={})
benchmark("GET /market/indices/kse-30", "GET", f"{BASE_URL}/market/indices/kse-30", req_headers={})
benchmark("GET /market/indices/kmi-30", "GET", f"{BASE_URL}/market/indices/kmi-30", req_headers={})
benchmark("GET /market/gainers", "GET", f"{BASE_URL}/market/gainers", req_headers={})
benchmark("GET /market/losers", "GET", f"{BASE_URL}/market/losers", req_headers={})
benchmark("GET /market/volume-spikes", "GET", f"{BASE_URL}/market/volume-spikes", req_headers={})
benchmark("GET /market/sentiment-overview", "GET", f"{BASE_URL}/market/sentiment-overview", req_headers={})

# 3. Portfolio APIs
print("\n--- [3] PORTFOLIO APIS ---")
benchmark("GET /portfolio", "GET", f"{BASE_URL}/portfolio")
benchmark("GET /portfolio/holdings", "GET", f"{BASE_URL}/portfolio/holdings")
benchmark("GET /portfolio/pnl", "GET", f"{BASE_URL}/portfolio/pnl")
benchmark("GET /portfolio/allocation", "GET", f"{BASE_URL}/portfolio/allocation")
benchmark("GET /portfolio/performance", "GET", f"{BASE_URL}/portfolio/performance")
benchmark("GET /portfolio/transactions", "GET", f"{BASE_URL}/portfolio/transactions")

# 4. Watchlist APIs
print("\n--- [4] WATCHLIST APIS ---")
benchmark("GET /watchlists", "GET", f"{BASE_URL}/watchlists")
benchmark("GET /watchlists/default", "GET", f"{BASE_URL}/watchlists/default")

# 5. Alerts & Notifications
print("\n--- [5] ALERTS & NOTIFICATIONS ---")
benchmark("GET /alerts", "GET", f"{BASE_URL}/alerts")
benchmark("GET /alerts/rules", "GET", f"{BASE_URL}/alerts/rules")
benchmark("GET /notifications", "GET", f"{BASE_URL}/notifications")

# 6. Events & Corporate Actions
print("\n--- [6] EVENTS & CORPORATE ACTIONS ---")
benchmark("GET /events/calendar", "GET", f"{BASE_URL}/events/calendar")

# 7. Community & Social
print("\n--- [7] COMMUNITY & SOCIAL ---")
benchmark("GET /community/feed", "GET", f"{BASE_URL}/community/feed")
benchmark("GET /community/trending", "GET", f"{BASE_URL}/community/trending")

# 8. Assistant (AI Chat)
print("\n--- [8] ASSISTANT (AI CHAT) ---")
benchmark("GET /assistant/conversations", "GET", f"{BASE_URL}/assistant/conversations")
benchmark("GET /assistant/quick-prompts", "GET", f"{BASE_URL}/assistant/quick-prompts")

# 9. Devices
print("\n--- [9] DEVICES ---")
device_payload = {
    "fcm_token": f"fcm_bench_{uuid.uuid4().hex[:12]}",
    "platform": "android",
    "device_name": "Benchmark Test Device"
}
benchmark("POST /devices/register", "POST", f"{BASE_URL}/devices/register", data=device_payload)

print("\n" + "=" * 90)
