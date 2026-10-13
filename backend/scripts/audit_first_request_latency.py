"""
Audit First-Request Latency across all 32 live endpoints on https://api.basarat.live.
Since the production server and Redis are already active and warmed,
this script measures what an incoming user actually experiences on their FIRST request.
"""

import sys
import time
import json
import statistics
from typing import List, Dict, Any
import urllib.request
import urllib.parse
import ssl

BASE_URL = "https://api.basarat.live"
DEMO_EMAIL = "trader1@basarat.pk"
DEMO_PASSWORD = "TestPassword12345!"

ctx = ssl.create_default_context()

def make_request(method: str, path: str, token: str = None) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    headers = {
        "User-Agent": "Basarat-Benchmark/1.0",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    req = urllib.request.Request(url, headers=headers, method=method)
    
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            content = resp.read()
            return {
                "path": path,
                "method": method,
                "status": resp.status,
                "latency_ms": round(elapsed_ms, 2),
                "bytes": len(content),
                "ok": True,
            }
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "path": path,
            "method": method,
            "status": e.code,
            "latency_ms": round(elapsed_ms, 2),
            "bytes": 0,
            "ok": False,
            "error": str(e),
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "path": path,
            "method": method,
            "status": 0,
            "latency_ms": round(elapsed_ms, 2),
            "bytes": 0,
            "ok": False,
            "error": str(e),
        }

def login_demo_user():
    print(f"[*] Authenticating with verified demo credentials ({DEMO_EMAIL})...", flush=True)
    url = f"{BASE_URL}/api/v1/auth/login"
    body = {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    headers = {"User-Agent": "Basarat-Benchmark/1.0", "Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            res_data = json.loads(resp.read().decode())
            token = res_data.get("access_token")
            print(f"    [+] Login successful! Active JWT token obtained.\n", flush=True)
            return token
    except Exception as e:
        print(f"    [-] Login failed for {DEMO_EMAIL}: {e}", flush=True)
        return None

def run_first_request_audit():
    print("=" * 82, flush=True)
    print(" BASARAT PRODUCTION: FIRST-REQUEST LATENCY AUDIT (WARMED REDIS STATE)", flush=True)
    print(f" Target: {BASE_URL} (Oracle Cloud Infrastructure)", flush=True)
    print("=" * 82, flush=True)

    token = login_demo_user()
    if not token:
        print("[-] Aborting: Could not obtain JWT token.")
        return

    endpoints = [
        ("Health (Liveness)", "GET", "/health"),
        ("Health (Readiness)", "GET", "/api/v1/health/ready"),
        ("User (Profile)", "GET", "/api/v1/users/me"),
        ("Market (Indices)", "GET", "/api/v1/market/indices"),
        ("Market (Gainers)", "GET", "/api/v1/market/gainers"),
        ("Market (Losers)", "GET", "/api/v1/market/losers"),
        ("Market (Sectors)", "GET", "/api/v1/market/sectors/performance"),
        ("Stocks (Search)", "GET", "/api/v1/stocks/search?q=HBL"),
        ("Stocks (Overview)", "GET", "/api/v1/stocks/HBL/overview"),
        ("Stocks (Technicals)", "GET", "/api/v1/stocks/HBL/technical-indicators"),
        ("Stocks (History)", "GET", "/api/v1/stocks/HBL/price-history?range=1M"),
        ("Stocks (Fundamentals)", "GET", "/api/v1/stocks/HBL/fundamentals"),
        ("Forecast (5-Day ML)", "GET", "/api/v1/forecast/HBL?horizon=1W"),
        ("Forecast (History)", "GET", "/api/v1/forecast/HBL/history?horizon=1W&limit=5"),
        ("Recommendations (Top)", "GET", "/api/v1/recommendations?limit=10"),
        ("Recommendations (Bounds)", "GET", "/api/v1/recommendations/HBL/target-stop"),
        ("Watchlist (Tracked)", "GET", "/api/v1/watchlists"),
        ("Portfolio (Holdings)", "GET", "/api/v1/portfolio/holdings"),
        ("Portfolio (PnL)", "GET", "/api/v1/portfolio/pnl"),
        ("Portfolio (Allocation)", "GET", "/api/v1/portfolio/allocation"),
        ("Risk (Portfolio VaR)", "GET", "/api/v1/risk/var"),
        ("Sentiment (Market)", "GET", "/api/v1/sentiment/market"),
        ("Sentiment (Scores)", "GET", "/api/v1/sentiment/scores?symbol=HBL"),
        ("News (Paginated Feed)", "GET", "/api/v1/news?limit=10"),
        ("Shariah (KMI-30)", "GET", "/api/v1/shariah/kmi30"),
        ("Shariah (Symbol Check)", "GET", "/api/v1/shariah/HBL"),
        ("ETFs (Directory)", "GET", "/api/v1/etfs"),
        ("ETFs (Detail)", "GET", "/api/v1/etfs/MIIETF"),
        ("IPOs (Directory)", "GET", "/api/v1/ipos"),
        ("IPOs (Calendar)", "GET", "/api/v1/ipos/calendar"),
        ("Community (Feed)", "GET", "/api/v1/community/posts?limit=10"),
        ("Community (Trending)", "GET", "/api/v1/community/trending?limit=5"),
    ]

    print(f"{'Domain / Route':<26} | {'Status':<6} | {'First Request (ms)':<20} | {'Estimated Server Latency'}")
    print("-" * 82, flush=True)

    latencies = []

    for name, method, path in endpoints:
        # EXACTLY ONE FIRST-REQUEST CALL
        res = make_request(method, path, token)
        ms = res["latency_ms"]
        status_str = f"{res['status']} OK" if res['ok'] else f"{res['status']} ERR"
        
        # Estimate internal server latency by removing network RTT (~140ms)
        est_server = f"~{max(0, round(ms - 140.0, 1))} ms" if ms >= 140.0 else "< 1 ms"

        if res["ok"]:
            latencies.append(ms)

        print(f"{name:<26} | {status_str:<6} | {ms:>16.2f} ms | {est_server:>24}", flush=True)

    print("\n" + "=" * 82, flush=True)
    print(" FIRST-REQUEST STATISTICAL ANALYSIS", flush=True)
    print("=" * 82, flush=True)
    
    total = len(endpoints)
    passed = len(latencies)
    print(f" Endpoints Tested       : {total}")
    print(f" Successful (HTTP 200)  : {passed} / {total} ({round(passed/total*100, 1)}%)\n")

    if latencies:
        latencies_sorted = sorted(latencies)
        p50 = statistics.median(latencies_sorted)
        p90 = latencies_sorted[int(len(latencies_sorted) * 0.90)]
        p95 = latencies_sorted[int(len(latencies_sorted) * 0.95)]
        avg = statistics.mean(latencies_sorted)
        min_l = min(latencies_sorted)
        max_l = max(latencies_sorted)

        print(f" First-Request Latency Summary:")
        print(f"   • Minimum Latency     : {min_l:.2f} ms")
        print(f"   • Median (P50)        : {p50:.2f} ms")
        print(f"   • Average             : {avg:.2f} ms")
        print(f"   • 90th Percentile (P90): {p90:.2f} ms")
        print(f"   • 95th Percentile (P95): {p95:.2f} ms")
        print(f"   • Maximum Latency     : {max_l:.2f} ms")
    print("=" * 82, flush=True)

if __name__ == "__main__":
    run_first_request_audit()
