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
        assert kmi_data["total_constituents"] >= 30
        assert "as_of" in kmi_data and isinstance(kmi_data["is_stale"], bool)
        assert all(
            row.get("debt_ratio") is None and row.get("purification_rate") is None
            for row in kmi_data["constituents"]
        )

        for symbol, expected in (("OGDC", True), ("HBL", False)):
            result = client.get(f"{BASE_URL}/shariah/{symbol}")
            assert result.status_code == 200, result.text
            body = result.json()
            assert body["is_shariah_compliant"] is expected
            assert body["overall_score"] is None

        unknown = client.get(f"{BASE_URL}/shariah/ZZZ999")
        assert unknown.status_code == 200
        assert unknown.json()["screening_available"] is False
        assert unknown.json()["is_shariah_compliant"] is None

        criteria = client.get(f"{BASE_URL}/shariah/OGDC/criteria")
        assert criteria.status_code == 200
        criteria_data = criteria.json()
        assert len(criteria_data["criteria"]) == 6
        assert all(
            row["value"] is None and row["passed"] is None
            for row in criteria_data["criteria"][1:]
        )

        purification = client.get(
            f"{BASE_URL}/shariah/OGDC/purification",
            params={"dividend_income": 15000.0},
        )
        assert purification.status_code == 422
        message = purification.json()["error"]["message"].lower()
        assert "verified purification rate" in message

        invalid = client.get(f"{BASE_URL}/shariah/OGDC/purification")
        assert invalid.status_code == 422


if __name__ == "__main__":
    test_shariah_endpoints()
    print(f"Public Shariah smoke checks passed against {BASE_URL}")
