import json

with open("full_crud_latency_results.json", "r", encoding="utf-8") as f:
    data = json.load(f)

slow = [d for d in data if d.get("warm_ms", 0) >= 300]
slow.sort(key=lambda x: x.get("warm_ms", 0), reverse=True)

print(f"Total endpoints tested: {len(data)}")
print(f"Endpoints with warm latency >= 300ms: {len(slow)}\n")
print(f"{'Method':<7} {'Path':<55} {'Warm (ms)':<12} {'Cold (ms)':<12} {'Category'}")
print("-" * 105)
for d in slow:
    print(f"{d['method']:<7} {d['path']:<55} {d['warm_ms']:<12.2f} {d['cold_ms']:<12.2f} {d['category']}")
