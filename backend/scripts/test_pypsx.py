import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import pypsx_toolkit
print("pypsx_toolkit:", pypsx_toolkit)

try:
    mw = pypsx_toolkit.market_watch()
    print("market_watch:", type(mw), len(mw) if mw is not None else "None")
except Exception as e:
    print("market_watch err:", e)

try:
    indices = pypsx_toolkit.get_indices()
    print("get_indices:", type(indices), len(indices) if indices is not None else "None")
except Exception as e:
    print("get_indices err:", e)

try:
    constituents = pypsx_toolkit.index_constituents("KSE100")
    print("KSE100 constituents:", type(constituents), len(constituents) if constituents is not None else "None")
except Exception as e:
    print("KSE100 err:", e)
"""

run_remote_python(code)
