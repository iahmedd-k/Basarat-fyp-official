import json

with open("reports/live_oracle_comprehensive_audit_2026-10-04.json", "r", encoding="utf-8") as f:
    report = json.load(f)

print("=== FAILED ENDPOINTS ===")
for r in report["results"]:
    if not r["is_success"]:
        print(f"#{r['id']:02d} [{r['status_code']}] {r['method']} {r['path']} ({r['name']}) -> {r.get('response_sample')}")

print("\n=== ENDPOINTS WITH NULLS ===")
for r in report["results"]:
    if r.get("has_null_values") and r["is_success"]:
        print(f"#{r['id']:02d} [{r['status_code']}] {r['method']} {r['path']} ({r['name']}) -> count: {r['null_count']}, fields: {[n['field'] for n in r['null_analysis'][:6]]}")

print("\n=== ENDPOINTS WITH ANOMALIES ===")
for r in report["results"]:
    if r.get("anomalies_or_wrong_values"):
        print(f"#{r['id']:02d} {r['path']} -> {r['anomalies_or_wrong_values']}")
