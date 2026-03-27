"""
building_info.py — 건축HUB 건축물대장정보 서비스
================================================
국토교통부_건축HUB_건축물대장정보 서비스 (data.go.kr)

엔드포인트:
  기본개요  : getArchHubBrBasisOulnInfo   — 건폐율·용적률·건물명
  총괄표제부: getArchHubBrRecapTitleInfo  — 연면적·대지면적·주용도·사용승인일
  표제부    : getArchHubBrTitleInfo       — 동별 연면적·구조·지상층수·건축연도

파라미터 (공통):
  serviceKey : 인증키 (MOLIT_API_KEY 동일)
  sigunguCd  : 시군구코드 5자리 (예: 11650 서초구)
  bjdongCd   : 법정동코드 10자리 (카카오 b_code)
  bun        : 지번 본번 4자리 (예: 0001)
  ji         : 지번 부번 4자리 (없으면 0000)
  numOfRows  : 조회 건수
  _type      : xml (기본) 또는 json

응답 주요 필드 (총괄표제부):
  platPlc    : 대지위치
  bldNm      : 건물명
  platArea   : 대지면적 (㎡)
  archArea   : 건축면적 (㎡)
  totArea    : 연면적 (㎡)
  mainPurpsCdNm : 주용도코드명 (공장, 창고, 업무시설 등)
  useAprDay  : 사용승인일 (YYYYMMDD)
  grndFlrCnt : 지상층수
  strctCdNm  : 주구조코드명 (철근콘크리트, 철골조 등)
  crtnDay    : 생성일자

.env:
  MOLIT_API_KEY  (실거래가 API 키와 동일)
"""

from __future__ import annotations

import os
from typing import Optional
import xml.etree.ElementTree as ET

import requests
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

MOLIT_API_KEY = os.getenv("MOLIT_API_KEY", "")

# 건축HUB 기본 URL
ARCH_HUB_BASE = "https://apis.data.go.kr/1613000/ArchHubBldRgstService"

# 서비스별 엔드포인트
ENDPOINTS = {
    "기본개요":   f"{ARCH_HUB_BASE}/getArchHubBrBasisOulnInfo",
    "총괄표제부": f"{ARCH_HUB_BASE}/getArchHubBrRecapTitleInfo",
    "표제부":     f"{ARCH_HUB_BASE}/getArchHubBrTitleInfo",
}


def _safe_key() -> str:
    return MOLIT_API_KEY.replace("+", "%2B").replace("=", "%3D")


def _call_api(endpoint: str, sigungu_cd: str, bjdong_cd: str,
              bun: str, ji: str = "", rows: int = 5) -> list[dict]:
    """
    건축HUB API 호출 → item 목록 반환.
    bjdongCd는 5자리 (법정동코드 10자리 중 뒤 5자리 사용).
    """
    if not MOLIT_API_KEY:
        print("[building_info] MOLIT_API_KEY 없음")
        return []

    # 법정동코드: 카카오는 10자리, API는 5자리 사용
    bjdong_5 = bjdong_cd[5:] if len(bjdong_cd) == 10 else bjdong_cd

    bun_4 = str(bun).zfill(4) if bun else "0000"
    ji_4  = str(ji).zfill(4)  if ji  else "0000"

    # bjdongCd 유효성 검사 — 00000 이거나 비어있으면 호출 자체를 차단
    # (건축HUB API는 bjdongCd 필수, 잘못된 값이면 500 오류)
    if not bjdong_5 or bjdong_5 == "00000":
        print(f"[building_info] bjdongCd 없음 → 건축물대장 조회 불가 "
              f"(sigungu={sigungu_cd}, bun={bun})")
        return []

    query = (
        f"serviceKey={_safe_key()}"
        f"&sigunguCd={sigungu_cd}"
        f"&bjdongCd={bjdong_5}"
        f"&bun={bun_4}"
        f"&ji={ji_4}"
        f"&numOfRows={rows}"
        f"&pageNo=1"
        f"&_type=xml"
    )
    url = f"{endpoint}?{query}"

    try:
        res = requests.get(url, timeout=10)
        res.raise_for_status()
        root = ET.fromstring(res.text)

        result_code = root.findtext(".//resultCode", "")
        if result_code.lstrip("0") not in ("", "0"):
            msg = root.findtext(".//resultMsg", "")
            print(f"[building_info] API 오류: {result_code} - {msg}")
            return []

        items = root.findall(".//item")
        result = []
        for item in items:
            d = {}
            for child in item:
                d[child.tag] = (child.text or "").strip()
            result.append(d)
        return result

    except requests.Timeout:
        print("[building_info] 타임아웃")
    except requests.HTTPError as e:
        if "500" in str(e):
            print(f"[building_info] 500 오류 — 건축HUB API 활용신청 필요 "
                  f"(data.go.kr → 국토교통부_건축HUB_건축물대장정보 서비스)")
        else:
            print(f"[building_info] HTTP 오류: {e}")
    except Exception as e:
        print(f"[building_info] 오류: {e}")
    return []


def fetch_building_info(
    sigungu_cd: str,
    bjdong_cd: str,
    bun: str,
    ji: str = "",
) -> Optional[dict]:
    """
    건축물대장 총괄표제부 + 표제부 조회.
    총괄표제부: 연면적·대지면적·주용도·사용승인일
    표제부:     동별 구조·지상층수 (총괄표제부에 구조 없을 때 보완)

    반환:
        {
            "tot_area":    연면적 (㎡),
            "arch_area":   건축면적 (㎡),
            "plat_area":   대지면적 (㎡),
            "build_year":  건축연도 (int),
            "strct_cd_nm": 주구조 (철근콘크리트 등),
            "main_purps":  주용도 (공장, 창고 등),
            "floor_cnt":   지상층수,
            "bld_nm":      건물명,
        }
    """
    if not sigungu_cd or not bun:
        print("[building_info] 지번 정보 부족")
        return None

    # ── 표제부 우선 조회 (단독건물·공장·창고에 적합) ─────────────────────
    # 총괄표제부: 집합건물(아파트·상가 등 여러 동) 전용
    # 표제부:     단독건물(공장·창고·단독주택 등) — 면적·구조·건축연도 포함
    title_first = _call_api(
        ENDPOINTS["표제부"], sigungu_cd, bjdong_cd, bun, ji
    )

    if title_first:
        print(f"[building_info] 표제부 조회 성공: {len(title_first)}건")
        recap_items = title_first
    else:
        # 표제부 없으면 총괄표제부 시도 (집합건물)
        recap_items = _call_api(
            ENDPOINTS["총괄표제부"], sigungu_cd, bjdong_cd, bun, ji
        )
        if not recap_items:
            print(f"[building_info] 표제부·총괄표제부 모두 없음 → 기본개요 시도")
            recap_items = _call_api(
                ENDPOINTS["기본개요"], sigungu_cd, bjdong_cd, bun, ji
            )
        if not recap_items:
            print(f"[building_info] 건축물대장 없음: {sigungu_cd} {bjdong_cd} {bun}-{ji}")
            return None

    item = recap_items[0]

    def _f(key: str) -> str:
        return item.get(key, "").strip()

    def _float(key: str) -> float:
        try:
            return float(_f(key) or 0)
        except ValueError:
            return 0.0

    def _int(key: str) -> int:
        try:
            return int(_f(key) or 0)
        except ValueError:
            return 0

    # 표제부 필드명 (단독건물)
    # totArea, archArea 는 공통
    # platArea → 표제부에서는 platArea 또는 siteArea
    tot_area   = _float("totArea")
    arch_area  = _float("archArea")
    plat_area  = _float("platArea") or _float("siteArea") or _float("platPlcArea")

    # 사용승인일 → 건축연도
    # 표제부: useAprDay / 총괄표제부: useAprDay 동일
    use_apr  = _f("useAprDay") or _f("pmsDay")
    crtn_day = _f("crtnDay")
    build_year = 0
    for date_str in [use_apr, crtn_day]:
        if date_str and len(date_str) >= 4:
            try:
                build_year = int(date_str[:4])
                if 1900 < build_year <= 2030:
                    break
            except ValueError:
                pass

    # 구조: 표제부=strctCdNm / 총괄표제부=mainStrctCdNm
    strct_nm   = _f("strctCdNm") or _f("mainStrctCdNm") or _f("strctNm")
    # 주용도: 표제부=mainPurpsCdNm / 기본개요=mainPurpsCdNm
    main_purps = _f("mainPurpsCdNm") or _f("etcPurps") or _f("bldUse")
    floor_cnt  = _int("grndFlrCnt")
    bld_nm     = _f("bldNm")

    # ── 표제부로 이미 조회했으면 별도 보완 불필요 ────────────────────────
    if not strct_nm and ENDPOINTS["표제부"] not in str(recap_items):
        title_items = _call_api(
            ENDPOINTS["표제부"], sigungu_cd, bjdong_cd, bun, ji
        )
        if title_items:
            strct_nm  = title_items[0].get("strctCdNm", "").strip()
            floor_cnt = floor_cnt or int(title_items[0].get("grndFlrCnt", "0") or 0)
            if not tot_area:
                tot_area = float(title_items[0].get("totArea", "0") or 0)

    result = {
        "tot_area":    tot_area,
        "arch_area":   arch_area,
        "plat_area":   plat_area,
        "build_year":  build_year,
        "strct_cd_nm": strct_nm,
        "main_purps":  main_purps,
        "floor_cnt":   floor_cnt,
        "bld_nm":      bld_nm,
    }

    print(
        f"[building_info] ✅ {bld_nm or main_purps} / "
        f"연면적 {tot_area}㎡ / 대지 {plat_area}㎡ / "
        f"건축연도 {build_year} / 구조 {strct_nm}"
    )
    return result


def get_building_area(
    sigungu_cd: str,
    bjdong_cd: str,
    bun: str,
    ji: str = "",
    prefer: str = "tot",
) -> tuple[float, int, str]:
    """
    건물 면적 + 건축연도 + 구조 반환 (단순 인터페이스).

    prefer:
        "tot"  → 연면적 (공장·창고·오피스 감정평가에 적합)
        "arch" → 건축면적
        "plat" → 대지면적 (토지 감정평가에 적합)

    반환: (면적_㎡, 건축연도, 구조명)
    """
    info = fetch_building_info(sigungu_cd, bjdong_cd, bun, ji)
    if not info:
        return 0.0, 0, ""

    area_map = {
        "tot":  info["tot_area"],
        "arch": info["arch_area"],
        "plat": info["plat_area"],
    }
    area = area_map.get(prefer, info["tot_area"])
    return area, info["build_year"], info.get("strct_cd_nm", "")


if __name__ == "__main__":
    if not MOLIT_API_KEY:
        print("⚠️  MOLIT_API_KEY 없음")
    else:
        # 테스트: 서울 강남구 테헤란로 152 (강남파이낸스센터)
        # sigunguCd=11680, bjdongCd=10800, bun=737, ji=0
        tests = [
            ("11680", "1168010800", "737", "0"),   # 강남구 역삼동
            ("11650", "1165010100", "1", "0"),      # 서초구 서초동
        ]
        for s, b, bun, ji in tests:
            print(f"\n📍 시군구:{s} 법정동:{b} 번지:{bun}-{ji}")
            info = fetch_building_info(s, b, bun, ji)
            if info:
                for k, v in info.items():
                    print(f"   {k}: {v}")
            else:
                print("   결과 없음")