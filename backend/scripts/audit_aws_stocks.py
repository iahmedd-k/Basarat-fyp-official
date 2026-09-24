import urllib.request
import urllib.error
import json
import sys

BASE_URL = "http://16.16.26.247:8000"
SYMBOLS = ["SYS", "OGDC", "ENGRO", "LUCK", "HBL", "PPL", "MCB", "MEBL", "FFC", "HUBC"]

def query_endpoint(url, desc):
    req = urllib.request.Request(url, headers={"User-Agent": "Basarat-Test-Runner/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as response:
            status = response.status
            raw_body = response.read().decode("utf-8")
            data = json.loads(raw_body)
            return status, data, None
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return e.code, None, err_msg
    except Exception as e:
        return 0, None, str(e)

def analyze_payload(data):
    if data is None:
        return "NULL / ERROR"
    if isinstance(data, list):
        count = len(data)
        return f"List[{count} items]" + (" (EMPTY!)" if count == 0 else " (POPULATED)")
    if isinstance(data, dict):
        # check specific keys
        summary_parts = []
        is_empty = True
        for k, v in data.items():
            if isinstance(v, list):
                summary_parts.append(f"{k}: list[{len(v)}]")
                if len(v) > 0:
                    is_empty = False
            elif isinstance(v, dict):
                summary_parts.append(f"{k}: dict[{len(v)} keys]")
                if len(v) > 0:
                    is_empty = False
            else:
                summary_parts.append(f"{k}={v}")
                if v not in (None, 0, 0.0, "", False):
                    is_empty = False
        summary = ", ".join(summary_parts[:6])
        if len(summary_parts) > 6:
            summary += f", ... (+{len(summary_parts)-6} more)"
        status_tag = " (EMPTY / DEFAULT)" if is_empty else " (POPULATED)"
        return summary + status_tag
    return str(data)

def main():
    print(f"================================================================================")
    print(f"AUDITING STOCKS ENDPOINTS ON LIVE AWS: {BASE_URL}")
    print(f"================================================================================", flush=True)

    # 1. Search endpoint
    print("\n--- 1. Testing Autocomplete Search Endpoint ---", flush=True)
    for q in ["SYS", "OGDC", "ENGRO", "Oil", "Bank"]:
        url = f"{BASE_URL}/api/v1/stocks/search?q={q}&limit=5"
        status, data, err = query_endpoint(url, f"Search q={q}")
        if status == 200:
            results = data.get("results", [])
            print(f"[HTTP {status}] GET /api/v1/stocks/search?q={q} -> Found {len(results)} matches: {results[:2]}", flush=True)
        else:
            print(f"[HTTP {status}] GET /api/v1/stocks/search?q={q} -> Error: {err}", flush=True)

    # 2. Per-symbol Stock Endpoints
    print("\n--- 2. Testing Stock Detail Endpoints Across Top Symbols ---", flush=True)
    endpoints = [
        ("/api/v1/stocks/{sym}/overview", "Overview"),
        ("/api/v1/stocks/{sym}/price-history?range=1M", "Price History (1M)"),
        ("/api/v1/stocks/{sym}/price-history?range=1W", "Price History (1W)"),
        ("/api/v1/stocks/{sym}/price-history?range=1Y", "Price History (1Y)"),
        ("/api/v1/stocks/{sym}/technical-indicators", "Technical Indicators"),
        ("/api/v1/stocks/{sym}/fundamentals", "Fundamentals"),
        ("/api/v1/stocks/{sym}/news", "Stock News"),
    ]

    for sym in SYMBOLS[:5]:
        print(f"\n>>>>> Testing Symbol: {sym} <<<<<", flush=True)
        for ep_pattern, name in endpoints:
            ep = ep_pattern.replace("{sym}", sym)
            url = f"{BASE_URL}{ep}"
            status, data, err = query_endpoint(url, f"{name} ({sym})")
            if status == 200:
                analysis = analyze_payload(data)
                print(f"  [HTTP 200 OK] {name:25} -> {analysis}", flush=True)
            elif status == 404:
                print(f"  [HTTP 404 NF] {name:25} -> {err}", flush=True)
            elif status == 503:
                print(f"  [HTTP 503 SU] {name:25} -> {err}", flush=True)
            else:
                print(f"  [HTTP {status} ERR] {name:25} -> {err}", flush=True)

if __name__ == "__main__":
    main()
