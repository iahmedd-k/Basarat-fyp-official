from datetime import datetime

from pydantic import BaseModel


class ShariahCriterion(BaseModel):
    name: str
    threshold: float
    value: float | None = None
    passed: bool


class ShariahScreeningResponse(BaseModel):
    symbol: str
    is_shariah_compliant: bool
    overall_score: float | None = None
    screening_method: str | None = None
    screened_at: datetime | None = None


class ShariahCriteriaResponse(BaseModel):
    symbol: str
    criteria: list[ShariahCriterion]


class ShariahPurificationResponse(BaseModel):
    symbol: str
    holding_qty: int
    holding_value: float
    purification_amount: float
    purification_rate: float


class ShariahKMI30Response(BaseModel):
    index: str
    constituents: list[dict]
