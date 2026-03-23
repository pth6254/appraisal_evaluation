"""
DeepAgent 부동산 가치 감정평가 — 리포트 생성 노드
router.py에서 분리된 독립 모듈

역할:
  - 전문 에이전트가 채운 AgentState를 받아
    마크다운 감정평가 리포트 문자열로 변환
  - LangGraph 노드 함수 report_node 제공
"""

from __future__ import annotations


def report_node(state: dict) -> dict:
    """LangGraph 노드 — 감정평가 결과 → 마크다운 리포트 생성"""
    intent = state.get("intent")
    geo    = state.get("geocoding_result") or {}
    result = state.get("analysis_result") or {}

    if not result:
        state["final_report"] = "❌ 감정평가 결과 없음"
        return state

    address  = geo.get("address_name", "") if isinstance(geo, dict) else ""
    category = getattr(intent, "category", "")
    detail   = getattr(intent, "category_detail", "")
    area_raw = getattr(intent, "area_raw", "미입력")

    estimated      = result.get("estimated_value", 0)
    value_min      = result.get("value_min", 0)
    value_max      = result.get("value_max", 0)
    ppyeong        = result.get("price_per_pyeong", 0)
    reg_ppyeong    = result.get("regional_avg_per_pyeong", 0)
    verdict        = result.get("valuation_verdict", "")
    deviation      = result.get("deviation_pct", 0.0)
    comp_avg       = result.get("comparable_avg", 0)
    comp_count     = result.get("comparable_count", 0)
    cap_rate       = result.get("cap_rate", 0.0)
    annual_inc     = result.get("annual_income", 0)
    roi_5yr        = result.get("roi_5yr", 0.0)
    inv_grade      = result.get("investment_grade", "")
    method         = result.get("valuation_method", "")
    opinion        = result.get("appraisal_opinion", "")
    strengths      = result.get("strengths", [])
    risks          = result.get("risk_factors", [])
    recommendation = result.get("recommendation", "")

    lines = [
        "# 부동산 가치 감정평가 리포트",
        "",
        "## 대상 물건",
        "| 항목 | 내용 |",
        "|------|------|",
        f"| 소재지 | {address} |",
        f"| 유형 | {category} / {detail} |",
        f"| 면적 | {area_raw} |",
        f"| 평가 기준 | {method} |",
        "",
        "## 감정평가액",
        "| 구분 | 금액 |",
        "|------|------|",
        f"| **추정 시장가치** | **{estimated:,}만원** |",
        f"| 추정 범위 | {value_min:,} ~ {value_max:,}만원 |",
        f"| 평당가 | {ppyeong:,}만원/평 |",
        f"| 지역 평균 평당가 | {reg_ppyeong:,}만원/평 |",
        "",
        "## 고/저평가 판단",
        "| 구분 | 내용 |",
        "|------|------|",
        f"| **판정** | **{verdict}** |",
        f"| 인근 실거래 평균 | {comp_avg:,}만원 ({comp_count}건) |",
        f"| 괴리율 | {deviation:+.1f}% |",
        "",
        "## 투자 수익성",
        "| 항목 | 수치 |",
        "|------|------|",
        f"| Cap Rate | {cap_rate}% |",
        f"| 연 임대수입 추정 | {annual_inc:,}만원 |",
        f"| 5년 예상 수익률 | {roi_5yr}% |",
        f"| **투자등급** | **{inv_grade}** |",
        "",
        "## 감정평가 의견",
        opinion,
        "",
        "### 가치 상승 요인",
    ]

    for s in strengths:
        lines.append(f"- {s}")

    lines += ["", "### 리스크 요인"]
    for r in risks:
        lines.append(f"- {r}")

    lines += ["", f"**종합 추천**: {recommendation}"]

    state["final_report"] = "\n".join(lines)

    # 콘솔 출력
    print("\n" + "=" * 60)
    print(state["final_report"])
    print("=" * 60)

    return state