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

    issue_size_shares: Optional[float] = None
    issue_size_pkr: Optional[float] = None
    floor_price: Optional[float] = None
    strike_price: Optional[float] = None
    listing_price: Optional[float] = None
    current_price: Optional[float] = None

    book_building_start: Optional[date] = None
    book_building_end: Optional[date] = None
    public_subscription_start: Optional[date] = None
    public_subscription_end: Optional[date] = None
    listing_date: Optional[date] = None

    lead_manager: Optional[str] = None
    is_shariah_compliant: bool = False
    prospectus_url: Optional[str] = None
    description: Optional[str] = None
    subscription_multiplier: Optional[float] = None

    listing_gain_pct: Optional[float] = None
    current_gain_pct: Optional[float] = None

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
    price_info: Optional[str] = None


class IPOCalendarResponse(BaseModel):
    total_events: int
    upcoming_milestones: List[IPOCalendarMilestone]


class IPOPerformanceItem(BaseModel):
    symbol: str
    company_name: str
    sector: str
    listing_date: Optional[date] = None
    offer_price: float
    first_day_close: Optional[float] = None
    current_price: Optional[float] = None
    first_day_return_pct: Optional[float] = None
    total_return_pct: Optional[float] = None


class IPOPerformanceResponse(BaseModel):
    total_listed: int
    average_listing_day_gain_pct: Optional[float] = None
    top_performers: List[IPOPerformanceItem]
    recent_listings: List[IPOPerformanceItem]
