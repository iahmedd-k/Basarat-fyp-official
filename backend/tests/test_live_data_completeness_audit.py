"""
========================================================================================
BASARAT LIVE AWS API - DEEP DATA COMPLETENESS & NULL-FIELD INTEGRITY AUDIT
Target: http://16.16.26.247:8000/api/v1

This script performs a deep data quality and null-field audit on live AWS API responses:
  1. Recursively inspects every nested JSON object and array.
  2. Flags unexpected None/null values, empty collections [], blank strings "", and NaNs.
  3. Validates essential domain schema fields.
  4. Calculates Data Completeness (%) for every module.
========================================================================================
"""

import os
import sys
import json
import time
import math
import requests
from typing import Any, Dict, List, Tuple

BASE_URL = "http://16.16.26.247:8000/api/v1"
HEALTH_URL = "http://16.16.26.247:8000"
ADMIN_EMAIL = "admin@basarat.pk"
ADMIN_PASSWORD = "TestPassword12345!"

class DataIntegrityAuditor:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip("/")
        self.session = requests.Session()
        self.session.headers.update({"Content-Type": "application/json", "Accept": "application/json"})
        self.access_token = None
        self.results: List[Dict[str, Any]] = []

    def set_token(self, token: str):
        self.access_token = token
        self.session.headers.update({"Authorization": f"Bearer {token}"})

    def analyze_payload(self, data: Any, path: str = "") -> Tuple[int, int, List[str], List[str]]:
        """
        Recursively scans a data structure.
        Returns: (total_keys, populated_keys, list_of_null_paths, list_of_empty_paths)
        """
        total = 0
        populated = 0
        null_paths = []
        empty_paths = []

        if isinstance(data, dict):
            for k, v in data.items():
                current_path = f"{path}.{k}" if path else k
                total += 1
                if v is None:
                    null_paths.append(current_path)
                elif isinstance(v, (dict, list)):
                    if len(v) == 0:
                        empty_paths.append(f"{current_path} (empty {type(v).__name__})")
                    else:
                        populated += 1
                    sub_total, sub_pop, sub_nulls, sub_empties = self.analyze_payload(v, current_path)
                    total += sub_total
                    populated += sub_pop
                    null_paths.extend(sub_nulls)
                    empty_paths.extend(sub_empties)
                elif isinstance(v, str):
                    if v.strip() == "":
                        empty_paths.append(f"{current_path} (blank string)")
                    else:
                        populated += 1
                elif isinstance(v, (int, float)):
                    if math.isnan(v) or math.isinf(v):
                        null_paths.append(f"{current_path} (NaN/Inf)")
                    else:
                        populated += 1
                else:
                    populated += 1
        elif isinstance(data, list):
            # Inspect first up to 5 items to assess structure
            sample_items = data[:5]
            for i, item in enumerate(sample_items):
                current_path = f"{path}[{i}]"
                sub_total, sub_pop, sub_nulls, sub_empties = self.analyze_payload(item, current_path)
                total += sub_total
                populated += sub_pop
                null_paths.extend(sub_nulls)
                empty_paths.extend(sub_empties)

        return total, populated, null_paths, empty_paths

    def audit_endpoint(
        self,
        module: str,
        method: str,
        endpoint: str,
        required_keys: List[str] = None,
        json_body: Dict[str, Any] = None,
        expected_status: int = 200,
        allow_empty: bool = False,
        full_url: str = None
    ) -> Dict[str, Any]:
        url = full_url if full_url else f"{self.base_url}{endpoint}"
        t0 = time.time()
        try:
            if method.upper() == "GET":
                resp = self.session.get(url, timeout=30)
            elif method.upper() == "POST":
                resp = self.session.post(url, json=json_body, timeout=30)
            elif method.upper() == "PATCH":
                resp = self.session.patch(url, json=json_body, timeout=30)
            else:
                resp = self.session.request(method, url, json=json_body, timeout=30)

            duration = round((time.time() - t0) * 1000, 1)
            status = resp.status_code

            if status != expected_status:
                record = {
                    "module": module,
                    "method": method,
                    "endpoint": endpoint,
                    "status": status,
                    "duration_ms": duration,
                    "completeness_pct": 0.0,
                    "total_fields": 0,
                    "populated_fields": 0,
                    "null_paths": [f"HTTP {status} instead of {expected_status}"],
                    "empty_paths": [],
                    "missing_keys": required_keys or [],
                    "verdict": "FAIL"
                }
                self.results.append(record)
                return record

            try:
                data = resp.json()
            except Exception:
                data = None

            missing_keys = []
            if required_keys and isinstance(data, dict):
                for k in required_keys:
                    if k not in data:
                        missing_keys.append(k)

            total_fields, pop_fields, null_paths, empty_paths = self.analyze_payload(data)

            # Completeness formula
            if total_fields > 0:
                pct = round((pop_fields / total_fields) * 100, 1)
            else:
                pct = 100.0 if not required_keys else 0.0

            # Verdict evaluation
            verdict = "COMPLETE"
            if missing_keys or (pct < 70.0 and not allow_empty):
                verdict = "INCOMPLETE"
            elif null_paths or (empty_paths and not allow_empty):
                verdict = "PARTIAL_NULLS" if pct >= 70.0 else "INCOMPLETE"

            record = {
                "module": module,
                "method": method,
                "endpoint": endpoint,
                "status": status,
                "duration_ms": duration,
                "completeness_pct": pct,
                "total_fields": total_fields,
                "populated_fields": pop_fields,
                "null_paths": null_paths,
                "empty_paths": empty_paths,
                "missing_keys": missing_keys,
                "verdict": verdict,
                "sample_data": data if isinstance(data, (dict, list)) else str(data)[:100]
            }
            self.results.append(record)
            return record

        except Exception as exc:
            duration = round((time.time() - t0) * 1000, 1)
            record = {
                "module": module,
                "method": method,
                "endpoint": endpoint,
                "status": 0,
                "duration_ms": duration,
                "completeness_pct": 0.0,
                "total_fields": 0,
                "populated_fields": 0,
                "null_paths": [str(exc)],
                "empty_paths": [],
                "missing_keys": required_keys or [],
                "verdict": "ERROR"
            }
            self.results.append(record)
            return record


def run_full_completeness_audit():
    auditor = DataIntegrityAuditor(BASE_URL)
    print("=" * 115)
    print(" BASARAT PRODUCTION DATA COMPLETENESS & NULL-FIELD AUDIT")
    print(f" TARGET: {BASE_URL}")
    print("=" * 115)

    # 1. HEALTH & SYSTEM
    print("\n[*] 1. System Health...")
    auditor.audit_endpoint(
        module="Health & System",
        method="GET",
        endpoint="/health",
        full_url=f"{HEALTH_URL}/health",
        required_keys=["status"]
    )
    auditor.audit_endpoint(
        module="Health & System",
        method="GET",
        endpoint="/health/ready",
        full_url=f"{HEALTH_URL}/health/ready"
    )

    # 2. AUTHENTICATION & USER PROFILE
    print("\n[*] 2. Authenticating Admin User & Inspecting User Profile...")
    login_rec = auditor.audit_endpoint(
        module="Auth & Security",
        method="POST",
        endpoint="/auth/login",
        json_body={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        required_keys=["access_token", "token_type", "user"]
    )
    if login_rec["status"] == 200 and isinstance(login_rec.get("sample_data"), dict):
        token = login_rec["sample_data"].get("access_token")
        auditor.set_token(token)
        print(f"    [+] Logged in successfully. Token acquired.")
    else:
        print(f"    [-] Authentication failed: {login_rec['null_paths']}")

    auditor.audit_endpoint(
        module="User Profile",
        method="GET",
        endpoint="/users/me",
        required_keys=["id", "email", "full_name", "role", "is_active"]
    )
    auditor.audit_endpoint(
        module="User Profile",
        method="GET",
        endpoint="/users/investment-profile/options"
    )

    # 3. MARKET OVERVIEW & BENCHMARKS
    print("\n[*] 3. Auditing Market Overview & Benchmark Indices...")
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/indices"
    )
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/indices/kse-100"
    )
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/indices/kse-30"
    )
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/indices/kmi-30"
    )
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/sectors/performance"
    )
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/gainers"
    )
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/losers"
    )
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/volume-spikes"
    )
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/sentiment-overview"
    )
    auditor.audit_endpoint(
        module="Market Overview",
        method="GET",
        endpoint="/market/quotes"
    )

    # 4. STOCKS DIRECTORY & ANALYTICS
    print("\n[*] 4. Auditing Stock Detail & Financial Metrics...")
    auditor.audit_endpoint(
        module="Stocks Engine",
        method="GET",
        endpoint="/stocks/search?q=OGDC"
    )
    auditor.audit_endpoint(
        module="Stocks Engine",
        method="GET",
        endpoint="/stocks/OGDC/overview",
        required_keys=["symbol", "current_price"]
    )
    auditor.audit_endpoint(
        module="Stocks Engine",
        method="GET",
        endpoint="/stocks/OGDC/price-history"
    )
    auditor.audit_endpoint(
        module="Stocks Engine",
        method="GET",
        endpoint="/stocks/OGDC/technical-indicators"
    )
    auditor.audit_endpoint(
        module="Stocks Engine",
        method="GET",
        endpoint="/stocks/OGDC/fundamentals"
    )

    # 5. AI RECOMMENDATIONS & SIGNALS
    print("\n[*] 5. Auditing AI Stock Recommendations...")
    auditor.audit_endpoint(
        module="AI Recommendations",
        method="GET",
        endpoint="/recommendations"
    )
    auditor.audit_endpoint(
        module="AI Recommendations",
        method="GET",
        endpoint="/recommendations/OGDC"
    )
    auditor.audit_endpoint(
        module="AI Recommendations",
        method="GET",
        endpoint="/recommendations/weights"
    )

    # 6. RISK MANAGEMENT & SIMULATIONS
    print("\n[*] 6. Auditing Risk Management Models...")
    auditor.audit_endpoint(
        module="Risk Engine",
        method="GET",
        endpoint="/risk/var?symbol=OGDC"
    )
    auditor.audit_endpoint(
        module="Risk Engine",
        method="GET",
        endpoint="/risk/stress-test?symbol=OGDC"
    )

    # 7. MARKET SENTIMENT & NLP
    print("\n[*] 7. Auditing Sentiment Analysis Engine...")
    auditor.audit_endpoint(
        module="Sentiment Engine",
        method="GET",
        endpoint="/sentiment/market-overview"
    )
    auditor.audit_endpoint(
        module="Sentiment Engine",
        method="GET",
        endpoint="/sentiment/OGDC"
    )
    auditor.audit_endpoint(
        module="Sentiment Engine",
        method="GET",
        endpoint="/sentiment/OGDC/history"
    )
    auditor.audit_endpoint(
        module="Sentiment Engine",
        method="GET",
        endpoint="/sentiment/OGDC/news"
    )

    # 8. AI FORECASTING
    print("\n[*] 8. Auditing AI Direction & Price Forecasts...")
    auditor.audit_endpoint(
        module="AI Forecast",
        method="GET",
        endpoint="/forecast/OGDC?horizon=1D"
    )
    auditor.audit_endpoint(
        module="AI Forecast",
        method="GET",
        endpoint="/forecast/OGDC?horizon=1W"
    )
    auditor.audit_endpoint(
        module="AI Forecast",
        method="GET",
        endpoint="/forecast/OGDC?horizon=1M"
    )

    # 9. PORTFOLIO & LEDGER
    print("\n[*] 9. Auditing Portfolio Valuation & PnL Ledger...")
    auditor.audit_endpoint(
        module="Portfolio Engine",
        method="GET",
        endpoint="/portfolio",
        allow_empty=True
    )
    auditor.audit_endpoint(
        module="Portfolio Engine",
        method="GET",
        endpoint="/portfolio/holdings",
        allow_empty=True
    )
    auditor.audit_endpoint(
        module="Portfolio Engine",
        method="GET",
        endpoint="/portfolio/pnl",
        allow_empty=True
    )
    auditor.audit_endpoint(
        module="Portfolio Engine",
        method="GET",
        endpoint="/portfolio/allocation",
        allow_empty=True
    )
    auditor.audit_endpoint(
        module="Portfolio Engine",
        method="GET",
        endpoint="/portfolio/performance",
        allow_empty=True
    )

    # 10. EVENTS CALENDAR
    print("\n[*] 10. Auditing Corporate Events Calendar...")
    auditor.audit_endpoint(
        module="Events Calendar",
        method="GET",
        endpoint="/events/calendar",
        allow_empty=True
    )

    # 11. SHARIAH COMPLIANCE ENGINE
    print("\n[*] 11. Auditing Shariah Screening & Purification...")
    auditor.audit_endpoint(
        module="Shariah Engine",
        method="GET",
        endpoint="/shariah/kmi30"
    )
    auditor.audit_endpoint(
        module="Shariah Engine",
        method="GET",
        endpoint="/shariah/OGDC"
    )
    auditor.audit_endpoint(
        module="Shariah Engine",
        method="GET",
        endpoint="/shariah/OGDC/criteria"
    )
    auditor.audit_endpoint(
        module="Shariah Engine",
        method="GET",
        endpoint="/shariah/SYS/purification?dividend_income=10000"
    )

    # 12. ALERTS & NOTIFICATIONS
    print("\n[*] 12. Auditing User Alerts & Notifications...")
    auditor.audit_endpoint(
        module="Alerts & Devices",
        method="GET",
        endpoint="/alerts",
        allow_empty=True
    )
    auditor.audit_endpoint(
        module="Alerts & Devices",
        method="GET",
        endpoint="/alerts/rules",
        allow_empty=True
    )
    auditor.audit_endpoint(
        module="Alerts & Devices",
        method="GET",
        endpoint="/notifications",
        allow_empty=True
    )

    # 13. COMMUNITY & SOCIAL FEED
    print("\n[*] 13. Auditing Community Posts & Social Feed...")
    auditor.audit_endpoint(
        module="Community & Social",
        method="GET",
        endpoint="/community/feed"
    )
    auditor.audit_endpoint(
        module="Community & Social",
        method="GET",
        endpoint="/community/me"
    )

    # 14. FINANCIAL NEWS
    print("\n[*] 14. Auditing Real-Time Financial News...")
    auditor.audit_endpoint(
        module="Financial News",
        method="GET",
        endpoint="/news"
    )
    auditor.audit_endpoint(
        module="Financial News",
        method="GET",
        endpoint="/news/sources"
    )

    # 15. AI ASSISTANT
    print("\n[*] 15. Auditing AI Conversational Assistant...")
    auditor.audit_endpoint(
        module="AI Assistant",
        method="GET",
        endpoint="/assistant/conversations",
        allow_empty=True
    )

    # PRESENT RESULTS TABLE
    print("\n" + "=" * 115)
    print(f"{'MODULE':<20} | {'METHOD & ENDPOINT':<40} | {'STATUS':<8} | {'COMPL %':<8} | {'NULL / EMPTY / MISSING':<30}")
    print("=" * 115)

    total_endpoints = len(auditor.results)
    perfect_count = 0
    total_fields_checked = sum(r["total_fields"] for r in auditor.results)
    total_populated_checked = sum(r["populated_fields"] for r in auditor.results)

    for r in auditor.results:
        endpoint_display = f"{r['method']} {r['endpoint']}"[:40]
        status_display = f"HTTP {r['status']}"
        compl_display = f"{r['completeness_pct']}%"
        
        issues = []
        if r["missing_keys"]:
            issues.append(f"MISSING: {r['missing_keys']}")
        if r["null_paths"]:
            issues.append(f"NULL: {r['null_paths'][:2]}")
        if r["empty_paths"] and r["verdict"] != "COMPLETE":
            issues.append(f"EMPTY: {r['empty_paths'][:2]}")
        
        issue_str = "; ".join(issues) if issues else "All Fields Populated"
        if len(issue_str) > 30:
            issue_str = issue_str[:27] + "..."

        if r["verdict"] in ("COMPLETE", "PARTIAL_NULLS") and not r["missing_keys"] and r["status"] in (200, 201, 202):
            perfect_count += 1

        print(f"{r['module']:<20} | {endpoint_display:<40} | {status_display:<8} | {compl_display:<8} | {issue_str:<30}")

    overall_completeness = round((total_populated_checked / max(1, total_fields_checked)) * 100, 2)

    print("=" * 115)
    print(f" AUDIT SUMMARY BENCHMARK:")
    print(f"  * Total Endpoints Evaluated : {total_endpoints}")
    print(f"  * Responsive & Valid HTTP   : {perfect_count} / {total_endpoints} ({round(perfect_count/total_endpoints*100, 1)}%)")
    print(f"  * Total Schema Fields Inspected : {total_fields_checked}")
    print(f"  * Populated Non-Null Fields     : {total_populated_checked}")
    print(f"  * Overall Platform Data Completeness: {overall_completeness}%")
    print("=" * 115)

    # Save detailed JSON report for full inspection
    report_file = os.path.join(os.path.dirname(__file__), "live_data_completeness_report.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(auditor.results, f, indent=2, default=str)
    print(f"\n[+] Detailed field-level report exported to: {report_file}")


if __name__ == "__main__":
    run_full_completeness_audit()
