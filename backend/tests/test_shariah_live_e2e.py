"""Manual public smoke checks for a deployed Shariah API.

Set AUDIT_BASE_URL to the deployment's /api/v1 URL before running. This script
does not create users, authenticate, or contain credentials.
"""

import os
import httpx

BASE_URL = os.getenv("AUDIT_BASE_URL", "http://localhost:8000/api/v1").rstrip("/")


def test_shariah_endpoints():
    with httpx.Client(timeout=30.0) as client:
        kmi = client.get(f"{BASE_URL}/shariah/kmi30")
        assert kmi.status_code == 200, kmi.text
        kmi_data = kmi.json()
        assert kmi_data["index"] == "KMI-30"
        assert kmi_data["total_constituents"] == len(kmi_data["constituents"])
        assert kmi_data["total_constituents"] == 30
        assert kmi_data["as_of"].startswith("2025-12-31")
        assert kmi_data["effective_from"].startswith("2026-05-25")
        assert kmi_data["source_url"].startswith("https://dps.psx.com.pk/")
        constituents = {row["symbol"]: row for row in kmi_data["constituents"]}
        assert len(constituents) == 30
        assert constituents["OGDC"]["interest_income_ratio"] == 0.0662
        assert constituents["OGDC"]["purification_rate_provisional"] is True
        assert constituents["MEBL"]["interest_income_ratio"] is None
        assert constituents["MEBL"]["purification_rate_provisional"] is False
        assert constituents["FFC"]["purification_rate_provisional"] is False
        assert constituents["SYS"]["purification_rate_provisional"] is False
        for symbol, expected in (("OGDC", True), ("HBL", False)):
            result = client.get(f"{BASE_URL}/shariah/{symbol}")
            assert result.status_code == 200, result.text
            body = result.json()
            assert body["is_shariah_compliant"] is expected
            assert body["overall_score"] is None
            assert body["screening_available"] is True
            if symbol == "OGDC":
                assert body["data_as_of"].startswith("2025-12-31")
                assert body["data_is_stale"] is True
                assert body["purification_rate"] == 0.0662

        unknown = client.get(f"{BASE_URL}/shariah/ZZZ999")
        assert unknown.status_code == 200
        assert unknown.json()["screening_available"] is False
        assert unknown.json()["is_shariah_compliant"] is None

        criteria = client.get(f"{BASE_URL}/shariah/OGDC/criteria")
        assert criteria.status_code == 200
        criteria_data = criteria.json()
        assert len(criteria_data["criteria"]) == 6
        assert criteria_data["screening_available"] is True
        assert criteria_data["data_as_of"].startswith("2025-12-31")
        income_criterion = next(row for row in criteria_data["criteria"] if "Income Ratio" in row["name"])
        assert income_criterion["value"] == 6.62
        assert income_criterion["threshold"] == 5.0
        assert income_criterion["passed"] is None
        assert "exception" in income_criterion and income_criterion["exception"]

        purification = client.get(
            f"{BASE_URL}/shariah/OGDC/purification",
            params={"dividend_income": 15000.0},
        )
        assert purification.status_code == 200, purification.text
        purification_data = purification.json()
        assert purification_data["purification_rate"] == 0.0662
        assert purification_data["purification_amount"] == 993.0
        assert purification_data["data_is_stale"] is True
        assert purification_data["rate_is_provisional"] is True

        unavailable_rate = client.get(
            f"{BASE_URL}/shariah/MEBL/purification",
            params={"dividend_income": 15000.0},
        )
        assert unavailable_rate.status_code == 422

        invalid = client.get(f"{BASE_URL}/shariah/OGDC/purification")
        assert invalid.status_code == 422


if __name__ == "__main__":
    test_shariah_endpoints()
    print(f"Public Shariah smoke checks passed against {BASE_URL}")
