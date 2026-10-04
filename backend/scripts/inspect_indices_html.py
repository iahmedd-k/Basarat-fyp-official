import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import httpx
from bs4 import BeautifulSoup
import json
import pandas as pd

url = "https://dps.psx.com.pk/indices"
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
r = httpx.get(url, headers=headers, timeout=15)
soup = BeautifulSoup(r.text, "html.parser")

for i, table in enumerate(soup.find_all("table")):
    headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
    print(f"Table {i} headers: {headers}")
    for row in table.find_all("tr")[1:4]:
        print(" ", [td.get_text(strip=True) for td in row.find_all(["th", "td"])])
"""

run_remote_python(code)
