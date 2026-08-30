"""매수 검토 케이스 API 입출력 스키마."""
from __future__ import annotations

from typing import Literal
from pydantic import BaseModel, Field, model_validator

CaseStatus = Literal["exploring", "reviewing", "negotiating", "decided", "archived"]
PropertyStatus = Literal["reviewing", "shortlisted", "rejected", "selected"]
ChecklistStatus = Literal["todo", "done", "warning", "blocked"]
MarketPropertyType = Literal[
    "all", "apartment", "row_house", "detached", "officetel",
    "non_residential", "industrial", "land",
]


class PurchaseCaseCreate(BaseModel):
    title: str = Field(min_length=1, max_length=150)
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    target_regions: list[str] = Field(default_factory=list, max_length=20)
    notes: str = Field(default="", max_length=5000)

    @model_validator(mode="after")
    def validate_budget(self):
        if self.budget_min is not None and self.budget_max is not None and self.budget_min > self.budget_max:
            raise ValueError("최소 예산은 최대 예산보다 클 수 없습니다")
        return self


class PurchaseCaseUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=150)
    status: CaseStatus | None = None
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    target_regions: list[str] | None = Field(default=None, max_length=20)
    notes: str | None = Field(default=None, max_length=5000)


class CasePropertyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    address: str = Field(default="", max_length=500)
    category: str = Field(default="", max_length=30)
    asking_price: int | None = Field(default=None, ge=0)
    area_sqm: float | None = Field(default=None, gt=0)
    legal_region_code: str | None = Field(default=None, pattern=r"^\d{10}$")
    source: Literal["manual", "recommendation", "appraisal"] = "manual"
    status: PropertyStatus = "reviewing"
    notes: str = Field(default="", max_length=5000)
    history_id: int | None = Field(default=None, gt=0)


class CasePropertyUpdate(BaseModel):
    status: PropertyStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)


class ChecklistItemUpdate(BaseModel):
    status: ChecklistStatus
    evidence: str | None = Field(default=None, max_length=5000)


class CaseRegionCreate(BaseModel):
    region_code: str = Field(pattern=r"^\d{10}$")
    property_type: MarketPropertyType = "all"
    budget_max_won: int | None = Field(default=None, ge=0)
    months: int = Field(default=12, ge=1, le=60)
    source: Literal["market_explorer", "concierge"] = "market_explorer"
