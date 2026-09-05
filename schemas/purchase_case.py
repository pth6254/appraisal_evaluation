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
ExecutionPhase = Literal["before_contract", "before_closing", "closing_day", "after_closing"]
ExecutionActor = Literal["self", "bank", "broker", "legal_agent", "tax_agent", "other"]
ExecutionTaskStatus = Literal["scheduled", "in_progress", "waiting_external", "done", "problem", "not_applicable"]


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
    asking_price: int | None = Field(default=None, ge=0)
    status: PropertyStatus | None = None
    notes: str | None = Field(default=None, max_length=5000)


class ChecklistItemUpdate(BaseModel):
    status: ChecklistStatus
    evidence: str | None = Field(default=None, max_length=5000)


class CaseDecisionCreate(BaseModel):
    property_id: int = Field(gt=0)
    reason: str = Field(min_length=3, max_length=5000)


class ExecutionPlanUpdate(BaseModel):
    contract_planned_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    closing_planned_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")

    @model_validator(mode="after")
    def validate_dates(self):
        if self.contract_planned_date and self.closing_planned_date and self.contract_planned_date > self.closing_planned_date:
            raise ValueError("잔금 예정일은 계약 예정일보다 빠를 수 없습니다")
        return self


class ExecutionTaskCreate(BaseModel):
    phase: ExecutionPhase
    title: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=5000)
    actor_type: ExecutionActor = "self"
    required: bool = False
    due_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class ExecutionTaskUpdate(BaseModel):
    status: ExecutionTaskStatus | None = None
    actor_type: ExecutionActor | None = None
    due_date: str | None = Field(default=None, pattern=r"^\d{4}-\d{2}-\d{2}$")
    checked_by: str | None = Field(default=None, max_length=150)
    outcome: str | None = Field(default=None, max_length=5000)
    evidence_note: str | None = Field(default=None, max_length=5000)
    follow_up: str | None = Field(default=None, max_length=5000)


class CaseRegionCreate(BaseModel):
    region_code: str = Field(pattern=r"^\d{10}$")
    property_type: MarketPropertyType = "all"
    budget_max_won: int | None = Field(default=None, ge=0)
    months: int = Field(default=12, ge=1, le=60)
    source: Literal["market_explorer", "concierge"] = "market_explorer"
