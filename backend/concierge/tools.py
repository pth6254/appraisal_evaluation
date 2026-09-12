"""컨시어지가 호출할 수 있는 도구의 명시적 허용 목록."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from backend.services.market_service import get_region_market_summary, resolve_region_name
from schemas.concierge import ConciergeCriteria, ConciergeIntent, ConciergeToolResult
from backend.concierge.decision_tools import compare_properties, simulate_investment


@dataclass(frozen=True)
class ToolDefinition:
    name: str
    intent: ConciergeIntent
    description: str
    enabled: bool
    handler: Callable[..., ConciergeToolResult] | None = None


def find_regions(criteria: ConciergeCriteria, user_id: int, candidate_context: dict | None = None) -> ConciergeToolResult:
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
    if not criteria.transaction_type:
        missing.append("transaction_type")
    if missing:
        return ConciergeToolResult(
            tool="find_regions", status="needs_input", missing_fields=missing,
        )

    if criteria.transaction_type != "purchase":
        return ConciergeToolResult(tool="find_regions", status="not_available")
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


def appraise_property(criteria: ConciergeCriteria, user_id: int, candidate_context: dict | None = None) -> ConciergeToolResult:
    from api.candidate_appraisal import start_candidate_appraisal
    if not candidate_context or not candidate_context.get("candidate_id"):
        return ConciergeToolResult(tool="appraise_property", status="needs_input", missing_fields=["candidate"])
    data = start_candidate_appraisal(user_id, candidate_context["case_id"], candidate_context["candidate_id"])
    return ConciergeToolResult(tool="appraise_property", status="needs_input" if data.get("missing_fields") else "queued",
                               data=data, missing_fields=data.get("missing_fields", []))


def answer_tax_legal(criteria: ConciergeCriteria, user_id: int, candidate_context: dict | None = None, *, message: str) -> ConciergeToolResult:
    from backend.services.chat_service import answer_question
    return ConciergeToolResult(tool="answer_tax_legal", status="completed", data=answer_question(message))


def general_help(criteria: ConciergeCriteria, user_id: int, candidate_context: dict | None = None) -> ConciergeToolResult:
    return ConciergeToolResult(tool="general_help", status="completed", data={"answer":
        "실거래 기반 동네 추천과 선택한 후보의 AVM 시세추정을 도와드립니다. "
        "동네 추천은 희망 지역·부동산 유형·거래 유형을 알려주세요. "
        "AVM은 케이스와 후보를 선택한 뒤 요청할 수 있습니다. "
        "법률·세금 질문, 후보 자금 계산과 케이스의 후보 비교도 여기에서 요청할 수 있습니다."})


TOOL_REGISTRY: dict[ConciergeIntent, ToolDefinition] = {
    ConciergeIntent.FIND_REGION: ToolDefinition(
        name="find_regions", intent=ConciergeIntent.FIND_REGION,
        description="실거래 기반 시·군·구 비교", enabled=True, handler=find_regions,
    ),
    ConciergeIntent.SELECT_PROPERTY: ToolDefinition(
        "select_properties", ConciergeIntent.SELECT_PROPERTY, "조건에 맞는 매물·단지 후보 선택", False,
    ),
    ConciergeIntent.APPRAISE: ToolDefinition(
        "appraise_property", ConciergeIntent.APPRAISE, "AVM 기반 가격 추정", True, appraise_property,
    ),
    ConciergeIntent.COMPARE: ToolDefinition(
        "compare_properties", ConciergeIntent.COMPARE, "후보 부동산 비교", True, compare_properties,
    ),
    ConciergeIntent.SIMULATE: ToolDefinition(
        "simulate_investment", ConciergeIntent.SIMULATE, "자금·투자 시나리오 계산", True, simulate_investment,
    ),
    ConciergeIntent.RIGHTS_CHECK: ToolDefinition(
        "check_rights", ConciergeIntent.RIGHTS_CHECK, "권리관계 점검", False,
    ),
    ConciergeIntent.TAX_LEGAL: ToolDefinition(
        "answer_tax_legal", ConciergeIntent.TAX_LEGAL, "부동산 세금·법률 정보 안내", True, answer_tax_legal,
    ),
    ConciergeIntent.GENERAL: ToolDefinition(
        "general_help", ConciergeIntent.GENERAL, "컨시어지 사용 안내", True, general_help,
    ),
}


def execute_tool(intent: ConciergeIntent, criteria: ConciergeCriteria, user_id: int, candidate_context: dict | None = None, *, message: str = "", funding: dict | None = None) -> ConciergeToolResult:
    definition = TOOL_REGISTRY[intent]
    if not definition.enabled or definition.handler is None:
        return ConciergeToolResult(
            tool=definition.name, status="not_available",
            data={"description": definition.description},
        )
    if intent == ConciergeIntent.TAX_LEGAL:
        return definition.handler(criteria, user_id, candidate_context, message=message)
    if intent == ConciergeIntent.SIMULATE:
        return definition.handler(criteria, user_id, candidate_context, funding=funding)
    return definition.handler(criteria, user_id, candidate_context)
