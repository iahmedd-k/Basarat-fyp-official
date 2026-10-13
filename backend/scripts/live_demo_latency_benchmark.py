"""
Comprehensive Live Production Latency Benchmark for Basarat API.
Logs in with trader1@basarat.pk, tests correctly mapped routes across all domains,
and measures Cold vs Warm Latencies.
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

def make_request(method: str, path: str, token: str = None, body: dict = None) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    headers = {
        "User-Agent": "Basarat-Benchmark/1.0",
        "Accept": "application/json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    
    data_bytes = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(body).encode("utf-8")
    
    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    
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

def run_benchmark():
    print("=" * 82, flush=True)
    print(" BASARAT PRODUCTION API LATENCY & ENDPOINT BENCHMARK", flush=True)
    print(f" Target: {BASE_URL} (Oracle Cloud Infrastructure)", flush=True)
    print("=" * 82, flush=True)

    token = login_demo_user()
    if not token:
        print("[-] Aborting: Could not obtain JWT token.")
        return

    endpoints = [
        # Domain, Method, Path
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

    print(f"{'Domain / Route':<26} | {'Status':<6} | {'Cold (ms)':<10} | {'Warm (ms)':<10} | {'Speedup'}")
    print("-" * 82, flush=True)

    cold_latencies = []
    warm_latencies = []

    for name, method, path in endpoints:
        # Pass 1: Cold request
        res1 = make_request(method, path, token)
        # Pass 2: Warm request (cached in Redis / L1 process cache)
        time.sleep(0.05)
        res2 = make_request(method, path, token)

        c_ms = res1["latency_ms"]
        w_ms = res2["latency_ms"]
        status_str = f"{res2['status']} OK" if res2['ok'] else f"{res2['status']} ERR"
        speedup = f"{round(c_ms / max(w_ms, 0.1), 1)}x" if c_ms > w_ms else "1.0x"

        if res2["ok"]:
            cold_latencies.append(c_ms)
            warm_latencies.append(w_ms)

        print(f"{name:<26} | {status_str:<6} | {c_ms:>8.2f}ms | {w_ms:>8.2f}ms | {speedup:>6}", flush=True)

    print("\n" + "=" * 82, flush=True)
    print(" STATISTICAL LATENCY ANALYSIS (PRODUCTION ORACLE VM)", flush=True)
    print("=" * 82, flush=True)
    
    total = len(endpoints)
    passed = len(warm_latencies)
    print(f" Endpoints Tested       : {total}")
    print(f" Successful (HTTP 200)  : {passed} / {total} ({round(passed/total*100, 1)}%)\n")

    if warm_latencies:
        warm_latencies.sort()
        p50 = statistics.median(warm_latencies)
        p90 = warm_latencies[int(len(warm_latencies) * 0.90)]
        p95 = warm_latencies[int(len(warm_latencies) * 0.95)]
        avg = statistics.mean(warm_latencies)
        min_l = min(warm_latencies)
        max_l = max(warm_latencies)

        print(f" Warm Response Summary:")
        print(f"   • Minimum Latency     : {min_l:.2f} ms")
        print(f"   • Median (P50)        : {p50:.2f} ms")
        print(f"   • Average             : {avg:.2f} ms")
        print(f"   • 90th Percentile (P90): {p90:.2f} ms")
        print(f"   • 95th Percentile (P95): {p95:.2f} ms")
        print(f"   • Maximum Latency     : {max_l:.2f} ms")
    print("=" * 82, flush=True)

if __name__ == "__main__":
    run_benchmark()
