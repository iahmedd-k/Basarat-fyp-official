import json

with open('reports/live_oracle_comprehensive_audit_2026-10-04.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

results = data.get('results', [])
failed = [r for r in results if not r.get('is_success')]

print(f"Total Failed: {len(failed)}")
for idx, r in enumerate(failed, 1):
    m = r.get('method')
    p = r.get('path')
    s = r.get('status_code')
    resp = r.get('response_sample')
    err = r.get('error')
    print(f"{idx:02d}. [{m:6s}] {p:45s} -> {s} | resp={resp}")
