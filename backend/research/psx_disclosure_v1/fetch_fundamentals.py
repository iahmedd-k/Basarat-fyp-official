"""Fetch fundamental & financial snapshot metrics via pypsx_toolkit for PSX stocks."""
import json
import logging
from pathlib import Path
import pandas as pd
import pypsx_toolkit as psx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("fetch_fundamentals")

HERE = Path(__file__).resolve().parent
DATA_DIR = HERE / "data"
OUT_PATH = DATA_DIR / "fundamentals_snapshot.json"

def main():
    events_cov = DATA_DIR / "events_coverage.json"
    symbols = ["SYS", "OGDC", "HUBC", "LUCK", "ENGRO", "MCB", "HBL", "MEBL", "UBL", "MARI", 
               "POL", "PSO", "ATRL", "FFC", "EFERT", "MLCF", "TRG", "AIRLINK", "SEARL", "DGKC",
               "BAHL", "BOP", "FABL", "HMB", "NBP", "SCBPL", "PPL", "APL", "SNGP", "SSGC",
               "CNERGY", "NRL", "PRL", "ENGROH", "FATIMA", "BWCL", "CHCC", "FCCL", "KOHC", "PIOC",
               "POWER", "KAPCO", "KEL", "NPL", "HUMNL", "PTC", "ABOT", "AGP", "CPHL", "GLAXO",
               "HALEON", "HINOON", "SHFA", "ATLH", "HCAR", "INDU", "MTL", "SAZEW", "THALL"]

    records = {}
    for i, symbol in enumerate(symbols, start=1):
        try:
            t = psx.Ticker(symbol)
            div_df = t.dividends() if callable(getattr(t, "dividends", None)) else t.dividends
            
            div_yield = None
            payout_ratio = None
            annual_div = None

            if isinstance(div_df, pd.DataFrame) and not div_df.empty:
                if "DIVIDEND YIELD" in div_df.columns:
                    div_yield = str(div_df["DIVIDEND YIELD"].iloc[0])
                if "PAYOUT RATIO" in div_df.columns:
                    payout_ratio = str(div_df["PAYOUT RATIO"].iloc[0])
                if "ANNUAL DIVIDEND" in div_df.columns:
                    annual_div = str(div_df["ANNUAL DIVIDEND"].iloc[0])

            records[symbol] = {
                "symbol": symbol,
                "dividend_yield": div_yield,
                "payout_ratio": payout_ratio,
                "annual_dividend": annual_div,
            }
            log.info("[%d/%d] Fetched %s -> Yield: %s | Payout: %s", i, len(symbols), symbol, div_yield, payout_ratio)
        except Exception as e:
            log.warning("[%d/%d] Failed %s: %s", i, len(symbols), symbol, e)
            records[symbol] = {"symbol": symbol, "dividend_yield": None, "payout_ratio": None, "annual_dividend": None}

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(records, indent=2), encoding="utf-8")
    log.info("Saved fundamentals snapshot to %s (%d symbols)", OUT_PATH, len(records))

if __name__ == "__main__":
    main()
