"""
price_analysis_service.py — 가격 분석 서비스 v1.0

기존 price_engine 함수들을 재사용해 PropertyQuery → AppraisalResult 흐름을 제공.
LangGraph 파이프라인(NLP→지오코딩→에이전트)을 거치지 않는 직접 호출 경로.

사용 대상:
  - 매물 추천 (recommendation_graph): 후보 매물 일괄 가격 분석
  - 매물 비교 (comparison): 두 매물 나란히 분석
  - 빠른 가격 조회: NLP 파싱이 이미 끝난 상태에서 숫자만 필요할 때

단위 주의:
  price_engine 내부 — 만원 (int)
  schemas (PropertyQuery / AppraisalResult) — 원 (int)
  변환은 이 파일의 _to_won() / _to_manwon() 에서만 수행한다.
"""

from __future__ import annotations

import sys
import os

# backend/ 를 경로에 추가 (schemas/ 는 프로젝트 루트에 위치)
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in [_BACKEND_DIR, _PROJECT_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from schemas.appraisal_result import AppraisalResult, ComparableTransaction
from schemas.property_query import PropertyQuery
from price_engine import (
    calc_estimated_value,
    calc_valuation_verdict,
    fetch_real_transaction_prices,
)


# ─────────────────────────────────────────
#  단위 변환
# ─────────────────────────────────────────

def _to_won(manwon: int | None) -> int | None:
    """만원 → 원"""
    if manwon is None or manwon == 0:
        return None
    return manwon * 10_000


def _to_manwon(won: int | None) -> int | None:
    """원 → 만원"""
    if won is None or won == 0:
        return None
    return won // 10_000


# ─────────────────────────────────────────
#  ComparableTransaction 변환
# ─────────────────────────────────────────

def _to_comparables(
    price_data: dict,
    apt_name_matched: str,
) -> list[ComparableTransaction]:
    samples = price_data.get("samples", [])
    if not samples:
        return []

    result = []
    for s in samples:
        # match_level 결정
        if apt_name_matched and s.get("apt_name") == apt_name_matched:
            match_level = "same_complex"
        elif s.get("dong"):
            match_level = "same_dong"
        else:
            match_level = "same_gu"

        # 거래일 조합 (YYYY-MM)
        deal_date = None
        if s.get("deal_year") and s.get("deal_month"):
            deal_date = f"{s['deal_year']}-{int(s['deal_month']):02d}"

        result.append(ComparableTransaction(
            complex_name  = s.get("apt_name") or None,
            address       = s.get("dong") or None,
            area_m2       = s.get("area_sqm") or None,
            deal_price    = _to_won(s.get("price")),
            deal_date     = deal_date,
            price_per_m2  = _to_won(s.get("per_sqm")),
            source        = "국토부 실거래가",
            match_level   = match_level,
        ))
    return result


# ─────────────────────────────────────────
#  신뢰도 계산
# ─────────────────────────────────────────

def _calc_confidence(price_data: dict) -> float:
    """
    실거래 건수와 데이터 출처를 기반으로 신뢰도 산출.

    기준:
      건수 20+       → 0.90
      건수 10~19     → 0.80
      건수 5~9       → 0.65
      건수 2~4       → 0.45
      건수 1         → 0.30
      건수 0 or 오류 → 0.10
    폴백 출처(공시가격·수익환원법·원가법) 사용 시 최대 0.40으로 제한.
    """
    if price_data.get("error") or price_data.get("avg", 0) == 0:
        return 0.10

    count  = price_data.get("count", 0)
    source = price_data.get("source", "")

    if count >= 20:   base = 0.90
    elif count >= 10: base = 0.80
    elif count >= 5:  base = 0.65
    elif count >= 2:  base = 0.45
    elif count == 1:  base = 0.30
    else:             base = 0.10

    # 폴백 출처 패널티
    fallback_keywords = ["공시가격", "수익환원법", "원가법", "공시지가"]
    if any(kw in source for kw in fallback_keywords):
        base = min(base, 0.40)

    return round(base, 2)


# ─────────────────────────────────────────
#  경고 메시지 수집
# ─────────────────────────────────────────

def _collect_warnings(price_data: dict, area_m2: float | None) -> list[str]:
    warnings = []

    count = price_data.get("count", 0)
    if count == 0:
        warnings.append("실거래 데이터 없음 — 추정가 신뢰도 낮음")
    elif count < 5:
        warnings.append(f"실거래 {count}건 미만 — 표본 부족")

    source = price_data.get("source", "")
    if "공시가격" in source:
        warnings.append("공시가격 역산 사용 (실거래 없음)")
    elif "수익환원법" in source:
        warnings.append("수익환원법 사용 (실거래 없음)")
    elif "원가법" in source:
        warnings.append("건축원가법 사용 (실거래 없음)")

    if not area_m2:
        warnings.append("면적 미입력 — 추정가는 지역 평균 기준")

    months = price_data.get("used_months", 0)
    if months and months > 3:
        warnings.append(f"최근 {months}개월 데이터 사용 (3개월 이내 실거래 없음)")

    return warnings


def _collect_sources(price_data: dict) -> list[str]:
    source = price_data.get("source", "")
    if source:
        return [source]
    if price_data.get("count", 0) > 0:
        return ["국토부 실거래가"]
    return []


# ─────────────────────────────────────────
#  공개 인터페이스
# ─────────────────────────────────────────

def analyze_price(query: PropertyQuery) -> AppraisalResult:
    """
    PropertyQuery를 받아 가격 분석 결과(AppraisalResult)를 반환.

    LangGraph 파이프라인을 거치지 않는 직접 호출 경로.
    query.region과 query.property_type이 있어야 실거래가를 조회할 수 있다.
    둘 다 없으면 빈 결과를 반환한다.

    Args:
        query: 구조화된 부동산 요청. region·property_type이 핵심 필드.

    Returns:
        AppraisalResult: 추정가·고저평가·비교사례·신뢰도 포함.
    """
    region        = query.region or ""
    property_type = query.property_type or "주거용"
    area_m2       = query.area_m2
    complex_name  = query.complex_name or ""

    # asking_price: 원 → 만원 변환
    asking_manwon = _to_manwon(query.asking_price)

    if not region:
        return AppraisalResult(
            judgement  = "분석 불가",
            confidence = 0.0,
            warnings   = ["region(지역) 정보 없음 — 실거래가 조회 불가"],
        )

    # ── 1. 실거래가 조회 ─────────────────────────────────────────────────
    price_data = fetch_real_transaction_prices(
        category        = property_type,
        region_2depth   = region,
        category_detail = property_type,
        apt_name        = complex_name,
    )

    apt_name_matched = price_data.get("apt_name_matched", "")

    # ── 2. 추정가 계산 (면적 있으면 단일가, 없으면 평균가) ──────────────
    val = calc_estimated_value(price_data, area_m2 or 0.0, property_type)

    # ── 3. 고저평가 판단 ─────────────────────────────────────────────────
    verd = calc_valuation_verdict(
        estimated_value = val["estimated_value"],
        price_data      = price_data,
        asking_price    = asking_manwon,
    )

    # ── 4. gap_rate: % → 소수 (예: 5.0 → 0.05) ─────────────────────────
    deviation_pct = verd.get("deviation_pct", 0.0)
    gap_rate      = round(deviation_pct / 100, 4) if deviation_pct else None

    # ── 5. 조립 및 반환 ──────────────────────────────────────────────────
    return AppraisalResult(
        estimated_price = _to_won(val["estimated_value"]),
        low_price       = _to_won(val["value_min"]),
        high_price      = _to_won(val["value_max"]),
        asking_price    = query.asking_price,
        gap_rate        = gap_rate,
        judgement       = verd.get("valuation_verdict", ""),
        confidence      = _calc_confidence(price_data),
        comparables     = _to_comparables(price_data, apt_name_matched),
        warnings        = _collect_warnings(price_data, area_m2),
        data_source     = _collect_sources(price_data),
        raw             = {**val, **verd, "price_data_count": price_data.get("count", 0)},
    )
