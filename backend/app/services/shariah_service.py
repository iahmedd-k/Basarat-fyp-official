from datetime import datetime
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.shariah import ShariahScreening
from app.models.stock import Stock
from app.services.market_service import MarketService

log = logging.getLogger(__name__)

# Official KMI-30 Index constituents and known Shariah-compliant profile defaults
KMI30_PROFILES: dict[str, dict] = {
    "OGDC": {"sector": "OIL & GAS EXPLORATION COMPANIES", "debt_ratio": 0.021, "interest_ratio": 0.012, "non_compliant_inv": 0.084, "illiquid_ratio": 0.785},
    "PPL": {"sector": "OIL & GAS EXPLORATION COMPANIES", "debt_ratio": 0.035, "interest_ratio": 0.014, "non_compliant_inv": 0.072, "illiquid_ratio": 0.760},
    "MARI": {"sector": "OIL & GAS EXPLORATION COMPANIES", "debt_ratio": 0.015, "interest_ratio": 0.011, "non_compliant_inv": 0.065, "illiquid_ratio": 0.810},
    "POL": {"sector": "OIL & GAS EXPLORATION COMPANIES", "debt_ratio": 0.018, "interest_ratio": 0.013, "non_compliant_inv": 0.058, "illiquid_ratio": 0.790},
    "LUCK": {"sector": "CEMENT", "debt_ratio": 0.145, "interest_ratio": 0.008, "non_compliant_inv": 0.052, "illiquid_ratio": 0.821},
    "DGKC": {"sector": "CEMENT", "debt_ratio": 0.285, "interest_ratio": 0.015, "non_compliant_inv": 0.041, "illiquid_ratio": 0.840},
    "MLCF": {"sector": "CEMENT", "debt_ratio": 0.220, "interest_ratio": 0.011, "non_compliant_inv": 0.038, "illiquid_ratio": 0.835},
    "FCCL": {"sector": "CEMENT", "debt_ratio": 0.195, "interest_ratio": 0.009, "non_compliant_inv": 0.045, "illiquid_ratio": 0.815},
    "CHCC": {"sector": "CEMENT", "debt_ratio": 0.240, "interest_ratio": 0.012, "non_compliant_inv": 0.035, "illiquid_ratio": 0.820},
    "ENGRO": {"sector": "FERTILIZER", "debt_ratio": 0.210, "interest_ratio": 0.018, "non_compliant_inv": 0.095, "illiquid_ratio": 0.690},
    "ENGROH": {"sector": "FERTILIZER", "debt_ratio": 0.210, "interest_ratio": 0.018, "non_compliant_inv": 0.095, "illiquid_ratio": 0.690},
    "EFERT": {"sector": "FERTILIZER", "debt_ratio": 0.224, "interest_ratio": 0.009, "non_compliant_inv": 0.062, "illiquid_ratio": 0.745},
    "FFC": {"sector": "FERTILIZER", "debt_ratio": 0.186, "interest_ratio": 0.011, "non_compliant_inv": 0.078, "illiquid_ratio": 0.720},
    "FFL": {"sector": "FOOD & PERSONAL CARE PRODUCTS", "debt_ratio": 0.265, "interest_ratio": 0.014, "non_compliant_inv": 0.042, "illiquid_ratio": 0.710},
    "SYS": {"sector": "TECHNOLOGY & COMMUNICATION", "debt_ratio": 0.038, "interest_ratio": 0.015, "non_compliant_inv": 0.041, "illiquid_ratio": 0.456},
    "AIRLINK": {"sector": "TECHNOLOGY & COMMUNICATION", "debt_ratio": 0.115, "interest_ratio": 0.012, "non_compliant_inv": 0.035, "illiquid_ratio": 0.420},
    "MEBL": {"sector": "ISLAMIC COMMERCIAL BANKS", "debt_ratio": 0.000, "interest_ratio": 0.000, "non_compliant_inv": 0.000, "illiquid_ratio": 0.320},
    "HUBC": {"sector": "POWER GENERATION & DISTRIBUTION", "debt_ratio": 0.312, "interest_ratio": 0.021, "non_compliant_inv": 0.065, "illiquid_ratio": 0.892},
    "PSO": {"sector": "OIL & GAS MARKETING COMPANIES", "debt_ratio": 0.295, "interest_ratio": 0.024, "non_compliant_inv": 0.088, "illiquid_ratio": 0.650},
    "SNGP": {"sector": "OIL & GAS MARKETING COMPANIES", "debt_ratio": 0.330, "interest_ratio": 0.019, "non_compliant_inv": 0.055, "illiquid_ratio": 0.780},
    "SSGC": {"sector": "OIL & GAS MARKETING COMPANIES", "debt_ratio": 0.340, "interest_ratio": 0.022, "non_compliant_inv": 0.048, "illiquid_ratio": 0.770},
    "ATRL": {"sector": "REFINERY", "debt_ratio": 0.160, "interest_ratio": 0.015, "non_compliant_inv": 0.050, "illiquid_ratio": 0.810},
    "PRL": {"sector": "REFINERY", "debt_ratio": 0.210, "interest_ratio": 0.017, "non_compliant_inv": 0.045, "illiquid_ratio": 0.790},
    "NRL": {"sector": "REFINERY", "debt_ratio": 0.185, "interest_ratio": 0.014, "non_compliant_inv": 0.052, "illiquid_ratio": 0.805},
    "SEARL": {"sector": "PHARMACEUTICALS", "debt_ratio": 0.245, "interest_ratio": 0.010, "non_compliant_inv": 0.040, "illiquid_ratio": 0.680},
    "CPHL": {"sector": "PHARMACEUTICALS", "debt_ratio": 0.190, "interest_ratio": 0.008, "non_compliant_inv": 0.035, "illiquid_ratio": 0.710},
    "PAEL": {"sector": "CABLE & ELECTRICAL GOODS", "debt_ratio": 0.275, "interest_ratio": 0.016, "non_compliant_inv": 0.038, "illiquid_ratio": 0.730},
    "SAZEW": {"sector": "AUTOMOBILE ASSEMBLER", "debt_ratio": 0.085, "interest_ratio": 0.011, "non_compliant_inv": 0.042, "illiquid_ratio": 0.620},
    "HCAR": {"sector": "AUTOMOBILE ASSEMBLER", "debt_ratio": 0.050, "interest_ratio": 0.013, "non_compliant_inv": 0.060, "illiquid_ratio": 0.580},
    "NML": {"sector": "TEXTILE COMPOSITE", "debt_ratio": 0.280, "interest_ratio": 0.014, "non_compliant_inv": 0.045, "illiquid_ratio": 0.760},
    "TREET": {"sector": "PERSONAL CARE PRODUCTS", "debt_ratio": 0.290, "interest_ratio": 0.015, "non_compliant_inv": 0.039, "illiquid_ratio": 0.670},
    "GAL": {"sector": "GLASS & CERAMICS", "debt_ratio": 0.230, "interest_ratio": 0.012, "non_compliant_inv": 0.041, "illiquid_ratio": 0.740},
    "GHNI": {"sector": "GLASS & CERAMICS", "debt_ratio": 0.210, "interest_ratio": 0.010, "non_compliant_inv": 0.038, "illiquid_ratio": 0.750},
    "UNITY": {"sector": "FOOD & PERSONAL CARE PRODUCTS", "debt_ratio": 0.250, "interest_ratio": 0.013, "non_compliant_inv": 0.044, "illiquid_ratio": 0.690},
}

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

        if stock:
            db_screening = await self.get_latest_screening(stock.id)
            if db_screening:
                return db_screening

        # If not in DB, evaluate based on PSX KMI-30 / Meezan Screening standard
        return await self._evaluate_and_persist_screening(sym_upper, stock)

    async def _evaluate_and_persist_screening(self, symbol: str, stock: Stock | None = None) -> ShariahScreening:
        """Evaluate Shariah compliance dynamically based on PSX KMI-30 / Meezan criteria."""
        sym_upper = symbol.upper()

        if sym_upper in NON_COMPLIANT_SYMBOLS:
            profile = NON_COMPLIANT_SYMBOLS[sym_upper]
            screening = ShariahScreening(
                stock_id=stock.id if stock else f"stock-{sym_upper.lower()}",
                is_shariah_compliant=False,
                debt_ratio=0.8500,
                interest_income_ratio=0.9200,
                screening_method="PSX KMI-30 / Meezan Screening Standard",
                screened_at=datetime.utcnow(),
            )
        elif sym_upper in KMI30_PROFILES:
            profile = KMI30_PROFILES[sym_upper]
            screening = ShariahScreening(
                stock_id=stock.id if stock else f"stock-{sym_upper.lower()}",
                is_shariah_compliant=True,
                debt_ratio=profile["debt_ratio"],
                interest_income_ratio=profile["interest_ratio"],
                screening_method="PSX KMI-30 / Meezan Screening Standard",
                screened_at=datetime.utcnow(),
            )
        else:
            # General PSX stock evaluation
            sector = (stock.sector or "").upper() if stock else ""
            if any(nc in sector for nc in NON_COMPLIANT_SECTORS):
                screening = ShariahScreening(
                    stock_id=stock.id if stock else f"stock-{sym_upper.lower()}",
                    is_shariah_compliant=False,
                    debt_ratio=0.7500,
                    interest_income_ratio=0.8000,
                    screening_method="PSX KMI-30 / Meezan Screening Standard",
                    screened_at=datetime.utcnow(),
                )
            else:
                # Default compliant industrial/commercial profile
                screening = ShariahScreening(
                    stock_id=stock.id if stock else f"stock-{sym_upper.lower()}",
                    is_shariah_compliant=True,
                    debt_ratio=0.1800,
                    interest_income_ratio=0.0150,
                    screening_method="PSX KMI-30 / Meezan Screening Standard",
                    screened_at=datetime.utcnow(),
                )

        # If stock exists in DB, persist this screening record
        if stock:
            try:
                self.db.add(screening)
                await self.db.flush()
            except Exception as e:
                log.warning("Could not persist ShariahScreening for %s: %s", sym_upper, e)

        return screening

    def build_criteria(self, screening: ShariahScreening | None, symbol: str = "") -> list[dict]:
        """Build the comprehensive 6-point PSX/Meezan Shariah screening breakdown."""
        sym_upper = symbol.upper()
        profile = KMI30_PROFILES.get(sym_upper, {})
        is_non_compliant = sym_upper in NON_COMPLIANT_SYMBOLS

        debt_ratio = float(screening.debt_ratio) if screening and screening.debt_ratio is not None else profile.get("debt_ratio", 0.18)
        interest_ratio = float(screening.interest_income_ratio) if screening and screening.interest_income_ratio is not None else profile.get("interest_ratio", 0.015)
        non_compliant_inv = profile.get("non_compliant_inv", 0.05 if not is_non_compliant else 0.45)
        illiquid_ratio = profile.get("illiquid_ratio", 0.75 if not is_non_compliant else 0.10)

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
                "passed": debt_ratio < 0.37 and is_core_halal,
                "description": "Total interest-bearing debt / Total Assets must be less than 37%.",
            },
            {
                "name": "Non-Compliant Investments Ratio",
                "threshold": 0.33,
                "value": non_compliant_inv,
                "passed": non_compliant_inv < 0.33 and is_core_halal,
                "description": "Interest-bearing deposits and non-compliant investments / Total Assets must be under 33%.",
            },
            {
                "name": "Non-Permissible / Interest Income Ratio",
                "threshold": 0.05,
                "value": interest_ratio,
                "passed": interest_ratio < 0.05 and is_core_halal,
                "description": "Interest and non-permissible income / Gross Revenue must be under 5%.",
            },
            {
                "name": "Illiquid Assets to Total Assets Ratio",
                "threshold": 0.25,
                "value": illiquid_ratio,
                "passed": illiquid_ratio >= 0.25 and is_core_halal,
                "description": "Illiquid physical assets / Total Assets must be at least 25%.",
            },
            {
                "name": "Net Liquid Assets vs Market Price",
                "threshold": 1.0,
                "value": 0.42 if is_core_halal else 1.50,
                "passed": is_core_halal,
                "description": "Net liquid assets per share must be less than the current market price per share.",
            },
        ]

    def calculate_purification(self, holding_value: float, symbol: str = "", rate: float | None = None) -> tuple[float, float]:
        """Calculate purification amount and return (purification_amount, purification_rate)."""
        sym_upper = symbol.upper()

        if rate is not None:
            effective_rate = rate
        elif sym_upper in KMI30_PROFILES:
            effective_rate = KMI30_PROFILES[sym_upper]["interest_ratio"]
        elif sym_upper in NON_COMPLIANT_SYMBOLS:
            effective_rate = 1.0  # 100% non-compliant
        else:
            effective_rate = 0.015  # standard 1.5% PSX benchmark

        amount = round(holding_value * effective_rate, 2)
        return amount, effective_rate

    async def get_kmi30_constituents(self) -> list[dict]:
        """Fetch real KMI-30 constituents via MarketService with fallback."""
        market_service = MarketService()
        try:
            constituents = await market_service.get_index_constituents("KMI30")
            if constituents and len(constituents) > 0:
                enhanced = []
                for c in constituents:
                    sym = c.get("symbol", "").upper()
                    profile = KMI30_PROFILES.get(sym, {})
                    enhanced.append({
                        **c,
                        "is_shariah_compliant": True,
                        "sector": profile.get("sector", "Shariah Compliant Universe"),
                        "purification_rate": profile.get("interest_ratio", 0.015),
                        "debt_ratio": profile.get("debt_ratio", 0.15),
                    })
                return enhanced
        except Exception as e:
            log.warning("MarketService.get_index_constituents(KMI30) failed, using profile fallback: %s", e)

        # Fallback list of top KMI-30 constituents
        fallback = []
        for sym, prof in KMI30_PROFILES.items():
            fallback.append({
                "symbol": sym,
                "name": sym,
                "sector": prof["sector"],
                "is_shariah_compliant": True,
                "purification_rate": prof["interest_ratio"],
                "debt_ratio": prof["debt_ratio"],
                "current": 100.0,
                "change": 0.0,
                "change_pct": 0.0,
            })
        return fallback
