"""
geocoding.py — 좌표 변환 + 건물명·부동산 유형 자동 판단 v2.4
--------------------------------------------------------------
흐름:
  1순위) 카카오 주소검색 API
         → road_address.building_name 으로 정확한 건물명 1:1 추출
         → 예) "서울시 서초구 반포대로 333" → "래미안원베일리"
         → 건물명으로 키워드검색 → category_name → 부동산 유형 판단

  2순위) 주소검색 실패 또는 building_name 없을 때
         → 입력값 그대로 키워드검색
         → place_name + category_name 한 번에 획득

  3순위) 전부 실패 → LLM category 폴백
"""

from __future__ import annotations

import os
import time
from typing import Optional

import requests
from dotenv import load_dotenv, find_dotenv
from pydantic import BaseModel, Field

load_dotenv(find_dotenv())

KAKAO_API_KEY  = os.getenv("KAKAO_REST_API_KEY", "")
VWORLD_API_KEY = os.getenv("VWORLD_API_KEY", "")

KAKAO_ADDR_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KWD_URL  = "https://dapi.kakao.com/v2/local/search/keyword.json"


# ─────────────────────────────────────────
#  1. 결과 데이터 모델
# ─────────────────────────────────────────

class GeocodingResult(BaseModel):
    lat: float = Field(description="위도 (WGS84)")
    lng: float = Field(description="경도 (WGS84)")

    address_name:  str = Field(default="", description="전체 주소 문자열")
    region_1depth: str = Field(default="", description="시·도")
    region_2depth: str = Field(default="", description="시·군·구")
    region_3depth: str = Field(default="", description="읍·면·동")

    method:     str   = Field(default="address")
    confidence: float = Field(default=1.0)

    # 건물 정보
    place_name:        str = Field(default="", description="건물·단지명")
    kakao_category:    str = Field(default="", description="카카오 원본 카테고리")
    property_category: str = Field(default="", description="주거용/상업용/업무용/산업용/토지")
    category_detail:   str = Field(default="", description="아파트/오피스텔/상가 등")
    category_source:   str = Field(default="", description="kakao | llm | fallback")

    # 토지 전용
    land_use_zone:       str   = Field(default="")
    land_area:           float = Field(default=0.0)
    official_land_price: int   = Field(default=0)


# ─────────────────────────────────────────
#  2. 카카오 category_name → 부동산 유형 매핑
# ─────────────────────────────────────────

KAKAO_CATEGORY_MAP: list[tuple[str, str, str]] = [
    ("아파트",       "주거용", "아파트"),
    ("오피스텔",     "주거용", "오피스텔"),
    ("빌라",         "주거용", "빌라"),
    ("연립",         "주거용", "연립다세대"),
    ("다세대",       "주거용", "연립다세대"),
    ("단독주택",     "주거용", "단독다가구"),
    ("다가구",       "주거용", "단독다가구"),
    ("주거시설",     "주거용", "아파트"),
    ("공장",         "산업용", "공장"),
    ("창고",         "산업용", "창고"),
    ("물류",         "산업용", "창고"),
    ("지식산업센터", "산업용", "공장"),
    ("산업단지",     "산업용", "공장"),
    ("사무",         "업무용", "사무실"),
    ("오피스",       "업무용", "사무실"),
    ("업무",         "업무용", "사무실"),
    ("상가",         "상업용", "상가"),
    ("마트",         "상업용", "상가"),
    ("백화점",       "상업용", "상가"),
    ("쇼핑",         "상업용", "상가"),
    ("판매",         "상업용", "상가"),
    ("숙박",         "상업용", "상가"),
    ("음식점",       "상업용", "상가"),
    ("토지",         "토지",   "토지"),
    ("농지",         "토지",   "토지"),
    ("임야",         "토지",   "토지"),
    ("대지",         "토지",   "토지"),
]


def _map_kakao_category(category_name: str) -> tuple[str, str]:
    for keyword, prop_cat, detail in KAKAO_CATEGORY_MAP:
        if keyword in category_name:
            return prop_cat, detail
    return "", ""


def _kakao_headers() -> dict:
    if not KAKAO_API_KEY:
        raise EnvironmentError("KAKAO_REST_API_KEY 환경변수가 없습니다.")
    return {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}


# ─────────────────────────────────────────
#  3. 카카오 주소검색 — building_name 포함 파싱
# ─────────────────────────────────────────

def _address_search(query: str) -> Optional[dict]:
    """
    카카오 주소검색 API 호출.
    road_address.building_name 포함하여 반환.

    반환:
        {
            "x", "y",
            "address_name",
            "road_address_name",
            "building_name",     ← 핵심: 래미안원베일리 등
            "region_1depth", "region_2depth", "region_3depth",
        }
    """
    try:
        res = requests.get(
            KAKAO_ADDR_URL,
            headers=_kakao_headers(),
            params={"query": query, "size": 1},
            timeout=5,
        )
        res.raise_for_status()
        docs = res.json().get("documents", [])
        if not docs:
            return None

        d    = docs[0]
        road = d.get("road_address") or {}
        addr = d.get("address") or {}

        return {
            "x":                 d.get("x", ""),
            "y":                 d.get("y", ""),
            "address_name":      d.get("address_name", ""),
            "road_address_name": road.get("address_name", ""),
            "building_name":     road.get("building_name", "").strip(),  # ← 핵심
            "region_1depth":     road.get("region_1depth_name") or addr.get("region_1depth_name", ""),
            "region_2depth":     road.get("region_2depth_name") or addr.get("region_2depth_name", ""),
            # 도로명 주소는 region_3depth_name 비어있음 → 지번(address)에서 동 정보 우선 추출
            "region_3depth":     addr.get("region_3depth_name") or road.get("region_3depth_name", ""),
        }

    except Exception as e:
        print(f"[address_search] 오류: {e}")
        return None


# ─────────────────────────────────────────
#  4. 카카오 키워드검색 — place_name + category 파싱
# ─────────────────────────────────────────

def _keyword_search(query: str, size: int = 5) -> list[dict]:
    """
    카카오 키워드검색 API 호출.
    place_name + category_name 반환.
    """
    try:
        res = requests.get(
            KAKAO_KWD_URL,
            headers=_kakao_headers(),
            params={"query": query, "size": size},
            timeout=5,
        )
        res.raise_for_status()
        return res.json().get("documents", [])
    except Exception as e:
        print(f"[keyword_search] 오류: {e}")
        return []


def _get_category_from_keyword(building_name: str) -> tuple[str, str, str]:
    """
    건물명으로 키워드검색 → category_name → 부동산 유형 판단.
    반환: (kakao_category, property_category, category_detail)
    """
    if not building_name:
        return "", "", ""

    docs = _keyword_search(building_name, size=3)
    for doc in docs:
        cat_name         = doc.get("category_name", "")
        prop_cat, detail = _map_kakao_category(cat_name)
        if prop_cat:
            print(f"[category] '{building_name}' → {cat_name} → {prop_cat}/{detail}")
            return cat_name, prop_cat, detail

    return "", "", ""


# ─────────────────────────────────────────
#  5. 통합 지오코딩 진입점
# ─────────────────────────────────────────

def geocode(location: str, category: str = "") -> Optional[GeocodingResult]:
    """
    주소 입력 → 좌표 + 건물명 + 부동산 유형 획득.

    1순위: 주소검색 → building_name 추출 → 건물명으로 category 판단
    2순위: 주소검색 실패 or building_name 없음 → 키워드검색
    3순위: 전부 실패 → LLM category 폴백
    """
    print(f"[geocode] 입력: '{location}'")

    # ── 1순위: 주소검색 → building_name ──────────────────────────────────
    addr_info = _address_search(location)

    if addr_info:
        lat = float(addr_info["y"])
        lng = float(addr_info["x"])
        building_name = addr_info["building_name"]

        print(f"[geocode] 주소검색 성공 → {lat:.4f}, {lng:.4f}")
        if building_name:
            print(f"[geocode] building_name: '{building_name}'")

        # 건물명으로 카테고리 판단
        kakao_cat, prop_cat, detail = _get_category_from_keyword(building_name)

        # 건물명 없으면 입력 주소 자체로 카테고리 판단 시도
        if not prop_cat:
            kakao_cat, prop_cat, detail = _get_category_from_keyword(location)

        result = GeocodingResult(
            lat=lat,
            lng=lng,
            address_name=addr_info["address_name"],
            region_1depth=addr_info["region_1depth"],
            region_2depth=addr_info["region_2depth"],
            region_3depth=addr_info["region_3depth"],
            method="address",
            confidence=1.0,
            place_name=building_name,
            kakao_category=kakao_cat,
            property_category=prop_cat or category,
            category_detail=detail,
            category_source="kakao" if prop_cat else ("llm" if category else "fallback"),
        )

        if result.property_category == "토지":
            _attach_land_info(result)

        print(f"[geocode] ✅ 완료: '{result.place_name}' / "
              f"{result.property_category}/{result.category_detail} "
              f"({result.category_source})")
        return result

    # ── 2순위: 키워드검색 폴백 ───────────────────────────────────────────
    print(f"[geocode] 주소검색 실패 → 키워드검색 폴백")
    docs = _keyword_search(location, size=5)

    for doc in docs:
        cat_name         = doc.get("category_name", "")
        prop_cat, detail = _map_kakao_category(cat_name)

        addr_parts = doc.get("address_name", "").split()
        result = GeocodingResult(
            lat=float(doc["y"]),
            lng=float(doc["x"]),
            address_name=doc.get("address_name", ""),
            region_1depth=addr_parts[0] if len(addr_parts) > 0 else "",
            region_2depth=addr_parts[1] if len(addr_parts) > 1 else "",
            region_3depth=addr_parts[2] if len(addr_parts) > 2 else "",
            method="keyword",
            confidence=0.85,
            place_name=doc.get("place_name", ""),
            kakao_category=cat_name,
            property_category=prop_cat or category,
            category_detail=detail,
            category_source="kakao" if prop_cat else ("llm" if category else "fallback"),
        )

        if result.property_category == "토지":
            _attach_land_info(result)

        print(f"[geocode] ✅ 키워드 완료: '{result.place_name}' / "
              f"{result.property_category}/{result.category_detail}")
        return result

    # ── 3순위: 전부 실패 ─────────────────────────────────────────────────
    print(f"[geocode] ❌ 변환 실패: '{location}'")
    return None


# ─────────────────────────────────────────
#  6. Vworld — 토지 법적 정보
# ─────────────────────────────────────────

VWORLD_LAND_URL = "https://api.vworld.kr/req/data"


def _attach_land_info(result: GeocodingResult):
    info = get_land_info_vworld(result.lat, result.lng)
    if info:
        result.land_use_zone        = info.get("land_use_zone", "")
        result.land_area            = info.get("land_area", 0.0)
        result.official_land_price  = info.get("official_land_price", 0)
        print(f"[vworld] 용도지역: {result.land_use_zone}")


def get_land_info_vworld(lat: float, lng: float) -> Optional[dict]:
    if not VWORLD_API_KEY:
        return None
    params = {
        "service": "data", "request": "GetFeature",
        "data": "LT_C_LHBLPN", "key": VWORLD_API_KEY,
        "format": "json", "size": "1", "page": "1",
        "geometry": "true", "attribute": "true",
        "crs": "EPSG:4326", "geomFilter": f"POINT({lng} {lat})",
    }
    try:
        res = requests.get(VWORLD_LAND_URL, params=params, timeout=8)
        res.raise_for_status()
        features = (
            res.json().get("response", {})
               .get("result", {})
               .get("featureCollection", {})
               .get("features", [])
        )
        if not features:
            return None
        props = features[0].get("properties", {})
        return {
            "land_use_zone":       props.get("prpos_area1_nm", ""),
            "land_area":           float(props.get("lndpcp_ar", 0)),
            "official_land_price": int(props.get("pblntf_pric", 0)),
        }
    except Exception as e:
        print(f"[vworld] 오류: {e}")
        return None


# ─────────────────────────────────────────
#  7. LangGraph 노드
# ─────────────────────────────────────────

def geocoding_node(state):
    def _g(s, key, default=None):
        if isinstance(s, dict): return s.get(key, default)
        return getattr(s, key, default)

    def _s(s, key, value):
        if isinstance(s, dict): s[key] = value
        else: object.__setattr__(s, key, value)
        return s

    intent = _g(state, "intent")
    if not intent:
        return _s(state, "error", "geocoding_node: intent 없음")

    location = getattr(intent, "location_normalized", "") or getattr(intent, "location_raw", "")
    if not location:
        return _s(state, "error", "geocoding_node: 위치 정보 없음")

    llm_category = getattr(intent, "category", "")
    result = geocode(location, category=llm_category)

    if not result:
        return _s(state, "error", f"좌표 변환 실패: '{location}'")

    # 카카오 판단 성공 → intent.category 업데이트
    if result.property_category and result.category_source == "kakao":
        try:
            old = intent.category
            intent.category = result.property_category
            if result.category_detail:
                intent.category_detail = result.category_detail
            print(f"[geocoding_node] category: {old} → {result.property_category} (카카오)")
        except Exception:
            pass

    # place_name → building_name 자동 설정 (사용자 미입력 시)
    if result.place_name and not _g(state, "building_name", ""):
        _s(state, "building_name", result.place_name)
        print(f"[geocoding_node] building_name 자동 설정: '{result.place_name}'")

    _s(state, "geocoding_result", result.model_dump())
    _s(state, "error", "")
    return state


# ─────────────────────────────────────────
#  8. 캐싱
# ─────────────────────────────────────────

_geocode_cache: dict[str, GeocodingResult] = {}


def geocode_cached(location: str, category: str = "") -> Optional[GeocodingResult]:
    key = f"{location}::{category}"
    if key in _geocode_cache:
        print(f"[cache] 히트: '{location}'")
        return _geocode_cache[key]
    result = geocode(location, category)
    if result:
        _geocode_cache[key] = result
    return result


# ─────────────────────────────────────────
#  9. CLI 테스트
# ─────────────────────────────────────────

if __name__ == "__main__":
    if not KAKAO_API_KEY:
        print("⚠️  KAKAO_REST_API_KEY 없음")
    else:
        tests = [
            "서울시 서초구 반포대로 333",       # 래미안원베일리 (아파트)
            "서울시 마포구 백범로 192",          # 마포래미안푸르지오 (아파트)
            "서울시 강남구 테헤란로 152",        # 강남파이낸스센터 (업무용)
            "서울시 영등포구 여의대로 108",      # 파크원 (업무용)
            "경기도 성남시 분당구 판교역로 235", # 판교테크노밸리 (산업용)
            "부산시 해운대구 해운대해변로 264",  # (상업용)
        ]
        print("=" * 60)
        for addr in tests:
            print(f"\n📍 입력: {addr}")
            r = geocode_cached(addr)
            if r:
                print(f"   building_name : {r.place_name or '(없음)'}")
                print(f"   카카오 카테고리: {r.kakao_category or '(없음)'}")
                print(f"   부동산 유형   : {r.property_category or '(미판단)'} / {r.category_detail}")
                print(f"   판단 근거     : {r.category_source}")
                print(f"   행정구역      : {r.region_2depth} {r.region_3depth}")
            else:
                print("   ❌ 실패")
            time.sleep(0.3)