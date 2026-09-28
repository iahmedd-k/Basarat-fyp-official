"""Map news articles to PSX-listed company symbols.

Strategy (keyword/entity matching — no NER model):
  1. Load the Stock table (symbol, name, sector) once per run.
  2. Build lookup dicts: symbol -> Stock, name -> symbol, alias -> symbol.
  3. For each article, case-insensitive match against title + summary.
  4. Return matched symbols (may be multiple per article).
  5. Structure is ready for NER replacement later.
"""

import logging
import re

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock

log = logging.getLogger(__name__)

# ── Static aliases (PSX tickers that differ from company name) ──────────
_STATIC_ALIASES: dict[str, list[str]] = {
    "MEBL": ["meezan bank", "meezan", "mezan bank", "mezan", "mebl", "mizan bank", "mizan"],
    "OGDC": ["ogdcl", "ogdc", "oil and gas development company", "oil and gas development", "oil and gas", "oil & gas"],
    "PPL": ["pakistan petroleum", "ppl"],
    "MARI": ["mari petroleum", "mari energies", "mari"],
    "SSGC": ["sui southern gas", "ssgc"],
    "SNGP": ["sui northern gas", "sngpl", "sngp"],
    "UBL": ["united bank", "ubl"],
    "HBL": ["habib bank", "hbl"],
    "MCB": ["mcbl", "mcba", "mcb bank", "mcb"],
    "ABL": ["allied bank", "abl"],
    "NBP": ["national bank", "nbp"],
    "BAFL": ["bank alfalah", "alfalah", "bafl"],
    "BAHL": ["bank al habib", "bahl", "al habib"],
    "BOP": ["bank of punjab", "bop"],
    "FABL": ["faysal bank", "fabl"],
    "MLCF": ["maple leaf cement", "maple leaf", "mlcf"],
    "LUCK": ["lucky cement", "lucky", "luck"],
    "FCCL": ["fauji cement", "fccl"],
    "DGKC": ["d. g. khan cement", "dg khan cement", "dgkc"],
    "ACPL": ["attock cement", "acpl"],
    "CHCC": ["cherat cement", "chcc"],
    "PIAA": ["pioneer cement", "pioneer"],
    "EFERT": ["engro fertilizers", "efert"],
    "ENGRO": ["engro corporation", "engro corp", "engro foods", "engro polymer", "engro"],
    "FATIMA": ["fatima fertilizers", "fatima fertilizer", "fatima"],
    "FFC": ["fauji fertilizer company", "fauji fertilizer", "ffc"],
    "FFBL": ["fauji fertilizer bin qasim", "ffbl"],
    "KEL": ["k electric", "k-electric", "kel", "kesc"],
    "HUBC": ["hub power", "hubco", "hubc"],
    "KAPCO": ["kot addu power", "kapco"],
    "NRL": ["national refinery", "nrl"],
    "PRL": ["pakistan refinery", "prl"],
    "BYCO": ["byco petroleum", "cnergyico"],
    "ATRL": ["attock refinery", "atrl"],
    "HASCOL": ["hascol petroleum", "hascol"],
    "WTL": ["worldcall telecom", "worldcall", "wtl"],
    "NETSOL": ["netsol technologies", "netsol"],
    "TRG": ["trg pakistan", "trg"],
    "SYS": ["systems limited", "systems", "sys"],
    "AIRLINK": ["airlink communication", "airlink"],
    "GHGL": ["ghaazi healthcare"],
    "SHEL": ["shell pakistan", "shell"],
    "PSO": ["pakistan state oil", "pso"],
    "PAK": ["pakistan international airlines", "pia"],
    "INDU": ["indus motor", "indus motors", "toyota"],
    "HCAR": ["honda atlas", "honda car", "hcar"],
    "ATYC": ["attock tex"],
    "ILP": ["interloop", "ilp"],
    "SEARL": ["the searle company", "searle", "searl"],
    "AVN": ["avanceon", "avn"],
    "UNITY": ["unity foods", "unity"],
    "PAEL": ["pak elektron", "pel", "pael"],
    "TREET": ["treet corporation", "treet"],
    "PTC": ["pakistan telecommunication", "ptcl", "ptc"],
    "EPCL": ["engro polymer", "epcl"],
}


def _build_alias_map(stocks: list[Stock]) -> dict[str, str]:
    """Map lowercased alias -> symbol."""
    alias_map: dict[str, str] = {}
    for s in stocks:
        sym = s.symbol.upper()
        # Map the symbol itself
        alias_map[sym.lower()] = sym
        # Map the full company name (lower-cased)
        if s.name:
            alias_map[s.name.lower().strip()] = sym
            # Map individual significant words (>=4 chars) from the name
            for word in s.name.lower().split():
                if len(word) >= 4 and word.isalpha():
                    alias_map.setdefault(word, sym)
        # Map sector keyword
        if s.sector:
            alias_map.setdefault(s.sector.lower().strip(), sym)
    # Static aliases
    for sym, aliases in _STATIC_ALIASES.items():
        for alias in aliases:
            alias_map[alias.lower()] = sym
    return alias_map


async def load_stock_symbols(db: AsyncSession) -> list[Stock]:
    """Load all active stocks from DB."""
    result = await db.execute(select(Stock).where(Stock.is_active == True))
    return list(result.scalars().all())


def tag_article(
    text: str,
    alias_map: dict[str, str],
    min_match_len: int = 3,
) -> list[str]:
    """Match text against the alias map. Returns sorted unique symbols."""
    text_lower = text.lower()
    matched_symbols: set[str] = set()

    for alias, symbol in alias_map.items():
        if len(alias) < min_match_len:
            continue
        # Use word-boundary regex to avoid false positives
        pattern = re.compile(r"\b" + re.escape(alias) + r"\b", re.IGNORECASE)
        if pattern.search(text_lower):
            matched_symbols.add(symbol)

    return sorted(matched_symbols)


async def tag_articles(
    db: AsyncSession,
    articles: list[dict],
) -> list[dict]:
    """Tag a batch of articles. Each dict must have 'title' and 'summary' keys.

    Returns the same dicts with 'symbols' and 'company_names' keys added.
    """
    stocks = await load_stock_symbols(db)
    alias_map = _build_alias_map(stocks)
    sym_to_name = {s.symbol.upper(): s.name for s in stocks}

    for article in articles:
        text = f"{article.get('title', '')} {article.get('summary', '')}"
        symbols = tag_article(text, alias_map)
        article["symbols"] = symbols
        article["company_names"] = [sym_to_name.get(s, "") for s in symbols]

    return articles
