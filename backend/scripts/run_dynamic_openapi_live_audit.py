import asyncio
import base64
import json
import logging
import math
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("dynamic_audit")

SSH_KEY = r"d:\FYP\OrcaleSecrets\ssh-key-2026-10-03.key"
REMOTE_USER = "ubuntu"
REMOTE_HOST = "193.123.84.223"
BASE_URL = "http://193.123.84.223:8000"


def fetch_seeded_token_and_user() -> Tuple[str, str, str]:
    """Fetch valid admin JWT and user info from live Oracle DB via SSH."""
    py_code = """
import json
from datetime import timedelta
from app.core.security import create_access_token
from app.db.base import get_sync_session_factory
from app.models.user import User

with get_sync_session_factory()() as s:
    u = s.query(User).filter(User.email == 'admin@basarat.pk').first()
    if not u:
        u = s.query(User).first()
    token = create_access_token(
        data={'sub': str(u.id), 'email': u.email, 'role': getattr(u, 'role', 'admin')},
        expires_delta=timedelta(days=7)
    )
    print(json.dumps({'token': token, 'user_id': str(u.id), 'email': u.email, 'role': getattr(u, 'role', 'admin')}))
"""
    b64 = base64.b64encode(py_code.encode("utf-8")).decode("ascii")
    remote_cmd = f"echo '{b64}' | base64 -d | sudo docker exec -i basarat-app-1 python"
    cmd = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", f"{REMOTE_USER}@{REMOTE_HOST}", remote_cmd]
    res = subprocess.run(cmd, capture_output=True, text=True)
    for line in res.stdout.splitlines():
        if line.strip().startswith("{") and "token" in line:
            data = json.loads(line)
            return data["token"], data["user_id"], data["email"]
    raise RuntimeError(f"Could not retrieve token: {res.stderr or res.stdout}")


def analyze_payload_nulls(data: Any, path: str = "") -> List[Dict[str, Any]]:
    nulls = []
    if data is None:
        nulls.append({"field": path or "root", "type": "null"})
    elif isinstance(data, dict):
        for k, v in data.items():
            curr_path = f"{path}.{k}" if path else k
            if v is None:
                nulls.append({"field": curr_path, "type": "null_property"})
            elif isinstance(v, (dict, list)):
                nulls.extend(analyze_payload_nulls(v, curr_path))
    elif isinstance(data, list):
        for i, item in enumerate(data[:10]):
            curr_path = f"{path}[{i}]"
            if item is None:
                nulls.append({"field": curr_path, "type": "null_element"})
            elif isinstance(item, (dict, list)):
                nulls.extend(analyze_payload_nulls(item, curr_path))
    return nulls


def infer_null_reason(field_name: str, endpoint: str) -> str:
    fn = field_name.lower()
    if any(k in fn for k in ["open", "high", "low", "ldcp", "change", "change_pct", "volume"]):
        return "Market Data: Illiquid stock or off-market hours with no trades executed in current session"
    if any(k in fn for k in ["pe_ratio", "pb_ratio", "eps", "dividend_yield"]):
        return "Fundamentals: Negative/zero earnings or no cash dividend declared by company"
    if any(k in fn for k in ["target_price", "stop_loss", "expected_return"]):
        return "ML Recommendations: Hold/Sideways recommendations do not set directional target prices"
    if any(k in fn for k in ["bio", "full_name", "phone", "avatar_url", "risk_tolerance", "sector_preferences"]):
        return "User Profile: Optional field left blank during initial onboarding"
    if any(k in fn for k in ["explanation", "sentiment_score", "article_url", "summary"]):
        return "AI/Context Metadata: Optional enrichment attribute"
    if any(k in fn for k in ["deleted_at", "parent_id", "updated_at"]):
        return "Entity Hierarchy / Lifecycle: Top-level entity or unmodified record"
    return "Optional domain attribute with no value assigned"


def check_wrong_values(data: Any, endpoint: str) -> List[str]:
    anomalies = []
    if isinstance(data, dict):
        if "sector" in data:
            sec = str(data.get("sector") or "")
            if sec.isdigit() and len(sec) == 4:
                anomalies.append(f"Sector '{sec}' returned as numeric code instead of sector title")
        if "price" in data and isinstance(data["price"], (int, float)) and data["price"] < 0:
            anomalies.append(f"Negative price detected: {data['price']}")
        if "current" in data and isinstance(data["current"], (int, float)) and data["current"] < 0:
            anomalies.append(f"Negative current price detected: {data['current']}")
        for k, v in data.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                anomalies.append(f"Float anomaly NaN/Inf in field '{k}'")
            elif isinstance(v, (dict, list)):
                anomalies.extend(check_wrong_values(v, endpoint))
    elif isinstance(data, list):
        for item in data[:20]:
            anomalies.extend(check_wrong_values(item, endpoint))
    return anomalies


async def main():
    print("=== DYNAMIC OPENAPI FULL SPEC LIVE VERIFICATION AUDIT ===")
    token, admin_user_id, admin_email = fetch_seeded_token_and_user()
    log.info(f"Using Admin: {admin_email} (ID: {admin_user_id})")

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    public_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=25.0) as client:
        r = await client.get(f"{BASE_URL}/api/v1/openapi.json")
        openapi = r.json()
        paths = openapi.get("paths", {})
        log.info(f"Loaded {len(paths)} unique OpenAPI route paths.")

        results = []
        op_id = 0

        # Sample dynamic objects created during audit
        created_post_id = None
        created_alert_id = None
        created_txn_id = None
        created_watchlist_symbol = "OGDC"

        for path_template, methods in paths.items():
            for method_str, op_meta in methods.items():
                method = method_str.upper()
                if method not in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                    continue

                op_id += 1
                summary = op_meta.get("summary") or op_meta.get("operationId") or path_template
                tags = op_meta.get("tags") or ["General"]
                category = tags[0]
                security = op_meta.get("security", [])
                requires_auth = bool(security) or "/users/me" in path_template or "/portfolio" in path_template or "/watchlist" in path_template or "/notifications" in path_template

                # Resolve Path Parameters
                actual_path = path_template
                actual_path = actual_path.replace("{symbol}", "OGDC")
                actual_path = actual_path.replace("{stock_symbol}", "OGDC")
                actual_path = actual_path.replace("{ticker}", "OGDC")
                actual_path = actual_path.replace("{user_id}", admin_user_id)
                actual_path = actual_path.replace("{index_code}", "KSE100")
                actual_path = actual_path.replace("{category}", "high_dividend_yield")

                if "{post_id}" in actual_path:
                    if not created_post_id:
                        continue
                    actual_path = actual_path.replace("{post_id}", str(created_post_id))
                if "{alert_id}" in actual_path:
                    if not created_alert_id:
                        continue
                    actual_path = actual_path.replace("{alert_id}", str(created_alert_id))
                if "{transaction_id}" in actual_path:
                    if not created_txn_id:
                        continue
                    actual_path = actual_path.replace("{transaction_id}", str(created_txn_id))
                if "{comment_id}" in actual_path:
                    continue
                if "{article_id}" in actual_path:
                    continue
                if "{event_id}" in actual_path:
                    continue
                if "{report_id}" in actual_path:
                    continue

                # Prepare Query Parameters
                params = {}
                parameters = op_meta.get("parameters", [])
                for param in parameters:
                    p_name = param.get("name")
                    p_in = param.get("in")
                    p_required = param.get("required", False)
                    schema = param.get("schema", {})
                    if p_in == "query":
                        if p_name == "q":
                            params["q"] = "OGDC"
                        elif p_name == "symbol":
                            params["symbol"] = "OGDC"
                        elif p_name == "symbols":
                            params["symbols"] = "OGDC,PPL,HBL"
                        elif p_name == "limit":
                            params["limit"] = 5
                        elif p_name == "offset":
                            params["offset"] = 0
                        elif p_name == "range":
                            params["range"] = "1M"
                        elif p_name == "order":
                            params["order"] = "desc"
                        elif p_name == "sort_by":
                            params["sort_by"] = "volume"
                        elif p_name == "period":
                            params["period"] = 14
                        elif p_name == "sector":
                            params["sector"] = "COMMERCIAL BANKS"
                        elif p_name == "category":
                            params["category"] = "high_dividend_yield"
                        elif p_required:
                            params[p_name] = schema.get("default", "1")

                # Prepare Request Body for POST / PUT / PATCH
                body = None
                if method in ("POST", "PUT", "PATCH"):
                    if "community/posts" in actual_path and method == "POST":
                        body = {"post_type": "stock_analysis", "stock_symbol": "OGDC", "content": "Live Dynamic Audit: Comprehensive post test."}
                    elif "community/posts" in actual_path and "comments" in actual_path:
                        body = {"content": "Live dynamic test comment."}
                    elif "watchlist" in actual_path and method == "POST":
                        body = {"symbol": "OGDC", "notes": "Automated dynamic test item"}
                    elif "portfolio/transactions" in actual_path and method == "POST":
                        body = {"symbol": "OGDC", "transaction_type": "BUY", "quantity": 50, "price": 314.50, "transaction_date": datetime.now(timezone.utc).isoformat(), "notes": "Dynamic test buy"}
                    elif "notifications/alerts" in actual_path and method == "POST":
                        body = {"symbol": "OGDC", "condition_type": "PRICE_ABOVE", "threshold_value": 350.0, "is_active": True}
                    elif "users/me/risk-profile" in actual_path:
                        body = {"risk_tolerance": "moderate", "investment_horizon": "long_term", "sector_preferences": ["Commercial Banks", "Oil & Gas"]}
                    elif "users/me" in actual_path and method == "PATCH":
                        body = {"full_name": "Antigravity Dynamic Auditor", "phone_number": "+923001234567"}
                    elif "shariah/purification" in actual_path:
                        body = {"symbol": "OGDC", "shares_held": 1000, "dividend_income": 5000}
                    elif "auth/login" in actual_path:
                        continue  # Tested separately
                    elif "auth/signup" in actual_path:
                        continue
                    elif "auth/password" in actual_path:
                        continue
                    else:
                        # Skip arbitrary unmodeled writes
                        if method in ("PUT", "PATCH", "DELETE") and not requires_auth:
                            continue

                # Ensure base URL format
                url_path = actual_path if actual_path.startswith("/") else f"/{actual_path}"
                if not url_path.startswith("/api/v1") and not url_path.startswith("/health"):
                    url_path = f"/api/v1{url_path}"
                full_url = f"{BASE_URL}{url_path}"

                req_headers = headers if requires_auth else public_headers

                t0 = time.perf_counter()
                status_code = None
                data = None
                err = None
                try:
                    if method == "GET":
                        resp = await client.get(full_url, params=params, headers=req_headers)
                    elif method == "POST":
                        resp = await client.post(full_url, params=params, json=body, headers=req_headers)
                    elif method == "PUT":
                        resp = await client.put(full_url, params=params, json=body, headers=req_headers)
                    elif method == "PATCH":
                        resp = await client.patch(full_url, params=params, json=body, headers=req_headers)
                    elif method == "DELETE":
                        resp = await client.delete(full_url, params=params, headers=req_headers)

                    status_code = resp.status_code
                    try:
                        data = resp.json()
                    except Exception:
                        data = resp.text
                except Exception as exc:
                    err = str(exc)

                latency_ms = round((time.perf_counter() - t0) * 1000, 2)
                is_success = status_code in (200, 201, 204) or (status_code == 409 and "watchlist" in actual_path)

                # Capture dynamic IDs
                if is_success and isinstance(data, dict):
                    if "community/posts" in actual_path and method == "POST" and not created_post_id:
                        created_post_id = data.get("id") or data.get("post_id")
                    elif "notifications/alerts" in actual_path and method == "POST" and not created_alert_id:
                        created_alert_id = data.get("id") or data.get("alert_id")
                    elif "portfolio/transactions" in actual_path and method == "POST" and not created_txn_id:
                        created_txn_id = data.get("id") or data.get("transaction_id")

                # Payload Inspection
                nulls = analyze_payload_nulls(data)
                has_nulls = len(nulls) > 0
                null_explanations = []
                if has_nulls:
                    for n in nulls[:8]:
                        null_explanations.append({
                            "field": n["field"],
                            "reason": infer_null_reason(n["field"], actual_path)
                        })

                wrong_values = check_wrong_values(data, actual_path)

                res_item = {
                    "op_id": op_id,
                    "category": category,
                    "summary": summary,
                    "method": method,
                    "endpoint": url_path,
                    "query_params": params,
                    "request_body": body,
                    "requires_auth": requires_auth,
                    "status_code": status_code,
                    "is_success": is_success,
                    "latency_ms": latency_ms,
                    "is_empty": (data is None or data == [] or data == {}),
                    "has_null_values": has_nulls,
                    "null_count": len(nulls),
                    "null_analysis": null_explanations,
                    "anomalies_or_wrong_values": wrong_values,
                    "error": err,
                    "response_sample": (str(data)[:200] + "..." if len(str(data)) > 200 else data) if data else None,
                }
                results.append(res_item)
                stat_tag = f"[{status_code}]" if status_code else "[ERR]"
                null_tag = f" | Nulls: {len(nulls)}" if has_nulls else ""
                anom_tag = f" | ANOMALY: {wrong_values}" if wrong_values else ""
                log.info(f"#{op_id:03d} {method:6} {url_path[:42]:42} -> {stat_tag} in {latency_ms:6.1f}ms{null_tag}{anom_tag}")

        # Post-test Cleanup
        if created_post_id:
            try:
                await client.delete(f"{BASE_URL}/api/v1/community/posts/{created_post_id}", headers=headers)
            except Exception:
                pass
        if created_alert_id:
            try:
                await client.delete(f"{BASE_URL}/api/v1/notifications/alerts/{created_alert_id}", headers=headers)
            except Exception:
                pass
        if created_watchlist_symbol:
            try:
                await client.delete(f"{BASE_URL}/api/v1/watchlist/{created_watchlist_symbol}", headers=headers)
            except Exception:
                pass

        # Summary Report
        total_ops = len(results)
        passed_ops = sum(1 for r in results if r["is_success"])
        failed_ops = total_ops - passed_ops
        avg_lat = round(sum(r["latency_ms"] for r in results) / total_ops, 2) if total_ops else 0.0
        with_nulls = sum(1 for r in results if r.get("has_null_values"))
        with_anomalies = sum(1 for r in results if r.get("anomalies_or_wrong_values"))

        categories_summary = {}
        for cat in sorted(list(set(r["category"] for r in results))):
            c_items = [r for r in results if r["category"] == cat]
            c_pass = sum(1 for r in c_items if r["is_success"])
            categories_summary[cat] = {
                "total": len(c_items),
                "passed": c_pass,
                "failed": len(c_items) - c_pass,
                "pass_rate_pct": round(c_pass / len(c_items) * 100, 1),
                "avg_latency_ms": round(sum(r["latency_ms"] for r in c_items) / len(c_items), 2),
            }

        full_report = {
            "metadata": {
                "title": "Live Oracle PSX Backend Dynamic OpenAPI Complete Audit",
                "target_host": REMOTE_HOST,
                "base_url": BASE_URL,
                "audited_at": datetime.now(timezone.utc).isoformat(),
                "admin_user": admin_email,
                "total_operations_audited": total_ops,
                "passed_operations": passed_ops,
                "failed_operations": failed_ops,
                "overall_success_rate_pct": round(passed_ops / total_ops * 100, 2) if total_ops else 0,
                "average_latency_ms": avg_lat,
                "endpoints_with_null_fields": with_nulls,
                "endpoints_with_anomalies": with_anomalies,
            },
            "category_summary": categories_summary,
            "detailed_operations": results,
        }

        out_path = Path(r"d:\FYP\Basarat-fyp-official\backend\reports\live_oracle_dynamic_openapi_audit_2026-10-04.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2)

        print("\n" + "=" * 70)
        print("DYNAMIC OPENAPI FULL AUDIT COMPLETE")
        print(f"Report Generated: {out_path}")
        print(f"Total Operations: {total_ops}")
        print(f"Passed: {passed_ops} ({full_report['metadata']['overall_success_rate_pct']}%)")
        print(f"Failed: {failed_ops}")
        print(f"Average Latency: {avg_lat} ms")
        print(f"Endpoints with Nulls: {with_nulls}")
        print(f"Endpoints with Anomalies: {with_anomalies}")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
