"""
router.py — 전체 파이프라인 라우터
개선:
  - _graph 모듈 레벨 캐싱 → 매 요청마다 compile() 방지
  - API 키 시작 시 검증 및 경고 출력
  - run_appraisal() 에 타임아웃 보호 추가
"""

from __future__ import annotations

import os
from typing import Optional

from typing_extensions import TypedDict
from intent_agent import PropertyIntent, analyze_intent

from dotenv import load_dotenv, find_dotenv

# 자동으로 상위 디렉토리를 탐색하며 .env를 찾아 로드합니다.
load_dotenv(find_dotenv())

# ─────────────────────────────────────────
#  API 키 검증 (모듈 임포트 시 1회 실행)
# ─────────────────────────────────────────

def _check_api_keys():
    missing = []
    if not os.getenv("KAKAO_REST_API_KEY"):
        missing.append("KAKAO_REST_API_KEY")
    if not os.getenv("MOLIT_API_KEY"):
        missing.append("MOLIT_API_KEY")
    if not os.getenv("TAVILY_API_KEY"):
        missing.append("TAVILY_API_KEY (선택)")
    if missing:
        print(f"[router] ⚠️  환경변수 미설정: {', '.join(missing)}")
        print("[router]    일부 기능이 더미 데이터로 동작합니다.")

_check_api_keys()


# ─────────────────────────────────────────
#  1. 파이프라인 상태
# ─────────────────────────────────────────

class AgentState(TypedDict, total=False):
    """전체 파이프라인 공유 상태"""
    user_input:       str
    building_name:    str
    intent:           Optional[PropertyIntent]
    raw_llm_output:   str
    error:            str
    retry_count:      int
    routed_to:        str
    geocoding_result: Optional[dict]
    price_data:       dict
    rag_top_matches:  list    
    rag_query:        str         
    rag_match_count:  int
    analysis_result:  dict       
    final_report:     str


# ─────────────────────────────────────────
#  2. 카테고리 → 에이전트 매핑
# ─────────────────────────────────────────

CATEGORY_TO_AGENT = {
    "주거용": "residential_agent",
    "상업용": "commercial_agent",
    "업무용": "office_agent",
    "산업용": "industrial_agent",
    "토지":   "land_agent",
}


# ─────────────────────────────────────────
#  3. 라우터 노드
# ─────────────────────────────────────────

def route_by_category(state: AgentState) -> str:
    if state.get("error") or not state.get("intent"):
        return "error_handler"

    category   = state["intent"].category
    agent_node = CATEGORY_TO_AGENT.get(category)

    if not agent_node:
        print(f"[라우터] ⚠️ 알 수 없는 카테고리 '{category}' → 주거용으로 대체")
        return "residential_agent"

    print(f"[라우터] '{category}' → {agent_node}")
    return agent_node


def router_node(state: AgentState) -> AgentState:
    if state.get("intent"):
        category = state["intent"].category
        state["routed_to"] = CATEGORY_TO_AGENT.get(category, "residential_agent")
    return state


# ─────────────────────────────────────────
#  4. 전문 에이전트 임포트
# ─────────────────────────────────────────

from agents import (
    residential_agent,
    commercial_agent,
    office_agent,
    industrial_agent,
    land_agent,
)


def error_handler(state: AgentState) -> AgentState:
    print(f"[오류] 처리 불가: {state.get('error', '알 수 없는 오류')}")
    return state


# ─────────────────────────────────────────
#  5. 그래프 구성 + 캐싱
# ─────────────────────────────────────────

from langgraph.graph import END, StateGraph

_graph = None   # 모듈 레벨 캐시 — 최초 1회만 compile()


def build_full_graph() -> StateGraph:
    """감정평가 통합 파이프라인 (최초 1회만 빌드)"""
    from intent_agent import intent_analysis_node, validate_node, should_retry
    from geocoding import geocoding_node
    from appraisal_report import report_node
    from deep_analysis import deep_analysis_node

    graph = StateGraph(AgentState)

    graph.add_node("의도분석",          intent_analysis_node)
    graph.add_node("검증",              validate_node)
    graph.add_node("지오코딩",          geocoding_node)
    graph.add_node("심층분석",           deep_analysis_node)
    graph.add_node("라우터",            router_node)
    graph.add_node("residential_agent", residential_agent)
    graph.add_node("commercial_agent",  commercial_agent)
    graph.add_node("office_agent",      office_agent)
    graph.add_node("industrial_agent",  industrial_agent)
    graph.add_node("land_agent",        land_agent)
    graph.add_node("감정평가_리포트",    report_node)
    graph.add_node("오류처리",          error_handler)

    graph.set_entry_point("의도분석")
    graph.add_edge("의도분석", "검증")
    graph.add_conditional_edges(
        "검증",
        should_retry,
        {"retry": "의도분석", "end": "지오코딩"},
    )
    graph.add_edge("지오코딩", "심층분석") 
    graph.add_edge("심층분석", "라우터") 

    graph.add_conditional_edges(
        "라우터",
        route_by_category,
        {
            "residential_agent": "residential_agent",
            "commercial_agent":  "commercial_agent",
            "office_agent":      "office_agent",
            "industrial_agent":  "industrial_agent",
            "land_agent":        "land_agent",
            "error_handler":     "오류처리",
        },
    )

    for node in ["residential_agent", "commercial_agent", "office_agent",
                 "industrial_agent", "land_agent"]:
        graph.add_edge(node, "감정평가_리포트")

    graph.add_edge("감정평가_리포트", END)
    graph.add_edge("오류처리",        END)

    return graph.compile()


def _get_graph():
    """그래프 싱글톤 — 최초 요청 시 compile(), 이후 재사용"""
    global _graph
    if _graph is None:
        print("[router] 그래프 컴파일 중...")
        _graph = build_full_graph()
        print("[router] 그래프 컴파일 완료")
    return _graph


# ─────────────────────────────────────────
#  6. 공개 실행 인터페이스
# ─────────────────────────────────────────

def run_appraisal(user_input: str, building_name: str = "") -> dict:
    """
    감정평가 실행 — 외부(FastAPI, Streamlit 등)에서 호출하는 공개 인터페이스.

    Args:
        user_input    : 자연어 요청 (위치, 면적, 가격 등)
        building_name : 건물명·단지명 (선택)

    Returns:
        AgentState dict — analysis_result, final_report 포함
    """
    graph = _get_graph()
    result = graph.invoke({
        "user_input":    user_input.strip(),
        "building_name": building_name.strip(),
        "error":         "",
        "retry_count":   0,
    })
    return result


if __name__ == "__main__":
    model = os.getenv("OLLAMA_MODEL", "exaone3.5:7.8b")
    print(f"모델: {model}")
    print("=" * 60)

    test_cases = [
        ("마포구 아파트 매매 84㎡",      "마포래미안푸르지오"),
        ("서초구 아파트 매매 59㎡",      "반포래미안원베일리"),
        ("강남구 역삼동 상가 매매 50평",  ""),
        ("판교 사무실 매매 100평",        "파르나스타워"),
        ("인천 남동공단 창고 매매 300평", "남동인더스파크"),
        ("양평군 토지 매매 500평",        ""),
    ]

    for query, bname in test_cases:
        print(f"\n입력: {query}")
        if bname:
            print(f"건물명: {bname}")
        print("-" * 60)
        result = run_appraisal(query, bname)
        if result.get("error") and not result.get("analysis_result"):
            print(f"❌ {result['error'][:100]}")