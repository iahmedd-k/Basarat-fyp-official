from datetime import datetime, date
from enum import Enum
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class IPOStatus(str, Enum):
    UPCOMING = "UPCOMING"
    OPEN_FOR_BOOK_BUILDING = "OPEN_FOR_BOOK_BUILDING"
    OPEN_FOR_PUBLIC_SUBSCRIPTION = "OPEN_FOR_PUBLIC_SUBSCRIPTION"
    LISTED = "LISTED"
    CLOSED = "CLOSED"


class IPOResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol: str
    company_name: str
    sector: str
    status: IPOStatus

    issue_size_shares: float = 0.0
    issue_size_pkr: float = 0.0
    floor_price: float = 0.0
    strike_price: float = 0.0
    listing_price: float = 0.0
    current_price: float = 0.0

    book_building_start: Optional[date] = None
    book_building_end: Optional[date] = None
    public_subscription_start: Optional[date] = None
    public_subscription_end: Optional[date] = None
    listing_date: Optional[date] = None

    lead_manager: str = ""
    is_shariah_compliant: bool = False
    prospectus_url: str = ""
    description: str = ""
    subscription_multiplier: float = 0.0

    listing_gain_pct: float = 0.0
    current_gain_pct: float = 0.0

    created_at: datetime
    updated_at: datetime


class IPOListResponse(BaseModel):
    total: int
    upcoming_count: int
    active_count: int
    listed_count: int
    ipos: List[IPOResponse]


class IPOCalendarMilestone(BaseModel):
    ipo_id: str
    symbol: str
    company_name: str
    event_type: str  # BOOK_BUILDING_START, BOOK_BUILDING_END, SUBSCRIPTION_START, SUBSCRIPTION_END, LISTING
    event_date: date
    status: str
    price_info: str = ""


class IPOCalendarResponse(BaseModel):
    total_events: int
    upcoming_milestones: List[IPOCalendarMilestone]


class IPOPerformanceItem(BaseModel):
    symbol: str
    company_name: str
    sector: str
    listing_date: Optional[date] = None
    offer_price: float = 0.0
    first_day_close: float = 0.0
    current_price: float = 0.0
    first_day_return_pct: float = 0.0
    total_return_pct: float = 0.0


class IPOPerformanceResponse(BaseModel):
    total_listed: int
    average_listing_day_gain_pct: float = 0.0
    top_performers: List[IPOPerformanceItem]
    recent_listings: List[IPOPerformanceItem]
