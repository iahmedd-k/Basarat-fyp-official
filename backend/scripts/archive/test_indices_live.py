import urllib.request
import json

urls = [
    "http://193.123.84.223:8000/api/v1/market/indices/kse-100",
    "http://193.123.84.223:8000/api/v1/market/indices/kse-30",
    "http://193.123.84.223:8000/api/v1/market/indices/kmi-30",
]

for u in urls:
    try:
        r = urllib.request.urlopen(u, timeout=15)
        d = json.loads(r.read().decode())
        c = d.get("constituents", [])
        print(f"{d.get('index')} ({d.get('code')}) -> {len(c)} constituents, is_stale={d.get('is_stale')}")
        if c:
            print("   Sample:", [x["symbol"] for x in c[:8]])
    except Exception as e:
        print(u, "ERR:", e)
