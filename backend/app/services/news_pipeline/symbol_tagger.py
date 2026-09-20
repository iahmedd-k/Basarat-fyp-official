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
    "OGDC": ["ogdcl", "oil and gas development"],
    "PPL": ["pakistan petroleum"],
    "MAR": ["mari petroleum"],
    "SSGC": ["sui southern gas"],
    "SSGC": ["sui northern gas", "sngpl"],
    "UBL": ["united bank"],
    "HBL": ["habib bank"],
    "MCB": ["mcbl", "mcba", "mcb bank"],
    "ABL": ["allied bank"],
    "NBP": ["national bank"],
    "BAFL": ["bank alfalah"],
    "BOP": ["bank of punjab"],
    "MLCF": ["maple leaf cement"],
    "LUCK": ["lucky cement"],
    "FCCL": ["fauji cement"],
    "DGKC": ["d. g. khan cement", "dg khan cement"],
    "ACPL": ["attock cement"],
    "EFERT": ["engro fertilizers"],
    "ENGRO": ["engro corporation", "engro foods", "engro polymer"],
    "FATIMA": ["fatima fertilizers"],
    "FFC": ["fauji fertilizer"],
    "FFBL": ["fauji fertilizer bin qasim"],
    "KEL": ["k electric", "k-electric"],
    "HUBC": ["hub power", "hubco"],
    "KAPCO": ["kot addu power"],
    "NRL": ["national refinery"],
    "PRL": ["pakistan refinery"],
    "BYCO": ["byco petroleum"],
    "ATRL": ["attock refinery"],
    "PIAA": ["pioneer cement", "pioneer"],
    "HASCOL": ["hascol petroleum"],
    "WTL": ["worldcall telecom", "worldcall"],
    "NETSOL": ["netsol technologies"],
    "TRG": ["trg Pakistan"],
    "SYS": ["systems limited"],
    "AIRLINK": ["airlink communication"],
    "GHGL": ["ghaazi healthcare"],
    "SHEL": ["shell pakistan"],
    "PSO": ["pakistan state oil"],
    "PAK": ["pakistan international airlines", "pia"],
    "INDU": ["indus motor"],
    "HCAR": ["hubco car", "honda car"],
    "ATYC": ["attock tex"],
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
