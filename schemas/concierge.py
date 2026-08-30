"""종합 부동산 컨시어지의 기능 간 공통 계약."""
from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field


class ConciergeIntent(str, Enum):
    FIND_REGION = "find_region"
    SELECT_PROPERTY = "select_property"
    APPRAISE = "appraise"
    COMPARE = "compare"
    SIMULATE = "simulate"
    RIGHTS_CHECK = "rights_check"
    TAX_LEGAL = "tax_legal"
    GENERAL = "general"


class ConciergeCriteria(BaseModel):
    property_type: Literal[
        "apartment", "row_house", "detached", "officetel",
        "non_residential", "industrial", "land",
    ] | None = None
    transaction_type: Literal["purchase", "rent", "lease"] = "purchase"
    budget_max_won: int | None = Field(default=None, ge=0)
    region_name: str | None = None
    region_code: str | None = Field(default=None, min_length=10, max_length=10)
    area_min_sqm: float | None = Field(default=None, ge=0)
    purpose: Literal["residence", "investment"] | None = None


class ConciergeDecision(BaseModel):
    intent: ConciergeIntent
    criteria: ConciergeCriteria = Field(default_factory=ConciergeCriteria)


class ConciergeMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    conversation_id: str | None = None


class ConciergeToolResult(BaseModel):
    tool: str
    status: Literal["completed", "needs_input", "not_available", "error"]
    data: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)


class ConciergeMessageResponse(BaseModel):
    conversation_id: str
    status: Literal["completed", "needs_input", "not_available", "error"]
    intent: ConciergeIntent
    answer: str
    criteria: ConciergeCriteria
    data: dict[str, Any] = Field(default_factory=dict)
    missing_fields: list[str] = Field(default_factory=list)
    tool_used: str | None = None
    pending_action: dict[str, Any] | None = None
