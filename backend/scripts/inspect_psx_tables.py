import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import httpx
from bs4 import BeautifulSoup
import json

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Screener headers
r = httpx.get("https://dps.psx.com.pk/screener", headers=headers, timeout=10)
soup = BeautifulSoup(r.text, "html.parser")
table = soup.find("table")
if table:
    headers = [th.get_text(strip=True) for th in table.find_all("th")]
    print("Screener headers:", headers)
    for row in table.find_all("tr")[1:6]:
        print("Row:", [td.get_text(strip=True) for td in row.find_all(["th", "td"])])

# Indices headers
r2 = httpx.get("https://dps.psx.com.pk/indices", headers=headers, timeout=10)
soup2 = BeautifulSoup(r2.text, "html.parser")
for t in soup2.find_all("table"):
    headers2 = [th.get_text(strip=True) for th in t.find_all("th")]
    print("Indices headers:", headers2)
    for row in t.find_all("tr")[1:4]:
        print("Ind row:", [td.get_text(strip=True) for td in row.find_all(["th", "td"])])
"""

run_remote_python(code)
