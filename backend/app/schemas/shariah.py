from datetime import datetime

from pydantic import BaseModel, Field


class ShariahCriterion(BaseModel):
    name: str
    threshold: float
    value: float = 0.0
    passed: bool = True
    description: str = ""
    exception: str = "None (Standard PSX KMI-30 screening)"


class ShariahScreeningResponse(BaseModel):
    symbol: str
    screening_available: bool = True
    is_shariah_compliant: bool = True
    overall_score: float = 100.0
    screening_method: str = "PSX KMI-30 / Meezan Screening Standard"
    screened_at: datetime | None = None
    data_as_of: datetime | None = None
    data_is_stale: bool = False
    effective_from: datetime | None = None
    source_url: str = "https://www.psx.com.pk"
    source_exception: str = "None (Standard PSX KMI-30 screening)"
    purification_rate_provisional: bool = False
    criteria: list[ShariahCriterion] = Field(default_factory=list)
    sector: str = "Commercial & Industrial"
    purification_rate: float = 0.0
    compliance_summary: str = ""


class ShariahCriteriaResponse(BaseModel):
    symbol: str
    screening_available: bool = True
    is_shariah_compliant: bool = True
    criteria: list[ShariahCriterion] = Field(default_factory=list)
    data_as_of: datetime | None = None
    data_is_stale: bool = False
    source_url: str = "https://www.psx.com.pk"


class ShariahPurificationResponse(BaseModel):
    symbol: str
    dividend_income: float
    purification_amount: float
    purification_rate: float
    notes: str = ""
    data_as_of: datetime | None = None
    data_is_stale: bool = False
    source_url: str = "https://www.psx.com.pk"
    rate_is_provisional: bool = False


class ShariahKMI30Response(BaseModel):
    index: str = "KMI-30"
    total_constituents: int = 30
    as_of: datetime | None = None
    is_stale: bool = False
    effective_from: datetime | None = None
    source_url: str = "https://www.psx.com.pk"
    constituents: list[dict] = Field(default_factory=list)


