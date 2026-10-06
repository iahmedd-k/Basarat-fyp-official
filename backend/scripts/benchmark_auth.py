import time
import uuid
import requests
import json

BASE_URL = "http://193.123.84.223:8000/api/v1"
TEST_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjMmI4YjAxMDQwYTA0NmM1OWNhNzA3MTc5YjZjYTljOSIsImV4cCI6MTc5MTI1NTEwMiwidHlwZSI6ImFjY2VzcyIsImp0aSI6IjhiMzVjMDY3YzhhZTQyZTc5ZGVlMDE1ZGVhMzg3NGM1In0.-aY_1XX75E2Q_UQ0OwoD6snPhApBm71fNsmBKWrVGRY"

headers = {
    "Authorization": f"Bearer {TEST_TOKEN}",
    "Content-Type": "application/json",
}

def benchmark(name, method, url, data=None, req_headers=None):
    if req_headers is None:
        req_headers = headers
    
    # Run 1: Cold / Initial
    t0 = time.perf_counter()
    try:
        if method == "GET":
            r1 = requests.get(url, headers=req_headers, timeout=10)
        elif method == "POST":
            r1 = requests.post(url, headers=req_headers, json=data, timeout=10)
        elif method == "PATCH":
            r1 = requests.patch(url, headers=req_headers, json=data, timeout=10)
        t1 = time.perf_counter()
        cold_lat = (t1 - t0) * 1000
        s1 = r1.status_code
    except Exception as e:
        print(f"FAILED {name}: {e}")
        return

    # Run 2: Warm
    t0 = time.perf_counter()
    if method == "GET":
        r2 = requests.get(url, headers=req_headers, timeout=10)
    elif method == "POST":
        r2 = requests.post(url, headers=req_headers, json=data, timeout=10)
    elif method == "PATCH":
        r2 = requests.patch(url, headers=req_headers, json=data, timeout=10)
    t1 = time.perf_counter()
    warm_lat = (t1 - t0) * 1000
    s2 = r2.status_code

    print(f"{name:45} | Cold: {cold_lat:6.1f} ms ({s1}) | Warm: {warm_lat:6.1f} ms ({s2})")

print("=" * 80)
print(f"BENCHMARKING AUTH & USER ENDPOINTS ON LIVE ORACLE SERVER ({BASE_URL})")
print("=" * 80)

# Unauthenticated / Options endpoints
benchmark("GET /users/investment-profile/options", "GET", f"{BASE_URL}/users/investment-profile/options", req_headers={})
benchmark("GET /users/risk-profile/options", "GET", f"{BASE_URL}/users/risk-profile/options", req_headers={})
benchmark("GET /users/sectors", "GET", f"{BASE_URL}/users/sectors", req_headers={})

# Authenticated Profile Endpoints
benchmark("GET /users/me", "GET", f"{BASE_URL}/users/me")
benchmark("GET /users/me/investment-profile", "GET", f"{BASE_URL}/users/me/investment-profile")
benchmark("GET /users/me/risk-profile", "GET", f"{BASE_URL}/users/me/risk-profile")

# Update Profile Endpoints
profile_payload = {
    "full_name": "Antigravity Test User",
    "risk_tolerance": "moderate",
    "investment_horizon": "medium_term",
    "sector_preferences": ["Commercial Banks", "Oil & Gas"]
}
benchmark("PATCH /users/me", "PATCH", f"{BASE_URL}/users/me", data=profile_payload)
benchmark("GET /users/me (cached verification)", "GET", f"{BASE_URL}/users/me")

# Notification preferences update
notif_payload = {
    "channels": ["email", "push"],
    "categories": ["price_alerts", "recommendations"]
}
benchmark("PATCH /users/me/notification-preferences", "PATCH", f"{BASE_URL}/users/me/notification-preferences", data=notif_payload)

# Dynamic Auth flow endpoints
uniq_email = f"benchmark_{uuid.uuid4().hex[:8]}@example.com"
benchmark("POST /auth/signup", "POST", f"{BASE_URL}/auth/signup", data={"email": uniq_email, "password": "SecurePassword123!", "full_name": "Bench User"}, req_headers={})
benchmark("POST /auth/resend-verification", "POST", f"{BASE_URL}/auth/resend-verification", data={"email": uniq_email}, req_headers={})
benchmark("POST /auth/forgot-password", "POST", f"{BASE_URL}/auth/forgot-password", data={"email": uniq_email}, req_headers={})

print("=" * 80)
