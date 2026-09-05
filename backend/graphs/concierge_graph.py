"""여러 부동산 기능을 도구로 확장하는 종합 컨시어지 LangGraph."""
from __future__ import annotations

import json
import re
from typing import Any

from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from backend.concierge.tools import execute_tool
from schemas.concierge import ConciergeCriteria, ConciergeDecision, ConciergeIntent, ConciergeToolResult


class ConciergeState(TypedDict, total=False):
    user_id: int
    message: str
    previous_criteria: dict[str, Any]
    decision: ConciergeDecision
    tool_result: ConciergeToolResult
    answer: str
    blocked: list[str]
    routing_error: str


ROUTER_PROMPT = """당신은 종합 부동산 컨시어지의 의도 분류기입니다.
사용자의 말에서 확인되는 값만 추출하고 추측하지 마세요. 금액은 원, 면적은 ㎡로 변환하세요.
intent는 find_region, select_property, appraise, compare, simulate, rights_check,
tax_legal, general 중 하나입니다. 반드시 아래 형태의 JSON만 반환하세요.
{"intent":"find_region","criteria":{"property_type":"apartment","transaction_type":"purchase",
"budget_max_won":1000000000,"region_name":"서울","region_code":null,"area_min_sqm":null,"purpose":null}}
동네·지역 추천은 find_region, 특정 매물·단지 선택은 select_property, 가격 추정은 appraise,
취득세·양도세·보유세·법률 질문은 tax_legal입니다."""


def _parse_json(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.DOTALL)
        return json.loads(match.group()) if match else {}


def decide_node(state: ConciergeState) -> ConciergeState:
    from backend.model_factory import get_llm_json

    previous = state.get("previous_criteria") or {}
    prompt = state["message"]
    if previous:
        prompt = f"이전 조건: {json.dumps(previous, ensure_ascii=False)}\n새 메시지: {prompt}"
    try:
        response = get_llm_json().invoke([("system", ROUTER_PROMPT), ("human", prompt)])
        decision = ConciergeDecision.model_validate(_parse_json(str(response.content)))
    except Exception as exc:
        # LLM 장애 시 숫자나 지역을 추측하지 않고 보완 입력을 받는 안전한 폴백이다.
        decision = ConciergeDecision(
            intent=ConciergeIntent.FIND_REGION,
            criteria=ConciergeCriteria.model_validate(previous),
        )
        return {**state, "decision": decision, "routing_error": type(exc).__name__}
    return {**state, "decision": decision}


def execute_node(state: ConciergeState) -> ConciergeState:
    decision = state["decision"]
    result = execute_tool(decision.intent, decision.criteria, state["user_id"])
    return {**state, "tool_result": result, "decision": decision}


def _fallback_answer(result: ConciergeToolResult) -> str:
    if result.status == "needs_input":
        labels = {"region": "희망 지역", "region_code": "정확한 지역",
                  "property_type": "부동산 유형", "budget_max_won": "최대 예산"}
        fields = ", ".join(labels.get(field, field) for field in result.missing_fields)
        if result.data.get("region_candidates"):
            names = ", ".join(item["full_name"] for item in result.data["region_candidates"])
            return f"같은 이름의 지역이 여러 곳입니다. 다음 중 선택해 주세요: {names}"
        return f"동네를 비교하려면 {fields}을(를) 알려주세요."
    if result.status == "not_available":
        return "이 요청을 처리할 도구는 종합 컨시어지 구조에 등록되어 있지만 아직 연결 준비 중입니다."
    items = result.data.get("items", [])
    if not items:
        return "선택한 조건으로 수집된 실거래 데이터를 찾지 못했습니다."
    names = ", ".join(item["region_name"] for item in items[:3])
    return f"수집된 실거래를 기준으로 우선 살펴볼 지역은 {names}입니다. 상세 수치는 지역 카드에서 확인해 주세요."


def explain_node(state: ConciergeState) -> ConciergeState:
    import backend.opinion_guard as opinion_guard
    from backend.model_factory import get_llm

    result = state["tool_result"]
    if result.status != "completed":
        return {**state, "answer": _fallback_answer(result), "blocked": []}

    context = json.dumps(result.data, ensure_ascii=False)
    allowed = opinion_guard.extract_numbers(context) | opinion_guard.extract_numbers(state["message"])
    prompt = ("아래 도구 결과에 있는 사실과 숫자만 사용해 한국어로 간결히 설명하세요. "
              "새 가격·비율·거래량을 만들지 말고, 실거래 출처와 기간을 밝히세요. "
              "현재 매물 호가라고 표현하지 마세요.\n" + context)
    try:
        raw = str(get_llm().invoke([("system", prompt), ("human", state["message"])]).content).strip()
        answer, blocked = opinion_guard.sanitize_text(raw, allowed)
    except Exception:
        answer, blocked = "", []
    return {**state, "answer": answer or _fallback_answer(result), "blocked": blocked}


def build_concierge_graph():
    graph = StateGraph(ConciergeState)
    graph.add_node("의도_조건_추출", decide_node)
    graph.add_node("허용_도구_실행", execute_node)
    graph.add_node("근거_결과_설명", explain_node)
    graph.set_entry_point("의도_조건_추출")
    graph.add_edge("의도_조건_추출", "허용_도구_실행")
    graph.add_edge("허용_도구_실행", "근거_결과_설명")
    graph.add_edge("근거_결과_설명", END)
    return graph.compile()


_GRAPH = None


def run_concierge(*, user_id: int, message: str, previous_criteria: dict | None = None) -> ConciergeState:
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_concierge_graph()
    return _GRAPH.invoke({
        "user_id": user_id, "message": message,
        "previous_criteria": previous_criteria or {},
    })
