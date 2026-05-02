"""
router.py — 파이프라인 진입점

그래프 빌드 로직은 graphs/appraisal_graph.py 로 이동.
이 파일은 싱글톤 캐시와 공개 API(run_appraisal, run_recommendation)만 유지.
"""

from __future__ import annotations

import os
from typing import Optional

from dotenv import find_dotenv, load_dotenv

from graphs.appraisal_graph import build_appraisal_graph
from graphs.recommendation_graph import build_recommendation_graph
from state import AgentState

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

_check_api_keys()


# ─────────────────────────────────────────
#  그래프 싱글톤
# ─────────────────────────────────────────

_graph = None
_rec_graph = None


def _get_graph():
    """감정평가 그래프 — 최초 요청 시 compile(), 이후 재사용"""
    global _graph
    if _graph is None:
        print("[router] 감정평가 그래프 컴파일 중...")
        _graph = build_appraisal_graph()
        print("[router] 감정평가 그래프 컴파일 완료")
    return _graph


def _get_rec_graph():
    """추천 그래프 — 최초 요청 시 compile(), 이후 재사용"""
    global _rec_graph
    if _rec_graph is None:
        print("[router] 추천 그래프 컴파일 중...")
        _rec_graph = build_recommendation_graph()
        print("[router] 추천 그래프 컴파일 완료")
    return _rec_graph


# ─────────────────────────────────────────
#  공개 실행 인터페이스
# ─────────────────────────────────────────

def run_appraisal(user_input: str, building_name: str = "") -> dict:
    """
    감정평가 실행 — Streamlit, FastAPI 등 외부에서 호출하는 공개 API.

    Args:
        user_input    : 자연어 요청 (위치, 면적, 가격 등)
        building_name : 건물명·단지명 (선택)

    Returns:
        AgentState dict — analysis_result, final_report 포함
    """
    graph = _get_graph()
    return graph.invoke({
        "user_input":    user_input.strip(),
        "building_name": building_name.strip(),
        "error":         "",
        "retry_count":   0,
    })


def run_recommendation(
    query,
    limit: int = 5,
    run_appraisal: bool = False,
) -> dict:
    """
    매물 추천 실행 — Streamlit, FastAPI 등 외부에서 호출하는 공개 API.

    Args:
        query:         PropertyQuery 객체. 필터·예산·면적 조건 포함.
        limit:         반환할 최대 추천 건수 (기본 5).
        run_appraisal: True면 매물별 감정평가 시도
                       (실패해도 추천은 계속, 기본 False).

    Returns:
        RecommendationState dict:
          - results : list[RecommendationResult]  — 점수 내림차순
          - report  : str                         — 마크다운 리포트
          - error   : str                         — 오류 시 메시지
    """
    graph = _get_rec_graph()
    return graph.invoke({
        "query":         query,
        "limit":         limit,
        "run_appraisal": run_appraisal,
        "error":         "",
    })


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
