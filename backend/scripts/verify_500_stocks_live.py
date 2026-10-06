import sys
import time
import httpx
import psycopg2

sys.stdout.reconfigure(encoding='utf-8')

DATABASE_URL = "postgresql://neondb_owner:npg_9RQm1usGdEJS@ep-bold-grass-b42cai5z-pooler.c-6.us-east-2.aws.neon.tech/neondb?sslmode=require"
SERVER_BASE = "http://193.123.84.223:8000"

print("=" * 80)
print("🔍 1. VERIFYING POSTGRESQL COUNTS")
print("=" * 80)

conn = psycopg2.connect(DATABASE_URL)
cur = conn.cursor()

cur.execute("SELECT COUNT(*) FROM stocks;")
total_stocks = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM stock_prices;")
total_prices = cur.fetchone()[0]

cur.execute("SELECT COUNT(*) FROM stock_fundamentals;")
total_fundamentals = cur.fetchone()[0]

print(f"Total Stocks in DB:            {total_stocks}")
print(f"Total Stock Prices (OHLCV):    {total_prices}")
print(f"Total Stock Fundamentals:      {total_fundamentals}")

# Sample non-KSE-100 and KSE-100 stocks
test_symbols = ["TRG", "SYS", "OGDC", "AABS", "ABOT", "AGTL", "BIPL", "BIFO", "FFBL", "GADT"]

try:
    with open("test_token.txt") as f:
        TOKEN = f.read().strip()
except Exception:
    TOKEN = None

headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}

print("\n" + "=" * 80)
print("🚀 2. VERIFYING LIVE SERVER ENDPOINTS FOR KSE-100 & NON-KSE-100 STOCKS")
print("=" * 80)

client = httpx.Client(timeout=20.0, headers=headers)

for sym in test_symbols:
    # 1. Overview
    t0 = time.perf_counter()
    r_ov = client.get(f"{SERVER_BASE}/api/v1/stocks/{sym}/overview")
    lat_ov = (time.perf_counter() - t0) * 1000.0
    status_ov = r_ov.status_code
    
    # 2. Fundamentals
    t0 = time.perf_counter()
    r_fu = client.get(f"{SERVER_BASE}/api/v1/stocks/{sym}/fundamentals")
    lat_fu = (time.perf_counter() - t0) * 1000.0
    status_fu = r_fu.status_code
    data_status = r_fu.json().get("data_status") if status_fu == 200 else "N/A"
    
    # 3. Technicals
    t0 = time.perf_counter()
    r_te = client.get(f"{SERVER_BASE}/api/v1/stocks/{sym}/technicals")
    lat_te = (time.perf_counter() - t0) * 1000.0
    status_te = r_te.status_code
    
    # 4. Forecast guardrail check
    t0 = time.perf_counter()
    r_fc = client.get(f"{SERVER_BASE}/api/v1/forecast/{sym}")
    lat_fc = (time.perf_counter() - t0) * 1000.0
    status_fc = r_fc.status_code

    print(f"[{sym:5s}] Overview: {status_ov} ({lat_ov:5.1f}ms) | Fund: {status_fu} [{data_status}] ({lat_fu:5.1f}ms) | Tech: {status_te} ({lat_te:5.1f}ms) | Forecast: {status_fc} ({lat_fc:5.1f}ms)")

print("=" * 80)
print("✅ Verification Complete!")
