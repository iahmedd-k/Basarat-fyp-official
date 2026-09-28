from datetime import datetime, date
from typing import Optional, List, Dict
from pydantic import BaseModel, ConfigDict


class ETFQuote(BaseModel):
    current_price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    open_price: Optional[float] = None
    high_price: Optional[float] = None
    low_price: Optional[float] = None
    close_price: Optional[float] = None
    volume: Optional[int] = None
    bid_price: Optional[float] = None
    ask_price: Optional[float] = None
    data_as_of: Optional[str] = None
    quote_source: str = "psx_live"


class ETFResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    symbol: str
    name: str
    fund_manager: str
    category: str
    benchmark_index: str
    is_shariah_compliant: bool
    expense_ratio: Optional[float] = None
    inception_date: Optional[date] = None
    total_assets_pkr: Optional[float] = None
    description: Optional[str] = None
    is_active: bool

    # Live market fields
    quote: Optional[ETFQuote] = None
    current_price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[int] = None

    created_at: datetime
    updated_at: datetime


class ETFListResponse(BaseModel):
    total: int
    shariah_count: int
    conventional_count: int
    etfs: List[ETFResponse]


class ETFHistoryItem(BaseModel):
    date: str
    open: float
    high: float
    low: float
    close: float
    volume: int


class ETFHistoryResponse(BaseModel):
    symbol: str
    timeframe: str
    count: int
    history: List[ETFHistoryItem]


class ETFPerformanceResponse(BaseModel):
    symbol: str
    name: str
    benchmark_index: str
    returns: Dict[str, Optional[float]]  # 1D, 1W, 1M, 3M, 1Y, YTD
    benchmark_returns: Dict[str, Optional[float]]
    tracking_difference_1m: Optional[float] = None
    volatility_annualized: Optional[float] = None
