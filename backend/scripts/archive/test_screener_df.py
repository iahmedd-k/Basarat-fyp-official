import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import httpx
from bs4 import BeautifulSoup
import pandas as pd
import re

def fetch_screener_df():
    url = "https://dps.psx.com.pk/screener"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    r = httpx.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    table = soup.find("table")
    if not table:
        return None
    
    headers = [th.get_text(strip=True).upper() for th in table.find_all("th")]
    sym_idx = headers.index("SYMBOL") if "SYMBOL" in headers else 0
    price_idx = headers.index("PRICE") if "PRICE" in headers else -1
    ch_idx = headers.index("CHANGE (%)") if "CHANGE (%)" in headers else -1
    sector_idx = headers.index("SECTOR") if "SECTOR" in headers else -1
    vol_idx = headers.index("30D VOLUME AVG.") if "30D VOLUME AVG." in headers else -1
    mcap_idx = headers.index("MARKET CAP.") if "MARKET CAP." in headers else -1
    
    rows = []
    for tr in table.find_all("tr")[1:]:
        tds = [td.get_text(strip=True) for td in tr.find_all(["th", "td"])]
        if len(tds) <= max(sym_idx, price_idx):
            continue
        sym = tds[sym_idx].upper().strip()
        if not sym or not sym.isalnum():
            continue
        
        try:
            curr = float(tds[price_idx].replace(",", "").replace("%", "")) if price_idx >= 0 else None
        except:
            curr = None
            
        try:
            ch_pct = float(tds[ch_idx].replace(",", "").replace("%", "")) if ch_idx >= 0 else 0.0
        except:
            ch_pct = 0.0
            
        try:
            vol_str = tds[vol_idx].replace(",", "") if vol_idx >= 0 else "0"
            vol = int(float(vol_str))
        except:
            vol = 0
            
        # LDCP calculated from price and change %
        ldcp = round(curr / (1 + ch_pct / 100.0), 2) if (curr and ch_pct is not None and ch_pct != -100) else curr
        change = round(curr - ldcp, 2) if (curr and ldcp) else 0.0
        
        rows.append({
            "SYMBOL": sym,
            "NAME": sym,
            "CURRENT": curr,
            "LDCP": ldcp,
            "OPEN": curr,
            "HIGH": curr,
            "LOW": curr,
            "CHANGE": change,
            "CHANGE_PCT": ch_pct,
            "VOLUME": vol,
            "SECTOR": tds[sector_idx] if sector_idx >= 0 else None,
        })
        
    df = pd.DataFrame(rows).set_index("SYMBOL")
    return df

df = fetch_screener_df()
print("Screener DF shape:", df.shape if df is not None else "None")
if df is not None:
    print("OGDC row:", df.loc["OGDC"].to_dict() if "OGDC" in df.index else "not in index")
    print("HBL row:", df.loc["HBL"].to_dict() if "HBL" in df.index else "not in index")
"""

run_remote_python(code)
