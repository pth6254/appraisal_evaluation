"""지오코딩의 LLM 후보와 결정론적 최종값 경계를 검증한다."""

from __future__ import annotations

import building_info
import geocoding


def _address_info(**overrides) -> dict:
    base = {
        "x": "127.036508620542",
        "y": "37.5000242405515",
        "address_name": "서울 강남구 테헤란로 152",
        "road_address_name": "서울 강남구 테헤란로 152",
        "building_name": "강남파이낸스센터",
        "region_1depth": "서울",
        "region_2depth": "강남구",
        "region_3depth": "역삼동",
        "sigungu_cd": "11680",
        "bjdong_cd": "1168010100",
        "bun": "737",
        "ji": "",
    }
    return {**base, **overrides}


def test_user_confirmed_category_has_highest_priority(monkeypatch):
    """UI에서 직접 고른 유형은 LLM·외부 보조 조회로 덮어쓰지 않는다."""
    monkeypatch.setattr(
        building_info,
        "fetch_building_info",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("조회하면 안 됨")),
    )

    category, detail, source, kakao = geocoding._resolve_property_category(
        _address_info(),
        confirmed_category="업무용",
        confirmed_detail="사무실",
    )

    assert (category, detail, source, kakao) == ("업무용", "사무실", "user", "")


def test_building_register_determines_category(monkeypatch):
    """사용자 확정값이 없으면 건축물대장의 법적 주용도를 사용한다."""
    monkeypatch.setattr(
        building_info,
        "fetch_building_info",
        lambda *args, **kwargs: {"main_purps": "업무시설"},
    )

    category, detail, source, _ = geocoding._resolve_property_category(_address_info())

    assert (category, detail, source) == ("업무용", "사무실", "building_register")


def test_nearby_store_cannot_classify_whole_building(monkeypatch):
    """건물 주소 주변의 입점 매장을 건물 자체 용도로 오인하지 않는다."""
    monkeypatch.setattr(building_info, "fetch_building_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        geocoding,
        "_keyword_search",
        lambda *args, **kwargs: [{
            "place_name": "나이키 강남점",
            "category_name": "가정,생활 > 패션 > 의류판매",
            "road_address_name": "서울 강남구 테헤란로 152",
            "x": "127.036508620542",
            "y": "37.5000242405515",
        }],
    )

    category, detail, source, kakao = geocoding._resolve_property_category(
        _address_info(building_name="테헤란센터")
    )

    assert (category, detail, source, kakao) == ("", "", "unknown", "")


def test_llm_category_is_only_hint(monkeypatch):
    """공식 근거가 없을 때 LLM category로 최종 유형을 채우지 않는다."""
    monkeypatch.setattr(
        geocoding,
        "_address_search",
        lambda query: _address_info(building_name="용도미상센터"),
    )
    monkeypatch.setattr(building_info, "fetch_building_info", lambda *args, **kwargs: None)
    monkeypatch.setattr(geocoding, "_keyword_search", lambda *args, **kwargs: [])

    result = geocoding.geocode("서울 강남구 테헤란로 152", category="상업용")

    assert result is not None
    assert result.property_category == ""
    assert result.category_source == "unknown"


def test_building_use_mapping_covers_five_service_types():
    assert geocoding._map_building_use("공동주택") == ("주거용", "아파트")
    assert geocoding._map_building_use("제2종근린생활시설") == ("상업용", "상가")
    assert geocoding._map_building_use("업무시설") == ("업무용", "사무실")
    assert geocoding._map_building_use("창고시설") == ("산업용", "창고")
    assert geocoding._map_building_use("분류되지않은시설") == ("", "")


def test_finance_center_name_is_deterministic_office_rule():
    assert geocoding._map_building_name("강남파이낸스센터") == ("업무용", "사무실")
