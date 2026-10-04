import httpx
import json

def main():
    for sym in ['OGDC', 'SYS', 'MEBL', 'HBL', 'PSO']:
        res = httpx.get(f'http://193.123.84.223:8000/api/v1/stocks/{sym}/fundamentals', timeout=15.0)
        print(f"=== LIVE {sym} ({res.status_code}) ===")
        if res.status_code == 200:
            d = res.json()
            print("Sector:", d.get('company_profile', {}).get('sector'))
            print("Trading Limits:", d.get('trading_limits'))
            so = d.get('sector_overview', {})
            print("Sector Overview:", so.get('sector'), f"({so.get('companies_count')} companies, rank {so.get('stock_rank')})")
            print("Stock Price in Sector Overview:", so.get('stock', {}).get('current'), "Volume:", so.get('stock', {}).get('volume'))
        print()

if __name__ == "__main__":
    main()
