import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import httpx
from bs4 import BeautifulSoup
import json

url = "https://dps.psx.com.pk/screener"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
r = httpx.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")
table = soup.find("table")
headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
sym_idx = headers.index("SYMBOL")
listed_idx = headers.index("LISTED IN")

kse100 = []
kse30 = []
kmi30 = []

for tr in table.find_all("tr")[1:]:
    tds = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
    if len(tds) <= max(sym_idx, listed_idx):
        continue
    sym = tds[sym_idx].upper().strip()
    listed = tds[listed_idx].upper()
    if "KSE100" in listed:
        kse100.append(sym)
    if "KSE30" in listed:
        kse30.append(sym)
    if "KMI30" in listed:
        kmi30.append(sym)

print(f"Screener index counts -> KSE100: {len(kse100)}, KSE30: {len(kse30)}, KMI30: {len(kmi30)}")
print("Sample KSE100:", kse100[:10])
print("Sample KSE30:", kse30[:10])
print("Sample KMI30:", kmi30[:10])
"""

run_remote_python(code)
