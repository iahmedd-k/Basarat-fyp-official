from datetime import date, datetime
from pydantic import BaseModel, Field


class HoldingCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, examples=["HBL"])
    quantity: int = Field(..., gt=0, examples=[100])
    avg_buy_price: float = Field(..., gt=0, examples=[85.50])
    purchase_date: date = Field(..., examples=["2025-06-15"])


class HoldingUpdate(BaseModel):
    symbol: str | None = Field(None, min_length=1, max_length=20)
    quantity: int | None = Field(None, gt=0)
    avg_buy_price: float | None = Field(None, gt=0)
    purchase_date: date | None = None


class HoldingResponse(BaseModel):
    id: str
    portfolio_id: str
    stock_id: str
    symbol: str
    quantity: int
    avg_buy_price: float
    purchase_date: date | None = None
    current_price: float | None = None
    current_value: float | None = None
    pnl: float | None = None
    pnl_pct: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PortfolioResponse(BaseModel):
    id: str
    name: str
    holdings: list[HoldingResponse]
    total_value: float
    total_invested: float
    total_pnl: float
    total_pnl_pct: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PnLSummary(BaseModel):
    total_invested: float
    total_current_value: float
    total_pnl: float
    total_pnl_pct: float
    holdings: list[HoldingResponse]


class AllocationItem(BaseModel):
    sector: str
    value: float
    weight_pct: float
    holding_count: int


class AllocationResponse(BaseModel):
    allocations: list[AllocationItem]
    total_value: float


class RiskMetricsResponse(BaseModel):
    var_95: float | None = Field(None, description="Value at Risk at 95% confidence")
    var_99: float | None = Field(None, description="Value at Risk at 99% confidence")
    sharpe_ratio: float | None = Field(None, description="Annualized Sharpe ratio")
    max_drawdown: float | None = Field(None, description="Maximum drawdown percentage")
    beta: float | None = None
    volatility: float | None = Field(None, description="Annualized volatility")
