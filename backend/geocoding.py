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

    # 건축물대장 조회용 지번 정보
    sigungu_cd: str = Field(default="", description="시군구코드 5자리")
    bjdong_cd:  str = Field(default="", description="법정동코드 10자리")
    bun:        str = Field(default="", description="지번 본번")
    ji:         str = Field(default="", description="지번 부번")


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
#  3. 카카오 좌표 → 지번 역지오코딩
# ─────────────────────────────────────────

def _coord2jibun(lat: float, lng: float) -> dict:
    """
    카카오 coord2address API — 좌표 → 지번 주소 변환.

    coord2address 가 address.b_code 를 정확히 못 줄 때
    regioncode API 로 법정동 코드를 보완한다.
    """
    try:
        # 1. coord2address — 지번 본번·부번 획득
        res = requests.get(
            "https://dapi.kakao.com/v2/local/geo/coord2address.json",
            headers=_kakao_headers(),
            params={"x": lng, "y": lat, "input_coord": "WGS84"},
            timeout=5,
        )
        res.raise_for_status()
        docs = res.json().get("documents", [])
        if not docs:
            return {}

        addr   = docs[0].get("address") or {}
        b_code = addr.get("b_code", "")
        bun    = addr.get("main_address_no", "")
        ji     = addr.get("sub_address_no",  "")

        # 2. b_code 뒤 5자리가 00000 이면 regioncode API 로 법정동 코드 보완
        bjdong_5 = b_code[5:] if len(b_code) == 10 else ""
        if not bjdong_5 or bjdong_5 == "00000":
            try:
                rc_res = requests.get(
                    "https://dapi.kakao.com/v2/local/geo/coord2regioncode.json",
                    headers=_kakao_headers(),
                    params={"x": lng, "y": lat, "input_coord": "WGS84"},
                    timeout=5,
                )
                rc_res.raise_for_status()
                for region in rc_res.json().get("documents", []):
                    if region.get("region_type") == "B":   # 법정동
                        b_code = region.get("code", b_code)
                        break
            except Exception as e2:
                print(f"[geocode] regioncode 보완 오류: {e2}")

        print(f"[geocode] 역지오코딩 → b_code={b_code} bun={bun} ji={ji} "
              f"({addr.get('address_name','')})")
        return {
            "b_code":     b_code,
            "sigungu_cd": b_code[:5] if b_code else "",
            "bjdong_cd":  b_code,
            "bun":        bun,
            "ji":         ji,
        }
    except Exception as e:
        print(f"[geocode] 역지오코딩 오류: {e}")
        return {}


# ─────────────────────────────────────────
#  4. 카카오 주소검색 — building_name 포함 파싱
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

        # 법정동코드 (b_code: 10자리) → 시군구코드 앞 5자리
        b_code     = addr.get("b_code", "")
        sigungu_cd = b_code[:5] if b_code else ""
        bun_val    = addr.get("main_address_no", "")
        ji_val     = addr.get("sub_address_no",  "")

        # bun 없거나 b_code 뒤 5자리가 00000이면
        # 해당 좌표로 바로 역지오코딩 → 정확한 지번 보완
        bjdong_5 = b_code[5:] if len(b_code) == 10 else ""
        if not bun_val or not bjdong_5 or bjdong_5 == "00000":
            x_val = d.get("x", "")
            y_val = d.get("y", "")
            if x_val and y_val:
                jibun = _coord2jibun(float(y_val), float(x_val))
                if jibun.get("bun"):
                    b_code     = jibun["bjdong_cd"]
                    sigungu_cd = jibun["sigungu_cd"]
                    bun_val    = jibun["bun"]
                    ji_val     = jibun["ji"]
                    print(f"[address_search] 지번 보완: "
                          f"bun={bun_val} bjdong={b_code} "
                          f"({addr.get('address_name', '')})")

        return {
            "x":                 d.get("x", ""),
            "y":                 d.get("y", ""),
            "address_name":      d.get("address_name", ""),
            "road_address_name": road.get("address_name", ""),
            "building_name":     road.get("building_name", "").strip(),
            "region_1depth":     road.get("region_1depth_name") or addr.get("region_1depth_name", ""),
            "region_2depth":     road.get("region_2depth_name") or addr.get("region_2depth_name", ""),
            "region_3depth":     addr.get("region_3depth_name") or road.get("region_3depth_name", ""),
            # 건축물대장 조회용 지번 정보
            "sigungu_cd": sigungu_cd,
            "bjdong_cd":  b_code,
            "bun":        bun_val,
            "ji":         ji_val,
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
    import re as _re
    # 특수문자 제거 (주), (유), (주식회사) → 공백으로 대체
    clean_query = _re.sub(r'\([주유]\)|\(주식회사\)', ' ', query).strip()
    # 나머지 특수문자도 공백으로
    clean_query = _re.sub(r'[^\w\s가-힣A-Za-z0-9]', ' ', clean_query).strip()
    clean_query = _re.sub(r'\s+', ' ', clean_query).strip()
    if clean_query != query:
        print(f"[keyword_search] 쿼리 정제: '{query}' → '{clean_query}'")
    try:
        res = requests.get(
            KAKAO_KWD_URL,
            headers=_kakao_headers(),
            params={"query": clean_query, "size": size},
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

    # ── 건물명 자체에서 키워드 판단 (카카오 검색 전 우선 처리) ──
    NAME_KEYWORDS = [
        ("공장",         "산업용", "공장"),
        ("창고",         "산업용", "창고"),
        ("물류센터",     "산업용", "창고"),
        ("물류",         "산업용", "창고"),
        ("지식산업센터", "산업용", "공장"),
        ("산업단지",     "산업용", "공장"),
        ("아파트",       "주거용", "아파트"),
        ("빌라",         "주거용", "빌라"),
        ("오피스텔",     "주거용", "오피스텔"),
        ("주상복합",     "주거용", "아파트"),
        ("사무소",       "업무용", "사무실"),
        ("빌딩",         "업무용", "사무실"),
        ("타워",         "업무용", "사무실"),
    ]
    for keyword, prop_cat, detail in NAME_KEYWORDS:
        if keyword in building_name:
            print(f"[category] '{building_name}' → 건물명 키워드 '{keyword}' → {prop_cat}/{detail}")
            return f"건물명:{keyword}", prop_cat, detail

    # ── 카카오 키워드검색 ──
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

def geocode(location: str, category: str = "",
            building_hint: str = "") -> Optional[GeocodingResult]:
    """
    주소 입력 → 좌표 + 건물명 + 부동산 유형 획득.

    building_hint: 사용자가 선택한 건물명 (예: 아모레퍼시픽 오산공장)
                   주소가 시·구 단위로 모호할 때 키워드검색으로 정확한 지번 획득

    1순위: building_hint 키워드검색 → 정확한 좌표·지번 획득
    2순위: 주소검색 → building_name 추출
    3순위: 역지오코딩으로 지번 보완
    4순위: LLM category 폴백
    """
    # 주소에 건물명이 혼합된 경우 분리
    # 예: "경기도 용인시 기흥구 보라동 57번길 10 삼성전자(주)기흥캠퍼스"
    #   → location = "경기도 용인시 기흥구 보라동 57번길 10"
    #   → building_hint = "삼성전자(주)기흥캠퍼스" (없을 때만)
    import re as _re
    # 도로명 주소 패턴 뒤에 건물명이 붙은 경우 감지
    road_pattern = _re.match(
        r'^(.+(?:로|길|대로)\s*\d+(?:-\d+)?)\s+([가-힣A-Za-z\(\)·\.\s]{2,})$',
        location.strip()
    )
    if road_pattern:
        addr_part  = road_pattern.group(1).strip()
        bldg_part  = road_pattern.group(2).strip()
        if not building_hint:
            building_hint = bldg_part
        location = addr_part
        print(f"[geocode] 주소/건물명 분리: '{addr_part}' / '{bldg_part}'")

    print(f"[geocode] 입력: '{location}'" + (f" / 건물힌트: '{building_hint}'" if building_hint else ""))

    # ── 0순위: building_hint 키워드검색 → 정확한 좌표·지번 ──────────────
    # 사용자가 건물명을 선택했을 때 해당 건물의 정확한 지번 확보
    # 단, 힌트의 시군구코드가 입력 주소와 다르면 무시 (엉뚱한 건물 방지)
    hint_jibun = {}
    if building_hint:
        hint_docs = _keyword_search(building_hint, size=1)
        if hint_docs:
            hint_addr_name = hint_docs[0].get("address_name", "")
            hint_addr_info = _address_search(hint_addr_name)
            if hint_addr_info and hint_addr_info.get("bun"):
                hint_sigungu = hint_addr_info.get("sigungu_cd", "")
                # 입력 주소도 주소검색해서 시군구 코드 비교
                loc_addr_info = _address_search(location)
                loc_sigungu   = loc_addr_info.get("sigungu_cd", "") if loc_addr_info else ""
                # 시군구가 일치하거나 입력 주소에서 코드를 못 가져온 경우만 힌트 사용
                if not loc_sigungu or hint_sigungu == loc_sigungu:
                    hint_jibun = {
                        "sigungu_cd": hint_sigungu,
                        "bjdong_cd":  hint_addr_info.get("bjdong_cd", ""),
                        "bun":        hint_addr_info.get("bun",       ""),
                        "ji":         hint_addr_info.get("ji",        ""),
                    }
                    print(f"[geocode] 건물힌트 지번: {hint_addr_name} "
                          f"→ bun={hint_jibun['bun']} bjdong={hint_jibun['bjdong_cd']}")
                else:
                    print(f"[geocode] 건물힌트 지역 불일치 무시 "
                          f"(힌트:{hint_sigungu} ≠ 입력:{loc_sigungu})")
            else:
                hint_lat = float(hint_docs[0].get("y", 0))
                hint_lng = float(hint_docs[0].get("x", 0))
                if hint_lat and hint_lng:
                    hint_jibun = _coord2jibun(hint_lat, hint_lng)
                    print(f"[geocode] 건물힌트 역지오코딩: bun={hint_jibun.get('bun')} "
                          f"bjdong={hint_jibun.get('bjdong_cd')}")

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

        # 지번 보완 우선순위: hint_jibun > addr_info (addr_info는 이미 역지오코딩 포함)
        if hint_jibun:
            final_sigungu = hint_jibun.get("sigungu_cd", "")
            final_bjdong  = hint_jibun.get("bjdong_cd",  "")
            final_bun     = hint_jibun.get("bun",        "")
            final_ji      = hint_jibun.get("ji",         "")
            print(f"[geocode] 힌트 지번 적용: bun={final_bun} bjdong={final_bjdong}")
        else:
            final_sigungu = addr_info.get("sigungu_cd", "")
            final_bjdong  = addr_info.get("bjdong_cd",  "")
            final_bun     = addr_info.get("bun",        "")
            final_ji      = addr_info.get("ji",         "")

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
            sigungu_cd=final_sigungu,
            bjdong_cd =final_bjdong,
            bun       =final_bun,
            ji        =final_ji,
        )

        # 토지·산업용·업무용·상업용 → Vworld 공시지가 조회
        if result.property_category in ("토지", "산업용", "업무용", "상업용"):
            _attach_land_info(result)

        print(f"[geocode] ✅ 완료: '{result.place_name}' / "
              f"{result.property_category}/{result.category_detail} "
              f"({result.category_source})")
        return result

    # ── 2순위: 키워드검색 폴백 ───────────────────────────────────────────
    print(f"[geocode] 주소검색 실패 → 키워드검색 폴백")
    # 주소검색 실패 시 building_hint로 키워드검색 시도 (더 정확)
    docs = []
    if building_hint:
        docs = _keyword_search(building_hint, size=3)
        if docs:
            print(f"[geocode] 건물힌트 키워드검색 성공: '{building_hint}'")
    if not docs:
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

        # 토지·산업용·업무용·상업용 → Vworld 공시지가 조회
        if result.property_category in ("토지", "산업용", "업무용", "상업용"):
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

    # 위치 우선순위:
    # 1. raw_inputs["address"] — 사용자가 입력한 원본 주소 (가장 정확)
    # 2. location_normalized   — LLM이 파싱한 위치 (축약 가능성 있음)
    # 3. location_raw          — 원본 쿼리
    raw_inputs = _g(state, "raw_inputs") or {}
    raw_address = raw_inputs.get("address", "") if isinstance(raw_inputs, dict) else ""

    location = (raw_address
                or getattr(intent, "location_normalized", "")
                or getattr(intent, "location_raw", ""))
    if not location:
        return _s(state, "error", "geocoding_node: 위치 정보 없음")

    if raw_address and raw_address != getattr(intent, "location_normalized", ""):
        print(f"[geocoding_node] 원본 주소 사용: '{raw_address}' "
              f"(LLM 파싱: '{getattr(intent, 'location_normalized', '')}')")

    llm_category  = getattr(intent, "category", "")
    building_hint = _g(state, "building_name", "") or ""
    result = geocode(location, category=llm_category, building_hint=building_hint)

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


def geocode_cached(location: str, category: str = "", building_hint: str = "") -> Optional[GeocodingResult]:
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