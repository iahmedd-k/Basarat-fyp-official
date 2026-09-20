from datetime import datetime

from pydantic import BaseModel, Field


class ShariahCriterion(BaseModel):
    name: str
    threshold: float
    value: float | None = None
    passed: bool
    description: str | None = None


class ShariahScreeningResponse(BaseModel):
    symbol: str
    is_shariah_compliant: bool
    overall_score: float | None = None
    screening_method: str | None = None
    screened_at: datetime | None = None
    sector: str | None = None
    purification_rate: float | None = None
    compliance_summary: str | None = None


class ShariahCriteriaResponse(BaseModel):
    symbol: str
    is_shariah_compliant: bool = True
    criteria: list[ShariahCriterion]


class ShariahPurificationResponse(BaseModel):
    symbol: str
    holding_qty: int
    holding_value: float
    purification_amount: float
    purification_rate: float
    notes: str | None = None


class ShariahKMI30Response(BaseModel):
    index: str = "KMI-30"
    total_constituents: int | None = None
    constituents: list[dict]

