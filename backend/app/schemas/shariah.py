from datetime import datetime

from pydantic import BaseModel, Field


class ShariahCriterion(BaseModel):
    name: str
    threshold: float
    value: float | None = None
    passed: bool | None
    description: str | None = None


class ShariahScreeningResponse(BaseModel):
    symbol: str
    screening_available: bool = True
    is_shariah_compliant: bool | None
    overall_score: float | None = None
    screening_method: str | None = None
    screened_at: datetime | None = None
    data_as_of: datetime | None = None
    data_is_stale: bool | None = None
    sector: str | None = None
    purification_rate: float | None = None
    compliance_summary: str | None = None


class ShariahCriteriaResponse(BaseModel):
    symbol: str
    screening_available: bool = True
    is_shariah_compliant: bool | None = True
    criteria: list[ShariahCriterion]


class ShariahPurificationResponse(BaseModel):
    symbol: str
    dividend_income: float
    purification_amount: float
    purification_rate: float
    notes: str | None = None


class ShariahKMI30Response(BaseModel):
    index: str = "KMI-30"
    total_constituents: int | None = None
    as_of: datetime | None = None
    is_stale: bool = True
    constituents: list[dict]

