"""Comprehensive E2E News & PSX Announcements Test Suite.

Tests and benchmarks:
1. Sources & Health: GET /news/sources
2. Market Operating Schedule: GET /news/market-status
3. Refresh Trigger: POST /news/refresh & GET /news/refresh/status
4. General News Feed: GET /news (with summaries, external URLs, source objects, sentiment tags)
5. Filtered Feeds: GET /news?sentiment=bullish, GET /news?source_type=official, GET /news?row=portfolio
6. Stock-Specific News & PSX Official Announcements: GET /stocks/{symbol}/news (OGDC, LUCK, SYS, HUBC, ENGRO)
7. Sentiment-Tagged News: GET /sentiment/{symbol}/news
8. Single Article Detail: GET /news/{article_id}
"""

import time
import uuid
import httpx

BASE_URL = "http://localhost:8000/api/v1"
results = []

def record(endpoint: str, method: str, status_code: int, duration_ms: float, passed: bool, notes: str = "", error_body: str = ""):
    results.append({
        "endpoint": endpoint,
        "method": method,
        "status_code": status_code,
        "duration_ms": round(duration_ms, 2),
        "passed": passed,
        "notes": notes,
    })
    status_sym = "PASS" if passed else "FAIL"
    err_snippet = f" | ERR: {error_body[:100]}" if (not passed and error_body) else ""
    print(f"[{status_sym}] {method:6} {endpoint:42} | {duration_ms:6.1f}ms | HTTP {status_code} | {notes}{err_snippet}")

def run_news_audit():
    print("=" * 110)
    print("STARTING FULL NEWS & PSX ANNOUNCEMENTS AUDIT & BENCHMARK")
    print("=" * 110)

    client = httpx.Client(timeout=30.0)
    email = f"news_tester_{uuid.uuid4().hex[:6]}@test.com"
    pwd = "NewsPassword123!"

    client.post(f"{BASE_URL}/auth/signup", json={"email": email, "password": pwd, "full_name": "News Auditor"})
    login_res = client.post(f"{BASE_URL}/auth/login", json={"email": email, "password": pwd}).json()
    token = login_res["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Sources Health
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/news/sources", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    src_data = r.json() if r.status_code == 200 else {}
    src_count = len(src_data.get("sources", []))
    record("/news/sources", "GET", r.status_code, d, r.status_code == 200 and src_count >= 8, f"configured_sources={src_count}", r.text)

    # 2. Market Status
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/news/market-status", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("/news/market-status", "GET", r.status_code, d, r.status_code == 200, f"status={r.json().get('status') if r.status_code==200 else ''}", r.text)

    # 3. Refresh Trigger & Status
    t0 = time.perf_counter()
    r = client.post(f"{BASE_URL}/news/refresh", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("/news/refresh", "POST", r.status_code, d, r.status_code == 200, f"status={r.json().get('status') if r.status_code==200 else ''}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/news/refresh/status", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("/news/refresh/status", "GET", r.status_code, d, r.status_code == 200, f"state={r.json().get('state') if r.status_code==200 else ''}", r.text)

    # 4. General News Feed
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/news?limit=20", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    news_items = r.json().get("items", []) if r.status_code == 200 else []
    first_item = news_items[0] if news_items else {}
    has_summary = bool(first_item.get("summary"))
    has_ext_link = bool(first_item.get("external_url"))
    record("/news", "GET", r.status_code, d, r.status_code == 200 and len(news_items) > 0, f"items={len(news_items)} | has_summary={has_summary} | has_ext_link={has_ext_link}", r.text)

    # 5. Filtered Feeds
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/news?sentiment=bullish", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("/news?sentiment=bullish", "GET", r.status_code, d, r.status_code == 200, f"bullish_count={len(r.json().get('items', [])) if r.status_code==200 else 0}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/news?source_type=official", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("/news?source_type=official", "GET", r.status_code, d, r.status_code == 200, f"official_announcements={len(r.json().get('items', [])) if r.status_code==200 else 0}", r.text)

    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/news?row=portfolio", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    record("/news?row=portfolio", "GET", r.status_code, d, r.status_code == 200, f"empty_reason={r.json().get('empty_reason') if r.status_code==200 else ''}", r.text)

    # 6. Stock-Specific News & PSX Official Announcements
    symbols_to_test = ["OGDC", "LUCK", "SYS", "HUBC", "ENGRO"]
    for sym in symbols_to_test:
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/stocks/{sym}/news", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        items = r.json().get("items", []) if r.status_code == 200 else []
        record(f"/stocks/{sym}/news", "GET", r.status_code, d, r.status_code == 200 and len(items) > 0, f"articles_found={len(items)}", r.text)

    # 7. Sentiment-Tagged News per Symbol
    t0 = time.perf_counter()
    r = client.get(f"{BASE_URL}/sentiment/OGDC/news", headers=headers)
    d = (time.perf_counter() - t0) * 1000
    s_items = r.json().get("items", []) if r.status_code == 200 else []
    record("/sentiment/OGDC/news", "GET", r.status_code, d, r.status_code == 200 and len(s_items) > 0, f"items={len(s_items)}", r.text)

    # 8. Single Article Detail
    if news_items:
        art_id = news_items[0].get("id")
        t0 = time.perf_counter()
        r = client.get(f"{BASE_URL}/news/{art_id}", headers=headers)
        d = (time.perf_counter() - t0) * 1000
        record(f"/news/{art_id[:16]}...", "GET", r.status_code, d, r.status_code == 200, f"title={r.json().get('title')[:35] if r.status_code==200 else ''}", r.text)

    print("=" * 110)
    passed = sum(1 for x in results if x["passed"])
    total = len(results)
    avg_d = sum(x["duration_ms"] for x in results) / total if total else 0
    print(f"NEWS & ANNOUNCEMENTS AUDIT SUMMARY: {passed}/{total} PASSED ({passed/total*100:.1f}%) | Avg Latency: {avg_d:.1f}ms")
    print("=" * 110)

if __name__ == "__main__":
    run_news_audit()
