"""
DeepAgent 부동산 가치 감정평가 — 리포트 생성 노드
router.py에서 분리된 독립 모듈

역할:
  - 전문 에이전트가 채운 AgentState를 받아
    마크다운 감정평가 리포트 문자열로 변환
  - LangGraph 노드 함수 report_node 제공
  - AppraisalResult 기반 가격 분석 리포트 생성 함수 제공
"""

from __future__ import annotations

import sys
import os

# schemas/ 는 프로젝트 루트에 위치 — 경로 추가
_BACKEND_DIR  = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in [_BACKEND_DIR, _PROJECT_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


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


# ─────────────────────────────────────────
#  AppraisalResult 기반 가격 분석 리포트
# ─────────────────────────────────────────

def generate_price_analysis_report(result: "AppraisalResult") -> str:  # type: ignore[name-defined]
    """
    AppraisalResult → 마크다운 가격 분석 리포트.

    기존 report_node()와 독립적으로 동작.
    단위 변환: 원(schemas) → 만원(표시용)
    """
    from schemas.appraisal_result import AppraisalResult  # 지연 import — 순환 방지

    def _manwon(won: int | None) -> str:
        if not won:
            return "—"
        return f"{won // 10_000:,}만원"

    def _pct(rate: float | None) -> str:
        if rate is None:
            return "—"
        return f"{rate * 100:+.1f}%"

    def _conf_label(c: float) -> str:
        if c >= 0.80: return f"높음 ({c:.0%})"
        if c >= 0.50: return f"보통 ({c:.0%})"
        return f"낮음 ({c:.0%})"

    # ── 헤더 ─────────────────────────────────────────────────────────────
    lines = [
        "# 가격 분석 리포트",
        "",
    ]

    # ── 추정가 섹션 ──────────────────────────────────────────────────────
    lines += [
        "## 추정 시장가치",
        "| 구분 | 금액 |",
        "|------|------|",
        f"| **추정가** | **{_manwon(result.estimated_price)}** |",
        f"| 하단 | {_manwon(result.low_price)} |",
        f"| 상단 | {_manwon(result.high_price)} |",
    ]
    if result.asking_price:
        lines.append(f"| 호가 | {_manwon(result.asking_price)} |")
    lines.append("")

    # ── 고저평가 판단 ─────────────────────────────────────────────────────
    lines += [
        "## 고저평가 판단",
        "| 구분 | 내용 |",
        "|------|------|",
        f"| **판정** | **{result.judgement or '—'}** |",
        f"| 괴리율 | {_pct(result.gap_rate)} |",
        f"| 신뢰도 | {_conf_label(result.confidence)} |",
        "",
    ]

    # ── 비교 사례 ─────────────────────────────────────────────────────────
    if result.comparables:
        lines += [
            "## 비교 사례",
            "| 단지명 | 면적 | 거래가 | 거래일 | 매칭 수준 |",
            "|--------|------|--------|--------|-----------|",
        ]
        for c in result.comparables:
            name     = c.complex_name or "—"
            area     = f"{c.area_m2:.1f}㎡" if c.area_m2 else "—"
            price    = _manwon(c.deal_price)
            date     = c.deal_date or "—"
            level_map = {
                "same_complex": "동일 단지",
                "same_dong":    "동일 동",
                "same_gu":      "동일 구",
                "nearby":       "인근",
                "fallback":     "폴백",
            }
            level = level_map.get(c.match_level or "", c.match_level or "—")
            lines.append(f"| {name} | {area} | {price} | {date} | {level} |")
        lines.append("")

    # ── 경고 및 데이터 출처 ──────────────────────────────────────────────
    if result.warnings:
        lines += ["## 주의사항"]
        for w in result.warnings:
            lines.append(f"- ⚠️ {w}")
        lines.append("")

    if result.data_source:
        lines += [
            "## 데이터 출처",
            ", ".join(result.data_source),
            "",
        ]

    return "\n".join(lines)