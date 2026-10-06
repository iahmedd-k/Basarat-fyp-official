import time
import requests

BASE_URL = "http://193.123.84.223:8000/api/v1"

endpoints = [
    ("News Feed (Limit 20)", f"{BASE_URL}/news?limit=20"),
    ("News Feed (Symbol OGDC)", f"{BASE_URL}/news?symbol=OGDC"),
    ("News Feed (Sentiment Bullish)", f"{BASE_URL}/news?sentiment=bullish"),
    ("News Feed (Official Sources)", f"{BASE_URL}/news?source_type=official"),
    ("News Sources Health", f"{BASE_URL}/news/sources"),
    ("News Market Status", f"{BASE_URL}/news/market-status"),
    ("Stock News OGDC", f"{BASE_URL}/stocks/OGDC/news"),
    ("Stock News HUBC", f"{BASE_URL}/stocks/HUBC/news"),
    ("Stock News LUCK", f"{BASE_URL}/stocks/LUCK/news"),
]

print("=" * 80)
print(f"BENCHMARKING NEWS ENDPOINTS ON ORACLE CLOUD ({BASE_URL})")
print("=" * 80)

for label, url in endpoints:
    # Run 1: Cold / Initial
    t0 = time.perf_counter()
    r1 = requests.get(url, timeout=15)
    t1 = time.perf_counter()
    cold_ms = (t1 - t0) * 1000

    # Run 2: Warm / Cached
    t0 = time.perf_counter()
    r2 = requests.get(url, timeout=15)
    t1 = time.perf_counter()
    warm_ms = (t1 - t0) * 1000

    item_count = 0
    if r2.status_code == 200:
        data = r2.json()
        if "items" in data:
            item_count = len(data["items"])
        elif "sources" in data:
            item_count = len(data["sources"])
        elif "market_window" in data:
            item_count = 1

    print(f"[{r2.status_code}] {label:<32} | Cold: {cold_ms:7.1f} ms | Warm: {warm_ms:7.1f} ms | Items: {item_count}")

print("=" * 80)
