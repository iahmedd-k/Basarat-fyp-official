import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import json
from app.services.stock_service import StockService
from app.services.market_service import MarketService

ss = StockService()
ms = MarketService()

quotes = ms.get_market_data_sync()
print(f"Market data sync quotes count: {len(quotes) if quotes else 0}")
if quotes:
    ogdc_quote = [q for q in quotes if q.get('symbol') == 'OGDC']
    print(f"OGDC quote from market service: {ogdc_quote}")

frame = ss._get_market_frame()
print(f"StockService market frame shape: {frame.shape if frame is not None else None}")
if frame is not None and 'OGDC' in frame.index:
    print(f"OGDC in frame: {frame.loc['OGDC'].to_dict()}")

overview = ss.get_overview("OGDC")
print(f"OGDC overview: {overview}")

price_hist = ss.get_price_history("OGDC", "1M")
print(f"OGDC price history bars count: {len(price_hist.get('bars', []))}")
"""

run_remote_python(code)
