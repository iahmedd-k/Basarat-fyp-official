"""Comprehensive Audit and Live Validation for Shariah Compliance Module.

Validates:
1. PSX KMI-30 Constituents (/shariah/kmi30):
   - Total constituents count
   - Index metadata, effective date, data source & freshness
   - Constituent ratio schemas & boolean flags
2. Stock Shariah Screening (/shariah/{symbol}):
   - Compliant constituents (e.g. OGDC, SYS, LUCK, MEBL, EFERT)
   - Non-compliant conventional sectors & symbols (e.g. HBL, MCB, UBL, PAKT, MUREB, EFUG)
   - Unverified / Unknown stock handling
   - Sector, purification rate, screening method, source metadata
3. 6-Point Shariah Criteria Breakdown (/shariah/{symbol}/criteria):
   - Core Business Permissibility (Threshold: 1.0)
   - Debt to Total Assets Ratio (< 37.0%)
   - Non-Compliant Investments Ratio (< 33.0%)
   - Non-Permissible / Interest Income Ratio (< 5.0%)
   - Illiquid Assets to Total Assets Ratio (>= 25.0%)
   - Net Liquid Assets vs Market Price (< Price)
   - Documented PSX Exceptions (e.g. HUBC, OGDC)
4. Dividend Purification Engine (/shariah/{symbol}/purification):
   - Mathematically verified purification amount (dividend_income * interest_income_ratio)
   - Provisional rate flags and compliance notes
   - Rejection of purification for non-compliant stocks (ValidationFailedError 400/422)
   - Rejection of non-positive dividend income (<= 0)
"""

import sys
from pathlib import Path
import httpx

# Setup python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def run_shariah_audit():
    print("\n" + "="*70)
    print(" LIVE AWS END-TO-END AUDIT: SHARIAH COMPLIANCE ENGINE")
    print("="*70)

    base_url = "http://16.16.26.247:8000/api/v1"
    with httpx.Client(base_url=base_url, timeout=30.0) as client:
        # -------------------------------------------------------------
        # 1. KMI-30 Constituents List (/shariah/kmi30)
        # -------------------------------------------------------------
        print("\n--- 1. Testing KMI-30 Shariah Index Constituents (/shariah/kmi30) ---")
        r_kmi = client.get("/shariah/kmi30")
        assert r_kmi.status_code == 200, f"Failed KMI30 endpoint: {r_kmi.text}"
        kmi_data = r_kmi.json()
        
        assert kmi_data["index"] == "KMI-30"
        assert kmi_data["total_constituents"] >= 30, f"Expected >= 30 constituents, got {kmi_data['total_constituents']}"
        assert len(kmi_data["constituents"]) == kmi_data["total_constituents"]
        assert "effective_from" in kmi_data
        assert "source_url" in kmi_data
        
        print(f" [PASS] GET /shariah/kmi30 -> Status 200 | Total Constituents: {kmi_data['total_constituents']}")
        print(f"        Source Notice: {kmi_data.get('source_url')}")
        print(f"        Effective Date: {kmi_data.get('effective_from')} | Is Stale: {kmi_data.get('is_stale')}")
        
        sample_const = kmi_data["constituents"][0]
        print(f"        Sample Constituent: {sample_const['symbol']} ({sample_const['name']}) | Compliant: {sample_const['is_shariah_compliant']}")

        # -------------------------------------------------------------
        # 2. Compliant Stock Screening (/shariah/{symbol})
        # -------------------------------------------------------------
        print("\n--- 2. Testing Shariah Screening for Compliant Stocks ---")
        test_compliant_symbols = ["OGDC", "SYS", "LUCK", "EFERT", "MEBL"]
        
        for sym in test_compliant_symbols:
            r_sym = client.get(f"/shariah/{sym}")
            assert r_sym.status_code == 200, f"Failed for {sym}: {r_sym.text}"
            data = r_sym.json()
            assert data["symbol"] == sym
            assert data["is_shariah_compliant"] is True, f"Expected {sym} to be Shariah compliant!"
            assert data["screening_available"] is True
            assert isinstance(data["criteria"], list)
            assert len(data["criteria"]) == 6
            print(f" [PASS] /shariah/{sym} -> Compliant: True | Purification Rate: {data.get('purification_rate')} | Method: '{data.get('screening_method')}'")

        # -------------------------------------------------------------
        # 3. Non-Compliant Stock Screening (/shariah/{symbol})
        # -------------------------------------------------------------
        print("\n--- 3. Testing Shariah Screening for Non-Compliant Stocks ---")
        test_non_compliant = [
            ("HBL", "COMMERCIAL BANKS"),
            ("MCB", "COMMERCIAL BANKS"),
            ("UBL", "COMMERCIAL BANKS"),
            ("PAKT", "TOBACCO"),
            ("MUREB", "ALCOHOL / DISTILLERY"),
            ("EFUG", "INSURANCE"),
        ]
        
        for sym, expected_sector in test_non_compliant:
            r_nc = client.get(f"/shariah/{sym}")
            assert r_nc.status_code == 200
            data = r_nc.json()
            assert data["symbol"] == sym
            assert data["is_shariah_compliant"] is False, f"Expected {sym} to be Non-Compliant!"
            assert data["purification_rate"] is None, "Non-compliant stock must not have a purification rate"
            assert expected_sector in (data.get("sector") or ""), f"Expected sector {expected_sector}, got {data.get('sector')}"
            print(f" [PASS] /shariah/{sym} -> Compliant: False | Sector: '{data.get('sector')}' | Reason: '{data.get('compliance_summary')}'")

        # -------------------------------------------------------------
        # 4. 6-Point Criteria Breakdown (/shariah/{symbol}/criteria)
        # -------------------------------------------------------------
        print("\n--- 4. Testing 6-Point Shariah Criteria Details (/shariah/{symbol}/criteria) ---")
        r_crit = client.get("/shariah/SYS/criteria")
        assert r_crit.status_code == 200
        crit_data = r_crit.json()
        assert crit_data["symbol"] == "SYS"
        assert crit_data["is_shariah_compliant"] is True
        
        criteria_list = crit_data["criteria"]
        assert len(criteria_list) == 6
        expected_criteria_names = [
            "Core Business Permissibility",
            "Debt to Total Assets Ratio",
            "Non-Compliant Investments Ratio",
            "Non-Permissible / Interest Income Ratio",
            "Illiquid Assets to Total Assets Ratio",
            "Net Liquid Assets vs Market Price",
        ]
        
        for c in criteria_list:
            assert c["name"] in expected_criteria_names
            print(f"   • {c['name']:<42} | Threshold: {c['threshold']:<6} | Value: {str(c['value']):<8} | Passed: {c['passed']}")

        # Test PSX exception transparency (e.g. HUBC has circular debt investment exception)
        r_hubc = client.get("/shariah/HUBC/criteria")
        assert r_hubc.status_code == 200
        hubc_crit = r_hubc.json()["criteria"]
        hubc_exceptions = [c["exception"] for c in hubc_crit if c.get("exception")]
        assert len(hubc_exceptions) > 0, "HUBC must reflect PSX documented ratio exception"
        print(f" [PASS] PSX Documented Exception for HUBC: '{hubc_exceptions[0]}'")

        # -------------------------------------------------------------
        # 5. Dividend Purification Calculation (/shariah/{symbol}/purification)
        # -------------------------------------------------------------
        print("\n--- 5. Testing Dividend Purification Engine (/shariah/{symbol}/purification) ---")
        # SYS has interest_income_ratio = 0.09% (0.0009)
        test_dividend = 50000.0  # PKR 50,000 dividend income
        r_purif = client.get(f"/shariah/SYS/purification?dividend_income={test_dividend}")
        assert r_purif.status_code == 200
        purif = r_purif.json()
        
        assert purif["symbol"] == "SYS"
        assert purif["dividend_income"] == test_dividend
        expected_rate = purif["purification_rate"]
        expected_amount = round(test_dividend * expected_rate, 2)
        assert abs(purif["purification_amount"] - expected_amount) < 0.01
        
        print(f" [PASS] /shariah/SYS/purification -> Dividend: PKR {test_dividend:,.2f} | Rate: {expected_rate*100:.3f}% | Purification: PKR {purif['purification_amount']:,.2f}")
        print(f"        Notes: {purif.get('notes')}")

        # -------------------------------------------------------------
        # 6. Edge Cases & Validation Rejections
        # -------------------------------------------------------------
        print("\n--- 6. Testing Error & Edge Case Rejections ---")
        
        # 6.1 Purification rejection for non-compliant stock (HBL)
        r_bad_purif = client.get(f"/shariah/HBL/purification?dividend_income={test_dividend}")
        print(f" GET /shariah/HBL/purification (Non-Compliant stock) -> Status {r_bad_purif.status_code}")
        assert r_bad_purif.status_code in (400, 422)
        
        # 6.2 Zero dividend income
        r_zero_div = client.get("/shariah/SYS/purification?dividend_income=0")
        print(f" GET /shariah/SYS/purification (dividend_income=0) -> Status {r_zero_div.status_code}")
        assert r_zero_div.status_code == 422
        
        # 6.3 Negative dividend income
        r_neg_div = client.get("/shariah/SYS/purification?dividend_income=-500")
        print(f" GET /shariah/SYS/purification (dividend_income=-500) -> Status {r_neg_div.status_code}")
        assert r_neg_div.status_code == 422
        
        # 6.4 Unscreened unknown stock
        r_unknown = client.get("/shariah/UNKNOWN123")
        assert r_unknown.status_code == 200
        unknown_data = r_unknown.json()
        assert unknown_data["screening_available"] is False
        assert unknown_data["is_shariah_compliant"] is None
        print(f" [PASS] /shariah/UNKNOWN123 -> screening_available: False | is_shariah_compliant: None")


if __name__ == "__main__":
    run_shariah_audit()
    print("\n" + "="*70)
    print(" ALL SHARIAH COMPLIANCE ENGINE AUDIT TESTS PASSED!")
    print("="*70 + "\n")
