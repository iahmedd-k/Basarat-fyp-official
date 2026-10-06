import time
import requests

BASE_URL = "http://193.123.84.223:8000/api/v1"

endpoints = [
    # ETF Endpoints
    ("ETFs List", f"{BASE_URL}/etfs"),
    ("ETFs Filter Shariah", f"{BASE_URL}/etfs?is_shariah_compliant=true"),
    ("ETF Detail MIIETF", f"{BASE_URL}/etfs/MIIETF"),
    ("ETF History MIIETF", f"{BASE_URL}/etfs/MIIETF/history?timeframe=1M"),
    ("ETF Performance MIIETF", f"{BASE_URL}/etfs/MIIETF/performance"),
    # IPO Endpoints
    ("IPOs List", f"{BASE_URL}/ipos"),
    ("IPOs Filter Listed", f"{BASE_URL}/ipos?status=LISTED"),
    ("IPO Detail IPACO", f"{BASE_URL}/ipos/IPACO"),
    ("IPO Calendar", f"{BASE_URL}/ipos/calendar"),
    ("IPO Performance", f"{BASE_URL}/ipos/performance"),
    # Shariah Endpoints
    ("Shariah KMI-30", f"{BASE_URL}/shariah/kmi30"),
    ("Shariah Screening OGDC", f"{BASE_URL}/shariah/OGDC"),
    ("Shariah Screening HBL", f"{BASE_URL}/shariah/HBL"),
    ("Shariah Criteria OGDC", f"{BASE_URL}/shariah/OGDC/criteria"),
    ("Shariah Purification OGDC", f"{BASE_URL}/shariah/OGDC/purification?dividend_income=10000"),
]

print("=" * 85)
print(f"BENCHMARKING ETFs, IPOs & SHARIAH ENDPOINTS ON ORACLE CLOUD ({BASE_URL})")
print("=" * 85)

for label, url in endpoints:
    # Run 1: Cold
    t0 = time.perf_counter()
    r1 = requests.get(url, timeout=15)
    t1 = time.perf_counter()
    cold_ms = (t1 - t0) * 1000

    # Run 2: Warm
    t0 = time.perf_counter()
    r2 = requests.get(url, timeout=15)
    t1 = time.perf_counter()
    warm_ms = (t1 - t0) * 1000

    print(f"[{r2.status_code}] {label:<28} | Cold: {cold_ms:7.1f} ms | Warm: {warm_ms:7.1f} ms")

print("=" * 85)
