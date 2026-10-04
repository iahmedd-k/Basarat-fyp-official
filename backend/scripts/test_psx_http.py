import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import httpx
from bs4 import BeautifulSoup
import json

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# 1. Test screener
try:
    r = httpx.get("https://dps.psx.com.pk/screener", headers=headers, timeout=10)
    print("Screener status:", r.status_code, "len:", len(r.text))
    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table")
    print("Screener tables count:", len(tables))
    if tables:
        rows = tables[0].find_all("tr")
        print("Screener rows count:", len(rows))
        if len(rows) > 1:
            print("Row 1 cells:", [td.get_text(strip=True) for td in rows[1].find_all(["th", "td"])])
except Exception as e:
    print("Screener err:", e)

# 2. Test indices / market watch / symbols
urls = [
    "https://dps.psx.com.pk/indices",
    "https://dps.psx.com.pk/timeseries/int/KSE100",
    "https://dps.psx.com.pk/timeseries/eod/KSE100",
    "https://dps.psx.com.pk/sector/0807",
    "https://dps.psx.com.pk/company/OGDC",
]
for url in urls:
    try:
        r = httpx.get(url, headers=headers, timeout=10)
        print(f"{url} -> status {r.status_code}, len {len(r.text)}")
    except Exception as e:
        print(f"{url} -> err {e}")
"""

run_remote_python(code)
