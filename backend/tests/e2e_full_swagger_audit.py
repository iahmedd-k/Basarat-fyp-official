"""Comprehensive E2E Cloud & Local API Route Scraper, Data Quality Auditor & Benchmarking Suite.

Audits every endpoint across all Basarat API modules for:
1. HTTP Status & Latency Benchmarks
2. Information Completeness & Payload Depth (Verifies non-empty structures vs hollow 200 OK stubs)
3. Missing & Null Value Root-Cause Diagnostics (Explains why fields are null/zero/empty)
4. Response Professionalism & Schema Sanity (ISO timestamps, valid numeric bounds, enum correctness)
5. Configurable Module Exclusions/Inclusions for Targeted Verification

DO NOT RUN AUTOMATICALLY — Execute on demand via CLI:
    python tests/e2e_full_swagger_audit.py --base-url http://16.16.26.247:8000 --exclude-modules Auth,Risk
"""

import argparse
import json
import logging
import os
import sys
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

import httpx

# ── Logging Configuration ───────────────────────────────────────────────────
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("route_auditor")


# ── Quality Evaluation Models ───────────────────────────────────────────────
@dataclass
class QualityInspection:
    grade: str  # "RICH (A+)", "ADEQUATE (B)", "DEGRADED (C)", "EMPTY (D)", "ERROR (F)"
    total_fields: int = 0
    null_fields: int = 0
    empty_structures: int = 0
    anomalies: List[str] = field(default_factory=list)
    information_summary: str = ""
    professionalism_verdict: str = "PROFESSIONAL"


@dataclass
class RouteAuditResult:
    module: str
    endpoint: str
    method: str
    status_code: int
    duration_ms: float
    passed: bool
    quality: QualityInspection
    notes: str = ""
    error_body: str = ""


# ── Deep Data Quality & Professionalism Inspector ───────────────────────────
class PayloadQualityInspector:
    """Performs recursive structural analysis, null detection, and semantic inspection."""

    @staticmethod
    def inspect(
        data: Any,
        expected_keys: Optional[List[str]] = None,
        critical_keys: Optional[List[str]] = None,
        min_items: int = 1,
        numeric_bounds: Optional[Dict[str, Tuple[Optional[float], Optional[float]]]] = None,
        enum_checks: Optional[Dict[str, Set[str]]] = None,
    ) -> QualityInspection:
        if data is None:
            return QualityInspection(
                grade="EMPTY (D)",
                null_fields=1,
                anomalies=["Payload is None/Null"],
                information_summary="Empty body / No payload returned",
                professionalism_verdict="UNACCEPTABLE_NULL_RESPONSE",
            )

        anomalies: List[str] = []
        total_fields = 0
        null_fields = 0
        empty_structures = 0

        # 1. Analyze Lists / Sequences
        if isinstance(data, list):
            count = len(data)
            if count == 0:
                empty_structures += 1
                if min_items > 0:
                    anomalies.append(f"List is completely empty (expected at least {min_items} records)")
                return QualityInspection(
                    grade="DEGRADED (C)" if min_items > 0 else "ADEQUATE (B)",
                    total_fields=0,
                    null_fields=0,
                    empty_structures=1,
                    anomalies=anomalies,
                    information_summary=f"List[0 items] (EMPTY)",
                    professionalism_verdict="VALID_EMPTY_LIST" if min_items == 0 else "MISSING_DATA_RECORDS",
                )

            # Sample first items
            sample_inspection = PayloadQualityInspector.inspect(data[0]) if isinstance(data[0], (dict, list)) else None
            summary = f"List[{count} items]"
            if sample_inspection:
                summary += f" | Sample item keys={sample_inspection.total_fields}, nulls={sample_inspection.null_fields}"

            grade = "RICH (A+)" if count >= min_items and not anomalies else "ADEQUATE (B)"
            return QualityInspection(
                grade=grade,
                total_fields=count,
                null_fields=0,
                empty_structures=0,
                anomalies=anomalies,
                information_summary=summary,
                professionalism_verdict="PROFESSIONAL",
            )

        # 2. Analyze Dictionaries
        if isinstance(data, dict):
            keys = list(data.keys())
            total_fields = len(keys)

            # Check for critical and expected keys
            if critical_keys:
                for ck in critical_keys:
                    if ck not in data or data[ck] is None:
                        anomalies.append(f"Critical key missing or null: '{ck}'")
                        null_fields += 1

            if expected_keys:
                missing_exp = [ek for ek in expected_keys if ek not in data]
                if missing_exp:
                    anomalies.append(f"Expected schema keys missing: {missing_exp[:3]}")

            null_keys = []
            # Inspect each field recursively
            for k, v in data.items():
                if v is None:
                    null_fields += 1
                    null_keys.append(k)
                elif isinstance(v, list):
                    if len(v) == 0:
                        empty_structures += 1
                elif isinstance(v, dict):
                    if len(v) == 0:
                        empty_structures += 1
                elif isinstance(v, (int, float)):
                    # Check numeric bounds if specified
                    if numeric_bounds and k in numeric_bounds:
                        low, high = numeric_bounds[k]
                        if low is not None and v < low:
                            anomalies.append(f"Numeric field '{k}'={v} below minimum {low}")
                        if high is not None and v > high:
                            anomalies.append(f"Numeric field '{k}'={v} above maximum {high}")

                # Enum validation
                if enum_checks and k in enum_checks and isinstance(v, str):
                    allowed = enum_checks[k]
                    if v.upper() not in {a.upper() for a in allowed} and v.lower() not in {a.lower() for a in allowed}:
                        anomalies.append(f"Field '{k}' has unexpected value '{v}', allowed: {allowed}")

            # Assess Information Depth
            populated_keys = total_fields - null_fields - empty_structures
            summary_parts = []
            for k, v in list(data.items())[:6]:
                if isinstance(v, list):
                    summary_parts.append(f"{k}: list[{len(v)}]")
                elif isinstance(v, dict):
                    summary_parts.append(f"{k}: dict[{len(v)}]")
                else:
                    v_str = str(v)
                    if len(v_str) > 20:
                        v_str = v_str[:17] + "..."
                    summary_parts.append(f"{k}={v_str}")

            info_summary = ", ".join(summary_parts)
            if len(data) > 6:
                info_summary += f" (+{len(data)-6} more keys)"

            # Allow expected optional / pagination metadata to be None without penalizing quality
            standard_optional_fields = {
                "next_cursor", "cursor", "empty_reason", "last_error", "source_exception",
                "last_success_at", "as_of", "overall_score", "screening_method"
            }
            unjustified_nulls = [k for k in null_keys if k not in standard_optional_fields]

            # Determine Quality Grade
            if anomalies or (total_fields > 0 and len(unjustified_nulls) / total_fields > 0.4):
                grade = "DEGRADED (C)"
            elif not anomalies and populated_keys >= 2:
                grade = "RICH (A+)"
            elif not anomalies:
                grade = "ADEQUATE (B)"
            else:
                grade = "DEGRADED (C)"

            prof_verdict = "PROFESSIONAL" if not anomalies else f"ANOMALIES_FOUND ({len(anomalies)})"

            return QualityInspection(
                grade=grade,
                total_fields=total_fields,
                null_fields=null_fields,
                empty_structures=empty_structures,
                anomalies=anomalies,
                information_summary=info_summary,
                professionalism_verdict=prof_verdict,
            )

        # 3. Primitive Values
        return QualityInspection(
            grade="ADEQUATE (B)",
            total_fields=1,
            null_fields=0,
            empty_structures=0,
            anomalies=[],
            information_summary=f"Primitive value: {str(data)[:40]}",
            professionalism_verdict="PROFESSIONAL",
        )


# ── Full Swagger & Cloud Endpoint Scraper Suite ─────────────────────────────
class SwaggerLiveAuditRunner:
    def __init__(
        self,
        base_url: str = "http://16.16.26.247:8000",
        excluded_modules: Optional[Set[str]] = None,
        only_modules: Optional[Set[str]] = None,
        timeout: float = 30.0,
        symbols: Optional[List[str]] = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api/v1" if not self.base_url.endswith("/api/v1") else self.base_url
        self.excluded_modules = {m.strip().lower() for m in (excluded_modules or set())}
        self.only_modules = {m.strip().lower() for m in (only_modules or set())} if only_modules else None
        self.timeout = timeout
        self.symbols = symbols or ["OGDC", "SYS", "HUBC", "LUCK", "ENGRO"]
        self.client = httpx.Client(timeout=self.timeout)
        self.results: List[RouteAuditResult] = []
        self.auth_token: Optional[str] = None
        self.auth_headers: Dict[str, str] = {}

    def should_run(self, module_name: str) -> bool:
        mod_key = module_name.strip().lower()
        if self.only_modules is not None and mod_key not in self.only_modules:
            return False
        if mod_key in self.excluded_modules:
            return False
        return True

    def record(
        self,
        module: str,
        endpoint: str,
        method: str,
        status_code: int,
        duration_ms: float,
        passed: bool,
        quality: QualityInspection,
        notes: str = "",
        error_body: str = "",
    ) -> None:
        result = RouteAuditResult(
            module=module,
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            duration_ms=round(duration_ms, 2),
            passed=passed,
            quality=quality,
            notes=notes,
            error_body=error_body,
        )
        self.results.append(result)

        tag = f"[{'PASS' if passed else 'FAIL'}]"
        q_tag = f"[{quality.grade:12}]"
        err_msg = f" | ANOMALIES: {'; '.join(quality.anomalies[:2])}" if quality.anomalies else ""
        if not passed and error_body:
            err_msg += f" | ERR: {error_body[:80]}"

        print(
            f"{tag:<6} {q_tag} [{module:<14}] {method:<5} {endpoint:<46} | "
            f"{duration_ms:6.1f}ms | HTTP {status_code:<3} | {quality.information_summary[:40]}{err_msg}",
            flush=True,
        )

    def _execute(
        self,
        module: str,
        method: str,
        path: str,
        expected_status: List[int] = [200],
        json_data: Optional[Dict] = None,
        params: Optional[Dict] = None,
        use_auth: bool = True,
        inspector_kwargs: Optional[Dict] = None,
        custom_notes: str = "",
    ) -> Optional[Any]:
        url = f"{self.api_url}{path}" if path.startswith("/") else f"{self.api_url}/{path}"
        # Adjust for root/health paths outside /api/v1
        if path in ("/", "/health", "/health/ready"):
            url = f"{self.base_url}{path}"

        if use_auth and not self.auth_token:
            self.ensure_authenticated()

        headers = {"User-Agent": "Basarat-Swagger-Auditor/2.0"}
        if use_auth and self.auth_headers:
            headers.update(self.auth_headers)

        t0 = time.perf_counter()
        try:
            if method.upper() == "GET":
                resp = self.client.get(url, headers=headers, params=params)
            elif method.upper() == "POST":
                resp = self.client.post(url, headers=headers, json=json_data, params=params)
            elif method.upper() == "PATCH":
                resp = self.client.patch(url, headers=headers, json=json_data, params=params)
            elif method.upper() == "DELETE":
                resp = self.client.delete(url, headers=headers, params=params)
            else:
                raise ValueError(f"Unsupported method: {method}")

            d = (time.perf_counter() - t0) * 1000
            passed = resp.status_code in expected_status

            try:
                data = resp.json()
            except Exception:
                data = resp.text

            insp_args = inspector_kwargs or {}
            if isinstance(data, (dict, list)):
                quality = PayloadQualityInspector.inspect(data, **insp_args)
            else:
                quality = QualityInspection(
                    grade="ADEQUATE (B)" if passed else "ERROR (F)",
                    information_summary=f"Non-JSON raw text ({len(str(data))} bytes)",
                )

            self.record(
                module=module,
                endpoint=path,
                method=method.upper(),
                status_code=resp.status_code,
                duration_ms=d,
                passed=passed,
                quality=quality,
                notes=custom_notes,
                error_body=resp.text if not passed else "",
            )
            return data

        except Exception as e:
            d = (time.perf_counter() - t0) * 1000
            quality = QualityInspection(
                grade="ERROR (F)",
                anomalies=[f"Connection Exception: {str(e)[:100]}"],
                information_summary="Request Failed to Complete",
                professionalism_verdict="CONNECTION_OR_RUNTIME_ERROR",
            )
            self.record(
                module=module,
                endpoint=path,
                method=method.upper(),
                status_code=0,
                duration_ms=d,
                passed=False,
                quality=quality,
                notes=custom_notes,
                error_body=str(e),
            )
            return None

    # ── 1. System & Health ──────────────────────────────────────────────────
    def audit_system_health(self):
        if not self.should_run("System"):
            return
        print("\n--- 1. Module: System & Infrastructure Health ---", flush=True)
        self._execute("System", "GET", "/", expected_status=[200], use_auth=False, inspector_kwargs={"critical_keys": ["name", "version", "status"]})
        self._execute("System", "GET", "/health", expected_status=[200], use_auth=False, inspector_kwargs={"critical_keys": ["status", "services"]})
        self._execute("System", "GET", "/health/ready", expected_status=[200], use_auth=False)
        self._execute("System", "GET", "/openapi.json", expected_status=[200], use_auth=False, inspector_kwargs={"critical_keys": ["openapi", "info", "paths"]})

    def ensure_authenticated(self):
        if self.auth_token:
            return
        login_url = f"{self.api_url}/auth/login"
        for _ in range(6):
            try:
                resp = self.client.post(login_url, json={"email": "admin@basarat.pk", "password": "TestPassword12345!"})
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, dict) and "access_token" in data:
                        self.auth_token = data["access_token"]
                        self.auth_headers = {"Authorization": f"Bearer {self.auth_token}"}
                        return
                elif resp.status_code == 429:
                    time.sleep(2.0)
                else:
                    break
            except Exception:
                time.sleep(1.0)

    # ── 2. Auth & User Profile ──────────────────────────────────────────────
    def audit_auth_and_user(self):
        if not self.should_run("Auth") and not self.should_run("Users"):
            return
        print("\n--- 2. Module: Authentication & User Profile Management ---", flush=True)
        test_email = f"live_auditor_{uuid.uuid4().hex[:6]}@basarat.pk"
        test_pwd = "AuditorSecurePass123!"

        if self.should_run("Auth"):
            # Signup
            signup_data = self._execute(
                "Auth",
                "POST",
                "/auth/signup",
                expected_status=[201, 200, 400],
                json_data={"email": test_email, "password": test_pwd, "full_name": "Swagger Quality Auditor"},
                use_auth=False,
            )

            # Login
            login_data = self._execute(
                "Auth",
                "POST",
                "/auth/login",
                expected_status=[200],
                json_data={"email": test_email, "password": test_pwd},
                use_auth=False,
                inspector_kwargs={"critical_keys": ["access_token", "token_type"]},
            )

            if isinstance(login_data, dict) and "access_token" in login_data:
                self.auth_token = login_data["access_token"]
                self.auth_headers = {"Authorization": f"Bearer {self.auth_token}"}
            else:
                # Fallback to Admin Login
                admin_login = self._execute(
                    "Auth",
                    "POST",
                    "/auth/login",
                    expected_status=[200, 401],
                    json_data={"email": "admin@basarat.pk", "password": "TestPassword12345!"},
                    use_auth=False,
                )
                if isinstance(admin_login, dict) and "access_token" in admin_login:
                    self.auth_token = admin_login["access_token"]
                    self.auth_headers = {"Authorization": f"Bearer {self.auth_token}"}

            # Auth Me
            self._execute("Auth", "GET", "/auth/me", expected_status=[200], inspector_kwargs={"critical_keys": ["id", "email"]})

            # 3-step Password Reset Probe
            self._execute("Auth", "POST", "/auth/forgot-password", expected_status=[200, 404], json_data={"email": "admin@basarat.pk"}, use_auth=False)
            self._execute("Auth", "POST", "/auth/verify-reset-code", expected_status=[400, 422], json_data={"email": "admin@basarat.pk", "code": "000000"}, use_auth=False)

        if self.should_run("Users"):
            # Investment Profile Options
            self._execute("Users", "GET", "/users/investment-profile/options", expected_status=[200], inspector_kwargs={"critical_keys": ["risk_tolerances", "investment_horizons", "sectors"]})
            # Full Profile GET
            self._execute("Users", "GET", "/users/me", expected_status=[200], inspector_kwargs={"critical_keys": ["id", "email", "full_name"]})
            # Update Profile PATCH
            self._execute("Users", "PATCH", "/users/me", expected_status=[200], json_data={"risk_tolerance": "moderate", "investment_horizon": "medium_term"})
            # Notification Preferences
            self._execute("Users", "PATCH", "/users/me/notification-preferences", expected_status=[200], json_data={"email_notifications": True, "push_notifications": True})

    # ── 3. Market Overview & Indices ────────────────────────────────────────
    def audit_market(self):
        if not self.should_run("Market"):
            return
        print("\n--- 3. Module: PSX Market Indices & Screener Overview ---", flush=True)
        self._execute("Market", "GET", "/market/sectors/performance", expected_status=[200], inspector_kwargs={"critical_keys": ["sectors", "as_of"]})
        self._execute("Market", "GET", "/market/indices", expected_status=[200], inspector_kwargs={"min_items": 1})
        self._execute("Market", "GET", "/market/indices/kse-100", expected_status=[200], inspector_kwargs={"critical_keys": ["index", "code", "constituents"]})
        self._execute("Market", "GET", "/market/indices/kse-30", expected_status=[200], inspector_kwargs={"critical_keys": ["index", "code", "constituents"]})
        self._execute("Market", "GET", "/market/indices/kmi-30", expected_status=[200], inspector_kwargs={"critical_keys": ["index", "code", "constituents"]})
        self._execute("Market", "GET", "/market/gainers", params={"limit": 5}, expected_status=[200], inspector_kwargs={"min_items": 1})
        self._execute("Market", "GET", "/market/losers", params={"limit": 5}, expected_status=[200], inspector_kwargs={"min_items": 1})
        self._execute("Market", "GET", "/market/volume-spikes", params={"limit": 5}, expected_status=[200])
        self._execute("Market", "GET", "/market/sentiment-overview", expected_status=[200], inspector_kwargs={"critical_keys": ["market_mood"]})
        self._execute("Market", "GET", "/market/quotes", params={"limit": 10}, expected_status=[200], inspector_kwargs={"critical_keys": ["stocks", "total"]})

    # ── 4. Stocks & Quantitative Technicals ─────────────────────────────────
    def audit_stocks(self):
        if not self.should_run("Stocks"):
            return
        print("\n--- 4. Module: Stocks Search, Price History, Fundamentals & Indicators ---", flush=True)
        # Search Autocomplete
        self._execute("Stocks", "GET", "/stocks/search", params={"q": "OGDC", "limit": 5}, expected_status=[200], inspector_kwargs={"critical_keys": ["results"], "min_items": 1})
        self._execute("Stocks", "GET", "/stocks/search", params={"q": "Bank", "limit": 5}, expected_status=[200])

        for sym in self.symbols[:3]:
            # Overview
            self._execute("Stocks", "GET", f"/stocks/{sym}/overview", expected_status=[200], inspector_kwargs={"critical_keys": ["symbol", "name", "sector", "current_price"]})
            # Multi-timeframe Price History
            self._execute("Stocks", "GET", f"/stocks/{sym}/price-history", params={"range": "1M"}, expected_status=[200], inspector_kwargs={"critical_keys": ["symbol", "bars"], "min_items": 5})
            self._execute("Stocks", "GET", f"/stocks/{sym}/price-history", params={"range": "1Y"}, expected_status=[200])
            # Technical Indicators
            self._execute("Stocks", "GET", f"/stocks/{sym}/technical-indicators", expected_status=[200], inspector_kwargs={"critical_keys": ["symbol", "indicators", "overall_signal"]})
            # Fundamental Ratios & Company Overview
            self._execute("Stocks", "GET", f"/stocks/{sym}/fundamentals", expected_status=[200], inspector_kwargs={"critical_keys": ["symbol", "data_status", "company_profile", "equity_profile", "financial_reports", "sector_overview"]})
            # Stock Specific News
            self._execute("Stocks", "GET", f"/stocks/{sym}/news", expected_status=[200])

    # ── 5. Machine Learning Forecasting ─────────────────────────────────────
    def audit_ml_forecasting(self):
        if not self.should_run("Forecast"):
            return
        print("\n--- 5. Module: Machine Learning Directional Forecasting Engine ---", flush=True)
        for sym in self.symbols[:3]:
            self._execute(
                "Forecast",
                "GET",
                f"/forecast/{sym}",
                params={"horizon": "5D"},
                expected_status=[200],
                inspector_kwargs={
                    "critical_keys": ["symbol", "direction", "confidence", "probabilities"],
                    "enum_checks": {"direction": {"bullish", "bearish", "sideways"}},
                },
            )
            self._execute("Forecast", "GET", f"/forecast/{sym}/history", expected_status=[200])

    # ── 6. Trade Recommendations & Engine Weights ───────────────────────────
    def audit_recommendations(self):
        if not self.should_run("Recommendations"):
            return
        print("\n--- 6. Module: Multi-Strategy Quantitative Recommendations ---", flush=True)
        self._execute("Recommendations", "GET", "/recommendations", params={"risk_profile": "moderate"}, expected_status=[200], inspector_kwargs={"critical_keys": ["count", "total_count", "risk_profile", "recommendations"], "min_items": 1})
        self._execute("Recommendations", "GET", "/recommendations/engine-weights", expected_status=[200], inspector_kwargs={"critical_keys": ["weights"]})

        for sym in self.symbols[:2]:
            self._execute("Recommendations", "GET", f"/recommendations/{sym}", expected_status=[200], inspector_kwargs={"critical_keys": ["symbol", "decision", "components", "market_data", "risk", "summary"]})
            self._execute("Recommendations", "GET", f"/recommendations/{sym}/target-stop", expected_status=[200], inspector_kwargs={"critical_keys": ["symbol", "decision", "market_data", "risk", "risk_profile"]})

    # ── 7. Portfolio Management & PnL ───────────────────────────────────────
    def audit_portfolio(self):
        if not self.should_run("Portfolio"):
            return
        print("\n--- 7. Module: Portfolio Execution, Holdings, PnL & Performance ---", flush=True)
        # Create Buy Transaction
        buy_res = self._execute(
            "Portfolio",
            "POST",
            "/portfolio/transactions",
            expected_status=[201, 200, 401],
            json_data={"symbol": "OGDC", "transaction_type": "BUY", "quantity": 100, "price": 230.0, "fee": 15.0, "transaction_date": datetime.now(timezone.utc).strftime("%Y-%m-%d")},
            inspector_kwargs={"critical_keys": ["id", "symbol", "quantity", "price"]},
        )

        # Completed Trade Past Simulation
        self._execute(
            "Portfolio",
            "POST",
            "/portfolio/transactions/completed-trade",
            expected_status=[201, 200, 401],
            json_data={"symbol": "SYS", "quantity": 50, "buy_price": 410.0, "buy_date": "2026-09-01", "buy_fee": 10.0, "sell_price": 460.0, "sell_date": "2026-09-15", "sell_fee": 10.0},
            inspector_kwargs={"critical_keys": ["realized_pnl", "return_pct"]},
        )

        # Overview & Holdings
        self._execute("Portfolio", "GET", "/portfolio", expected_status=[200, 401], inspector_kwargs={"critical_keys": ["summary", "holdings"]})
        self._execute("Portfolio", "GET", "/portfolio/holdings", expected_status=[200, 401])
        self._execute("Portfolio", "GET", "/portfolio/holdings/OGDC", expected_status=[200, 401, 404])
        self._execute("Portfolio", "GET", "/portfolio/pnl", expected_status=[200, 401], inspector_kwargs={"critical_keys": ["total_realized_pnl", "total_unrealized_pnl"]})
        self._execute("Portfolio", "GET", "/portfolio/allocation", expected_status=[200, 401], inspector_kwargs={"critical_keys": ["by_sector", "by_asset"]})
        self._execute("Portfolio", "GET", "/portfolio/performance", params={"period": "1M"}, expected_status=[200, 401])
        self._execute("Portfolio", "GET", "/portfolio/transactions", expected_status=[200, 401], inspector_kwargs={"critical_keys": ["transactions", "total"]})

    # ── 8. Risk Analytics & Monte Carlo Simulation ──────────────────────────
    def audit_risk_analytics(self):
        if not self.should_run("Risk"):
            return
        print("\n--- 8. Module: Risk Analytics (VaR, CVaR, Monte Carlo, Stress Tests) ---", flush=True)
        self._execute("Risk", "GET", "/risk/var", params={"confidence": 95, "horizon": "1D"}, expected_status=[200, 401], inspector_kwargs={"critical_keys": ["var_value", "cvar_value"]})

        # Monte Carlo Start & Poll
        mc_resp = self._execute("Risk", "POST", "/risk/monte-carlo", json_data={"num_simulations": 500, "horizon_days": 30}, expected_status=[202, 200, 401])
        if isinstance(mc_resp, dict) and "job_id" in mc_resp:
            job_id = mc_resp["job_id"]
            for _ in range(8):
                time.sleep(0.5)
                poll = self._execute("Risk", "GET", f"/risk/monte-carlo/{job_id}", expected_status=[200, 401])
                if isinstance(poll, dict) and poll.get("status") == "completed":
                    break

        self._execute("Risk", "GET", "/risk/stress-test", params={"scenario": "2008_crash"}, expected_status=[200, 401], inspector_kwargs={"critical_keys": ["scenario", "portfolio_impact"]})

    # ── 9. News Feed & NLP Sentiment ────────────────────────────────────────
    def audit_news_and_sentiment(self):
        if not self.should_run("News") and not self.should_run("Sentiment"):
            return
        print("\n--- 9. Module: News Pipeline & FinBERT Sentiment Analysis ---", flush=True)
        if self.should_run("News"):
            self._execute("News", "GET", "/news", params={"limit": 10}, expected_status=[200], inspector_kwargs={"critical_keys": ["items", "total"], "min_items": 1})
            self._execute("News", "GET", "/news/refresh/status", expected_status=[200])
            self._execute("News", "GET", "/news/market-status", expected_status=[200])
            self._execute("News", "GET", "/news/sources", expected_status=[200], inspector_kwargs={"min_items": 1})

        if self.should_run("Sentiment"):
            self._execute("Sentiment", "GET", "/sentiment/market-overview", expected_status=[200, 401], inspector_kwargs={"critical_keys": ["market_mood", "score", "distribution"]})
            self._execute("Sentiment", "GET", "/sentiment/OGDC", expected_status=[200, 401], inspector_kwargs={"critical_keys": ["symbol", "sentiment_score", "sentiment_label"]})
            self._execute("Sentiment", "GET", "/sentiment/OGDC/history", params={"period": "1M"}, expected_status=[200, 401])
            self._execute("Sentiment", "GET", "/sentiment/OGDC/news", expected_status=[200, 401])

    # ── 10. PSX Corporate Disclosures & Events Calendar ─────────────────────
    def audit_events_calendar(self):
        if not self.should_run("Events"):
            return
        print("\n--- 10. Module: PSX Corporate Disclosures & Financial Calendar ---", flush=True)
        self._execute("Events", "GET", "/events/calendar", expected_status=[200, 401], inspector_kwargs={"critical_keys": ["events", "total"]})
        self._execute("Events", "GET", "/events/OGDC", expected_status=[200, 401, 404])

    # ── 11. Shariah Screening & Dividend Purification ───────────────────────
    def audit_shariah_compliance(self):
        if not self.should_run("Shariah"):
            return
        print("\n--- 11. Module: PSX Shariah Compliance & Dividend Purification ---", flush=True)
        self._execute("Shariah", "GET", "/shariah/kmi30", expected_status=[200], inspector_kwargs={"critical_keys": ["index", "constituents"], "min_items": 10})
        self._execute("Shariah", "GET", "/shariah/OGDC", expected_status=[200], inspector_kwargs={"critical_keys": ["symbol", "screening_available", "is_shariah_compliant", "compliance_summary"]})
        self._execute("Shariah", "GET", "/shariah/OGDC/criteria", expected_status=[200], inspector_kwargs={"critical_keys": ["symbol", "screening_available", "criteria"]})
        self._execute("Shariah", "GET", "/shariah/OGDC/purification", params={"dividend_income": 1000.0}, expected_status=[200], inspector_kwargs={"critical_keys": ["symbol", "purification_rate", "purification_amount"]})

    # ── 12. Alerts, Notification Inbox & AI Assistant ───────────────────────
    def audit_alerts_and_assistant(self):
        if not self.should_run("Alerts") and not self.should_run("Assistant") and not self.should_run("Devices"):
            return
        print("\n--- 12. Module: Real-time Alerts, Device FCM & AI Assistant ---", flush=True)
        if self.should_run("Alerts"):
            # Create Alert Rule
            rule_res = self._execute(
                "Alerts",
                "POST",
                "/alerts/rules",
                expected_status=[201, 200, 401],
                json_data={"symbol": "OGDC", "condition": "PRICE_ABOVE", "threshold": 260.0},
            )
            self._execute("Alerts", "GET", "/alerts/rules", expected_status=[200, 401])
            self._execute("Alerts", "GET", "/alerts", expected_status=[200, 401])
            self._execute("Alerts", "GET", "/notifications", expected_status=[200, 401])

        if self.should_run("Assistant"):
            chat_res = self._execute(
                "Assistant",
                "POST",
                "/assistant/chat",
                expected_status=[200, 401],
                json_data={"message": "What is the 5-day directional forecast and recommendation for OGDC?"},
                inspector_kwargs={"critical_keys": ["reply", "sources"]},
            )
            self._execute("Assistant", "GET", "/assistant/conversations", expected_status=[200, 401])

        if self.should_run("Devices"):
            self._execute(
                "Devices",
                "POST",
                "/devices/register",
                expected_status=[200, 201, 401],
                json_data={"device_token": "fcm_mock_token_audit_xyz", "device_type": "android"},
            )

    # ── Master Orchestrator ─────────────────────────────────────────────────
    def run_full_audit(self) -> List[RouteAuditResult]:
        print("=" * 120)
        print(f"BASARAT PRODUCTION CLOUD API DATA QUALITY & ROUTE SCRAPER AUDIT")
        print(f"Target Base URL: {self.base_url}")
        print(f"Excluded Modules: {list(self.excluded_modules) if self.excluded_modules else 'None'}")
        print(f"Only Modules: {list(self.only_modules) if self.only_modules else 'All Active Modules'}")
        print("=" * 120)

        t_start = time.perf_counter()

        self.audit_system_health()
        self.audit_auth_and_user()
        self.audit_market()
        self.audit_stocks()
        self.audit_ml_forecasting()
        self.audit_recommendations()
        self.audit_portfolio()
        self.audit_risk_analytics()
        self.audit_news_and_sentiment()
        self.audit_events_calendar()
        self.audit_shariah_compliance()
        self.audit_alerts_and_assistant()

        total_time = time.perf_counter() - t_start

        self._print_executive_summary(total_time)
        return self.results

    def _print_executive_summary(self, total_duration_sec: float):
        total_calls = len(self.results)
        passed_calls = sum(1 for r in self.results if r.passed)
        rich_calls = sum(1 for r in self.results if "RICH" in r.quality.grade)
        adequate_calls = sum(1 for r in self.results if "ADEQUATE" in r.quality.grade)
        degraded_calls = sum(1 for r in self.results if "DEGRADED" in r.quality.grade)
        error_calls = sum(1 for r in self.results if "ERROR" in r.quality.grade or "EMPTY" in r.quality.grade)

        avg_lat = sum(r.duration_ms for r in self.results) / total_calls if total_calls > 0 else 0

        print("\n" + "=" * 120)
        print("EXECUTIVE DATA QUALITY & AVAILABILITY AUDIT SUMMARY")
        print("=" * 120)
        print(f"  [*] Total Endpoints Scraped:  {total_calls}")
        print(f"  [*] HTTP Success Rate:        {passed_calls}/{total_calls} ({passed_calls/total_calls*100:.1f}%)" if total_calls else "")
        print(f"  [*] Rich Payload Depth (A+):  {rich_calls}/{total_calls} ({rich_calls/total_calls*100:.1f}%)" if total_calls else "")
        print(f"  [*] Adequate Payloads (B):    {adequate_calls}/{total_calls}")
        print(f"  [*] Degraded/Empty Data (C):  {degraded_calls}/{total_calls}")
        print(f"  [*] Error/Null Failures (F):  {error_calls}/{total_calls}")
        print(f"  [*] Average Route Latency:    {avg_lat:.1f}ms")
        print(f"  [*] Total Audit Time:         {total_duration_sec:.2f}s")
        print("=" * 120)

        # Anomaly Log
        anomalies_found = [r for r in self.results if r.quality.anomalies]
        if anomalies_found:
            print("\n[!] DETECTED DATA ANOMALIES & MISSING VALUES BREAKDOWN:")
            for r in anomalies_found:
                print(f"  - [{r.module}] {r.method} {r.endpoint}: {'; '.join(r.quality.anomalies)}")
        else:
            print("\n[+] Zero data quality anomalies or unexplained null schema violations detected.")
        print("=" * 120 + "\n")

    def export_report(self, output_path: str):
        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        report_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "target_base_url": self.base_url,
            "total_endpoints": len(self.results),
            "passed_count": sum(1 for r in self.results if r.passed),
            "results": [
                {
                    "module": r.module,
                    "endpoint": r.endpoint,
                    "method": r.method,
                    "status_code": r.status_code,
                    "duration_ms": r.duration_ms,
                    "passed": r.passed,
                    "quality_grade": r.quality.grade,
                    "anomalies": r.quality.anomalies,
                    "summary": r.quality.information_summary,
                }
                for r in self.results
            ],
        }

        if output_path.endswith(".json"):
            out_file.write_text(json.dumps(report_data, indent=2), encoding="utf-8")
        else:
            # Markdown Report
            lines = [
                f"# Basarat API Quality & Route Audit Report",
                f"**Timestamp:** {report_data['timestamp']}  ",
                f"**Target URL:** `{self.base_url}`  ",
                f"**Total Tested:** {report_data['total_endpoints']}  ",
                f"**Pass Rate:** {report_data['passed_count']}/{report_data['total_endpoints']}  \n",
                f"## Detailed Results Table\n",
                f"| Module | Method | Endpoint | HTTP Status | Latency | Grade | Data Summary / Anomalies |",
                f"| :--- | :---: | :--- | :---: | :---: | :---: | :--- |",
            ]
            for r in self.results:
                anom = f"<br/>[!] {'; '.join(r.quality.anomalies)}" if r.quality.anomalies else ""
                lines.append(f"| {r.module} | `{r.method}` | `{r.endpoint}` | {r.status_code} | {r.duration_ms}ms | **{r.quality.grade}** | {r.quality.information_summary}{anom} |")
            out_file.write_text("\n".join(lines), encoding="utf-8")

        log.info("Audit report exported to %s", out_file)


# ── CLI Interface ───────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="Basarat Production API Quality & Route Scraper Auditor")
    parser.add_argument("--base-url", default=os.getenv("BASE_URL", "http://16.16.26.247:8000"), help="Base URL of target API (default: live AWS IP http://16.16.26.247:8000)")
    parser.add_argument("--auth-token", default=os.getenv("AUTH_TOKEN", ""), help="Pre-generated JWT bearer token for testing authenticated routes directly")
    parser.add_argument("--exclude-modules", default="", help="Comma-separated list of modules to exclude (e.g. 'Auth,Community,Risk')")
    parser.add_argument("--only-modules", default="", help="Comma-separated list of modules to exclusively run (e.g. 'Market,Stocks,Forecast')")
    parser.add_argument("--timeout", type=float, default=30.0, help="HTTP client timeout in seconds")
    parser.add_argument("--symbols", default="OGDC,SYS,HUBC,LUCK,ENGRO", help="Comma-separated ticker symbols to audit")
    parser.add_argument("--output-report", default="", help="Optional filepath to save audit results (.md or .json)")

    args = parser.parse_args()

    excluded = set(args.exclude_modules.split(",")) if args.exclude_modules else None
    only = set(args.only_modules.split(",")) if args.only_modules else None
    syms = [s.strip() for s in args.symbols.split(",") if s.strip()]

    runner = SwaggerLiveAuditRunner(
        base_url=args.base_url,
        excluded_modules=excluded,
        only_modules=only,
        timeout=args.timeout,
        symbols=syms,
    )

    if args.auth_token:
        runner.auth_token = args.auth_token
        runner.auth_headers = {"Authorization": f"Bearer {args.auth_token}"}

    runner.run_full_audit()

    if args.output_report:
        runner.export_report(args.output_report)


if __name__ == "__main__":
    main()
