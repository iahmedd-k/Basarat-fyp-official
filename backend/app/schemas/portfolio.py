from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class TransactionCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, description="Stock symbol (e.g., OGDC)")
    transaction_type: Literal["BUY", "SELL"] = Field(..., description="Transaction type: BUY or SELL")
    quantity: Decimal = Field(..., gt=0, description="Number of shares", max_digits=18, decimal_places=4)
    price: Decimal = Field(..., ge=0, description="Price per share", max_digits=18, decimal_places=4)
    fee: Decimal = Field(default=Decimal("0"), ge=0, description="Transaction fee", max_digits=18, decimal_places=4)
    transaction_date: date = Field(..., description="Transaction date (YYYY-MM-DD)")

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        return v.strip().upper()

    @field_validator("quantity", "price", "fee", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))

    @field_validator("transaction_type")
    @classmethod
    def _normalize_type(cls, v: str) -> str:
        return v.strip().upper()


class TransactionUpdate(BaseModel):
    quantity: Decimal | None = Field(None, gt=0, description="Number of shares", max_digits=18, decimal_places=4)
    price: Decimal | None = Field(None, ge=0, description="Price per share", max_digits=18, decimal_places=4)
    fee: Decimal | None = Field(None, ge=0, description="Transaction fee", max_digits=18, decimal_places=4)
    transaction_date: date | None = Field(None, description="Transaction date (YYYY-MM-DD)")

    @field_validator("quantity", "price", "fee", mode="before")
    @classmethod
    def _to_decimal(cls, v):
        if v is None:
            return None
        if isinstance(v, Decimal):
            return v
        return Decimal(str(v))


class TransactionResponse(BaseModel):
    id: str
    symbol: str
    transaction_type: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    transaction_date: date
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    items: list[TransactionResponse]
    total: int
    page: int
    limit: int


class HoldingItem(BaseModel):
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal | None = None
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_percent: float | None = None
    portfolio_weight: float | None = None
    price_updated_at: datetime | None = None
    price_status: str = "AVAILABLE"


class PortfolioSummary(BaseModel):
    total_invested: Decimal
    current_value: Decimal
    total_pnl: Decimal
    total_pnl_percent: float
    today_pnl: Decimal


class PortfolioResponse(BaseModel):
    summary: PortfolioSummary
    holdings: list[HoldingItem]
    updated_at: datetime


class HoldingDetailResponse(BaseModel):
    symbol: str
    company_name: str | None = None
    sector: str | None = None
    quantity: Decimal
    average_cost: Decimal
    current_price: Decimal | None = None
    invested_value: Decimal
    market_value: Decimal | None = None
    unrealized_pnl: Decimal | None = None
    unrealized_pnl_percent: float | None = None
    realized_pnl: Decimal
    portfolio_weight: float | None = None
    transactions: list[TransactionResponse]
    price_updated_at: datetime | None = None
    price_status: str = "AVAILABLE"


class PnLResponse(BaseModel):
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_pnl: Decimal
    total_pnl_percent: float
    today_pnl: Decimal


class AllocationByStock(BaseModel):
    symbol: str
    market_value: Decimal
    percentage: float


class AllocationBySector(BaseModel):
    sector: str
    market_value: Decimal
    percentage: float


class AllocationResponse(BaseModel):
    by_stock: list[AllocationByStock]
    by_sector: list[AllocationBySector]


class PerformancePoint(BaseModel):
    date: str
    value: Decimal


class PerformanceResponse(BaseModel):
    period: str
    data: list[PerformancePoint]


class PortfolioQueryParams(BaseModel):
    page: int = Field(default=1, ge=1)
    limit: int = Field(default=20, ge=1, le=100)
    symbol: str | None = None
    transaction_type: Literal["BUY", "SELL"] | None = None
    from_date: date | None = None
    to_date: date | None = None