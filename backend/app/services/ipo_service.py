import logging
from datetime import datetime, date
from typing import Optional, List, Dict, Any
from sqlalchemy import select, update, delete, desc, or_, and_, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.redis import cache_get, cache_set
from app.models.ipo import IPO
from app.schemas.ipo import (
    IPOStatus,
    IPOResponse,
    IPOListResponse,
    IPOCalendarMilestone,
    IPOCalendarResponse,
    IPOPerformanceItem,
    IPOPerformanceResponse,
)

log = logging.getLogger(__name__)

INITIAL_PSX_IPOS = [
    {
        "symbol": "IPACO",
        "company_name": "International Packaging Films Limited",
        "sector": "Paper & Board",
        "status": "LISTED",
        "issue_size_shares": 70105000,
        "issue_size_pkr": 1472205000,
        "floor_price": 21.00,
        "strike_price": 21.00,
        "listing_price": 21.00,
        "current_price": 23.45,
        "book_building_start": date(2024, 5, 8),
        "book_building_end": date(2024, 5, 9),
        "public_subscription_start": date(2024, 5, 15),
        "public_subscription_end": date(2024, 5, 16),
        "listing_date": date(2024, 5, 28),
        "lead_manager": "Arif Habib Limited",
        "is_shariah_compliant": True,
        "prospectus_url": "https://dps.psx.com.pk/download/document/227481.pdf",
        "description": "Manufacturer of Biaxially Oriented Polypropylene (BOPP) films in Pakistan.",
        "subscription_multiplier": 1.73,
    },
    {
        "symbol": "BBCL",
        "company_name": "Big Bird Foods Limited",
        "sector": "Food & Personal Care",
        "status": "LISTED",
        "issue_size_shares": 18360000,
        "issue_size_pkr": 907000000,
        "floor_price": 49.40,
        "strike_price": 49.40,
        "listing_price": 49.40,
        "current_price": 54.20,
        "book_building_start": date(2024, 4, 18),
        "book_building_end": date(2024, 4, 19),
        "public_subscription_start": date(2024, 4, 25),
        "public_subscription_end": date(2024, 4, 26),
        "listing_date": date(2024, 5, 10),
        "lead_manager": "AKD Securities Limited",
        "is_shariah_compliant": True,
        "prospectus_url": "https://dps.psx.com.pk/download/document/226190.pdf",
        "description": "Producer of value-added poultry and ready-to-cook chicken products.",
        "subscription_multiplier": 2.15,
    },
    {
        "symbol": "FAST",
        "company_name": "Fast Cables Limited",
        "sector": "Engineering",
        "status": "LISTED",
        "issue_size_shares": 128000000,
        "issue_size_pkr": 3072000000,
        "floor_price": 24.00,
        "strike_price": 24.45,
        "listing_price": 24.45,
        "current_price": 27.80,
        "book_building_start": date(2024, 5, 15),
        "book_building_end": date(2024, 5, 16),
        "public_subscription_start": date(2024, 5, 22),
        "public_subscription_end": date(2024, 5, 23),
        "listing_date": date(2024, 6, 12),
        "lead_manager": "AKD Securities & Meezan Bank",
        "is_shariah_compliant": True,
        "prospectus_url": "https://dps.psx.com.pk/download/document/228100.pdf",
        "description": "Premier manufacturer of electrical cables and copper conductors in Pakistan.",
        "subscription_multiplier": 1.48,
    },
    {
        "symbol": "GTECH",
        "company_name": "Green Technology Solutions Ltd",
        "sector": "Technology & Communication",
        "status": "OPEN_FOR_BOOK_BUILDING",
        "issue_size_shares": 45000000,
        "issue_size_pkr": 1125000000,
        "floor_price": 25.00,
        "strike_price": None,
        "listing_price": None,
        "current_price": None,
        "book_building_start": date(2026, 10, 5),
        "book_building_end": date(2026, 10, 6),
        "public_subscription_start": date(2026, 10, 14),
        "public_subscription_end": date(2026, 10, 15),
        "listing_date": date(2026, 10, 28),
        "lead_manager": "Topline Securities Limited",
        "is_shariah_compliant": True,
        "prospectus_url": "https://dps.psx.com.pk/download/document/prospectus_gtech.pdf",
        "description": "Enterprise software and green IoT smart-grid automation solutions.",
        "subscription_multiplier": None,
    },
    {
        "symbol": "PRX",
        "company_name": "Pharmarex Laboratories Limited",
        "sector": "Pharmaceuticals",
        "status": "UPCOMING",
        "issue_size_shares": 30000000,
        "issue_size_pkr": 900000000,
        "floor_price": 30.00,
        "strike_price": None,
        "listing_price": None,
        "current_price": None,
        "book_building_start": date(2026, 11, 2),
        "book_building_end": date(2026, 11, 3),
        "public_subscription_start": date(2026, 11, 10),
        "public_subscription_end": date(2026, 11, 11),
        "listing_date": date(2026, 11, 25),
        "lead_manager": "Next Capital Limited",
        "is_shariah_compliant": True,
        "prospectus_url": "https://dps.psx.com.pk/download/document/prospectus_prx.pdf",
        "description": "Specialized oncology formulations and active pharmaceutical ingredient (API) synthesis.",
        "subscription_multiplier": None,
    },
]


class IPOService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def ensure_seed_data(self) -> None:
        """Seed initial PSX IPO records if the table is empty."""
        try:
            count_res = await self.db.execute(select(func.count(IPO.id)))
            if (count_res.scalar() or 0) == 0:
                for item in INITIAL_PSX_IPOS:
                    self.db.add(IPO(**item))
                await self.db.commit()
                log.info("Initialized %d default PSX IPO records", len(INITIAL_PSX_IPOS))
        except Exception as exc:
            log.warning("Could not verify/seed IPO initial data: %s", exc)
            await self.db.rollback()


    def _format_ipo_response(self, ipo: IPO) -> IPOResponse:
        listing_gain_pct = 0.0
        current_gain_pct = 0.0
        base_offer = ipo.strike_price or ipo.floor_price or ipo.listing_price
        if base_offer and base_offer > 0:
            if ipo.listing_price:
                listing_gain_pct = round(((ipo.listing_price - base_offer) / base_offer) * 100, 2)
            if ipo.current_price:
                current_gain_pct = round(((ipo.current_price - base_offer) / base_offer) * 100, 2)

        return IPOResponse(
            id=ipo.id,
            symbol=ipo.symbol,
            company_name=ipo.company_name,
            sector=ipo.sector,
            status=IPOStatus(ipo.status),
            issue_size_shares=float(ipo.issue_size_shares or 0.0),
            issue_size_pkr=float(ipo.issue_size_pkr or 0.0),
            floor_price=float(ipo.floor_price or 0.0),
            strike_price=float(ipo.strike_price or 0.0),
            listing_price=float(ipo.listing_price or 0.0),
            current_price=float(ipo.current_price or 0.0),
            book_building_start=ipo.book_building_start,
            book_building_end=ipo.book_building_end,
            public_subscription_start=ipo.public_subscription_start,
            public_subscription_end=ipo.public_subscription_end,
            listing_date=ipo.listing_date,
            lead_manager=ipo.lead_manager or "",
            is_shariah_compliant=bool(ipo.is_shariah_compliant),
            prospectus_url=ipo.prospectus_url or "",
            description=ipo.description or "",
            subscription_multiplier=float(ipo.subscription_multiplier or 0.0),
            listing_gain_pct=listing_gain_pct,
            current_gain_pct=current_gain_pct,
            created_at=ipo.created_at,
            updated_at=ipo.updated_at,
        )

    # ───────────────────────────────────────────────────────────────────
    # Public Read Endpoints (with Redis Caching)
    # ───────────────────────────────────────────────────────────────────

    async def get_ipos(
        self,
        status: Optional[str] = None,
        sector: Optional[str] = None,
        is_shariah_compliant: Optional[bool] = None,
        search: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> IPOListResponse:
        cache_key = f"ipo:list:v1:{status}:{sector}:{is_shariah_compliant}:{search}:{limit}:{offset}"
        cached = await cache_get(cache_key)
        if cached:
            return IPOListResponse(**cached)

        await self.ensure_seed_data()
        query = select(IPO)
        if status:
            st_upper = status.strip().upper()
            if st_upper in ("UPCOMING", "OPEN_FOR_BOOK_BUILDING", "OPEN_FOR_PUBLIC_SUBSCRIPTION", "LISTED", "CLOSED"):
                query = query.where(IPO.status == st_upper)
            elif st_upper == "ACTIVE":
                query = query.where(
                    IPO.status.in_(["OPEN_FOR_BOOK_BUILDING", "OPEN_FOR_PUBLIC_SUBSCRIPTION"])
                )
        if sector and sector.strip():
            query = query.where(IPO.sector.ilike(f"%{sector.strip()}%"))
        if is_shariah_compliant is not None:
            query = query.where(IPO.is_shariah_compliant == is_shariah_compliant)
        if search and search.strip():
            q = search.strip()
            query = query.where(
                or_(
                    IPO.symbol.ilike(f"%{q}%"),
                    IPO.company_name.ilike(f"%{q}%"),
                    IPO.sector.ilike(f"%{q}%"),
                )
            )

        query = query.order_by(desc(IPO.listing_date), desc(IPO.created_at)).offset(offset).limit(limit)
        result = await self.db.execute(query)
        ipos = result.scalars().all()

        # Consolidated counts in a single query
        counts_res = await self.db.execute(select(IPO.status, func.count(IPO.id)).group_by(IPO.status))
        counts_map = {row[0]: row[1] for row in counts_res.all()}
        total_count = sum(counts_map.values())
        upcoming_count = counts_map.get("UPCOMING", 0)
        active_count = counts_map.get("OPEN_FOR_BOOK_BUILDING", 0) + counts_map.get("OPEN_FOR_PUBLIC_SUBSCRIPTION", 0)
        listed_count = counts_map.get("LISTED", 0)

        response = IPOListResponse(
            total=total_count or len(ipos),
            upcoming_count=upcoming_count,
            active_count=active_count,
            listed_count=listed_count,
            ipos=[self._format_ipo_response(item) for item in ipos],
        )

        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response


    async def get_ipo_by_id_or_symbol(self, identifier: str) -> IPOResponse:
        cache_key = f"ipo:detail:v1:{identifier.upper()}"
        cached = await cache_get(cache_key)
        if cached:
            return IPOResponse(**cached)

        await self.ensure_seed_data()
        query = select(IPO).where(
            or_(IPO.id == identifier, IPO.symbol == identifier.upper())
        )
        res = await self.db.execute(query)
        ipo = res.scalars().first()
        if not ipo:
            raise NotFoundError(f"IPO for '{identifier}' not found.")

        response = self._format_ipo_response(ipo)
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response

    async def get_calendar(self) -> IPOCalendarResponse:
        cache_key = "ipo:calendar:v1"
        cached = await cache_get(cache_key)
        if cached:
            return IPOCalendarResponse(**cached)

        await self.ensure_seed_data()
        query = select(IPO).where(
            IPO.status.in_(["UPCOMING", "OPEN_FOR_BOOK_BUILDING", "OPEN_FOR_PUBLIC_SUBSCRIPTION"])
        ).order_by(IPO.book_building_start.asc(), IPO.public_subscription_start.asc())
        res = await self.db.execute(query)
        active_ipos = res.scalars().all()

        milestones: List[IPOCalendarMilestone] = []
        for item in active_ipos:
            price_txt = f"Floor: PKR {item.floor_price}" if item.floor_price else ""
            if item.book_building_start:
                milestones.append(
                    IPOCalendarMilestone(
                        ipo_id=item.id,
                        symbol=item.symbol,
                        company_name=item.company_name,
                        event_type="BOOK_BUILDING_START",
                        event_date=item.book_building_start,
                        status="SCHEDULED" if item.book_building_start > date.today() else "LIVE",
                        price_info=price_txt,
                    )
                )
            if item.book_building_end:
                milestones.append(
                    IPOCalendarMilestone(
                        ipo_id=item.id,
                        symbol=item.symbol,
                        company_name=item.company_name,
                        event_type="BOOK_BUILDING_END",
                        event_date=item.book_building_end,
                        status="SCHEDULED" if item.book_building_end > date.today() else "CLOSING",
                        price_info=price_txt,
                    )
                )
            if item.public_subscription_start:
                milestones.append(
                    IPOCalendarMilestone(
                        ipo_id=item.id,
                        symbol=item.symbol,
                        company_name=item.company_name,
                        event_type="PUBLIC_SUBSCRIPTION_START",
                        event_date=item.public_subscription_start,
                        status="SCHEDULED" if item.public_subscription_start > date.today() else "LIVE",
                        price_info=f"Strike: PKR {item.strike_price or item.floor_price}",
                    )
                )
            if item.public_subscription_end:
                milestones.append(
                    IPOCalendarMilestone(
                        ipo_id=item.id,
                        symbol=item.symbol,
                        company_name=item.company_name,
                        event_type="PUBLIC_SUBSCRIPTION_END",
                        event_date=item.public_subscription_end,
                        status="SCHEDULED" if item.public_subscription_end > date.today() else "CLOSING",
                        price_info=f"Strike: PKR {item.strike_price or item.floor_price}",
                    )
                )
            if item.listing_date:
                milestones.append(
                    IPOCalendarMilestone(
                        ipo_id=item.id,
                        symbol=item.symbol,
                        company_name=item.company_name,
                        event_type="EXCHANGE_LISTING",
                        event_date=item.listing_date,
                        status="EXPECTED",
                        price_info=f"Listing Date",
                    )
                )

        milestones.sort(key=lambda m: m.event_date)
        response = IPOCalendarResponse(
            total_events=len(milestones),
            upcoming_milestones=milestones,
        )
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response

    async def get_performance(self) -> IPOPerformanceResponse:
        cache_key = "ipo:performance:v1"
        cached = await cache_get(cache_key)
        if cached:
            return IPOPerformanceResponse(**cached)

        await self.ensure_seed_data()
        query = select(IPO).where(IPO.status == "LISTED").order_by(desc(IPO.listing_date))
        res = await self.db.execute(query)
        listed_ipos = res.scalars().all()

        items: List[IPOPerformanceItem] = []
        gains = []
        for item in listed_ipos:
            offer = item.strike_price or item.floor_price or item.listing_price or 1.0
            first_day = item.listing_price or offer
            current = item.current_price or first_day

            first_day_ret = round(((first_day - offer) / offer) * 100, 2)
            total_ret = round(((current - offer) / offer) * 100, 2)
            gains.append(first_day_ret)

            items.append(
                IPOPerformanceItem(
                    symbol=item.symbol,
                    company_name=item.company_name,
                    sector=item.sector,
                    listing_date=item.listing_date,
                    offer_price=round(offer, 2),
                    first_day_close=round(first_day, 2),
                    current_price=round(current, 2),
                    first_day_return_pct=first_day_ret,
                    total_return_pct=total_ret,
                )
            )

        top = sorted(items, key=lambda i: (i.total_return_pct or 0), reverse=True)
        avg_gain = round(sum(gains) / len(gains), 2) if gains else 0.0

        response = IPOPerformanceResponse(
            total_listed=len(items),
            average_listing_day_gain_pct=avg_gain,
            top_performers=top[:5],
            recent_listings=items[:10],
        )
        await cache_set(cache_key, response.model_dump(mode="json"), ttl_seconds=300)
        return response
