"""Map news articles to PSX-listed company symbols.

Strategy (keyword & entity phrase matching):
  1. Load the Stock table (symbol, name, sector) once per run.
  2. Build clean lookup dicts with unambiguous company aliases and ticker patterns.
  3. Filter out generic financial words (e.g., 'bank', 'systems', 'power', 'limited')
     to prevent false positives across unrelated macroeconomic articles.
  4. Perform case-sensitive matching for short ticker symbols and case-insensitive
     matching for distinct multi-word company aliases.
  5. Return matched symbols (may be multiple per article).
"""

import logging
import re
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.stock import Stock

log = logging.getLogger(__name__)

# ── Generic stopwords that must NEVER match as standalone aliases ──────
_GENERIC_STOPWORDS = {
    "bank", "banks", "limited", "ltd", "corporation", "corp", "company", "co",
    "pakistan", "power", "energy", "cement", "fertilizer", "fertilizers", "sugar",
    "textile", "textiles", "chemical", "chemicals", "refinery", "refineries",
    "oil", "gas", "petroleum", "investments", "investment", "holdings", "holding",
    "services", "service", "engineering", "financial", "finance", "securities",
    "security", "leasing", "modaraba", "mutual", "fund", "funds", "group",
    "foods", "food", "motors", "motor", "pharma", "pharmaceutical", "pharmaceuticals",
    "industries", "industry", "industrial", "global", "capital", "tech", "technology",
    "technologies", "telecom", "telecommunication", "international", "commercial",
    "glass", "auto", "automotive", "development", "electric", "syndicate", "trust",
    "paper", "board", "general", "insurance", "takaful", "islamic", "first",
    "national", "southern", "northern", "united", "allied", "standard", "premier",
}

# ── Static Curated Aliases for PSX Companies ───────────────────────────
_STATIC_ALIASES: dict[str, list[str]] = {
    "MEBL": ["meezan bank", "meezan", "mezan bank", "mizan bank", "mebl"],
    "OGDC": ["ogdcl", "ogdc", "oil & gas development company", "oil and gas development company", "oil & gas development co", "oil and gas development co"],
    "PPL": ["pakistan petroleum", "pakistan petroleum limited", "ppl"],
    "MARI": ["mari petroleum", "mari energies", "mari petroleum company"],
    "SSGC": ["sui southern gas", "sui southern gas company", "ssgc"],
    "SNGP": ["sui northern gas", "sui northern gas pipelines", "sngpl", "sngp"],
    "UBL": ["united bank limited", "united bank ltd", "united bank", "ubl"],
    "HBL": ["habib bank limited", "habib bank ltd", "habib bank", "hbl"],
    "MCB": ["mcb bank limited", "mcb bank ltd", "mcb bank", "mcbl", "mcb"],
    "ABL": ["allied bank limited", "allied bank ltd", "allied bank", "abl"],
    "NBP": ["national bank of pakistan", "national bank", "nbp"],
    "BAFL": ["bank alfalah", "bank alfalah limited", "bafl"],
    "BAHL": ["bank al habib", "bank al-habib", "bahl"],
    "BOP": ["bank of punjab", "the bank of punjab", "bop"],
    "FABL": ["faysal bank", "faysal bank limited", "fabl"],
    "HMB": ["habib metropolitan bank", "habib metro", "hmb"],
    "SNBL": ["soneri bank", "soneri bank limited", "snbl"],
    "AKBL": ["askari bank", "askari bank limited", "akbl"],
    "SCBPL": ["standard chartered bank pakistan", "standard chartered pakistan", "scbpl"],
    "MLCF": ["maple leaf cement", "maple leaf cement factory", "mlcf"],
    "LUCK": ["lucky cement", "lucky cement limited", "luck"],
    "FCCL": ["fauji cement", "fauji cement company", "fccl"],
    "DGKC": ["d.g. khan cement", "dg khan cement", "dgkc"],
    "ACPL": ["attock cement", "attock cement pakistan", "acpl"],
    "CHCC": ["cherat cement", "cherat cement company", "chcc"],
    "PIOC": ["pioneer cement", "pioneer cement limited", "pioc"],
    "EFERT": ["engro fertilizers", "engro fertilizer", "efert"],
    "ENGRO": ["engro corporation", "engro corp", "engro polymer", "engro foods"],
    "FATIMA": ["fatima fertilizer", "fatima fertilizers", "fatima fertilizer company"],
    "FFC": ["fauji fertilizer company", "fauji fertilizer", "ffc"],
    "FFBL": ["fauji fertilizer bin qasim", "ffbl"],
    "KEL": ["k electric", "k-electric", "kel", "kesc"],
    "HUBC": ["hub power", "hub power company", "hubco", "hubc"],
    "KAPCO": ["kot addu power", "kot addu power company", "kapco"],
    "NRL": ["national refinery", "national refinery limited", "nrl"],
    "PRL": ["pakistan refinery", "pakistan refinery limited", "prl"],
    "CNERGY": ["cnergyico", "cnergyico pk", "byco petroleum", "byco"],
    "ATRL": ["attock refinery", "attock refinery limited", "atrl"],
    "APL": ["attock petroleum", "attock petroleum limited", "apl"],
    "HASCOL": ["hascol petroleum", "hascol petroleum limited", "hascol"],
    "WTL": ["worldcall telecom", "worldcall telecom limited", "worldcall", "wtl"],
    "NETSOL": ["netsol technologies", "netsol technologies limited", "netsol"],
    "TRG": ["trg pakistan", "trg pakistan limited", "trg"],
    "SYS": ["systems limited", "systems ltd", "sys"],
    "AIRLINK": ["air link communication", "airlink communication", "airlink"],
    "SHEL": ["shell pakistan", "shell pakistan limited"],
    "PSO": ["pakistan state oil", "pakistan state oil company", "pso"],
    "INDU": ["indus motor", "indus motor company", "indus motors", "toyota indus"],
    "HCAR": ["honda atlas", "honda atlas cars", "honda car", "hcar"],
    "PSMC": ["pak suzuki", "pak suzuki motor", "psmc"],
    "ILP": ["interloop", "interloop limited", "ilp"],
    "SEARL": ["the searle company", "searle company", "searle", "searl"],
    "AVN": ["avanceon", "avanceon limited", "avn"],
    "UNITY": ["unity foods", "unity foods limited"],
    "PAEL": ["pak elektron", "pak elektron limited", "pel", "pael"],
    "TREET": ["treet corporation", "treet corp", "treet"],
    "PTC": ["pakistan telecommunication", "pakistan telecommunication company", "ptcl", "ptc"],
    "EPCL": ["engro polymer", "engro polymer & chemicals", "epcl"],
    "GLAXO": ["glaxosmithkline pakistan", "glaxosmithkline", "gsk pakistan", "glaxo"],
    "AGP": ["agp limited", "agp pharma", "agp"],
    "HIGHNOON": ["highnoon laboratories", "highnoon"],
    "TGL": ["tariq glass", "tariq glass industries", "tgl"],
    "GGGL": ["ghani global glass", "ghani glass", "gggl"],
}


def _clean_company_name(name: str) -> str:
    """Strip generic corporate suffixes while preserving the distinctive brand core."""
    cleaned = re.sub(
        r"\b(limited|ltd|corporation|corp|company|co|inc|plc|pakistan|the)\b",
        "",
        name,
        flags=re.IGNORECASE,
    )
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def _build_alias_map(stocks: list[Stock]) -> dict[str, str]:
    """Map lowercased alias / company phrases -> symbol."""
    alias_map: dict[str, str] = {}

    for s in stocks:
        sym = s.symbol.upper()
        # Always map the exact ticker
        alias_map[sym.lower()] = sym

        if s.name:
            full_name = s.name.lower().strip()
            alias_map[full_name] = sym

            # Cleaned company name (e.g. "Lucky Cement Limited" -> "lucky cement")
            core_name = _clean_company_name(s.name).lower()
            if len(core_name) >= 3 and core_name not in _GENERIC_STOPWORDS:
                alias_map[core_name] = sym

    # Incorporate static aliases
    for sym, aliases in _STATIC_ALIASES.items():
        for alias in aliases:
            cleaned_alias = alias.lower().strip()
            if cleaned_alias and cleaned_alias not in _GENERIC_STOPWORDS:
                alias_map[cleaned_alias] = sym

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
    """Match text against the alias map. Returns sorted unique symbols.
    
    Protects against false positives by ensuring word boundaries and checking
    against generic words.
    """
    if not text:
        return []

    text_lower = text.lower()
    matched_symbols: set[str] = set()

    for alias, symbol in alias_map.items():
        if len(alias) < min_match_len or alias in _GENERIC_STOPWORDS:
            continue

        # Use word-boundary regex to prevent partial substring matches
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

