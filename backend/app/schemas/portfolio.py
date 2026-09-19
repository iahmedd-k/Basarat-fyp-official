from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class TransactionBase(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, examples=["OGDC"])
    type: str = Field(..., pattern="^(BUY|SELL)$", examples=["BUY"])
    quantity: int = Field(..., gt=0, examples=[100])
    price: float = Field(..., gt=0, examples=[98.50])
    fees: float = Field(default=0, ge=0, examples=[25.00])
    transaction_date: date = Field(..., examples=["2026-09-15"])


class TransactionCreate(TransactionBase):
    pass


class TransactionUpdate(BaseModel):
    quantity: Optional[int] = Field(None, gt=0)
    price: Optional[float] = Field(None, gt=0)
    fees: Optional[float] = Field(None, ge=0)
    transaction_date: Optional[date] = None


class TransactionResponse(TransactionBase):
    id: str
    user_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TransactionListResponse(BaseModel):
    data: list[TransactionResponse]
    pagination: dict


class PriceResponse(BaseModel):
    symbol: str
    ldcp: float
    current_price: float
    change: float
    change_percent: float
    market_status: str
    last_updated: datetime
    stale: Optional[bool] = None

    model_config = ConfigDict(from_attributes=True)


class BulkPriceRequest(BaseModel):
    symbols: list[str] = Field(..., min_length=1)


class BulkPriceResponse(BaseModel):
    prices: dict[str, dict]


class HoldingDetail(BaseModel):
    symbol: str
    quantity: int
    avg_cost: float
    invested_value: float
    current_price: float
    current_value: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    day_change_percent: float
    weight_in_portfolio: float
    market_status: str


class PortfolioSummaryResponse(BaseModel):
    total_invested: float
    total_current_value: float
    total_unrealized_pnl: float
    total_unrealized_pnl_percent: float
    day_change: float
    day_change_percent: float
    holdings: list[HoldingDetail]
    generated_at: datetime


class HoldingDetailResponse(BaseModel):
    symbol: str
    quantity: int
    avg_cost: float
    current_price: float
    unrealized_pnl: float
    unrealized_pnl_percent: float
    transactions: list[TransactionResponse]
    price_history_ref: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    message: str


class SuccessResponse(BaseModel):
    success: bool
    message: str