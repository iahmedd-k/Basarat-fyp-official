import time
import requests

BASE_URL = "http://193.123.84.223:8000/api/v1"
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjMmI4YjAxMDQwYTA0NmM1OWNhNzA3MTc5YjZjYTljOSIsImV4cCI6MTc5MTI1NTEwMiwidHlwZSI6ImFjY2VzcyIsImp0aSI6IjhiMzVjMDY3YzhhZTQyZTc5ZGVlMDE1ZGVhMzg3NGM1In0.-aY_1XX75E2Q_UQ0OwoD6snPhApBm71fNsmBKWrVGRY"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Accept": "application/json",
}

endpoints = [
    # Recommendations
    ("GET", "/recommendations", "Recommendations List"),
    ("GET", "/recommendations?sector=Commercial%20Banks", "Recommendations By Sector"),
    ("GET", "/recommendations/OGDC", "Recommendation Detail OGDC"),
    ("GET", "/recommendations/engine-weights", "Recommendation Weights"),
    ("GET", "/recommendations/OGDC/target-stop", "Recommendation Target-Stop OGDC"),
    # Forecast
    ("GET", "/forecast/OGDC", "Forecast OGDC (1W)"),
    ("GET", "/forecast/OGDC?horizon=1D", "Forecast OGDC (1D)"),
    ("GET", "/forecast/OGDC/history", "Forecast History OGDC"),
    # Risk
    ("GET", "/risk/var", "Risk VaR & CVaR (Historical)"),
    ("GET", "/risk/stress-test?scenario=2008_crash", "Risk Stress Test (2008)"),
    ("GET", "/risk/stress-test?scenario=covid_crash", "Risk Stress Test (COVID)"),
    # Sentiment
    ("GET", "/sentiment/market-overview", "Sentiment Market Overview"),
    ("GET", "/sentiment/OGDC", "Sentiment Stock OGDC"),
    ("GET", "/sentiment/OGDC/history", "Sentiment History OGDC"),
    ("GET", "/sentiment/OGDC/news", "Sentiment News OGDC"),
]

print("=" * 95)
print(f"BASELINE LATENCY BENCHMARK: RECOMMENDATION, FORECAST, RISK, SENTIMENT ({BASE_URL})")
print("=" * 95)

results = []
for method, path, name in endpoints:
    url = f"{BASE_URL}{path}"
    # Measure cold
    t0 = time.perf_counter()
    try:
        r1 = requests.get(url, headers=HEADERS, timeout=20)
        c_lat = (time.perf_counter() - t0) * 1000
        status1 = r1.status_code
    except Exception as e:
        c_lat = -1
        status1 = str(e)[:20]

    # Measure warm
    t0 = time.perf_counter()
    try:
        r2 = requests.get(url, headers=HEADERS, timeout=20)
        w_lat = (time.perf_counter() - t0) * 1000
        status2 = r2.status_code
    except Exception as e:
        w_lat = -1
        status2 = str(e)[:20]

    results.append((status2, name, c_lat, w_lat))
    print(f"[{status2}] {name:<35} | Cold: {c_lat:8.1f} ms | Warm: {w_lat:8.1f} ms")

print("=" * 95)
