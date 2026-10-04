import json
import sys

def main():
    report_path = "backend/reports/live_oracle_comprehensive_audit_2026-10-04.json"
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("=== SUMMARY METADATA ===")
    print(json.dumps(data["metadata"], indent=2))

    print("\n=== FAILED ENDPOINTS ===")
    for r in data["results"]:
        if not r["is_success"]:
            print(f"ID {r['id']}: [{r['method']}] {r['path']} -> Error: {r.get('error')}")

    print("\n=== ENDPOINTS WITH NULL VALUES ===")
    for r in data["results"]:
        if r["has_null_values"]:
            print(f"ID {r['id']}: [{r['method']}] {r['path']} (Category: {r['category']}) -> Null Count: {r['null_count']}")
            for p in r["null_analysis"][:10]:
                print(f"   - {p}")
            if len(r["null_analysis"]) > 10:
                print(f"   ... and {len(r['null_analysis']) - 10} more")

if __name__ == "__main__":
    main()
