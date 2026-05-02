"""
scoring_tool.py — 매물 종합 점수 산출 도구 (Phase 3-2)

calculate_listing_score(listing, query, appraisal) 를 호출하면
price / location / investment / risk 4개 축 점수(0-10)와
total_score, recommendation_label, reasons, risks 를 담은 dict 를 반환한다.

가중치:
  total = price * 0.35 + location * 0.30 + investment * 0.20 + (10 - risk) * 0.15
"""

from __future__ import annotations

import os
import sys
from typing import Optional

_TOOLS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR  = os.path.dirname(_TOOLS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)

for _p in [_BACKEND_DIR, _PROJECT_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from schemas.appraisal_result import AppraisalResult
from schemas.property_listing import PropertyListing
from schemas.property_query import PropertyQuery

_CURRENT_YEAR = 2026

# ─────────────────────────────────────────
#  price_score  (0-10)
# ─────────────────────────────────────────

def _score_price(
    listing: PropertyListing,
    query: PropertyQuery,
    appraisal: Optional[AppraisalResult],
) -> tuple[float, list[str], list[str]]:
    """가격 적정성 점수. (score, reasons, risks)"""
    reasons: list[str] = []
    risks:   list[str] = []

    judgement_scores = {
        "저평가":    8.5,
        "적정":      6.5,
        "소폭 고평가": 4.5,
        "고평가":    2.5,
    }

    if appraisal and appraisal.judgement:
        base = judgement_scores.get(appraisal.judgement, 5.0)
        confidence = appraisal.confidence
        # 신뢰도 낮을수록 중간값(5)으로 끌어당김
        score = base * (0.6 + 0.4 * confidence) + 5.0 * (1 - (0.6 + 0.4 * confidence))
        score = base + (5.0 - base) * (1 - confidence) * 0.4

        label = appraisal.judgement
        if label == "저평가":
            reasons.append(f"감정평가 결과 저평가 (신뢰도 {confidence:.0%})")
        elif label == "적정":
            reasons.append(f"감정평가 결과 적정가 수준 (신뢰도 {confidence:.0%})")
        elif label == "소폭 고평가":
            risks.append(f"감정평가 결과 소폭 고평가 (신뢰도 {confidence:.0%})")
        else:
            risks.append(f"감정평가 결과 고평가 — 추정가 대비 호가 과다 (신뢰도 {confidence:.0%})")
    else:
        score = 5.0

    # 예산 범위 적합도 보정
    price = listing.asking_price
    if query.budget_max is not None and price > query.budget_max:
        over_pct = (price - query.budget_max) / query.budget_max * 100
        score -= 1.5
        risks.append(f"호가가 최대 예산 초과 ({over_pct:.0f}%)")
    elif query.budget_min is not None and query.budget_max is not None:
        if query.budget_min <= price <= query.budget_max:
            score += 0.5
            reasons.append("호가가 희망 예산 범위 내")
    elif query.budget_max is not None and price <= query.budget_max:
        score += 0.3
        reasons.append("호가가 최대 예산 이내")

    return max(0.0, min(10.0, score)), reasons, risks


# ─────────────────────────────────────────
#  location_score  (0-10)
# ─────────────────────────────────────────

def _score_location(
    listing: PropertyListing,
    query: PropertyQuery,
) -> tuple[float, list[str], list[str]]:
    """입지 점수. (score, reasons, risks)"""
    reasons: list[str] = []
    risks:   list[str] = []

    # 역세권 (0-5점)
    sd = listing.station_distance_m
    if sd is None:
        station_pts = 0.5
    elif sd <= 200:
        station_pts = 5.0
        reasons.append(f"초역세권 (지하철 {sd}m)")
    elif sd <= 400:
        station_pts = 4.0
        reasons.append(f"역세권 (지하철 {sd}m)")
    elif sd <= 600:
        station_pts = 3.0
        reasons.append(f"역 도보권 (지하철 {sd}m)")
    elif sd <= 800:
        station_pts = 2.0
    elif sd <= 1200:
        station_pts = 1.0
        risks.append(f"지하철 원거리 ({sd}m)")
    else:
        station_pts = 0.5
        risks.append(f"지하철 매우 원거리 ({sd}m)")

    # 학교 접근성 (0-2점, 주거용만 가산)
    is_residential = listing.property_type == "주거용"
    sc = listing.school_distance_m
    if not is_residential:
        school_pts = 1.0
    elif sc is None:
        school_pts = 0.5
    elif sc <= 300:
        school_pts = 2.0
        reasons.append(f"학교 인접 ({sc}m)")
    elif sc <= 600:
        school_pts = 1.5
    elif sc <= 1000:
        school_pts = 1.0
    else:
        school_pts = 0.5
        if is_residential:
            risks.append(f"학교 원거리 ({sc}m)")

    # 건축연도 신축성 (0-2점)
    by = listing.built_year
    if by is None:
        year_pts = 0.3
    elif by >= 2020:
        year_pts = 2.0
        reasons.append(f"{by}년 신축")
    elif by >= 2015:
        year_pts = 1.5
        reasons.append(f"{by}년 준공 (비교적 신축)")
    elif by >= 2010:
        year_pts = 1.2
    elif by >= 2005:
        year_pts = 1.0
    elif by >= 2000:
        year_pts = 0.7
    elif by >= 1990:
        year_pts = 0.5
        risks.append(f"{by}년 준공 구축")
    else:
        year_pts = 0.3
        risks.append(f"{by}년 준공 노후 건물")

    # 층수 (0-1점)
    fl = listing.floor
    if fl is None:
        floor_pts = 0.5
    elif fl >= 10:
        floor_pts = 1.0
        reasons.append(f"{fl}층 (조망·일조 양호)")
    elif fl >= 5:
        floor_pts = 0.7
    else:
        floor_pts = 0.5

    score = station_pts + school_pts + year_pts + floor_pts
    return max(0.0, min(10.0, score)), reasons, risks


# ─────────────────────────────────────────
#  investment_score  (0-10)
# ─────────────────────────────────────────

def _score_investment(
    listing: PropertyListing,
    appraisal: Optional[AppraisalResult],
) -> tuple[float, list[str], list[str]]:
    """투자 가치 점수. (score, reasons, risks)"""
    reasons: list[str] = []
    risks:   list[str] = []

    # 전세가율 기반 기본 점수 (주거용)
    jp = listing.jeonse_price
    ap = listing.asking_price

    if jp and ap and ap > 0:
        ratio = jp / ap
        if ratio >= 0.75:
            base = 8.5
            reasons.append(f"전세가율 {ratio:.0%} — 갭투자 메리트 높음")
        elif ratio >= 0.65:
            base = 7.5
            reasons.append(f"전세가율 {ratio:.0%} — 투자 양호")
        elif ratio >= 0.55:
            base = 6.0
        elif ratio >= 0.45:
            base = 5.0
        elif ratio >= 0.35:
            base = 4.0
            risks.append(f"전세가율 {ratio:.0%} — 갭 부담")
        else:
            base = 2.5
            risks.append(f"전세가율 {ratio:.0%} — 갭 매우 큼")
    else:
        # 상업용 등 전세 없는 경우
        base = 5.0

    # 저평가 여부 보정 (gap_rate: 음수 = 저평가)
    gap_adj = 0.0
    if appraisal and appraisal.gap_rate is not None:
        gr = appraisal.gap_rate
        if gr < -0.10:
            gap_adj = 2.0
            reasons.append(f"시세 대비 {abs(gr):.0%} 저평가 — 상승 여력")
        elif gr < -0.05:
            gap_adj = 1.0
            reasons.append(f"시세 대비 소폭 저평가 ({abs(gr):.0%})")
        elif gr < 0.05:
            gap_adj = 0.0
        elif gr < 0.15:
            gap_adj = -1.0
            risks.append(f"시세 대비 {gr:.0%} 고평가 — 상승 여력 제한")
        else:
            gap_adj = -2.0
            risks.append(f"시세 대비 {gr:.0%} 고평가 — 조정 위험")

    score = base + gap_adj
    return max(0.0, min(10.0, score)), reasons, risks


# ─────────────────────────────────────────
#  risk_score  (0-10, 높을수록 위험)
# ─────────────────────────────────────────

def _score_risk(
    listing: PropertyListing,
    appraisal: Optional[AppraisalResult],
) -> tuple[float, list[str], list[str]]:
    """위험도 점수. (score, reasons, risks) — 높을수록 위험"""
    reasons: list[str] = []
    risks:   list[str] = []

    # 건물 노후화 위험
    by = listing.built_year
    if by is None:
        age_risk = 2.0
    else:
        age = _CURRENT_YEAR - by
        if age <= 3:
            age_risk = 0.0
            reasons.append(f"준공 {age}년 이내 신축 — 구조 리스크 낮음")
        elif age <= 8:
            age_risk = 0.5
        elif age <= 15:
            age_risk = 1.0
        elif age <= 25:
            age_risk = 2.0
        elif age <= 35:
            age_risk = 3.5
            risks.append(f"준공 {age}년 노후 건물 — 수선·하자 위험")
        else:
            age_risk = 5.0
            risks.append(f"준공 {age}년 초노후 건물 — 재건축 여부 확인 필요")

    # 감정평가 신뢰도 위험
    if appraisal is None:
        conf_risk = 1.5
        risks.append("감정평가 데이터 미제공 — 가격 신뢰도 불명")
    else:
        conf = appraisal.confidence
        if conf < 0.3:
            conf_risk = 3.0
            risks.append(f"감정평가 신뢰도 낮음 ({conf:.0%}) — 비교 사례 부족")
        elif conf < 0.5:
            conf_risk = 1.5
            risks.append(f"감정평가 신뢰도 보통 ({conf:.0%})")
        elif conf < 0.7:
            conf_risk = 0.5
        else:
            conf_risk = 0.0

    # 경고 메시지 페널티
    warning_count = len(appraisal.warnings) if appraisal else 0
    warn_risk = min(warning_count * 0.5, 2.0)
    if warning_count >= 2:
        risks.append(f"감정평가 주의사항 {warning_count}건")

    # 고평가 리스크
    overval_risk = 0.0
    if appraisal and appraisal.judgement:
        if appraisal.judgement == "고평가":
            overval_risk = 2.0
        elif appraisal.judgement == "소폭 고평가":
            overval_risk = 1.0

    score = age_risk + conf_risk + warn_risk + overval_risk
    return max(0.0, min(10.0, score)), reasons, risks


# ─────────────────────────────────────────
#  합산 및 레이블
# ─────────────────────────────────────────

def _calc_total_score(
    price: float,
    location: float,
    investment: float,
    risk: float,
) -> float:
    raw = price * 0.35 + location * 0.30 + investment * 0.20 + (10.0 - risk) * 0.15
    return round(max(0.0, min(10.0, raw)), 2)


def _recommendation_label(total: float) -> str:
    if total >= 8.0:
        return "적극 추천"
    if total >= 6.5:
        return "추천"
    if total >= 5.0:
        return "검토 필요"
    return "비추천"


# ─────────────────────────────────────────
#  공개 인터페이스
# ─────────────────────────────────────────

def calculate_listing_score(
    listing: PropertyListing,
    query: PropertyQuery,
    appraisal: Optional[AppraisalResult] = None,
) -> dict:
    """
    매물 종합 점수 산출.

    반환 dict:
      total_score         float 0-10
      price_score         float 0-10
      location_score      float 0-10
      investment_score    float 0-10
      risk_score          float 0-10  (높을수록 위험)
      recommendation_label str
      reasons             list[str]
      risks               list[str]
    """
    price_score,      p_reasons, p_risks = _score_price(listing, query, appraisal)
    location_score,   l_reasons, l_risks = _score_location(listing, query)
    investment_score, i_reasons, i_risks = _score_investment(listing, appraisal)
    risk_score,       r_reasons, r_risks = _score_risk(listing, appraisal)

    total_score = _calc_total_score(price_score, location_score, investment_score, risk_score)

    reasons = p_reasons + l_reasons + i_reasons + r_reasons
    risks   = p_risks   + l_risks   + i_risks   + r_risks

    return {
        "total_score":          round(total_score, 2),
        "price_score":          round(price_score, 2),
        "location_score":       round(location_score, 2),
        "investment_score":     round(investment_score, 2),
        "risk_score":           round(risk_score, 2),
        "recommendation_label": _recommendation_label(total_score),
        "reasons":              reasons,
        "risks":                risks,
    }
