"""컨시어지가 호출할 수 있는 도구의 명시적 허용 목록."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.services.market_service import get_region_market_summary, resolve_region_name
from schemas.concierge import ConciergeCriteria, ConciergeIntent, ConciergeToolResult


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    intent: ConciergeIntent
    description: str
    enabled: bool
    handler: Callable[[ConciergeCriteria, int], ConciergeToolResult] | None = None


def find_regions(criteria: ConciergeCriteria, user_id: int) -> ConciergeToolResult:
    del user_id  # 조회 도구지만 모든 호출자가 같은 서명을 갖도록 유지한다.
    if not criteria.region_code and criteria.region_name:
        resolved = resolve_region_name(criteria.region_name)
        if resolved["status"] == "ambiguous":
            return ConciergeToolResult(
                tool="find_regions", status="needs_input",
                data={"region_candidates": resolved["candidates"]},
                missing_fields=["region_code"],
            )
        if resolved["status"] == "resolved":
            criteria.region_code = resolved["code"]

    missing = []
    if not criteria.region_code:
        missing.append("region")
    if not criteria.property_type:
        missing.append("property_type")
    if missing:
        return ConciergeToolResult(
            tool="find_regions", status="needs_input", missing_fields=missing,
        )

    summary = get_region_market_summary(
        region_code=criteria.region_code,
        property_type=criteria.property_type,
        months=12,
        budget_max_won=criteria.budget_max_won,
    )
    return ConciergeToolResult(
        tool="find_regions", status="completed",
        data={**summary, "items": summary.get("items", [])[:10]},
    )


TOOL_REGISTRY: dict[ConciergeIntent, ToolDefinition] = {
    ConciergeIntent.FIND_REGION: ToolDefinition(
        name="find_regions", intent=ConciergeIntent.FIND_REGION,
        description="실거래 기반 시·군·구 비교", enabled=True, handler=find_regions,
    ),
    ConciergeIntent.SELECT_PROPERTY: ToolDefinition(
        "select_properties", ConciergeIntent.SELECT_PROPERTY, "조건에 맞는 매물·단지 후보 선택", False,
    ),
    ConciergeIntent.APPRAISE: ToolDefinition(
        "appraise_property", ConciergeIntent.APPRAISE, "AVM 기반 가격 추정", False,
    ),
    ConciergeIntent.COMPARE: ToolDefinition(
        "compare_properties", ConciergeIntent.COMPARE, "후보 부동산 비교", False,
    ),
    ConciergeIntent.SIMULATE: ToolDefinition(
        "simulate_investment", ConciergeIntent.SIMULATE, "자금·투자 시나리오 계산", False,
    ),
    ConciergeIntent.RIGHTS_CHECK: ToolDefinition(
        "check_rights", ConciergeIntent.RIGHTS_CHECK, "권리관계 점검", False,
    ),
    ConciergeIntent.TAX_LEGAL: ToolDefinition(
        "answer_tax_legal", ConciergeIntent.TAX_LEGAL, "부동산 세금·법률 정보 안내", False,
    ),
    ConciergeIntent.GENERAL: ToolDefinition(
        "general_help", ConciergeIntent.GENERAL, "컨시어지 사용 안내", False,
    ),
}


def execute_tool(intent: ConciergeIntent, criteria: ConciergeCriteria, user_id: int) -> ConciergeToolResult:
    definition = TOOL_REGISTRY[intent]
    if not definition.enabled or definition.handler is None:
        return ConciergeToolResult(
            tool=definition.name, status="not_available",
            data={"description": definition.description},
        )
    return definition.handler(criteria, user_id)
