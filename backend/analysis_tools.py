"""
analysis_tools.py — 공통 분석 도구 v2.3
개선:
  - 더미 데이터 완전 제거
  - API 실패 시 빈 결과 반환 + 명확한 오류 메시지
  - 현재 날짜 기준 최근 3개월 자동 조회
"""

from __future__ import annotations

import json
import os
import re
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime
from typing import Optional

import requests
from dotenv import load_dotenv, find_dotenv
from langchain_ollama import ChatOllama
from pydantic import BaseModel, Field

load_dotenv(find_dotenv())

KAKAO_API_KEY  = os.getenv("KAKAO_REST_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")
MOLIT_API_KEY  = os.getenv("MOLIT_API_KEY", "")

if not MOLIT_API_KEY:
    print("[analysis_tools] ⚠️  MOLIT_API_KEY 없음 → 실거래가 조회 불가")
if not KAKAO_API_KEY:
    print("[analysis_tools] ⚠️  KAKAO_REST_API_KEY 없음 → 주변시설 조회 불가")


# ─────────────────────────────────────────
#  1. 감정평가 결과 모델
# ─────────────────────────────────────────

class ValuationResult(BaseModel):
    agent_name: str

    estimated_value: int         = Field(default=0)
    value_min: int               = Field(default=0)
    value_max: int               = Field(default=0)
    value_unit: str              = Field(default="만원")
    valuation_method: str        = Field(default="")

    price_per_pyeong: int        = Field(default=0)
    area_pyeong: float           = Field(default=0.0)
    regional_avg_per_pyeong: int = Field(default=0)
    price_per_sqm: int           = Field(default=0)

    comparable_avg: int          = Field(default=0)
    comparable_count: int        = Field(default=0)
    deviation_pct: float         = Field(default=0.0)
    valuation_verdict: str       = Field(default="")
    comparables: list[dict]      = Field(default_factory=list)

    cap_rate: float              = Field(default=0.0)
    annual_income: int           = Field(default=0)
    roi_5yr: float               = Field(default=0.0)
    investment_grade: str        = Field(default="")

    price_avg: int               = Field(default=0)
    price_min: int               = Field(default=0)
    price_max: int               = Field(default=0)
    price_sample_count: int      = Field(default=0)

    nearby_facilities: dict      = Field(default_factory=dict)
    web_summary: str             = Field(default="")

    appraisal_opinion: str       = Field(default="")
    strengths: list[str]         = Field(default_factory=list)
    risk_factors: list[str]      = Field(default_factory=list)
    recommendation: str          = Field(default="")

    # 실거래가 조회 실패 시 오류 메시지
    price_error: str             = Field(default="")


# ─────────────────────────────────────────
#  2. 빈 실거래가 결과 (더미 없음)
# ─────────────────────────────────────────

def _empty_price_data(reason: str = "") -> dict:
    """
    실거래가 조회 실패 시 반환하는 빈 결과.
    더미 숫자 없이 0으로만 채움 → UI에서 '데이터 없음'으로 표시.
    """
    if reason:
        print(f"[molit] ❌ 실거래가 조회 실패 — {reason}")
    return {
        "avg":              0,
        "min":              0,
        "max":              0,
        "count":            0,
        "per_sqm_avg":      0,
        "samples":          [],
        "apt_name_matched": "",
        "error":            reason,
    }


# ─────────────────────────────────────────
#  3. 현재 날짜 기준 조회 월 목록
# ─────────────────────────────────────────

def _get_recent_deal_ymds(months: int = 3) -> list[str]:
    """
    현재 날짜 기준 최근 n개월 YYYYMM 목록 반환.
    국토부 API는 해당 월 데이터가 다음 달 중순 등록 → 안전하게 3개월 조회.
    예) 2026년 3월 → ["202601", "202602", "202603"]
    """
    now    = datetime.now()
    result = []
    for i in range(months - 1, -1, -1):
        year  = now.year
        month = now.month - i
        while month <= 0:
            month += 12
            year  -= 1
        result.append(f"{year}{month:02d}")
    return result


# ─────────────────────────────────────────
#  4. 공동주택 공시가격 API (실거래가 폴백)
# ─────────────────────────────────────────

OFFICIAL_PRICE_URL = (
    "https://apis.data.go.kr/1613000"
    "/PblntfPublicWrtPrcInfo/getPblntfPublicWrtPrcInfo"
)

# 현실화율 (2024년 기준, 국토부 고시)
REALIZATION_RATE = {
    "아파트":     0.69,
    "오피스텔":   0.69,
    "연립다세대": 0.654,
    "단독다가구": 0.536,
}


def _fetch_by_official_price(
    lawd_code: str,
    apt_name: str,
    category_detail: str = "",
    area_sqm: float = 0.0,
) -> dict:
    """
    공동주택 공시가격 API 호출 → 현실화율 역산 → 추정 시세 반환.

    실거래가 없을 때만 호출되는 폴백 함수.
    반환 구조는 fetch_real_transaction_prices() 와 동일.
    """
    if not MOLIT_API_KEY:
        return _empty_price_data("MOLIT_API_KEY 없음 (공시가격 조회 불가)")

    safe_key  = MOLIT_API_KEY.replace("+", "%2B").replace("=", "%3D")
    this_year = datetime.now().year

    # 올해 없으면 전년도로 폴백 (공시가격은 매년 1월 기준 4~5월 공시)
    for year in [this_year, this_year - 1]:
        query = (
            f"serviceKey={safe_key}"
            f"&LAWD_CD={lawd_code}"
            f"&STDR_YEAR={year}"
            f"&numOfRows=100"
            f"&pageNo=1"
        )
        if apt_name:
            query += f"&BLDG_NM={apt_name}"

        try:
            res = requests.get(f"{OFFICIAL_PRICE_URL}?{query}", timeout=10)
            res.raise_for_status()
            root  = ET.fromstring(res.text)

            result_code = root.findtext(".//resultCode", "")
            if result_code.lstrip("0") not in ("", "0"):
                print(f"[official] API 오류: {result_code} - {root.findtext('.//resultMsg','')}")
                continue

            items = root.findall(".//item")
            print(f"[official] {year}년 공시가격: {len(items)}건")

            if not items:
                continue

            # 면적 필터 — area_sqm 입력 시 ±10㎡ 범위
            if area_sqm > 0:
                items = [
                    it for it in items
                    if abs(float(it.findtext("excluUseAr", "0") or 0) - area_sqm) <= 10
                ] or items  # 필터 후 0건이면 전체 사용

            prices = []
            for it in items:
                prc_text = it.findtext("pblntfPrc", "") or ""
                try:
                    prc = int(prc_text.replace(",", "").strip())
                    if prc > 0:
                        prices.append(prc)
                except ValueError:
                    pass

            if not prices:
                continue

            avg_official = sum(prices) // len(prices)
            rate         = REALIZATION_RATE.get(category_detail, 0.69)
            avg_est      = round(avg_official / rate)
            per_sqm_est  = round(avg_est / area_sqm) if area_sqm > 0 else 0

            print(f"[official] ✅ 공시가격 평균 {avg_official:,}만원 "
                  f"/ 현실화율 {rate:.1%} "
                  f"/ 추정 시세 {avg_est:,}만원")

            return {
                "avg":              avg_est,
                "min":              round(avg_est * 0.90),
                "max":              round(avg_est * 1.10),
                "count":            len(prices),
                "per_sqm_avg":      per_sqm_est,
                "samples":          [],
                "apt_name_matched": apt_name,
                "used_months":      0,
                "used_region":      "",
                "source":           f"공시가격 역산 ({year}년 기준, 현실화율 {rate:.1%})",
                "error":            "",
            }

        except requests.Timeout:
            print(f"[official] {year}년 타임아웃")
        except Exception as e:
            print(f"[official] {year}년 오류: {e}")

    return _empty_price_data("공시가격 조회 실패 (실거래·공시가격 모두 없음)")


# ─────────────────────────────────────────
#  5. 국토부 실거래가 API
# ─────────────────────────────────────────

MOLIT_BASE_URL = "https://apis.data.go.kr/1613000"

MOLIT_ENDPOINTS = {
    ("주거용", "아파트"):    "/RTMSDataSvcAptTrade/getRTMSDataSvcAptTrade",
    ("주거용", "연립다세대"): "/RTMSDataSvcRHTrade/getRTMSDataSvcRHTrade",
    ("주거용", "단독다가구"): "/RTMSDataSvcSHTrade/getRTMSDataSvcSHTrade",
    ("주거용", "오피스텔"):  "/RTMSDataSvcOffiTrade/getRTMSDataSvcOffiTrade",
    ("상업용", "상가"):      "/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade",
    ("업무용", "사무실"):    "/RTMSDataSvcNrgTrade/getRTMSDataSvcNrgTrade",
    ("산업용", "공장"):      "/RTMSDataSvcInduTrade/getRTMSDataSvcInduTrade",
    ("산업용", "창고"):      "/RTMSDataSvcInduTrade/getRTMSDataSvcInduTrade",
    ("토지",   "토지"):      "/RTMSDataSvcLandTrade/getRTMSDataSvcLandTrade",
}

# 국토부 API 응답 필드명 (영문 태그)
PRICE_FIELD_MAP = {
    "주거용": ["dealAmount"],
    "상업용": ["dealAmount"],
    "업무용": ["dealAmount"],
    "산업용": ["dealAmount"],
    "토지":   ["dealAmount"],
}

AREA_FIELD_MAP = {
    "주거용": ["excluUseAr"],
    "상업용": ["excluUseAr", "plottageAr"],
    "업무용": ["excluUseAr"],
    "산업용": ["buildingAr", "plottageAr"],   # buildingAr: 건물면적
    "토지":   ["plottageAr", "jimokAr"],
}


def _select_endpoint(category: str, category_detail: str) -> str:
    detail = category_detail.strip()
    if category == "주거용":
        if "오피스텔" in detail:          key = ("주거용", "오피스텔")
        elif any(k in detail for k in ["빌라", "연립", "다세대"]): key = ("주거용", "연립다세대")
        elif any(k in detail for k in ["단독", "다가구", "주택"]): key = ("주거용", "단독다가구")
        else:                             key = ("주거용", "아파트")
    elif category == "상업용": key = ("상업용", "상가")
    elif category == "업무용": key = ("업무용", "사무실")
    elif category == "산업용": key = ("산업용", "창고") if "창고" in detail else ("산업용", "공장")
    elif category == "토지":   key = ("토지", "토지")
    else:                      key = ("주거용", "아파트")
    return MOLIT_ENDPOINTS.get(key, MOLIT_ENDPOINTS[("주거용", "아파트")])


def get_lawd_code(region_2depth: str) -> str:
    from cache_db import get_lawd_code as _get
    return _get(region_2depth)


def _parse_items(items, category: str) -> list[dict]:
    price_fields = PRICE_FIELD_MAP.get(category, ["거래금액"])
    area_fields  = AREA_FIELD_MAP.get(category, ["전용면적"])
    result = []
    for item in items:
        price_val = 0
        for f in price_fields:
            el = item.find(f)
            if el is not None and el.text:
                try:
                    # dealAmount 는 "240,000" 형태 → 쉼표 제거 후 변환
                    price_val = int(el.text.replace(",", "").strip())
                    break
                except ValueError:
                    pass
        area_val = 0.0
        for f in area_fields:
            el = item.find(f)
            if el is not None and el.text:
                try:
                    area_val = float(el.text.strip())
                    break
                except ValueError:
                    pass
        if price_val <= 0:
            continue

        # 거래금액 쉼표 제거 (예: "240,000" → 240000)
        # price_val이 이미 int이면 그대로, 아니면 변환
        if isinstance(price_val, str):
            price_val = int(price_val.replace(",", "").strip())

        # 단지명: 주거용=aptNm, 산업용=건물용도+동명
        apt_nm = (item.findtext("aptNm", "")
                  or item.findtext("mhouseNm", "")
                  or item.findtext("buildNm", ""))
        if not apt_nm:
            # 산업용·상업용: 건물용도 + 동명 조합
            bldg_use = item.findtext("buildingUse", "")
            umd_nm   = item.findtext("umdNm", "")
            apt_nm   = f"{umd_nm} {bldg_use}".strip() if bldg_use else umd_nm

        result.append({
            "price":       price_val,
            "area_sqm":    area_val,
            "area_pyeong": round(area_val / 3.3058, 1) if area_val else 0,
            "per_sqm":     round(price_val / area_val) if area_val > 0 else 0,
            "floor":       item.findtext("floor", ""),
            "year_built":  item.findtext("buildYear", ""),
            "dong":        item.findtext("umdNm", ""),
            "apt_name":    apt_nm,
            "deal_year":   item.findtext("dealYear", ""),
            "deal_month":  item.findtext("dealMonth", ""),
        })
    return result


def _fetch_one_month(args: tuple) -> list:
    """단일 월 실거래가 조회 — 병렬 호출용"""
    url, safe_key, lawd_code, deal_ymd, category = args
    query_string = (
        f"serviceKey={safe_key}"
        f"&LAWD_CD={lawd_code}"
        f"&DEAL_YMD={deal_ymd}"
        f"&numOfRows=1000"   # 100 → 1000 (1회 호출로 더 많은 데이터)
        f"&pageNo=1"
    )
    full_url = f"{url}?{query_string}"
    try:
        res = requests.get(full_url, timeout=10)
        res.raise_for_status()
        root = ET.fromstring(res.text)

        result_code = root.findtext(".//resultCode", "")
        if result_code and result_code.lstrip("0") not in ("", "0"):
            result_msg = root.findtext(".//resultMsg", "")
            print(f"[molit] API 오류 ({deal_ymd}): {result_code} - {result_msg}")
            return []

        items  = root.findall(".//item")
        parsed = _parse_items(items, category)
        print(f"[molit] {deal_ymd}: {len(parsed)}건")
        return parsed

    except requests.Timeout:
        print(f"[molit] {deal_ymd} 타임아웃")
        return []
    except Exception as e:
        print(f"[molit] {deal_ymd} 오류: {e}")
        return []


def _fetch_by_ymds(url: str, safe_key: str, lawd_code: str,
                   deal_ymds: list, category: str) -> list:
    """
    병렬 호출로 여러 월 실거래가 동시 조회.
    ThreadPoolExecutor로 최대 6개 동시 요청.
    """
    from concurrent.futures import ThreadPoolExecutor

    args_list  = [(url, safe_key, lawd_code, ymd, category) for ymd in deal_ymds]
    all_parsed = []

    with ThreadPoolExecutor(max_workers=6) as executor:
        results = executor.map(_fetch_one_month, args_list)
        for parsed in results:
            all_parsed.extend(parsed)

    return all_parsed


def fetch_real_transaction_prices(
    category: str,
    region_2depth: str,
    category_detail: str = "",
    apt_name: str = "",
    region_3depth: str = "",   # 읍·면·동 — 동일 동 내로 결과 제한
) -> dict:
    """
    국토부 실거래가 API.

    조회 전략:
      1) 같은 구 + 같은 동(region_3depth) 필터링 — 3개월
      2) 같은 구 전체 — 3개월
      3) 같은 구 전체 — 6개월
      4) 인접 지역(구) — 6개월 (상업·업무·주거)
    """
    if not MOLIT_API_KEY:
        return _empty_price_data("MOLIT_API_KEY 미설정 — .env 파일을 확인하세요")

    lawd_code = get_lawd_code(region_2depth)
    if not lawd_code:
        return _empty_price_data(f"'{region_2depth}' 지역코드 없음 — cache_db 확인 필요")

    endpoint = _select_endpoint(category, category_detail)
    url      = MOLIT_BASE_URL + endpoint
    safe_key = MOLIT_API_KEY.replace("+", "%2B").replace("=", "%3D")

    all_parsed  = []
    used_months = 0
    used_region = region_2depth
    dong_filter = region_3depth.replace("동", "").replace("읍", "").replace("면", "").strip()
    apt_clean   = apt_name.strip() if apt_name else ""

    # ── 우선순위: 단지명 → 동 → 구 전체 ────────────────────────────────────
    #
    # 1순위: 단지명 매칭 (3 → 6개월)
    # 2순위: 동 필터링  (3 → 6개월)
    # 3순위: 구 전체    (3 → 6개월)

    # 단지명 접미사 제거 함수 (양쪽 비교 시 사용)
    _SUFFIXES = ["아파트", "빌라", "오피스텔", "주상복합", "타운", "빌딩", "타워"]
    def _strip_suffix(name: str) -> str:
        for s in _SUFFIXES:
            if name.endswith(s):
                return name[:-len(s)].strip()
        return name

    apt_clean_stripped = _strip_suffix(apt_clean)

    # ── 1단계: 단지명 매칭 (3 → 6 → 12개월) ───────────────────────────────
    # 정확 매칭 → 공백 제거 매칭 → 부분 매칭 순으로 시도
    apt_no_space = apt_clean_stripped.replace(" ", "")
    if apt_clean:
        for months in [3, 6, 12]:
            deal_ymds  = _get_recent_deal_ymds(months=months)
            print(f"[molit] 단지 조회: '{apt_clean_stripped}' / {months}개월")
            raw_parsed = _fetch_by_ymds(url, safe_key, lawd_code, deal_ymds, category)
            if not raw_parsed:
                print(f"[molit] '{apt_clean_stripped}' {months}개월 없음 → 기간 확장")
                continue

            # 디버그: 후보 단지명 출력
            actual_names = list(set(d["apt_name"] for d in raw_parsed))
            candidates   = [n for n in actual_names
                            if apt_no_space[:4] in n.replace(" ", "")]
            if candidates:
                print(f"[molit] 후보 단지명: {candidates[:5]}")

            # 1-1. 정확 매칭 (접미사 제거)
            exact = [d for d in raw_parsed
                     if _strip_suffix(d["apt_name"]) == apt_clean_stripped]
            if exact:
                all_parsed  = exact
                used_months = months
                print(f"[molit] ✅ 단지 정확 매칭: '{apt_clean_stripped}' {len(exact)}건 / {months}개월")
                break

            # 1-2. 공백 제거 후 매칭
            no_space = [d for d in raw_parsed
                        if _strip_suffix(d["apt_name"]).replace(" ", "") == apt_no_space]
            if no_space:
                top_name    = Counter(d["apt_name"] for d in no_space).most_common(1)[0][0]
                all_parsed  = no_space
                used_months = months
                print(f"[molit] ✅ 단지 공백제거 매칭: '{apt_clean_stripped}' → '{top_name}' {len(no_space)}건 / {months}개월")
                break

            # 1-3. 부분 매칭
            partial = [d for d in raw_parsed
                       if (apt_no_space in _strip_suffix(d["apt_name"]).replace(" ", "")
                           or _strip_suffix(d["apt_name"]).replace(" ", "") in apt_no_space)
                       and len(_strip_suffix(d["apt_name"]).replace(" ", "")) >= 3]
            if partial:
                top_name    = Counter(d["apt_name"] for d in partial).most_common(1)[0][0]
                matched     = [d for d in partial if d["apt_name"] == top_name]
                all_parsed  = matched
                used_months = months
                print(f"[molit] ✅ 단지 부분 매칭: '{apt_clean_stripped}' → '{top_name}' {len(matched)}건 / {months}개월")
                break

            # 디버그: 실제 단지명 목록 출력 (매칭 실패 원인 파악)
            if raw_parsed:
                actual_names = list(set(d["apt_name"] for d in raw_parsed[:20]))
                candidates = [n for n in actual_names
                              if any(c in n.replace(" ","") for c in apt_no_space[:4])]
                if candidates:
                    print(f"[molit] 후보 단지명: {candidates[:5]}")
            print(f"[molit] '{apt_clean_stripped}' {months}개월 없음 → 기간 확장")

    # ── 2단계: 단지 없으면 동 필터링 (3 → 6개월) ───────────────────────────
    if not all_parsed and dong_filter:
        for months in [3, 6]:
            deal_ymds  = _get_recent_deal_ymds(months=months)
            print(f"[molit] 동 조회: '{dong_filter}동' / {months}개월")
            raw_parsed = _fetch_by_ymds(url, safe_key, lawd_code, deal_ymds, category)
            if raw_parsed:
                dong_filtered = [d for d in raw_parsed if dong_filter in d.get("dong", "")]
                if dong_filtered:
                    all_parsed  = dong_filtered
                    used_months = months
                    print(f"[molit] ✅ 동 필터링: '{dong_filter}동' {len(dong_filtered)}건 / {months}개월")
                    break
            print(f"[molit] '{dong_filter}동' {months}개월 없음 → 기간 확장")

    # ── 3단계: 동도 없으면 구 전체 (3 → 6개월) ─────────────────────────────
    if not all_parsed:
        for months in [3, 6]:
            deal_ymds  = _get_recent_deal_ymds(months=months)
            print(f"[molit] 구 전체 조회: {region_2depth} / {months}개월")
            raw_parsed = _fetch_by_ymds(url, safe_key, lawd_code, deal_ymds, category)
            if raw_parsed:
                all_parsed  = raw_parsed
                used_months = months
                print(f"[molit] ✅ 구 전체: {len(raw_parsed)}건 / {months}개월")
                break
            print(f"[molit] {months}개월 데이터 없음 → 기간 확장")

    # ── 실거래 없음 → 공시가격 폴백 (주거용만, 산업용·토지 제외) ─────────────
    if not all_parsed:
        if category == "주거용":
            print(f"[molit] 실거래 없음 → 공시가격 폴백 시도")
            return _fetch_by_official_price(
                lawd_code      = lawd_code,
                apt_name       = apt_clean,
                category_detail= category_detail,
                area_sqm       = 0.0,
            )
        return _empty_price_data("최근 6개월 실거래 데이터 없음")

    # ── 결과 집계 ─────────────────────────────────────────────────────────
    apt_name_matched = all_parsed[0].get("apt_name", "") if apt_clean else ""
    filtered         = all_parsed

    prices = [d["price"] for d in filtered if d["price"] > 0]
    areas  = [d["area_sqm"] for d in filtered if d["area_sqm"] > 0]

    if not prices:
        return _empty_price_data("필터링 후 유효한 가격 데이터 없음")

    avg_price = sum(prices) // len(prices)
    per_sqm   = round(sum(p / a for p, a in zip(prices, areas)) / len(areas)) if areas else 0
    samples   = filtered[:10]

    for s in samples:
        s["apt_name_matched"] = apt_name_matched

    print(f"[molit] ✅ {len(prices)}건 / 평균 {avg_price:,}만원 / ㎡당 {per_sqm:,}만원 / {used_months}개월 기준")

    return {
        "avg":              avg_price,
        "min":              min(prices),
        "max":              max(prices),
        "count":            len(prices),
        "per_sqm_avg":      per_sqm,
        "samples":          samples,
        "apt_name_matched": apt_name_matched,
        "used_months":      used_months,   # 실제 사용된 조회 기간
        "used_region":      used_region,   # 실제 사용된 지역 (인접 지역 확장 시 변경)
        "error":            "",
    }


# ─────────────────────────────────────────
#  5. 감정평가 계산
# ─────────────────────────────────────────

# 면적대 구간 정의 (전용면적 기준, ㎡)
AREA_BANDS = [
    (0,   40,  "초소형 (40㎡ 미만)"),
    (40,  60,  "소형 (40~60㎡)"),
    (60,  85,  "중소형 (60~85㎡)"),
    (85,  115, "중형 (85~115㎡)"),
    (115, 135, "중대형 (115~135㎡)"),
    (135, 999, "대형 (135㎡ 이상)"),
]


def _calc_area_band_ranges(samples: list[dict], per_sqm: int) -> list[dict]:
    """
    실거래 샘플을 면적대별로 분류하여 가격 범위 반환.
    면적 미입력 시 이 결과를 UI에 범위로 표시.
    """
    band_result = []
    for lo, hi, label in AREA_BANDS:
        band_samples = [
            s for s in samples
            if lo <= s.get("area_sqm", 0) < hi and s.get("price", 0) > 0
        ]
        if band_samples:
            prices = [s["price"] for s in band_samples]
            mid_area = (lo + hi) / 2 if hi < 999 else lo + 20
            est = round(per_sqm * mid_area) if per_sqm else sum(prices) // len(prices)
            band_result.append({
                "label":     label,
                "area_lo":   lo,
                "area_hi":   hi,
                "estimated": est,
                "price_min": min(prices),
                "price_max": max(prices),
                "count":     len(prices),
            })
    return band_result


def calc_estimated_value(price_data: dict, area_sqm: float, category: str) -> dict:
    avg         = price_data.get("avg", 0)
    per_sqm     = price_data.get("per_sqm_avg", 0)
    samples     = price_data.get("samples", [])
    area_pyeong = round(area_sqm / 3.3058, 1) if area_sqm else 0

    # ── 면적 입력 있을 때: 단일 추정가 산출 ──────────────────────────────────
    if area_sqm > 0:
        estimated = round(per_sqm * area_sqm) if per_sqm else (avg or 0)
        value_min = round(estimated * 0.90)
        value_max = round(estimated * 1.10)
        area_band_ranges = []   # 단일 추정이므로 범위 불필요

    # ── 면적 미입력: 면적대별 가격 범위 산출 ─────────────────────────────────
    else:
        estimated = avg or 0    # 대표값은 평균가
        value_min = price_data.get("min", 0)
        value_max = price_data.get("max", 0)
        # 실거래 샘플로 면적대별 범위 계산
        area_band_ranges = _calc_area_band_ranges(samples, per_sqm)
        # 샘플 없으면 per_sqm 기준 면적대 추정
        if not area_band_ranges and per_sqm:
            for lo, hi, label in AREA_BANDS:
                mid = (lo + hi) / 2 if hi < 999 else lo + 20
                area_band_ranges.append({
                    "label":     label,
                    "area_lo":   lo,
                    "area_hi":   hi,
                    "estimated": round(per_sqm * mid),
                    "price_min": round(per_sqm * lo) if lo > 0 else 0,
                    "price_max": round(per_sqm * hi) if hi < 999 else round(per_sqm * (lo + 50)),
                    "count":     0,
                })

    price_per_pyeong = round(per_sqm * 3.3058) if per_sqm else 0

    regional_ppyeong = 0
    if samples:
        ppyeongs = [round(s["per_sqm"] * 3.3058) for s in samples if s.get("per_sqm", 0) > 0]
        if ppyeongs:
            regional_ppyeong = sum(ppyeongs) // len(ppyeongs)

    return {
        "estimated_value":         estimated,
        "value_min":               value_min,
        "value_max":               value_max,
        "price_per_pyeong":        price_per_pyeong,
        "area_pyeong":             area_pyeong,
        "regional_avg_per_pyeong": regional_ppyeong,
        "price_per_sqm":           per_sqm,
        "area_band_ranges":        area_band_ranges,  # 면적대별 가격 범위
        "has_area_input":          area_sqm > 0,       # 면적 입력 여부
    }


def calc_valuation_verdict(
    estimated_value: int,
    price_data: dict,
    asking_price: Optional[int] = None,
) -> dict:
    comparable_avg   = price_data.get("avg", 0)
    comparable_count = price_data.get("count", 0)
    samples          = price_data.get("samples", [])[:5]

    base     = asking_price if asking_price and asking_price > 0 else estimated_value
    deviation = round((base - comparable_avg) / comparable_avg * 100, 1) if comparable_avg > 0 else 0.0

    if deviation <= -10:   verdict = "저평가"
    elif deviation <= 5:   verdict = "적정"
    elif deviation <= 15:  verdict = "소폭 고평가"
    else:                  verdict = "고평가"

    return {
        "comparable_avg":    comparable_avg,
        "comparable_count":  comparable_count,
        "deviation_pct":     deviation,
        "valuation_verdict": verdict,
        "comparables":       samples,
    }


# ─────────────────────────────────────────
#  수익환원법 — 상업용·업무용 전용
#  R-ONE API 없을 때 지역별 기준값 사용
# ─────────────────────────────────────────

RBONE_API_KEY = os.getenv("RBONE_API_KEY", "")
RBONE_BASE_URL = "https://www.reb.or.kr/r-one/openapi/SttsApiTblData.do"

# 건물유형 코드
RBONE_BLDG_TYPE = {
    "상업용": "A01",   # 중대형 상가
    "업무용": "B01",   # 오피스
}

# 지역별 ㎡당 월 임대료 기준값 (만원/㎡, R-ONE 2024년 기준)
# R-ONE API 호출 실패 시 폴백으로 사용
RBONE_RENT_FALLBACK = {
    "상업용": {
        "서울": {"서초구": 12.0, "강남구": 14.0, "마포구": 8.0,
                 "영등포구": 9.0, "송파구": 10.0, "default": 7.0},
        "경기": {"default": 4.5},
        "부산": {"해운대구": 6.0, "default": 4.0},
        "default": 4.0,
    },
    "업무용": {
        "서울": {"서초구": 3.5, "강남구": 4.0, "중구": 3.8,
                 "영등포구": 3.2, "마포구": 2.8, "default": 2.5},
        "경기": {"성남시": 2.0, "default": 1.5},
        "부산": {"default": 1.5},
        "default": 1.5,
    },
}

# 지역별 공실률 기준값 (%)
RBONE_VACANCY_FALLBACK = {
    "상업용": {
        "서울": {"서초구": 7.0, "강남구": 6.0, "default": 10.0},
        "default": 12.0,
    },
    "업무용": {
        "서울": {"서초구": 8.0, "강남구": 7.0, "여의도": 9.0, "default": 12.0},
        "경기": {"default": 15.0},
        "default": 14.0,
    },
}

# Cap Rate 기준값 (%)
CAP_RATE_TABLE = {
    "상업용": {"서울": 4.5, "경기": 5.5, "default": 5.5},
    "업무용": {"서울": 4.0, "경기": 5.0, "default": 5.0},
}


def _get_rbone_rent(category: str, region_1depth: str, region_2depth: str) -> tuple[float, float]:
    """
    R-ONE API → 지역별 ㎡당 월 임대료 + 공실률 반환.
    API 실패 시 RBONE_RENT_FALLBACK 사용.
    반환: (월임대료 만원/㎡, 공실률 %)
    """
    # R-ONE API 시도
    if RBONE_API_KEY:
        try:
            bldg_type = RBONE_BLDG_TYPE.get(category, "A01")
            now       = datetime.now()
            # 분기 계산 (R-ONE은 분기별 제공)
            quarter   = (now.month - 1) // 3 + 1
            # 최신 분기가 아직 미공표일 수 있어 한 분기 전 사용
            if quarter == 1:
                stdr_de = f"{now.year - 1}Q4"
            else:
                stdr_de = f"{now.year}Q{quarter - 1}"

            params = (
                f"serviceKey={RBONE_API_KEY}"
                f"&statbl_id=A_2024_00006"   # 상업용부동산 임대동향
                f"&stdr_de={stdr_de}"
                f"&numOfRows=100"
                f"&pageNo=1"
            )
            res = requests.get(f"{RBONE_BASE_URL}?{params}", timeout=8)
            res.raise_for_status()
            root  = ET.fromstring(res.text)
            items = root.findall(".//row")

            for item in items:
                area = item.findtext("AREA_NM", "")
                type_nm = item.findtext("BLDG_TYPE_NM", "")
                if region_2depth in area and bldg_type in type_nm:
                    rent    = float(item.findtext("RENT_AMT", "0") or 0)
                    vacancy = float(item.findtext("VCNC_RATE", "0") or 0)
                    if rent > 0:
                        print(f"[rbone] {region_2depth} {category} 임대료: {rent}만원/㎡, 공실: {vacancy}%")
                        return rent, vacancy

        except Exception as e:
            print(f"[rbone] API 오류: {e} → 기준값 사용")

    # 폴백: 지역별 기준값
    rent_table    = RBONE_RENT_FALLBACK.get(category, {})
    vacancy_table = RBONE_VACANCY_FALLBACK.get(category, {})

    r1 = region_1depth.replace("특별시", "").replace("광역시", "").replace("특별자치시", "").replace("도", "").strip()

    rent_region    = rent_table.get(r1, rent_table.get("default", {}))
    vacancy_region = vacancy_table.get(r1, vacancy_table.get("default", {}))

    if isinstance(rent_region, dict):
        rent    = rent_region.get(region_2depth, rent_region.get("default", 4.0))
        vacancy = vacancy_region.get(region_2depth, vacancy_region.get("default", 12.0)) if isinstance(vacancy_region, dict) else vacancy_region
    else:
        rent    = rent_region
        vacancy = vacancy_region if isinstance(vacancy_region, (int, float)) else 12.0

    print(f"[rbone] 기준값 사용: {region_2depth} {category} 임대료 {rent}만원/㎡, 공실 {vacancy}%")
    return float(rent), float(vacancy)


def _fetch_by_income_approach(
    category: str,
    region_1depth: str,
    region_2depth: str,
    area_sqm: float,
    cap_rate_override: float = 0.0,
) -> dict:
    """
    수익환원법: NOI / Cap Rate = 추정 시세
    상업용·업무용 실거래 없을 때 폴백.

    NOI = 연 임대수입 × (1 - 공실률) × (1 - 운영비율)
    추정가 = NOI / Cap Rate
    """
    if area_sqm <= 0:
        return _empty_price_data("수익환원법: 면적 정보 없음")

    rent_per_sqm, vacancy_rate = _get_rbone_rent(category, region_1depth, region_2depth)

    # 연 임대수입
    annual_rent = rent_per_sqm * area_sqm * 12

    # 공실 손실
    vacancy_loss = annual_rent * (vacancy_rate / 100)

    # 운영비용 (관리비·수선비·보험료 등, 통상 15%)
    operating_cost = annual_rent * 0.15

    # 순영업수익 (NOI)
    noi = annual_rent - vacancy_loss - operating_cost

    # Cap Rate
    r1   = region_1depth.replace("특별시","").replace("광역시","").replace("도","").strip()
    cap_table = CAP_RATE_TABLE.get(category, {})
    cap_rate  = cap_rate_override or cap_table.get(r1, cap_table.get("default", 5.0))
    cap_rate  = cap_rate / 100

    # 추정가
    estimated = round(noi / cap_rate) if cap_rate > 0 else 0
    per_sqm   = round(estimated / area_sqm) if area_sqm > 0 else 0

    print(f"[수익환원법] 월임대료 {rent_per_sqm}만원/㎡ × {area_sqm}㎡ "
          f"→ 연임대 {annual_rent:,.0f}만원 / NOI {noi:,.0f}만원 "
          f"/ Cap {cap_rate:.1%} → 추정가 {estimated:,}만원")

    return {
        "avg":              estimated,
        "min":              round(estimated * 0.85),
        "max":              round(estimated * 1.15),
        "count":            0,
        "per_sqm_avg":      per_sqm,
        "samples":          [],
        "apt_name_matched": "",
        "used_months":      0,
        "used_region":      region_2depth,
        "noi":              round(noi),
        "annual_rent":      round(annual_rent),
        "vacancy_rate":     vacancy_rate,
        "cap_rate_used":    cap_rate * 100,
        "source":           (f"수익환원법 (월임대료 {rent_per_sqm}만원/㎡, "
                             f"공실률 {vacancy_rate}%, Cap Rate {cap_rate:.1%})"),
        "error":            "",
    }


# ─────────────────────────────────────────
#  건축원가법 — 산업용 (공장·창고) 전용
# ─────────────────────────────────────────

# 구조별 표준건축비 (만원/㎡, 국토부 고시 기준)
STANDARD_CONSTRUCTION_COST = {
    "공장": {
        "철근콘크리트": 95,
        "철골철근콘크리트": 100,
        "철골조":       80,
        "조적조":       60,
        "default":     80,
    },
    "창고": {
        "철근콘크리트": 65,
        "철골철근콘크리트": 70,
        "철골조":       50,
        "조적조":       40,
        "default":     50,
    },
    "물류창고": {
        "철근콘크리트": 75,
        "철골조":       60,
        "default":     60,
    },
}

# 구조별 내용연수 (년)
USEFUL_LIFE = {
    "공장": {
        "철근콘크리트": 40,
        "철골철근콘크리트": 40,
        "철골조":       30,
        "조적조":       20,
        "default":     35,
    },
    "창고": {
        "철근콘크리트": 30,
        "철골철근콘크리트": 30,
        "철골조":       25,
        "조적조":       20,
        "default":     25,
    },
    "물류창고": {
        "철근콘크리트": 35,
        "철골조":       25,
        "default":     30,
    },
}

# 구조별 잔존가치율 (감가 완료 후 최소 잔존 비율)
RESIDUAL_VALUE_RATE = {
    "철근콘크리트":     0.10,
    "철골철근콘크리트": 0.10,
    "철골조":           0.05,
    "조적조":           0.05,
    "default":          0.10,
}


def _get_strct_key(strct_nm: str) -> str:
    """건물구조명 → 표준 키 변환"""
    for key in ["철골철근콘크리트", "철근콘크리트", "철골조", "조적조"]:
        if key in strct_nm:
            return key
    return "default"


def _calc_residual_rate(age: int, useful_life: int, residual: float,
                        method: str = "declining") -> float:
    """
    감가상각 잔가율 계산.

    method:
        "declining" — 정률법 (초기 감가 크고 후기 완만, 실물자산에 적합)
        "straight"  — 정액법 (매년 균등 감가)

    정률법 감가율 r = 1 - (잔존가치율) ^ (1/내용연수)
    잔가율 = (1 - r) ^ 경과연수
    """
    if age <= 0:
        return 1.0

    if method == "declining":
        # 정률법
        r = 1 - (residual ** (1 / useful_life))
        rate = (1 - r) ** age
    else:
        # 정액법
        rate = 1 - (1 - residual) * (age / useful_life)

    return round(max(residual, rate), 4)


def calc_cost_approach(
    land_area_sqm: float,
    official_land_price: int,
    build_area_sqm: float,
    build_year: int,
    category_detail: str,
    strct_nm: str = "",          # 건물구조 (건축물대장에서 자동 조회)
    depreciation: str = "declining",  # 감가방법: declining(정률) | straight(정액)
) -> dict:
    """
    건축원가법: 토지가격 + 건물가격(감가상각 적용)

    토지가격  = 공시지가(만원/㎡) × 토지면적(㎡)
    건물가격  = 표준건축비(만원/㎡) × 건물면적(㎡) × 잔가율

    잔가율 (정률법):
      감가율 r = 1 - (잔존가치율)^(1/내용연수)
      잔가율   = (1-r)^경과연수
      → 초기 감가가 크고 후기에 완만 (실물자산 현실에 부합)

    잔가율 (정액법):
      잔가율 = 1 - (1-잔존가치율) × (경과연수/내용연수)
      → 매년 균등 감가
    """
    now_year   = datetime.now().year
    detail_key = next((k for k in STANDARD_CONSTRUCTION_COST if k in category_detail), "창고")
    strct_key  = _get_strct_key(strct_nm)

    cost_table = STANDARD_CONSTRUCTION_COST[detail_key]
    life_table = USEFUL_LIFE[detail_key]

    std_cost    = cost_table.get(strct_key, cost_table["default"])
    useful_life = life_table.get(strct_key, life_table["default"])
    residual    = RESIDUAL_VALUE_RATE.get(strct_key, RESIDUAL_VALUE_RATE["default"])

    age    = max(0, now_year - int(build_year)) if build_year else 10
    잔가율  = _calc_residual_rate(age, useful_life, residual, method=depreciation)

    # 토지가격
    land_value  = round(official_land_price * land_area_sqm) if official_land_price and land_area_sqm else 0

    # 건물가격 (재조달원가 × 잔가율)
    재조달원가  = round(std_cost * build_area_sqm) if build_area_sqm else 0
    build_value = round(재조달원가 * 잔가율)
    감가액       = 재조달원가 - build_value

    total = land_value + build_value

    if total <= 0:
        return _empty_price_data("건축원가법: 토지가격·건물가격 모두 0 (면적 및 공시지가 필요)")

    per_sqm     = round(total / build_area_sqm) if build_area_sqm > 0 else 0
    source_note = "공시지가 + 표준건축비" if land_value > 0 else "표준건축비만 (토지가격 미산정)"
    strct_label = strct_key if strct_key != "default" else "기본"

    print(
        f"[원가법] 구조:{strct_label} / 재조달원가 {재조달원가:,}만원 "
        f"→ 감가 {감가액:,}만원 (잔가율 {잔가율:.1%}, {depreciation}, 경과 {age}년) "
        f"/ 토지 {land_value:,}만원 + 건물 {build_value:,}만원 = {total:,}만원 [{source_note}]"
    )

    return {
        "avg":              total,
        "min":              round(total * 0.85),
        "max":              round(total * 1.15),
        "count":            0,
        "per_sqm_avg":      per_sqm,
        "samples":          [],
        "apt_name_matched": "",
        "used_months":      0,
        "used_region":      "",
        "land_value":       land_value,
        "build_value":      build_value,
        "재조달원가":        재조달원가,
        "감가액":            감가액,
        "잔가율":            잔가율,
        "build_age":        age,
        "strct_nm":         strct_label,
        "depreciation":     depreciation,
        "source":           (
            f"건축원가법 ({source_note}, {strct_label}구조, "
            f"잔가율 {잔가율:.1%}, {depreciation}법, 경과 {age}년)"
        ),
        "error":            "",
    }


def calc_investment_return(estimated_value: int, category: str, area_sqm: float) -> dict:
    cap_rates = {"주거용": 3.5, "상업용": 5.0, "업무용": 4.5, "산업용": 6.0, "토지": 2.5}
    cap_rate      = cap_rates.get(category, 4.0)
    annual_income = round(estimated_value * cap_rate / 100) if estimated_value else 0
    roi_5yr       = round(cap_rate * 5, 1)

    if cap_rate >= 6.0:   grade = "A"
    elif cap_rate >= 4.5: grade = "B"
    elif cap_rate >= 3.0: grade = "C"
    else:                 grade = "D"

    return {"cap_rate": cap_rate, "annual_income": annual_income,
            "roi_5yr": roi_5yr, "investment_grade": grade}


# ─────────────────────────────────────────
#  6. 카카오 주변 시설
# ─────────────────────────────────────────

KAKAO_CATEGORY_URL   = "https://dapi.kakao.com/v2/local/search/category.json"
KAKAO_CATEGORY_CODES = {
    "지하철역": "SW8", "학교": "SC4", "마트": "MT1",
    "편의점": "CS2",  "병원": "HP8", "음식점": "FD6",
    "카페": "CE7",    "주차장": "PK6", "은행": "BK9",
}


def search_nearby_facilities(lat: float, lng: float,
                              categories: list[str], radius: int = 1000) -> dict:
    if not KAKAO_API_KEY:
        return {}
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    result  = {}
    for cat_name in categories:
        cat_code = KAKAO_CATEGORY_CODES.get(cat_name)
        if not cat_code:
            continue
        try:
            res  = requests.get(KAKAO_CATEGORY_URL, headers=headers, params={
                "category_group_code": cat_code,
                "x": lng, "y": lat, "radius": radius, "size": 15, "sort": "distance",
            }, timeout=5)
            docs = res.json().get("documents", [])
            result[cat_name] = {
                "count":        len(docs),
                "nearest_m":    int(docs[0].get("distance", 9999)) if docs else 9999,
                "nearest_name": docs[0].get("place_name", "") if docs else "",
            }
            time.sleep(0.05)
        except Exception as e:
            print(f"[kakao_nearby] {cat_name} 오류: {e}")
    return result


# ─────────────────────────────────────────
#  7. Tavily 웹 검색
# ─────────────────────────────────────────

def search_web_tavily(query: str, max_results: int = 3) -> str:
    if not TAVILY_API_KEY:
        return ""
    try:
        res  = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query,
                  "max_results": max_results, "search_depth": "basic",
                  "include_answer": True},
            timeout=10,
        )
        data = res.json()
        if data.get("answer"):
            return data["answer"]
        return " / ".join(r.get("content", "")[:200] for r in data.get("results", []))
    except Exception as e:
        print(f"[tavily] 오류: {e}")
        return ""


# ─────────────────────────────────────────
#  8. LLM 감정평가 의견서
# ─────────────────────────────────────────

APPRAISAL_PROMPT = """당신은 국가공인 부동산 감정평가사입니다.
아래 데이터를 바탕으로 전문적인 감정평가 의견서를 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
{
  "appraisal_opinion": "3~4문장의 전문 감정평가 의견",
  "strengths": ["가치 상승 요인1", "요인2", "요인3"],
  "risk_factors": ["리스크 요인1", "요인2"],
  "recommendation": "매수 적극 고려 | 매수 고려 | 관망 | 매수 비추천"
}"""


def generate_appraisal_opinion(category, location, valuation_data, nearby_data, web_summary) -> dict:
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "exaone3.5:7.8b"),
        temperature=0.1, format="json", num_predict=1024,
    )
    estimated   = valuation_data.get("estimated_value", 0)
    verdict     = valuation_data.get("valuation_verdict", "")
    deviation   = valuation_data.get("deviation_pct", 0)
    cap_rate    = valuation_data.get("cap_rate", 0)
    ppyeong     = valuation_data.get("price_per_pyeong", 0)
    reg_ppyeong = valuation_data.get("regional_avg_per_pyeong", 0)

    nearby_text = "\n".join(
        f"  {k}: {v['count']}개 (최근접 {v['nearest_m']}m)"
        for k, v in nearby_data.items() if v.get("count", 0) > 0
    ) or "주변 시설 정보 없음"

    user_content = f"""
감정평가 대상: {category} / {location}
추정 시장가치: {estimated:,}만원
평당가: {ppyeong:,}만원/평 (지역 평균: {reg_ppyeong:,}만원/평)
고저평가 판정: {verdict} ({deviation:+.1f}%)
Cap Rate: {cap_rate}%
주변 환경: {nearby_text}
시장 동향: {web_summary or '정보 없음'}
"""
    try:
        response = llm.invoke([("system", APPRAISAL_PROMPT), ("human", user_content)])
        raw   = response.content.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"[appraisal_llm] 오류: {e}")

    return {
        "appraisal_opinion": f"{location} {category} 추정 시장가치 {estimated:,}만원. 인근 실거래 대비 {verdict} 수준.",
        "strengths":    ["실거래 데이터 기반 분석 완료"],
        "risk_factors": ["LLM 의견서 생성 실패 — 수치 기반 결과만 제공"],
        "recommendation": "관망",
    }


# ─────────────────────────────────────────
#  9. 인텐트 요약 헬퍼
# ─────────────────────────────────────────

def _intent_summary(intent) -> str:
    if not intent:
        return ""
    parts = [
        f"위치: {getattr(intent, 'location_normalized', '')}",
        f"거래: {getattr(intent, 'transaction_type', '')}",
        f"가격: {getattr(intent, 'price_raw', '')}",
        f"면적: {getattr(intent, 'area_raw', '')}",
        f"특수조건: {', '.join(getattr(intent, 'special_conditions', []))}",
    ]
    return " | ".join(p for p in parts if p.split(": ")[1])


# ─────────────────────────────────────────
#  CLI 테스트
# ─────────────────────────────────────────

if __name__ == "__main__":
    ymds = _get_recent_deal_ymds(3)
    print(f"현재 날짜  : {datetime.now().strftime('%Y-%m-%d')}")
    print(f"조회 대상월: {ymds}")

    if MOLIT_API_KEY:
        data = fetch_real_transaction_prices("주거용", "서초구", "아파트", apt_name="래미안원베일리")
        print(f"\n래미안원베일리 실거래가:")
        print(f"  건수   : {data['count']}건")
        print(f"  평균   : {data['avg']:,}만원")
        print(f"  오류   : {data.get('error') or '없음'}")
        print(f"  매칭   : {data.get('apt_name_matched') or '없음'}")
    else:
        print("\n⚠️  MOLIT_API_KEY 없음 — .env 파일을 확인하세요")