from datetime import datetime
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shariah import ShariahScreening
from app.models.stock import Stock
from app.services.market_service import MarketService

log = logging.getLogger(__name__)

# Compliance outcomes use source-backed index membership or known business activity.
# Non-compliant conventional institutions & sectors
NON_COMPLIANT_SECTORS = {
    "BANKING",
    "COMMERCIAL BANKS",
    "CONVENTIONAL BANKING",
    "INSURANCE",
    "LIFE INSURANCE",
    "TOBACCO",
    "DISTILLERY",
    "ALCOHOL",
    "GAMBLING",
}

NON_COMPLIANT_SYMBOLS: dict[str, dict] = {
    "HBL": {"name": "Habib Bank Limited", "sector": "COMMERCIAL BANKS", "reason": "Conventional interest-based banking."},
    "UBL": {"name": "United Bank Limited", "sector": "COMMERCIAL BANKS", "reason": "Conventional interest-based banking."},
    "MCB": {"name": "MCB Bank Limited", "sector": "COMMERCIAL BANKS", "reason": "Conventional interest-based banking."},
    "NBP": {"name": "National Bank of Pakistan", "sector": "COMMERCIAL BANKS", "reason": "Conventional interest-based banking."},
    "BAFL": {"name": "Bank Alfalah Limited", "sector": "COMMERCIAL BANKS", "reason": "Conventional banking business."},
    "BAHL": {"name": "Bank AL Habib Limited", "sector": "COMMERCIAL BANKS", "reason": "Conventional banking business."},
    "ABL": {"name": "Allied Bank Limited", "sector": "COMMERCIAL BANKS", "reason": "Conventional banking business."},
    "JSBL": {"name": "JS Bank Limited", "sector": "COMMERCIAL BANKS", "reason": "Conventional banking business."},
    "BOP": {"name": "The Bank of Punjab", "sector": "COMMERCIAL BANKS", "reason": "Conventional banking business."},
    "SNBL": {"name": "Soneri Bank Limited", "sector": "COMMERCIAL BANKS", "reason": "Conventional banking business."},
    "PAKT": {"name": "Pakistan Tobacco Company", "sector": "TOBACCO", "reason": "Tobacco manufacturing."},
    "PMPK": {"name": "Philip Morris (Pakistan)", "sector": "TOBACCO", "reason": "Tobacco manufacturing."},
    "MUREB": {"name": "Murree Brewery Co. Ltd.", "sector": "ALCOHOL / DISTILLERY", "reason": "Alcohol & brewery manufacturing."},
    "EFUG": {"name": "EFU General Insurance", "sector": "INSURANCE", "reason": "Conventional commercial insurance."},
    "AICL": {"name": "Adamjee Insurance Co.", "sector": "INSURANCE", "reason": "Conventional commercial insurance."},
    "IGIHL": {"name": "IGI Holdings Limited", "sector": "INSURANCE", "reason": "Conventional insurance group."},
}


class ShariahService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_stock_by_symbol(self, symbol: str) -> Stock | None:
        result = await self.db.execute(
            select(Stock).where(Stock.symbol == symbol.upper())
        )
        return result.scalars().first()

    async def get_latest_screening(self, stock_id: str) -> ShariahScreening | None:
        result = await self.db.execute(
            select(ShariahScreening)
            .where(ShariahScreening.stock_id == stock_id)
            .order_by(ShariahScreening.screened_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    async def get_screening(self, symbol: str) -> ShariahScreening | None:
        sym_upper = symbol.upper()
        stock = await self.get_stock_by_symbol(sym_upper)

        # Legacy database rows were populated from static profiles. They have no
        # source/as-of metadata, so their ratios cannot be presented as current.
        return await self._evaluate_and_persist_screening(sym_upper, stock)

    async def _evaluate_and_persist_screening(self, symbol: str, stock: Stock | None = None) -> ShariahScreening | None:
        """Evaluate Shariah compliance dynamically based on PSX KMI-30 / Meezan criteria."""
        sym_upper = symbol.upper()

        if sym_upper in NON_COMPLIANT_SYMBOLS:
            profile = NON_COMPLIANT_SYMBOLS[sym_upper]
            screening = ShariahScreening(
                stock_id=stock.id if stock else f"stock-{sym_upper.lower()}",
                is_shariah_compliant=False,
                # Business activity is sufficient for this known category;
                # these financial ratios are not available from the source.
                debt_ratio=None,
                interest_income_ratio=None,
                screening_method="Known business activity classification; financial ratios unavailable",
                screened_at=datetime.utcnow(),
            )
        elif await self._is_current_kmi30_member(sym_upper):
            screening = ShariahScreening(
                stock_id=stock.id if stock else f"stock-{sym_upper.lower()}",
                is_shariah_compliant=True,
                debt_ratio=None,
                interest_income_ratio=None,
                screening_method="Cached PSX KMI-30 constituent membership; financial ratios unavailable",
                screened_at=datetime.utcnow(),
            )
        else:
            # General PSX stock evaluation
            sector = (stock.sector or "").upper() if stock else ""
            if any(nc in sector for nc in NON_COMPLIANT_SECTORS):
                screening = ShariahScreening(
                    stock_id=stock.id if stock else f"stock-{sym_upper.lower()}",
                    is_shariah_compliant=False,
                    debt_ratio=None,
                    interest_income_ratio=None,
                    screening_method="Known business activity classification; financial ratios unavailable",
                    screened_at=datetime.utcnow(),
                )
            else:
                # A missing stock or an unclassified sector is not evidence of
                # Shariah compliance. Do not manufacture financial ratios.
                return None

        return screening

    async def _is_current_kmi30_member(self, symbol: str) -> bool:
        """Use the current source-backed constituent cache, never a static profile."""
        try:
            freshness = MarketService.constituents_freshness("KMI30")
            if freshness.get("is_stale", True):
                return False
            rows = await MarketService().get_index_constituents("KMI30")
            return any(str(row.get("symbol", "")).upper() == symbol for row in (rows or []))
        except Exception as exc:
            log.warning("KMI-30 membership unavailable while screening %s: %s", symbol, exc)
            return False

    def build_criteria(self, screening: ShariahScreening | None, symbol: str = "") -> list[dict]:
        """Build the comprehensive 6-point PSX/Meezan Shariah screening breakdown."""
        if screening is None:
            return [
                {"name": name, "threshold": threshold, "value": None, "passed": None,
                 "description": "No screening data is available for this symbol."}
                for name, threshold in (
                    ("Core Business Permissibility", 1.0),
                    ("Debt to Total Assets Ratio", 0.37),
                    ("Non-Compliant Investments Ratio", 0.33),
                    ("Non-Permissible / Interest Income Ratio", 0.05),
                    ("Illiquid Assets to Total Assets Ratio", 0.25),
                    ("Net Liquid Assets vs Market Price", 1.0),
                )
            ]
        sym_upper = symbol.upper()
        is_non_compliant = sym_upper in NON_COMPLIANT_SYMBOLS

        debt_ratio = float(screening.debt_ratio) if screening and screening.debt_ratio is not None else None
        interest_ratio = float(screening.interest_income_ratio) if screening and screening.interest_income_ratio is not None else None
        non_compliant_inv = None
        illiquid_ratio = None

        is_core_halal = not is_non_compliant and (screening.is_shariah_compliant if screening else True)

        return [
            {
                "name": "Core Business Permissibility",
                "threshold": 1.0,
                "value": 1.0 if is_core_halal else 0.0,
                "passed": is_core_halal,
                "description": "Core business activities must be halal and free from prohibited elements.",
            },
            {
                "name": "Debt to Total Assets Ratio",
                "threshold": 0.37,
                "value": debt_ratio,
                "passed": None if debt_ratio is None else debt_ratio < 0.37 and is_core_halal,
                "description": "Total interest-bearing debt / Total Assets must be less than 37%.",
            },
            {
                "name": "Non-Compliant Investments Ratio",
                "threshold": 0.33,
                "value": non_compliant_inv,
                "passed": None if non_compliant_inv is None else non_compliant_inv < 0.33 and is_core_halal,
                "description": "Interest-bearing deposits and non-compliant investments / Total Assets must be under 33%.",
            },
            {
                "name": "Non-Permissible / Interest Income Ratio",
                "threshold": 0.05,
                "value": interest_ratio,
                "passed": None if interest_ratio is None else interest_ratio < 0.05 and is_core_halal,
                "description": "Interest and non-permissible income / Gross Revenue must be under 5%.",
            },
            {
                "name": "Illiquid Assets to Total Assets Ratio",
                "threshold": 0.25,
                "value": illiquid_ratio,
                "passed": None if illiquid_ratio is None else illiquid_ratio >= 0.25 and is_core_halal,
                "description": "Illiquid physical assets / Total Assets must be at least 25%.",
            },
            {
                "name": "Net Liquid Assets vs Market Price",
                "threshold": 1.0,
                "value": None,
                "passed": None,
                "description": "Net liquid assets per share must be less than the current market price per share.",
            },
        ]

    def calculate_purification(self, dividend_income: float, symbol: str = "", rate: float | None = None) -> tuple[float, float]:
        """Calculate purification amount and return (purification_amount, purification_rate)."""
        sym_upper = symbol.upper()

        if rate is not None:
            effective_rate = rate
        else:
            raise ValueError(f"No verified purification rate is available for {sym_upper}.")

        amount = round(dividend_income * effective_rate, 2)
        return amount, effective_rate

    async def get_kmi30_constituents(self) -> list[dict]:
        """Fetch source-backed KMI-30 constituents without inventing prices or ratios."""
        market_service = MarketService()
        try:
            constituents = await market_service.get_index_constituents("KMI30")
            if constituents and len(constituents) > 0:
                return [{**c, "is_shariah_compliant": True, "purification_rate": None, "debt_ratio": None}
                        for c in constituents if c.get("symbol")]
        except Exception as e:
            log.warning("MarketService.get_index_constituents(KMI30) unavailable: %s", e)
        return []

    @staticmethod
    def market_constituents_freshness() -> dict:
        return MarketService.constituents_freshness("KMI30")
