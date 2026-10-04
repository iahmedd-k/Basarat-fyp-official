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
log = logging.getLogger("live_audit")

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
    """Recursively identify null/None values in JSON responses."""
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
    """Infer why a field might be null based on domain semantics."""
    fn = field_name.lower()
    if any(k in fn for k in ["open", "high", "low", "ldcp", "change", "change_pct"]):
        return "Market data feed: No intraday trade recorded for illiquid stock / off-hours session"
    if any(k in fn for k in ["pe_ratio", "pb_ratio", "eps", "dividend_yield"]):
        return "Fundamentals: Negative earnings or company did not declare cash dividends"
    if any(k in fn for k in ["target_price", "stop_loss", "expected_return"]):
        return "ML Recommendation: Sideways/Hold recommendations do not project directional target prices"
    if any(k in fn for k in ["bio", "full_name", "phone", "avatar_url", "risk_tolerance"]):
        return "User Profile: Optional field not provided by user during onboarding"
    return "Optional domain attribute with no value assigned"


def check_wrong_values(data: Any, endpoint: str) -> List[str]:
    """Check for suspicious or invalid values in API response."""
    anomalies = []
    if isinstance(data, dict):
        if "sector" in data:
            sec = str(data.get("sector") or "")
            if sec.isdigit() and len(sec) == 4:
                anomalies.append(f"Sector '{sec}' returned as raw numeric code instead of sector title")
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
    print("=== LIVE ORACLE BACKEND COMPREHENSIVE ENDPOINT AUDIT ===")
    print(f"Target Base URL: {BASE_URL}")

    # 1. Fetch live admin token
    log.info("Fetching seeded Admin JWT token from live container...")
    try:
        token, admin_user_id, admin_email = fetch_seeded_token_and_user()
        log.info(f"Retrieved token for {admin_email} (ID: {admin_user_id})")
    except Exception as e:
        log.error(f"Failed to fetch live admin token: {e}")
        return

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    public_headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # 2. Build comprehensive test cases across all modules
    test_cases = []

    # System & Health
    test_cases.append({"category": "System", "method": "GET", "path": "/health", "auth": False, "desc": "Liveness Probe"})
    test_cases.append({"category": "System", "method": "GET", "path": "/api/v1/health/ready", "auth": False, "desc": "Readiness Probe"})

    # Market Module
    test_cases.extend([
        {"category": "Market", "method": "GET", "path": "/api/v1/market/live", "auth": False, "desc": "Market Status & Transport Info"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/indices", "auth": False, "desc": "Benchmark Indices Overview"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/indices/kse-100", "auth": False, "desc": "KSE-100 Constituents"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/indices/kse-30", "auth": False, "desc": "KSE-30 Constituents"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/indices/kmi-30", "auth": False, "desc": "KMI-30 Islamic Constituents"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/gainers?limit=5", "auth": False, "desc": "Top Gainers (Filter: limit=5)"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/losers?limit=5", "auth": False, "desc": "Top Losers (Filter: limit=5)"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/volume-spikes?limit=5", "auth": False, "desc": "Volume Spikes (Filter: limit=5)"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/sentiment-overview", "auth": False, "desc": "Market Sentiment Overview"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/sectors/performance?order=desc", "auth": False, "desc": "Sector Performance (Order: desc)"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/sectors/performance?order=asc", "auth": False, "desc": "Sector Performance (Order: asc)"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/quotes?limit=10&sort_by=volume&order=desc", "auth": False, "desc": "Market Quotes (Filter: limit=10, sort=volume)"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/quotes?sector=COMMERCIAL%20BANKS&limit=5", "auth": False, "desc": "Market Quotes (Filter: sector=COMMERCIAL BANKS)"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/curated?category=high_dividend_yield&limit=5", "auth": False, "desc": "Curated Stocks: High Dividend Yield"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/curated?category=value_investing&limit=5", "auth": False, "desc": "Curated Stocks: Value Investing"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/curated?category=most_liquid&limit=5", "auth": False, "desc": "Curated Stocks: Most Liquid"},
        {"category": "Market", "method": "GET", "path": "/api/v1/market/curated?category=best_returning_1y&limit=5", "auth": False, "desc": "Curated Stocks: Best 1-Year Return"},
    ])

    # Stocks Module
    test_cases.extend([
        {"category": "Stocks", "method": "GET", "path": "/api/v1/stocks/search?q=OGDC&limit=5", "auth": False, "desc": "Search Stock (q=OGDC)"},
        {"category": "Stocks", "method": "GET", "path": "/api/v1/stocks/search?q=Habib&limit=5", "auth": False, "desc": "Search Stock Alias (q=Habib)"},
        {"category": "Stocks", "method": "GET", "path": "/api/v1/stocks/OGDC/overview", "auth": False, "desc": "Stock Snapshot: OGDC"},
        {"category": "Stocks", "method": "GET", "path": "/api/v1/stocks/HBL/overview", "auth": False, "desc": "Stock Snapshot: HBL"},
        {"category": "Stocks", "method": "GET", "path": "/api/v1/stocks/SYS/overview", "auth": False, "desc": "Stock Snapshot: SYS"},
        {"category": "Stocks", "method": "GET", "path": "/api/v1/stocks/OGDC/price-history?range=1M", "auth": False, "desc": "Price History 1M: OGDC"},
        {"category": "Stocks", "method": "GET", "path": "/api/v1/stocks/OGDC/price-history?range=1Y", "auth": False, "desc": "Price History 1Y: OGDC"},
        {"category": "Stocks", "method": "GET", "path": "/api/v1/stocks/OGDC/technical-indicators?period=14&limit=10", "auth": False, "desc": "Technical Indicators: OGDC"},
        {"category": "Stocks", "method": "GET", "path": "/api/v1/stocks/OGDC/fundamentals", "auth": False, "desc": "Fundamentals: OGDC"},
    ])

    # Shariah Compliance Module
    test_cases.extend([
        {"category": "Shariah", "method": "GET", "path": "/api/v1/shariah/kmi30", "auth": False, "desc": "KMI-30 Islamic Index Screened List"},
        {"category": "Shariah", "method": "GET", "path": "/api/v1/shariah/OGDC", "auth": False, "desc": "Shariah Screening: OGDC (Compliant)"},
        {"category": "Shariah", "method": "GET", "path": "/api/v1/shariah/HBL", "auth": False, "desc": "Shariah Screening: HBL (Non-Compliant Bank)"},
        {"category": "Shariah", "method": "GET", "path": "/api/v1/shariah/SYS", "auth": False, "desc": "Shariah Screening: SYS"},
        {"category": "Shariah", "method": "GET", "path": "/api/v1/shariah/OGDC/criteria", "auth": False, "desc": "Detailed 6-Criteria Screening: OGDC"},
        {"category": "Shariah", "method": "GET", "path": "/api/v1/shariah/OGDC/purification?dividend_income=5000", "auth": False, "desc": "Calculate Purification Amount: OGDC"},
    ])

    # AI & ML Recommendations Module
    test_cases.extend([
        {"category": "Recommendations", "method": "GET", "path": "/api/v1/recommendations", "auth": True, "desc": "AI Recommendations List"},
        {"category": "Recommendations", "method": "GET", "path": "/api/v1/recommendations/engine-weights", "auth": True, "desc": "Engine Model Weights"},
        {"category": "Recommendations", "method": "POST", "path": "/api/v1/recommendations/engine-weights", "auth": True, "body": {"gru_weight": 0.35, "technical_weight": 0.25, "fundamental_weight": 0.25, "sentiment_weight": 0.15}, "desc": "Set Engine Weights (POST)"},
        {"category": "Recommendations", "method": "GET", "path": "/api/v1/recommendations/OGDC", "auth": True, "desc": "Stock Recommendation: OGDC"},
        {"category": "Recommendations", "method": "GET", "path": "/api/v1/recommendations/OGDC/target-stop", "auth": True, "desc": "Target Price & Stop Loss: OGDC"},
        {"category": "Recommendations", "method": "GET", "path": "/api/v1/recommendations/SYS", "auth": True, "desc": "Stock Recommendation: SYS"},
    ])

    # Sentiment & News Module
    test_cases.extend([
        {"category": "News & Sentiment", "method": "GET", "path": "/api/v1/news?limit=10", "auth": True, "desc": "Financial News Feed (limit=10)"},
        {"category": "News & Sentiment", "method": "GET", "path": "/api/v1/news?symbol=OGDC&limit=5", "auth": True, "desc": "News Filtered by Symbol OGDC"},
        {"category": "News & Sentiment", "method": "GET", "path": "/api/v1/sentiment/market-overview", "auth": True, "desc": "Market-wide Sentiment Overview"},
        {"category": "News & Sentiment", "method": "GET", "path": "/api/v1/sentiment/OGDC", "auth": True, "desc": "Stock Sentiment: OGDC"},
        {"category": "News & Sentiment", "method": "GET", "path": "/api/v1/sentiment/OGDC/history", "auth": True, "desc": "Sentiment History: OGDC"},
        {"category": "News & Sentiment", "method": "GET", "path": "/api/v1/sentiment/OGDC/news", "auth": True, "desc": "Sentiment News: OGDC"},
    ])

    # Risk Profiling & Analytics Module
    test_cases.extend([
        {"category": "Risk Profiling", "method": "GET", "path": "/api/v1/users/me/risk-profile", "auth": True, "desc": "User Risk Profile Settings"},
        {"category": "Risk Profiling", "method": "GET", "path": "/api/v1/users/risk-profile/options", "auth": False, "desc": "Allowed Risk Tolerances & Sectors"},
        {"category": "Risk Analytics", "method": "GET", "path": "/api/v1/risk/var?confidence=95&horizon=1D", "auth": True, "desc": "Portfolio Value-at-Risk (VaR)"},
        {"category": "Risk Analytics", "method": "GET", "path": "/api/v1/risk/stress-test?scenario=2008_crash", "auth": True, "desc": "Portfolio Stress Test (2008 Crash)"},
    ])

    # Users Module
    test_cases.extend([
        {"category": "Users", "method": "GET", "path": "/api/v1/users/me", "auth": True, "desc": "Current User Profile"},
        {"category": "Users", "method": "PATCH", "path": "/api/v1/users/me", "auth": True, "body": {"full_name": "Antigravity Live Tester", "phone_number": "+923001234567"}, "desc": "Update Profile (PATCH)"},
        {"category": "Users", "method": "PATCH", "path": "/api/v1/users/me/risk-profile", "auth": True, "body": {"risk_tolerance": "moderate", "investment_horizon": "long_term", "sector_preferences": ["Commercial Banks", "Oil & Gas"]}, "desc": "Update Risk Profile (PATCH)"},
    ])

    # Community Module
    test_cases.extend([
        {"category": "Community", "method": "GET", "path": "/api/v1/community/feed?limit=10", "auth": True, "desc": "Community Discussion Feed"},
        {"category": "Community", "method": "GET", "path": "/api/v1/community/posts/search?q=OGDC&limit=5", "auth": True, "desc": "Community Feed Search (q=OGDC)"},
        {"category": "Community", "method": "GET", "path": "/api/v1/community/me", "auth": True, "desc": "Community User Self Profile"},
        {"category": "Community", "method": "POST", "path": "/api/v1/community/posts", "auth": True, "form_data": {"content": "Live Automated Audit: Testing stock discussion post lifecycle.", "post_type": "GENERAL_MARKET"}, "desc": "Create Community Post (POST)"},
    ])

    # Watchlists Module
    test_cases.extend([
        {"category": "Watchlist", "method": "GET", "path": "/api/v1/watchlists", "auth": True, "desc": "Get User Watchlists"},
        {"category": "Watchlist", "method": "GET", "path": "/api/v1/watchlists/default", "auth": True, "desc": "Get Default Watchlist"},
        {"category": "Watchlist", "method": "GET", "path": "/api/v1/watchlists/check/OGDC", "auth": True, "desc": "Check Symbol in Watchlist"},
        {"category": "Watchlist", "method": "POST", "path": "/api/v1/watchlists", "auth": True, "body": {"name": "Audit Watchlist", "description": "Audited via live runner", "symbols": ["OGDC", "SYS"]}, "desc": "Create Custom Watchlist (POST)"},
    ])

    # Portfolio Module
    test_cases.extend([
        {"category": "Portfolio", "method": "GET", "path": "/api/v1/portfolio", "auth": True, "desc": "Complete Portfolio Overview"},
        {"category": "Portfolio", "method": "GET", "path": "/api/v1/portfolio/holdings", "auth": True, "desc": "Portfolio Active Holdings"},
        {"category": "Portfolio", "method": "GET", "path": "/api/v1/portfolio/pnl", "auth": True, "desc": "Portfolio P&L Summary"},
        {"category": "Portfolio", "method": "GET", "path": "/api/v1/portfolio/performance?range=1M", "auth": True, "desc": "Portfolio Performance History"},
        {"category": "Portfolio", "method": "GET", "path": "/api/v1/portfolio/allocation", "auth": True, "desc": "Portfolio Allocation by Sector"},
        {"category": "Portfolio", "method": "GET", "path": "/api/v1/portfolio/transactions", "auth": True, "desc": "Portfolio Transactions History"},
        {"category": "Portfolio", "method": "POST", "path": "/api/v1/portfolio/transactions", "auth": True, "body": {"symbol": "OGDC", "transaction_type": "BUY", "quantity": 100, "price": 314.50, "transaction_date": "2026-10-04", "fee": 15.0}, "desc": "Add Portfolio Transaction (POST)"},
    ])

    # IPO Module
    test_cases.extend([
        {"category": "IPO", "method": "GET", "path": "/api/v1/ipos", "auth": False, "desc": "List IPOs Directory"},
        {"category": "IPO", "method": "GET", "path": "/api/v1/ipos/calendar", "auth": False, "desc": "IPO Calendar Milestones"},
        {"category": "IPO", "method": "GET", "path": "/api/v1/ipos/performance", "auth": False, "desc": "IPO Listing Performance"},
    ])

    # ETFs Module
    test_cases.extend([
        {"category": "ETFs", "method": "GET", "path": "/api/v1/etfs", "auth": False, "desc": "List PSX ETFs Directory"},
    ])

    # Notification & Alerts Module
    test_cases.extend([
        {"category": "Alerts", "method": "GET", "path": "/api/v1/notifications", "auth": True, "desc": "User Notifications List"},
        {"category": "Alerts", "method": "GET", "path": "/api/v1/alerts/rules", "auth": True, "desc": "User Price Alert Rules"},
        {"category": "Alerts", "method": "POST", "path": "/api/v1/alerts/rules", "auth": True, "body": {"symbol": "OGDC", "condition": "price_above", "threshold": 350.0}, "desc": "Create Alert Rule (POST)"},
        {"category": "Alerts", "method": "POST", "path": "/api/v1/alerts/quick-rule", "auth": True, "body": {"symbol": "OGDC", "percent_threshold": 3.0, "direction": "both"}, "desc": "Create Quick 1-Click Alert (POST)"},
    ])

    # Dynamic CRUD trackers for cleanup
    created_post_id = None
    created_watchlist_id = None
    created_alert_rule_id = None

    results = []
    total_latency = 0.0
    passed_count = 0
    failed_count = 0

    log.info(f"Executing {len(test_cases)} primary endpoint verifications...")

    async with httpx.AsyncClient(timeout=25.0) as client:
        for idx, tc in enumerate(test_cases, 1):
            method = tc["method"]
            path = tc["path"]
            auth = tc.get("auth", False)
            body = tc.get("body")
            form_data = tc.get("form_data")
            url = f"{BASE_URL}{path}"

            req_headers = {"Authorization": f"Bearer {token}"} if auth else {}
            if body is not None:
                req_headers["Content-Type"] = "application/json"

            t0 = time.perf_counter()
            resp = None
            err = None
            status_code = None
            data = None
            try:
                if method == "GET":
                    resp = await client.get(url, headers=req_headers)
                elif method == "POST":
                    if form_data:
                        resp = await client.post(url, data=form_data, headers=req_headers)
                    else:
                        resp = await client.post(url, json=body, headers=req_headers)
                elif method == "PUT":
                    resp = await client.put(url, json=body, headers=req_headers)
                elif method == "PATCH":
                    resp = await client.patch(url, json=body, headers=req_headers)
                elif method == "DELETE":
                    resp = await client.delete(url, headers=req_headers)

                status_code = resp.status_code
                try:
                    data = resp.json()
                except Exception:
                    data = resp.text
            except Exception as exc:
                err = str(exc)

            latency_ms = round((time.perf_counter() - t0) * 1000, 2)
            total_latency += latency_ms

            is_success = status_code in (200, 201, 204)
            if is_success:
                passed_count += 1
            else:
                failed_count += 1

            is_empty = False
            if data is None or data == "" or data == [] or data == {}:
                is_empty = True

            nulls = analyze_payload_nulls(data)
            has_nulls = len(nulls) > 0
            null_explanations = []
            if has_nulls:
                for n in nulls[:10]:
                    reason = infer_null_reason(n["field"], path)
                    null_explanations.append({"field": n["field"], "reason": reason})

            wrong_values = check_wrong_values(data, path)

            # Capture IDs for subsequent CRUD steps
            if is_success and isinstance(data, dict):
                if "community/posts" in path and method == "POST":
                    created_post_id = data.get("id")
                elif "watchlists" in path and method == "POST":
                    created_watchlist_id = data.get("id")
                elif "alerts/rules" in path and method == "POST":
                    created_alert_rule_id = data.get("id")

            res_entry = {
                "id": idx,
                "category": tc["category"],
                "name": tc["desc"],
                "method": method,
                "path": path,
                "url": url,
                "requires_auth": auth,
                "request_payload": body or form_data,
                "status_code": status_code,
                "is_success": is_success,
                "latency_ms": latency_ms,
                "is_empty": is_empty,
                "has_null_values": has_nulls,
                "null_count": len(nulls),
                "null_analysis": null_explanations,
                "anomalies_or_wrong_values": wrong_values,
                "error": err,
                "response_sample": data if (isinstance(data, (dict, list)) and len(str(data)) < 400) else (str(data)[:250] + "..." if data else None),
            }
            results.append(res_entry)
            status_tag = f"[{status_code}]" if status_code else "[ERR]"
            null_tag = f" (nulls: {len(nulls)})" if has_nulls else ""
            log.info(f"[{idx}/{len(test_cases)}] {method:6} {path[:40]:40} -> {status_tag} in {latency_ms:6.1f}ms {null_tag}")

        # Complete Lifecycle CRUD Cleanups
        log.info("Executing CRUD Lifecycle Updates & Cleanups...")

        if created_post_id:
            # Comment
            t0 = time.perf_counter()
            r_c = await client.post(
                f"{BASE_URL}/api/v1/community/posts/{created_post_id}/comments",
                json={"content": "Automated audit comment"},
                headers={"Authorization": f"Bearer {token}"},
            )
            lat = round((time.perf_counter() - t0) * 1000, 2)
            results.append({
                "id": len(results) + 1,
                "category": "Community CRUD",
                "name": "Add Comment to Post (POST)",
                "method": "POST",
                "path": f"/api/v1/community/posts/{created_post_id}/comments",
                "status_code": r_c.status_code,
                "is_success": r_c.status_code in (200, 201),
                "latency_ms": lat,
                "is_empty": False,
                "has_null_values": False,
                "anomalies_or_wrong_values": [],
            })

            # Delete Post
            t0 = time.perf_counter()
            r_d = await client.delete(f"{BASE_URL}/api/v1/community/posts/{created_post_id}", headers={"Authorization": f"Bearer {token}"})
            lat = round((time.perf_counter() - t0) * 1000, 2)
            results.append({
                "id": len(results) + 1,
                "category": "Community CRUD",
                "name": "Delete Community Post (DELETE)",
                "method": "DELETE",
                "path": f"/api/v1/community/posts/{created_post_id}",
                "status_code": r_d.status_code,
                "is_success": r_d.status_code in (200, 204),
                "latency_ms": lat,
                "is_empty": False,
                "has_null_values": False,
                "anomalies_or_wrong_values": [],
            })

        if created_watchlist_id:
            t0 = time.perf_counter()
            r_wdel = await client.delete(f"{BASE_URL}/api/v1/watchlists/{created_watchlist_id}", headers={"Authorization": f"Bearer {token}"})
            lat = round((time.perf_counter() - t0) * 1000, 2)
            results.append({
                "id": len(results) + 1,
                "category": "Watchlist CRUD",
                "name": "Delete Custom Watchlist (DELETE)",
                "method": "DELETE",
                "path": f"/api/v1/watchlists/{created_watchlist_id}",
                "status_code": r_wdel.status_code,
                "is_success": r_wdel.status_code in (200, 204),
                "latency_ms": lat,
                "is_empty": False,
                "has_null_values": False,
                "anomalies_or_wrong_values": [],
            })

        if created_alert_rule_id:
            t0 = time.perf_counter()
            r_adel = await client.delete(f"{BASE_URL}/api/v1/alerts/rules/stock/OGDC", headers={"Authorization": f"Bearer {token}"})
            lat = round((time.perf_counter() - t0) * 1000, 2)
            results.append({
                "id": len(results) + 1,
                "category": "Alerts CRUD",
                "name": "Delete Alert Rules by Stock (DELETE)",
                "method": "DELETE",
                "path": "/api/v1/alerts/rules/stock/OGDC",
                "status_code": r_adel.status_code,
                "is_success": r_adel.status_code in (200, 204),
                "latency_ms": lat,
                "is_empty": False,
                "has_null_values": False,
                "anomalies_or_wrong_values": [],
            })

    # Summary Statistics
    total_endpoints = len(results)
    successful = sum(1 for r in results if r["is_success"])
    failed = total_endpoints - successful
    avg_latency = round(total_latency / total_endpoints, 2) if total_endpoints else 0
    endpoints_with_nulls = sum(1 for r in results if r.get("has_null_values"))
    endpoints_with_anomalies = sum(1 for r in results if r.get("anomalies_or_wrong_values"))

    report = {
        "metadata": {
            "title": "Live Oracle PSX Backend Comprehensive Endpoint Verification Audit",
            "base_url": BASE_URL,
            "audited_at": datetime.now(timezone.utc).isoformat(),
            "admin_user": admin_email,
            "admin_id": admin_user_id,
            "total_endpoints_tested": total_endpoints,
            "successful_endpoints": successful,
            "failed_endpoints": failed,
            "success_rate_pct": round(successful / total_endpoints * 100, 2) if total_endpoints else 0,
            "average_latency_ms": avg_latency,
            "endpoints_with_nulls_count": endpoints_with_nulls,
            "endpoints_with_anomalies_count": endpoints_with_anomalies,
        },
        "audit_summary_by_category": {},
        "results": results,
    }

    categories = sorted(list(set(r["category"] for r in results)))
    for cat in categories:
        cat_items = [r for r in results if r["category"] == cat]
        cat_success = sum(1 for r in cat_items if r["is_success"])
        report["audit_summary_by_category"][cat] = {
            "total": len(cat_items),
            "passed": cat_success,
            "failed": len(cat_items) - cat_success,
            "avg_latency_ms": round(sum(r["latency_ms"] for r in cat_items) / len(cat_items), 2),
        }

    out_path = Path(r"d:\FYP\Basarat-fyp-official\backend\reports\live_oracle_comprehensive_audit_2026-10-04.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 60)
    print("AUDIT COMPLETED SUCCESSFULLY!")
    print(f"Report File: {out_path}")
    print(f"Total Operations Tested: {total_endpoints}")
    print(f"Successful: {successful} ({report['metadata']['success_rate_pct']}%)")
    print(f"Failed: {failed}")
    print(f"Average Response Latency: {avg_latency} ms")
    print(f"Endpoints with Null Values: {endpoints_with_nulls}")
    print(f"Endpoints with Anomalies/Wrong Values: {endpoints_with_anomalies}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
