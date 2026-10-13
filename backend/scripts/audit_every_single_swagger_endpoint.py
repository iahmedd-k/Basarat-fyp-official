"""
Comprehensive Dynamic Swagger/OpenAPI Full-Coverage Latency Auditor.
Extracts EVERY single endpoint and method from the live OpenAPI 3.1 specification (176 operations across 25 tags),
executes authenticated requests with smart parameter resolution, measures latencies, and outputs detailed metrics.
"""

import sys
import time
import json
import re
import statistics
from collections import defaultdict
from typing import List, Dict, Any, Tuple
import urllib.request
import urllib.parse
import ssl

BASE_URL = sys.argv[1] if len(sys.argv) > 1 else "https://api.basarat.live"
DEMO_EMAIL = "trader1@basarat.pk"
DEMO_PASSWORD = "TestPassword12345!"

ctx = ssl.create_default_context()

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Basarat-Auditor/1.0"

def get_token() -> Tuple[str, str]:
    url = f"{BASE_URL}/api/v1/auth/login"
    body = {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    headers = {"User-Agent": USER_AGENT, "Content-Type": "application/json"}
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
            res_data = json.loads(resp.read().decode())
            token = res_data.get("access_token")
            # Fetch me to get user id
            me_req = urllib.request.Request(f"{BASE_URL}/api/v1/users/me", headers={"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"})
            with urllib.request.urlopen(me_req, context=ctx, timeout=10) as me_resp:
                me_data = json.loads(me_resp.read().decode())
                user_id = str(me_data.get("id", ""))
                return token, user_id
    except Exception as e:
        print(f"[-] Authentication failed: {e}", flush=True)
        return "", ""

def fetch_dynamic_entities(token: str) -> Dict[str, str]:
    """Fetch real IDs from the live database to accurately test parameterized paths."""
    headers = {"User-Agent": USER_AGENT, "Authorization": f"Bearer {token}"}
    entities = {
        "symbol": "HBL",
        "ticker": "HBL",
        "post_id": "demo-post-id",
        "comment_id": "demo-comment-id",
        "rule_id": "demo-rule-id",
        "holding_id": "demo-holding-id",
        "transaction_id": "demo-tx-id",
        "device_token": "demo-fcm-token",
        "horizon": "1W",
        "timeframe": "1M",
        "range": "1M",
        "period": "1M",
        "sector": "Commercial Banks",
        "index_code": "KSE100",
        "code": "KSE100",
    }
    
    # 1. Try to fetch a real post ID
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/v1/community/posts?limit=1", headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            items = data.get("items", []) or data.get("posts", [])
            if items and isinstance(items, list) and len(items) > 0:
                entities["post_id"] = str(items[0].get("id", "demo-post-id"))
    except Exception:
        pass

    # 2. Try to fetch alert rules
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/v1/alerts/rules", headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            if isinstance(data, list) and len(data) > 0:
                entities["rule_id"] = str(data[0].get("id", "demo-rule-id"))
    except Exception:
        pass

    # 3. Try to fetch holdings
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/v1/portfolio/holdings", headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            items = data.get("holdings", []) if isinstance(data, dict) else data
            if items and isinstance(items, list) and len(items) > 0:
                entities["holding_id"] = str(items[0].get("id", "demo-holding-id"))
    except Exception:
        pass

    return entities

def resolve_path(path_template: str, entities: Dict[str, str], user_id: str) -> str:
    path = path_template
    # Replace known placeholders
    replacements = {
        "{user_id}": user_id or "00000000-0000-0000-0000-000000000001",
        "{symbol}": entities.get("symbol", "HBL"),
        "{ticker}": entities.get("ticker", "HBL"),
        "{sym}": entities.get("symbol", "HBL"),
        "{post_id}": entities.get("post_id", "demo-post-id"),
        "{comment_id}": entities.get("comment_id", "demo-comment-id"),
        "{rule_id}": entities.get("rule_id", "demo-rule-id"),
        "{alert_id}": entities.get("rule_id", "demo-rule-id"),
        "{holding_id}": entities.get("holding_id", "demo-holding-id"),
        "{transaction_id}": entities.get("transaction_id", "demo-tx-id"),
        "{device_token}": entities.get("device_token", "demo-token"),
        "{horizon}": "1W",
        "{timeframe}": "1M",
        "{range}": "1M",
        "{period}": "1M",
        "{sector}": urllib.parse.quote("Commercial Banks"),
        "{code}": "KSE100",
        "{index_code}": "KSE100",
        "{plan_id}": "pro_monthly",
        "{session_id}": "demo-session-id",
        "{id}": entities.get("post_id", "demo-id"),
    }
    for placeholder, val in replacements.items():
        path = path.replace(placeholder, val)
    
    # Catch any remaining {param}
    path = re.sub(r"\{[a-zA-Z0-9_]+\}", "default", path)
    return path

def generate_sample_body(method: str, path: str, op_spec: dict) -> dict:
    if method not in ("POST", "PUT", "PATCH"):
        return None
    # Provide intelligent payloads for known endpoints
    if "/auth/login" in path:
        return {"email": DEMO_EMAIL, "password": DEMO_PASSWORD}
    if "/assistant/chat" in path:
        return {"message": "Summarize KSE-100 index performance today", "conversation_id": "bench-convo-1"}
    if "/portfolio/transactions" in path:
        return {"symbol": "HBL", "transaction_type": "buy", "quantity": 10, "price": 150.0, "transaction_date": "2026-10-09T10:00:00Z"}
    if "/alerts/rules" in path:
        return {"symbol": "HBL", "condition": "above", "target_price": 250.0}
    if "/community/posts" in path:
        return {"content": "PSX Market rally analysis post #HBL #KSE100", "symbols": ["HBL"]}
    if "/stocks/compare" in path:
        return {"symbols": ["HBL", "MCB", "MEBL"]}
    if "/watchlists" in path and not "/items" in path:
        return {"name": "Audit Watchlist", "description": "Benchmark list"}
    if "/watchlists" in path and "/items" in path:
        return {"symbol": "HBL"}
    
    # Generic minimal JSON body
    return {}

def test_endpoint(method: str, path: str, token: str, body: dict = None) -> Dict[str, Any]:
    url = f"{BASE_URL}{path}"
    headers = {
        "User-Agent": USER_AGENT,
        "Accept": "application/json",
        "Authorization": f"Bearer {token}",
    }
    data_bytes = None
    if body is not None and method in ("POST", "PUT", "PATCH"):
        headers["Content-Type"] = "application/json"
        data_bytes = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data_bytes, headers=headers, method=method)
    
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            content = resp.read()
            return {
                "method": method,
                "path": path,
                "status": resp.status,
                "latency_ms": round(elapsed_ms, 2),
                "bytes": len(content),
                "ok": resp.status < 400,
            }
    except urllib.error.HTTPError as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "method": method,
            "path": path,
            "status": e.code,
            "latency_ms": round(elapsed_ms, 2),
            "bytes": 0,
            "ok": e.code in (200, 201, 204),
            "error": str(e),
        }
    except Exception as e:
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        return {
            "method": method,
            "path": path,
            "status": 0,
            "latency_ms": round(elapsed_ms, 2),
            "bytes": 0,
            "ok": False,
            "error": str(e),
        }

def run_full_swagger_audit():
    print("=" * 86, flush=True)
    print(" BASARAT COMPLETE SWAGGER / OPENAPI SPECIFICATION LATENCY AUDIT", flush=True)
    print(f" Target: {BASE_URL}", flush=True)
    print("=" * 86, flush=True)

    print("[1/4] Authenticating with demo investor account...", flush=True)
    token, user_id = get_token()
    if not token:
        print("[-] Authentication failed.")
        return
    print(f"      [+] Authenticated User ID: {user_id}", flush=True)

    print("[2/4] Fetching dynamic live entities for accurate parameter resolution...", flush=True)
    entities = fetch_dynamic_entities(token)
    print(f"      [+] Resolved context: symbol={entities['symbol']}, post_id={entities['post_id']}", flush=True)

    print("[3/4] Fetching full OpenAPI 3.1 schema...", flush=True)
    schema_req = urllib.request.Request(f"{BASE_URL}/api/v1/openapi.json", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(schema_req, context=ctx, timeout=10) as resp:
        schema = json.loads(resp.read().decode())

    paths_dict = schema.get("paths", {})
    all_operations = []
    
    for path_tpl, methods in paths_dict.items():
        # Exclude websocket endpoints from standard HTTP tests
        if "/ws" in path_tpl:
            continue
        for method_name, op_spec in methods.items():
            if method_name.upper() not in ("GET", "POST", "PUT", "DELETE", "PATCH"):
                continue
            tags = op_spec.get("tags", ["General"])
            tag = tags[0] if tags else "General"
            summary = op_spec.get("summary", "")
            resolved_p = resolve_path(path_tpl, entities, user_id)
            body = generate_sample_body(method_name.upper(), resolved_p, op_spec)
            all_operations.append({
                "tag": tag,
                "method": method_name.upper(),
                "path_template": path_tpl,
                "resolved_path": resolved_p,
                "summary": summary,
                "body": body,
            })

    total_ops = len(all_operations)
    print(f"      [+] Found {total_ops} HTTP Operations across {len(schema.get('tags', []))} Tags to benchmark.\n", flush=True)

    print("[4/4] Executing Live Latency Benchmark across all Swagger endpoints...\n", flush=True)
    print(f"{'#':<3} | {'Domain / Tag':<18} | {'Method':<6} | {'Status':<7} | {'Cold (ms)':<9} | {'Warm (ms)':<9} | {'Endpoint Path'}", flush=True)
    print("-" * 86, flush=True)

    results_by_tag = defaultdict(list)
    all_warm_latencies = []
    all_cold_latencies = []
    passed_count = 0

    for idx, op in enumerate(all_operations, 1):
        method = op["method"]
        path = op["resolved_path"]
        tag = op["tag"]

        # Run Cold test
        res_cold = test_endpoint(method, path, token, op["body"])
        time.sleep(0.03)
        # Run Warm test
        res_warm = test_endpoint(method, path, token, op["body"])

        c_ms = res_cold["latency_ms"]
        w_ms = res_warm["latency_ms"]
        status = res_warm["status"]
        ok = res_warm["ok"]

        if ok:
            passed_count += 1
            all_cold_latencies.append(c_ms)
            all_warm_latencies.append(w_ms)

        status_display = f"{status} OK" if ok else f"{status}"
        print(f"{idx:<3} | {tag:<18} | {method:<6} | {status_display:<7} | {c_ms:>7.2f}ms | {w_ms:>7.2f}ms | {path}", flush=True)

        results_by_tag[tag].append({
            "method": method,
            "path": path,
            "summary": op["summary"],
            "status": status,
            "cold_ms": c_ms,
            "warm_ms": w_ms,
            "ok": ok,
        })

    # Summary Statistics
    print("\n" + "=" * 86, flush=True)
    print(" COMPLETE SWAGGER LATENCY BENCHMARK REPORT (BY DOMAIN TAG)", flush=True)
    print("=" * 86, flush=True)
    print(f"{'Domain / Tag':<22} | {'Ops':<4} | {'Pass Rate':<10} | {'Avg Cold':<10} | {'Avg Warm':<10} | {'P50 Warm':<10} | {'P90 Warm'}")
    print("-" * 86, flush=True)

    for tag, ops in sorted(results_by_tag.items()):
        warm_vals = [o["warm_ms"] for o in ops if o["ok"]]
        cold_vals = [o["cold_ms"] for o in ops if o["ok"]]
        pass_rate = f"{len(warm_vals)}/{len(ops)} ({round(len(warm_vals)/len(ops)*100)}%)"
        
        avg_c = f"{statistics.mean(cold_vals):.1f}ms" if cold_vals else "N/A"
        avg_w = f"{statistics.mean(warm_vals):.1f}ms" if warm_vals else "N/A"
        p50_w = f"{statistics.median(warm_vals):.1f}ms" if warm_vals else "N/A"
        p90_w = f"{warm_vals[int(len(warm_vals)*0.9)]:.1f}ms" if len(warm_vals) >= 2 else (avg_w if warm_vals else "N/A")

        print(f"{tag:<22} | {len(ops):<4} | {pass_rate:<10} | {avg_c:>10} | {avg_w:>10} | {p50_w:>10} | {p90_w:>10}", flush=True)

    # Method Breakdown
    results_by_method = defaultdict(list)
    for op in all_operations:
        m = op["method"]
        # Find results
        for r in results_by_tag[op["tag"]]:
            if r["path"] == op["resolved_path"] and r["method"] == m:
                results_by_method[m].append(r)
                break

    print("\n" + "=" * 86, flush=True)
    print(" SWAGGER LATENCY BENCHMARK BY HTTP METHOD", flush=True)
    print("=" * 86, flush=True)
    print(f"{'Method':<8} | {'Total Ops':<10} | {'Pass Rate':<12} | {'First Request (Cold)':<22} | {'Warm (P50)'}")
    print("-" * 86, flush=True)
    for m in ("GET", "POST", "PUT", "DELETE", "PATCH"):
        if m in results_by_method:
            m_ops = results_by_method[m]
            m_passed = [o for o in m_ops if o["ok"]]
            m_c = [o["cold_ms"] for o in m_ops]
            m_w = [o["warm_ms"] for o in m_passed]
            c_avg = f"{statistics.mean(m_c):.1f}ms" if m_c else "N/A"
            w_p50 = f"{statistics.median(m_w):.1f}ms" if m_w else "N/A"
            pass_str = f"{len(m_passed)}/{len(m_ops)} ({round(len(m_passed)/len(m_ops)*100)}%)"
            print(f"{m:<8} | {len(m_ops):<10} | {pass_str:<12} | {c_avg:>22} | {w_p50:>10}", flush=True)

    print("\n" + "=" * 86, flush=True)
    print(" OVERALL SYSTEM LATENCY METRICS", flush=True)
    print("=" * 86, flush=True)
    print(f" Total Operations Benchmarked: {total_ops}")
    print(f" Passing Operations (2xx)    : {passed_count} / {total_ops} ({round(passed_count/total_ops*100, 1)}%)\n")

    if all_cold_latencies:
        all_cold_latencies.sort()
        print(f" FIRST REQUEST (COLD) LATENCY DISTRIBUTION:")
        print(f"   • Minimum Latency     : {min(all_cold_latencies):.2f} ms")
        print(f"   • Median (P50)        : {statistics.median(all_cold_latencies):.2f} ms")
        print(f"   • Average             : {statistics.mean(all_cold_latencies):.2f} ms")
        print(f"   • 90th Percentile (P90): {all_cold_latencies[int(len(all_cold_latencies) * 0.90)]:.2f} ms")
        print(f"   • 95th Percentile (P95): {all_cold_latencies[int(len(all_cold_latencies) * 0.95)]:.2f} ms")
        print(f"   • Maximum Latency     : {max(all_cold_latencies):.2f} ms\n")

    if all_warm_latencies:
        all_warm_latencies.sort()
        p50 = statistics.median(all_warm_latencies)
        p90 = all_warm_latencies[int(len(all_warm_latencies) * 0.90)]
        p95 = all_warm_latencies[int(len(all_warm_latencies) * 0.95)]
        p99 = all_warm_latencies[int(len(all_warm_latencies) * 0.99)]
        avg = statistics.mean(all_warm_latencies)
        min_l = min(all_warm_latencies)
        max_l = max(all_warm_latencies)

        print(f" SUBSEQUENT (WARM CACHE) LATENCY DISTRIBUTION:")
        print(f"   • Minimum Latency     : {min_l:.2f} ms")
        print(f"   • Median (P50)        : {p50:.2f} ms")
        print(f"   • Average             : {avg:.2f} ms")
        print(f"   • 90th Percentile (P90): {p90:.2f} ms")
        print(f"   • 95th Percentile (P95): {p95:.2f} ms")
        print(f"   • 99th Percentile (P99): {p99:.2f} ms")
        print(f"   • Maximum Latency     : {max_l:.2f} ms")
    print("=" * 86, flush=True)

if __name__ == "__main__":
    run_full_swagger_audit()
