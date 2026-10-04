import urllib.request
import json
import time

base = "http://193.123.84.223:8000"

test_endpoints = [
    # Health & System
    "/health",
    "/api/v1/health/ready",
    # Market
    "/api/v1/market/summary",
    "/api/v1/market/indices",
    "/api/v1/market/gainers",
    "/api/v1/market/losers",
    "/api/v1/market/volume-spikes",
    "/api/v1/market/sentiment-overview",
    "/api/v1/market/all-stocks",
    "/api/v1/market/quotes",
    "/api/v1/market/curated",
    # Stocks search & details
    "/api/v1/stocks/search?q=OGDC",
    "/api/v1/stocks/OGDC/overview",
    "/api/v1/stocks/OGDC/price-history?range=1M",
    "/api/v1/stocks/OGDC/technical-indicators",
    "/api/v1/stocks/OGDC/fundamentals",
    "/api/v1/stocks/HBL/overview",
    "/api/v1/stocks/HBL/price-history?range=1M",
    "/api/v1/stocks/HBL/technical-indicators",
    "/api/v1/stocks/HBL/fundamentals",
    "/api/v1/stocks/LUCK/fundamentals",
    "/api/v1/stocks/SYS/fundamentals",
    "/api/v1/stocks/ENGROH/fundamentals",
    # News
    "/api/v1/news",
    "/api/v1/news/sources",
    "/api/v1/news/market-status",
    "/api/v1/stocks/OGDC/news",
    # Shariah
    "/api/v1/shariah/kmi30",
    "/api/v1/shariah/OGDC",
    "/api/v1/shariah/OGDC/criteria",
    # ETFs & IPOs
    "/api/v1/etfs",
    "/api/v1/ipos",
    "/api/v1/ipos/calendar",
    "/api/v1/ipos/performance",
    # WebSockets stats
    "/api/v1/ws/protocol",
    "/api/v1/ws/stats",
]

print(f"{'STATUS':<8} | {'ENDPOINT':<45} | {'SAMPLE PAYLOAD SUMMARY'}")
print("-" * 80)

passed = 0
failed = 0

for ep in test_endpoints:
    url = f"{base}{ep}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "BasaratTest/1.0"})
        r = urllib.request.urlopen(req, timeout=8)
        status = r.getcode()
        body = json.loads(r.read().decode("utf-8"))
        if isinstance(body, list):
            summary = f"Array[{len(body)} items]"
        elif isinstance(body, dict):
            summary = f"Dict[{len(body)} keys: {', '.join(list(body.keys())[:4])}]"
        else:
            summary = str(body)[:50]
        print(f"[{status} OK]  | {ep:<45} | {summary}")
        passed += 1
    except urllib.error.HTTPError as e:
        print(f"[{e.code} ERR] | {ep:<45} | HTTP Error: {e.reason}")
        failed += 1
    except Exception as e:
        print(f"[FAIL]    | {ep:<45} | Error: {e}")
        failed += 1

print("-" * 80)
print(f"Testing Summary: {passed} PASSED, {failed} FAILED out of {len(test_endpoints)} endpoints tested.")
