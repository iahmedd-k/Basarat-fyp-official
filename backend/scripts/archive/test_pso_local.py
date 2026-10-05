import json
from app.services.stock_service import StockService

def main():
    s = StockService()
    data = s.get_fundamentals('PSO')
    print("=== ENRICHED PSO FUNDAMENTALS ===")
    print("Company Profile Sector:", data.get("company_profile", {}).get("sector"))
    print("Trading Limits:", json.dumps(data.get("trading_limits"), indent=2))
    print("Sector Overview:", json.dumps(data.get("sector_overview"), indent=2))

if __name__ == "__main__":
    main()
