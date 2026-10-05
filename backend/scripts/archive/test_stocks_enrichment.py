import os
os.environ["SECRET_KEY"] = "testsecretkey12345678901234567890"

import sys
import json
from pathlib import Path

# Add backend to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.stock_service import StockService

def main():
    s = StockService()
    for sym in ["PSO", "OGDC", "SYS", "MEBL", "HBL"]:
        data = s.get_fundamentals(sym)
        print(f"=== {sym} ===")
        print("Sector:", data.get("company_profile", {}).get("sector"))
        print("Trading Limits:", data.get("trading_limits"))
        so = data.get("sector_overview", {})
        print("Sector Overview:", so.get("sector"), f"({so.get('companies_count')} companies, rank {so.get('stock_rank')})")
        print()

if __name__ == "__main__":
    main()
