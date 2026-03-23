"""
agents.py — 5개 전문 에이전트 v2.1
개선:
  - import re를 파일 최상단으로 이동 (함수 내 반복 import 제거)
  - _print_result()를 로깅 레벨로 정리
  - 각 에이전트 예외 처리 추가 — 에이전트 실패 시 빈 결과 반환
"""

from __future__ import annotations

import re

from analysis_tools import (
    ValuationResult,
    calc_estimated_value,
    calc_investment_return,
    calc_valuation_verdict,
    fetch_real_transaction_prices,
    generate_appraisal_opinion,
    search_nearby_facilities,
    search_web_tavily,
    _intent_summary,
)


# ─────────────────────────────────────────
#  공통 헬퍼
# ─────────────────────────────────────────

def _extract_context(state: dict):
    intent   = state.get("intent")
    geo      = state.get("geocoding_result") or {}
    region   = geo.get("region_2depth", "") if isinstance(geo, dict) else getattr(geo, "region_2depth", "")
    region3  = geo.get("region_3depth", "") if isinstance(geo, dict) else getattr(geo, "region_3depth", "")
    return intent, geo, region, region3


def _geo_coords(geo) -> tuple[float, float]:
    if isinstance(geo, dict):
        return geo.get("lat", 0.0), geo.get("lng", 0.0)
    return getattr(geo, "lat", 0.0), getattr(geo, "lng", 0.0)


def _save_result(state: dict, result: ValuationResult) -> dict:
    state["analysis_result"] = result.model_dump()
    return state


def _get_area_sqm(intent) -> float:
    area_min = getattr(intent, "area_min", None) or 0.0
    area_max = getattr(intent, "area_max", None) or 0.0
    if area_min and area_max:
        return (area_min + area_max) / 2
    return area_min or area_max or 0.0


def _get_asking_price(intent) -> int:
    return getattr(intent, "price_max", None) or getattr(intent, "price_min", None) or 0


# 단지명에서 제거할 접미사 목록
_BUILDING_SUFFIXES = ["아파트", "빌라", "오피스텔", "주상복합", "타운", "빌딩", "타워"]

def _get_building_name(state: dict) -> str:
    """
    building_name 에서 불필요한 접미사 제거.
    예) "래미안원베일리아파트" → "래미안원베일리"
        "마포래미안푸르지오아파트" → "마포래미안푸르지오"
    """
    name = state.get("building_name", "").strip()
    for suffix in _BUILDING_SUFFIXES:
        if name.endswith(suffix):
            name = name[:-len(suffix)].strip()
            break
    return name


def _print_result(result: ValuationResult):
    print(f"\n  ┌─ 감정평가 결과 ({result.agent_name}) ─────────────────")
    print(f"  │ 추정 시장가치 : {result.estimated_value:>10,}만원")
    print(f"  │ 가치 범위     : {result.value_min:,} ~ {result.value_max:,}만원")
    print(f"  │ 평당가        : {result.price_per_pyeong:,}만원/평  (지역평균: {result.regional_avg_per_pyeong:,}만원/평)")
    print(f"  │ 고저평가      : {result.valuation_verdict} ({result.deviation_pct:+.1f}%)")
    print(f"  │ 비교사례      : {result.comparable_count}건 평균 {result.comparable_avg:,}만원")
    print(f"  │ Cap Rate      : {result.cap_rate}%  |  연 수입 추정: {result.annual_income:,}만원")
    print(f"  │ 투자등급      : {result.investment_grade}")
    print(f"  │ 추천          : {result.recommendation}")
    print(f"  └─────────────────────────────────────────────────")


def _empty_result(agent_name: str, error_msg: str) -> ValuationResult:
    """에이전트 실패 시 반환하는 빈 결과"""
    return ValuationResult(
        agent_name=agent_name,
        appraisal_opinion=f"감정평가 중 오류가 발생했습니다: {error_msg}",
        recommendation="재시도 필요",
    )


# ═══════════════════════════════════════════════════════════════
#  1. 주거용 에이전트 (아파트·빌라·오피스텔)
# ═══════════════════════════════════════════════════════════════

def residential_agent(state: dict) -> dict:
    try:
        intent, geo, region, region3 = _extract_context(state)
        lat, lng   = _geo_coords(geo)
        location   = getattr(intent, "location_normalized", region)
        detail     = getattr(intent, "category_detail", "아파트")
        area_sqm   = _get_area_sqm(intent)
        asking     = _get_asking_price(intent)

        print(f"\n[주거용 에이전트] {location} / {detail} / {area_sqm}㎡")

        building_name = _get_building_name(state)
        price_data    = fetch_real_transaction_prices("주거용", region, detail, apt_name=building_name, region_3depth=region3)
        if building_name and price_data.get("apt_name_matched"):
            print(f"  → 단지 감정평가: {price_data['apt_name_matched']} ({price_data['count']}건)")
        elif building_name:
            print(f"  → 단지명 '{building_name}' 미발견 — 지역 평균으로 대체")

        val  = calc_estimated_value(price_data, area_sqm, "주거용")
        verd = calc_valuation_verdict(val["estimated_value"], price_data, asking)
        roi  = calc_investment_return(val["estimated_value"], "주거용", area_sqm)

        nearby = search_nearby_facilities(lat, lng,
            ["지하철역", "학교", "편의점", "마트", "병원"], radius=1000)

        subway_m = nearby.get("지하철역", {}).get("nearest_m", 9999)
        if subway_m <= 300:
            val["estimated_value"] = round(val["estimated_value"] * 1.05)
            val["value_max"]       = round(val["value_max"] * 1.05)
        elif subway_m > 1000:
            val["estimated_value"] = round(val["estimated_value"] * 0.97)

        web     = search_web_tavily(f"{location} 아파트 시세 매매 실거래가")
        llm_out = generate_appraisal_opinion("주거용", location, {**val, **verd, **roi}, nearby, web)

        result = ValuationResult(
            agent_name="주거용",
            valuation_method="비교사례법 (인근 실거래 평균)",
            price_avg=price_data["avg"], price_min=price_data["min"],
            price_max=price_data["max"], price_sample_count=price_data["count"],
            nearby_facilities=nearby, web_summary=web,
            **val, **verd, **roi,
            appraisal_opinion=llm_out.get("appraisal_opinion", ""),
            strengths=llm_out.get("strengths", []),
            risk_factors=llm_out.get("risk_factors", []),
            recommendation=llm_out.get("recommendation", ""),
        )
        _print_result(result)
        return _save_result(state, result)

    except Exception as e:
        print(f"[주거용 에이전트] 오류: {e}")
        return _save_result(state, _empty_result("주거용", str(e)))


# ═══════════════════════════════════════════════════════════════
#  2. 상업용 에이전트 (상가)
# ═══════════════════════════════════════════════════════════════

def commercial_agent(state: dict) -> dict:
    try:
        intent, geo, region, region3 = _extract_context(state)
        lat, lng   = _geo_coords(geo)
        location   = getattr(intent, "location_normalized", region)
        area_sqm   = _get_area_sqm(intent)
        asking     = _get_asking_price(intent)

        print(f"\n[상업용 에이전트] {location} / 상가 / {area_sqm}㎡")

        building_name = _get_building_name(state)
        price_data    = fetch_real_transaction_prices("상업용", region, "상가", apt_name=building_name, region_3depth=region3)

        val  = calc_estimated_value(price_data, area_sqm, "상업용")
        verd = calc_valuation_verdict(val["estimated_value"], price_data, asking)
        roi  = calc_investment_return(val["estimated_value"], "상업용", area_sqm)

        nearby = search_nearby_facilities(lat, lng,
            ["음식점", "카페", "지하철역", "주차장", "은행"], radius=500)

        food_count = (nearby.get("음식점", {}).get("count", 0) +
                      nearby.get("카페", {}).get("count", 0))
        if food_count >= 15:
            roi["cap_rate"] = min(roi["cap_rate"] + 0.5, 8.0)
        elif food_count <= 3:
            roi["cap_rate"] = max(roi["cap_rate"] - 0.5, 2.0)

        web     = search_web_tavily(f"{location} 상가 매매 실거래 시세 공실률")
        llm_out = generate_appraisal_opinion("상업용", location, {**val, **verd, **roi}, nearby, web)

        result = ValuationResult(
            agent_name="상업용",
            valuation_method="수익환원법 + 비교사례법",
            price_avg=price_data["avg"], price_min=price_data["min"],
            price_max=price_data["max"], price_sample_count=price_data["count"],
            nearby_facilities=nearby, web_summary=web,
            **val, **verd, **roi,
            appraisal_opinion=llm_out.get("appraisal_opinion", ""),
            strengths=llm_out.get("strengths", []),
            risk_factors=llm_out.get("risk_factors", []),
            recommendation=llm_out.get("recommendation", ""),
        )
        _print_result(result)
        return _save_result(state, result)

    except Exception as e:
        print(f"[상업용 에이전트] 오류: {e}")
        return _save_result(state, _empty_result("상업용", str(e)))


# ═══════════════════════════════════════════════════════════════
#  3. 업무용 에이전트 (오피스)
# ═══════════════════════════════════════════════════════════════

def office_agent(state: dict) -> dict:
    try:
        intent, geo, region, region3 = _extract_context(state)
        lat, lng   = _geo_coords(geo)
        location   = getattr(intent, "location_normalized", region)
        area_sqm   = _get_area_sqm(intent)
        asking     = _get_asking_price(intent)

        print(f"\n[업무용 에이전트] {location} / 사무실 / {area_sqm}㎡")

        building_name = _get_building_name(state)
        price_data    = fetch_real_transaction_prices("업무용", region, "사무실", apt_name=building_name, region_3depth=region3)

        val  = calc_estimated_value(price_data, area_sqm, "업무용")
        verd = calc_valuation_verdict(val["estimated_value"], price_data, asking)
        roi  = calc_investment_return(val["estimated_value"], "업무용", area_sqm)

        avg = price_data.get("avg", 0)
        if avg >= 50000:
            val["estimated_value"] = round(val["estimated_value"] * 1.08)
        elif avg < 20000:
            val["estimated_value"] = round(val["estimated_value"] * 0.95)

        nearby = search_nearby_facilities(lat, lng,
            ["지하철역", "주차장", "은행", "카페", "음식점"], radius=800)

        web     = search_web_tavily(f"{location} 오피스 사무실 매매 시세")
        llm_out = generate_appraisal_opinion("업무용", location, {**val, **verd, **roi}, nearby, web)

        result = ValuationResult(
            agent_name="업무용",
            valuation_method="비교사례법 + 오피스등급 보정",
            price_avg=price_data["avg"], price_min=price_data["min"],
            price_max=price_data["max"], price_sample_count=price_data["count"],
            nearby_facilities=nearby, web_summary=web,
            **val, **verd, **roi,
            appraisal_opinion=llm_out.get("appraisal_opinion", ""),
            strengths=llm_out.get("strengths", []),
            risk_factors=llm_out.get("risk_factors", []),
            recommendation=llm_out.get("recommendation", ""),
        )
        _print_result(result)
        return _save_result(state, result)

    except Exception as e:
        print(f"[업무용 에이전트] 오류: {e}")
        return _save_result(state, _empty_result("업무용", str(e)))


# ═══════════════════════════════════════════════════════════════
#  4. 산업용 에이전트 (공장·창고)
# ═══════════════════════════════════════════════════════════════

def industrial_agent(state: dict) -> dict:
    try:
        intent, geo, region, region3 = _extract_context(state)
        lat, lng   = _geo_coords(geo)
        location   = getattr(intent, "location_normalized", region)
        detail     = getattr(intent, "category_detail", "창고")
        area_sqm   = _get_area_sqm(intent)
        asking     = _get_asking_price(intent)
        special    = getattr(intent, "special_conditions", [])

        print(f"\n[산업용 에이전트] {location} / {detail} / {area_sqm}㎡")

        building_name = _get_building_name(state)
        price_data    = fetch_real_transaction_prices("산업용", region, detail, apt_name=building_name, region_3depth=region3)

        val  = calc_estimated_value(price_data, area_sqm, "산업용")
        verd = calc_valuation_verdict(val["estimated_value"], price_data, asking)
        roi  = calc_investment_return(val["estimated_value"], "산업용", area_sqm)

        # re 는 파일 최상단에서 import — 함수 내 재import 불필요
        cond_str     = " ".join(special)
        height_match = re.search(r"층고\s*(\d+)", cond_str)
        if height_match:
            height = int(height_match.group(1))
            if height >= 10:
                val["estimated_value"] = round(val["estimated_value"] * 1.12)
            elif height >= 6:
                val["estimated_value"] = round(val["estimated_value"] * 1.06)

        nearby = search_nearby_facilities(lat, lng,
            ["주차장", "편의점", "음식점"], radius=2000)

        web     = search_web_tavily(f"{location} 공장 창고 매매 시세 물류")
        llm_out = generate_appraisal_opinion("산업용", location, {**val, **verd, **roi}, nearby, web)

        result = ValuationResult(
            agent_name="산업용",
            valuation_method="비교사례법 + 물류인프라 보정",
            price_avg=price_data["avg"], price_min=price_data["min"],
            price_max=price_data["max"], price_sample_count=price_data["count"],
            nearby_facilities=nearby, web_summary=web,
            **val, **verd, **roi,
            appraisal_opinion=llm_out.get("appraisal_opinion", ""),
            strengths=llm_out.get("strengths", []),
            risk_factors=llm_out.get("risk_factors", []),
            recommendation=llm_out.get("recommendation", ""),
        )
        _print_result(result)
        return _save_result(state, result)

    except Exception as e:
        print(f"[산업용 에이전트] 오류: {e}")
        return _save_result(state, _empty_result("산업용", str(e)))


# ═══════════════════════════════════════════════════════════════
#  5. 토지 에이전트
# ═══════════════════════════════════════════════════════════════

LAND_USE_ZONE_TABLE = {
    "제1종전용주거지역":  {"건폐율": 50, "용적률": 100,  "보정계수": 1.0},
    "제2종전용주거지역":  {"건폐율": 50, "용적률": 150,  "보정계수": 1.1},
    "제1종일반주거지역":  {"건폐율": 60, "용적률": 200,  "보정계수": 1.2},
    "제2종일반주거지역":  {"건폐율": 60, "용적률": 250,  "보정계수": 1.3},
    "제3종일반주거지역":  {"건폐율": 50, "용적률": 300,  "보정계수": 1.4},
    "준주거지역":         {"건폐율": 70, "용적률": 500,  "보정계수": 1.6},
    "근린상업지역":       {"건폐율": 70, "용적률": 900,  "보정계수": 2.0},
    "일반상업지역":       {"건폐율": 80, "용적률": 1300, "보정계수": 2.5},
    "중심상업지역":       {"건폐율": 90, "용적률": 1500, "보정계수": 3.0},
    "준공업지역":         {"건폐율": 70, "용적률": 400,  "보정계수": 1.5},
    "일반공업지역":       {"건폐율": 70, "용적률": 350,  "보정계수": 1.3},
    "자연녹지지역":       {"건폐율": 20, "용적률": 100,  "보정계수": 0.7},
    "생산녹지지역":       {"건폐율": 20, "용적률": 100,  "보정계수": 0.6},
    "보전녹지지역":       {"건폐율": 20, "용적률": 80,   "보정계수": 0.5},
}


def land_agent(state: dict) -> dict:
    try:
        intent, geo, region, region3 = _extract_context(state)
        lat, lng   = _geo_coords(geo)
        location   = getattr(intent, "location_normalized", region)
        area_sqm   = _get_area_sqm(intent)
        asking     = _get_asking_price(intent)

        geo_dict       = geo if isinstance(geo, dict) else {}
        land_use_zone  = geo_dict.get("land_use_zone", "")
        official_price = geo_dict.get("official_land_price", 0)
        zone_info      = LAND_USE_ZONE_TABLE.get(land_use_zone, {})
        correction     = zone_info.get("보정계수", 1.0)

        print(f"\n[토지 에이전트] {location} / {land_use_zone or '용도지역 미확인'} / {area_sqm}㎡")

        building_name = _get_building_name(state)
        price_data    = fetch_real_transaction_prices("토지", region, "토지", apt_name=building_name, region_3depth=region3)

        val = calc_estimated_value(price_data, area_sqm, "토지")
        if official_price > 0 and area_sqm > 0:
            official_total = round(official_price * area_sqm / 10000)
            corrected      = round(official_total * correction)
            val["estimated_value"] = max(val["estimated_value"], corrected)
            val["value_min"]  = round(val["estimated_value"] * 0.88)
            val["value_max"]  = round(val["estimated_value"] * 1.12)

        verd = calc_valuation_verdict(val["estimated_value"], price_data, asking)
        roi  = calc_investment_return(val["estimated_value"], "토지", area_sqm)

        web          = search_web_tavily(f"{location} 토지 개발 호재 지가 상승 GTX 재개발")
        dev_keywords = ["GTX", "재개발", "재건축", "신도시", "도시개발", "산업단지"]
        dev_count    = sum(1 for k in dev_keywords if k in web)
        if dev_count >= 2:
            val["estimated_value"] = round(val["estimated_value"] * 1.10)
            print(f"  → 개발호재 {dev_count}개 감지 → 추정가 +10%")

        nearby  = search_nearby_facilities(lat, lng, ["지하철역", "편의점", "병원"], radius=3000)
        llm_out = generate_appraisal_opinion(
            "토지", location,
            {**val, **verd, **roi,
             "용도지역": land_use_zone,
             "건폐율": zone_info.get("건폐율", 0),
             "용적률": zone_info.get("용적률", 0),
             "공시지가(원/㎡)": official_price},
            nearby, web,
        )

        result = ValuationResult(
            agent_name="토지",
            valuation_method="공시지가×보정계수 + 개발호재 프리미엄",
            price_avg=price_data["avg"], price_min=price_data["min"],
            price_max=price_data["max"], price_sample_count=price_data["count"],
            nearby_facilities=nearby, web_summary=web,
            **val, **verd, **roi,
            appraisal_opinion=llm_out.get("appraisal_opinion", ""),
            strengths=llm_out.get("strengths", []),
            risk_factors=llm_out.get("risk_factors", []),
            recommendation=llm_out.get("recommendation", ""),
        )
        _print_result(result)
        return _save_result(state, result)

    except Exception as e:
        print(f"[토지 에이전트] 오류: {e}")
        return _save_result(state, _empty_result("토지", str(e)))