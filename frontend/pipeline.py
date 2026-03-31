"""
pipeline.py — Streamlit 진행 표시 래퍼
개선:
  - 더미 _invoke() 제거, router.run_appraisal() 실제 연결
  - 단계별 진행 상황을 generator 로 yield
  - 예외 발생 시 error 이벤트로 전달
"""

from __future__ import annotations

from typing import Generator


# ── 실제 LangGraph 파이프라인 연결 ──────────────────────────────────────────
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

from router import run_appraisal as _run_appraisal

def _invoke(user_input: str, building_name: str = "") -> dict:
    """router.run_appraisal() 호출 후 UI 친화적 dict 반환."""
    state = _run_appraisal(user_input, building_name)

    print(f"[debug] analysis_result: {state.get('analysis_result')}") 
    print(f"[debug] error: {state.get('error')}")

    # analysis_result 내부 필드를 최상위로 flatten (UI 컴포넌트 호환)
    ar = state.get("analysis_result") or {}
    merged = {**state, **ar}

    # intent 에서 category/area 보완
    intent = state.get("intent")
    if intent:
        merged.setdefault("category",    getattr(intent, "category", ""))
        merged.setdefault("area_m2",     getattr(intent, "area_min", 0))
        merged.setdefault("asking_price", getattr(intent, "price_min", 0))

    return merged


# ─────────────────────────────────────────
#  단계 레이블 (진행 표시용)
# ─────────────────────────────────────────

STEP_LABELS = [
    ("🔍", "의도 분석",     "카테고리 · 위치 · 면적 · 호가 추출"),
    ("📍", "지오코딩",      "자연어 지명 → 위도/경도 변환"),
    ("🏗️", "실거래가 조회", "국토부 API 인근 매매 사례 수집"),
    ("📊", "감정평가 계산", "비교사례법 · Cap Rate 산출"),
    ("📝", "의견서 생성",   "LLM 전문 감정평가 의견서 작성"),
]


# ─────────────────────────────────────────
#  진행 이벤트 generator
# ─────────────────────────────────────────

def run_with_progress(
    user_input: str,
    building_name: str = "",
) -> Generator[dict, None, None]:
    """
    파이프라인을 실행하면서 단계 진행 이벤트를 yield 합니다.

    yield 형태:
        {"type": "step",   "index": int, "icon": str, "title": str, "desc": str}
        {"type": "result", "data": dict}
        {"type": "error",  "message": str}

    LangGraph 내부에서 단계가 완료되는 시점을 정확히 알 수 없으므로
    파이프라인 실행 전/후로 단계를 일괄 표시합니다.
    (실제 streaming 이벤트가 필요하면 LangGraph stream() 연동 가능)
    """
    try:
        # 단계 표시 (실행 시작 전)
        for i, (icon, title, desc) in enumerate(STEP_LABELS):
            yield {"type": "step", "index": i, "icon": icon, "title": title, "desc": desc}

        # 실제 파이프라인 실행
        result = _invoke(user_input, building_name)

        if result.get("error") and not result.get("analysis_result"):
            yield {"type": "error", "message": result["error"]}
        else:
            yield {"type": "result", "data": result}

    except Exception as e:
        yield {"type": "error", "message": str(e)}
