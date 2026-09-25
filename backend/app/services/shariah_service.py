from datetime import date, datetime, timezone
import json
import logging
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shariah import ShariahScreening
from app.models.stock import Stock
from app.services.market_service import MarketService

log = logging.getLogger(__name__)

_PSX_SCREENING_PATH = Path(__file__).resolve().parents[1] / "data" / "psx_kmi30_screening_2025-12.json"
with _PSX_SCREENING_PATH.open(encoding="utf-8") as _source_file:
    PSX_KMI30_SCREENING = json.load(_source_file)
PSX_KMI30_COMPANIES: dict[str, dict] = PSX_KMI30_SCREENING["companies"]
_SCREENING_AS_OF = date.fromisoformat(PSX_KMI30_SCREENING["accounts_as_of"])
_KMI30_EFFECTIVE_FROM = date.fromisoformat(PSX_KMI30_SCREENING["effective_from"])


def _screening_source_fields(row: dict) -> dict:
    """Return clearly dated official PSX screening values in API decimal units."""
    as_of = datetime.combine(_SCREENING_AS_OF, datetime.min.time(), tzinfo=timezone.utc)
    return {
        "debt_ratio": None if row["debt"] is None else row["debt"] / 100,
        "interest_income_ratio": None if row["income"] is None else row["income"] / 100,
        "non_compliant_investment_ratio": None if row["investment"] is None else row["investment"] / 100,
        "illiquid_assets_ratio": None if row["illiquid"] is None else row["illiquid"] / 100,
        "net_liquid_assets_per_share": row["nla"],
        "reference_share_price": row["price"],
        "screening_method": "PSX KMI-30 screening notice PSX/N-610 (2026-05-15)",
        "screened_at": as_of.replace(tzinfo=None),
        "data_as_of": as_of,
        "effective_from": datetime.combine(_KMI30_EFFECTIVE_FROM, datetime.min.time(), tzinfo=timezone.utc),
        "data_is_stale": (date.today() - _SCREENING_AS_OF).days > 180,
        "source_url": PSX_KMI30_SCREENING["source_url"],
        "purification_rate_provisional": bool(row.get("provisional", False)),
        "source_exception": row.get("exception") or row.get("note"),
    }

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

        # Use the latest dated PSX KMI screening snapshot rather than requiring
        # a market-price cache to disclose verified screening ratios.
        if sym_upper in PSX_KMI30_COMPANIES:
            row = PSX_KMI30_COMPANIES[sym_upper]
            screening = ShariahScreening(
                stock_id=stock.id if stock else f"stock-{sym_upper.lower()}",
                is_shariah_compliant=bool(row["status"]),
                **{key: value for key, value in _screening_source_fields(row).items()
                   if key in {"debt_ratio", "interest_income_ratio", "screening_method", "screened_at"}},
            )
            for key, value in _screening_source_fields(row).items():
                setattr(screening, key, value)
            return screening

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
                    ("Debt to Total Assets Ratio", 37.0),
                    ("Non-Compliant Investments Ratio", 33.0),
                    ("Non-Permissible / Interest Income Ratio", 5.0),
                    ("Illiquid Assets to Total Assets Ratio", 25.0),
                    ("Net Liquid Assets vs Market Price", 1.0),
                )
            ]
        sym_upper = symbol.upper()
        is_non_compliant = sym_upper in NON_COMPLIANT_SYMBOLS

        debt_ratio = float(screening.debt_ratio) if screening and screening.debt_ratio is not None else None
        interest_ratio = float(screening.interest_income_ratio) if screening and screening.interest_income_ratio is not None else None
        non_compliant_inv = getattr(screening, "non_compliant_investment_ratio", None)
        illiquid_ratio = getattr(screening, "illiquid_assets_ratio", None)
        nla = getattr(screening, "net_liquid_assets_per_share", None)
        share_price = getattr(screening, "reference_share_price", None)
        source_exception = getattr(screening, "source_exception", None)
        has_ratio_exception = bool(source_exception)

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
                "threshold": 37.0,
                "value": None if debt_ratio is None else round(debt_ratio * 100, 2),
                "passed": None if debt_ratio is None else debt_ratio < 0.37 and is_core_halal,
                "description": "Total interest-bearing debt / Total Assets must be less than 37%.",
            },
            {
                "name": "Non-Compliant Investments Ratio",
                "threshold": 33.0,
                "value": None if non_compliant_inv is None else round(non_compliant_inv * 100, 2),
                "passed": None if non_compliant_inv is None or (source_exception and "investment" in source_exception.lower()) else non_compliant_inv < 0.33 and is_core_halal,
                "description": "Interest-bearing deposits and non-compliant investments / Total Assets must be under 33%.",
                "exception": source_exception if source_exception and "investment" in source_exception.lower() else None,
            },
            {
                "name": "Non-Permissible / Interest Income Ratio",
                "threshold": 5.0,
                "value": None if interest_ratio is None else round(interest_ratio * 100, 2),
                "passed": None if interest_ratio is None or has_ratio_exception else interest_ratio < 0.05 and is_core_halal,
                "description": "Interest and non-permissible income / Gross Revenue must be under 5%.",
                "exception": source_exception,
            },
            {
                "name": "Illiquid Assets to Total Assets Ratio",
                "threshold": 25.0,
                "value": None if illiquid_ratio is None else round(illiquid_ratio * 100, 2),
                "passed": None if illiquid_ratio is None else illiquid_ratio >= 0.25 and is_core_halal,
                "description": "Illiquid physical assets / Total Assets must be at least 25%.",
            },
            {
                "name": "Net Liquid Assets vs Market Price",
                "threshold": share_price if share_price is not None else 1.0,
                "value": nla,
                "passed": None if nla is None or share_price is None else nla < share_price,
                "description": "Net liquid assets per share must be less than the reference share price reported for the screening date.",
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
        """Merge PSX's dated authoritative roster with fresh market quotes when available."""
        market_service = MarketService()
        try:
            constituents = await market_service.get_index_constituents("KMI30")
            if constituents and len(constituents) > 0:
                market_rows = {str(c.get("symbol", "")).upper(): c for c in constituents if c.get("symbol")}
                return [self._kmi_constituent(symbol, row, market_rows.get(symbol))
                        for symbol, row in PSX_KMI30_COMPANIES.items()]
        except Exception as e:
            log.warning("MarketService.get_index_constituents(KMI30) unavailable: %s", e)
        return [self._kmi_constituent(symbol, row, None) for symbol, row in PSX_KMI30_COMPANIES.items()]

    @staticmethod
    def _kmi_constituent(symbol: str, row: dict, market_row: dict | None) -> dict:
        source_fields = _screening_source_fields(row)
        return {
            **(market_row or {}),
            "symbol": symbol,
            "name": row["name"],
            "is_shariah_compliant": bool(row["status"]),
            "debt_ratio": source_fields["debt_ratio"],
            "interest_income_ratio": source_fields["interest_income_ratio"],
            "data_as_of": source_fields["data_as_of"].isoformat(),
            "purification_rate_provisional": source_fields["purification_rate_provisional"],
        }

    @staticmethod
    def market_constituents_freshness() -> dict:
        return MarketService.constituents_freshness("KMI30")
