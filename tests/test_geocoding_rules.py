"""지오코딩의 LLM 후보와 결정론적 최종값 경계를 검증한다."""

from __future__ import annotations

from types import SimpleNamespace

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
        lambda *args, **kwargs: {"main_purps": "업무시설"},
    )

    resolution = geocoding._resolve_property_category(
        _address_info(),
        confirmed_category="업무용",
        confirmed_detail="사무실",
    )

    assert (resolution.category, resolution.detail, resolution.source) == (
        "업무용", "사무실", "user",
    )
    assert resolution.official_category == "업무용"
    assert resolution.conflict is False


def test_building_register_determines_category(monkeypatch):
    """사용자 확정값이 없으면 건축물대장의 법적 주용도를 사용한다."""
    monkeypatch.setattr(
        building_info,
        "fetch_building_info",
        lambda *args, **kwargs: {"main_purps": "업무시설"},
    )

    resolution = geocoding._resolve_property_category(_address_info())

    assert (resolution.category, resolution.detail, resolution.source) == (
        "업무용", "사무실", "building_register",
    )
    assert resolution.confidence == 0.95


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

    resolution = geocoding._resolve_property_category(
        _address_info(building_name="테헤란센터")
    )

    assert (resolution.category, resolution.detail, resolution.source) == (
        "", "", "unknown",
    )


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


def test_unit_use_overrides_building_main_use(monkeypatch):
    """복합건물은 전체 주용도보다 해당 호실의 전유부 용도를 우선한다."""
    monkeypatch.setattr(
        building_info,
        "fetch_unit_info",
        lambda *args, **kwargs: {"exclusive_area": 40.0, "main_purps": "제1종근린생활시설"},
    )
    monkeypatch.setattr(
        building_info,
        "fetch_building_info",
        lambda *args, **kwargs: {"main_purps": "업무시설"},
    )

    resolution = geocoding._resolve_property_category(
        _address_info(), dong_no="A동", ho_no="101호"
    )

    assert (resolution.category, resolution.detail, resolution.source) == (
        "상업용", "상가", "unit_register",
    )
    assert resolution.unit_use == "제1종근린생활시설"
    assert resolution.building_main_use == "업무시설"
    assert resolution.confidence == 1.0


def test_user_and_official_category_conflict_is_preserved(monkeypatch):
    monkeypatch.setattr(
        building_info,
        "fetch_building_info",
        lambda *args, **kwargs: {"main_purps": "업무시설"},
    )

    resolution = geocoding._resolve_property_category(
        _address_info(),
        confirmed_category="상업용",
        confirmed_detail="상가",
    )

    assert resolution.category == "상업용"
    assert resolution.official_category == "업무용"
    assert resolution.conflict is True
    assert "건축물대장" in resolution.conflict_message


def test_fetch_unit_info_keeps_unit_use(monkeypatch):
    xml = """
    <response><header><resultCode>00</resultCode></header><body><items><item>
      <dongNm>A동</dongNm><hoNm>101</hoNm><excluUseAr>40.5</excluUseAr>
      <mainPurpsCdNm>제1종근린생활시설</mainPurpsCdNm>
    </item></items></body></response>
    """

    class FakeResponse:
        text = xml

        @staticmethod
        def raise_for_status():
            return None

    monkeypatch.setattr(building_info, "MOLIT_API_KEY", "test-key")
    monkeypatch.setattr(building_info.requests, "get", lambda *args, **kwargs: FakeResponse())

    info = building_info.fetch_unit_info(
        "11680", "1168010100", "737", "", "A동", "101호"
    )

    assert info == {
        "exclusive_area": 40.5,
        "main_purps": "제1종근린생활시설",
        "dong_name": "A동",
        "ho_name": "101",
    }


def test_vworld_not_found_status_is_distinguished(monkeypatch):
    class FakeResponse:
        @staticmethod
        def raise_for_status():
            return None

        @staticmethod
        def json():
            return {"response": {"status": "NOT_FOUND"}}

    monkeypatch.setattr(geocoding, "VWORLD_API_KEY", "test-key")
    monkeypatch.setattr(geocoding.requests, "get", lambda *args, **kwargs: FakeResponse())

    info, status = geocoding._fetch_land_info_vworld(37.5, 127.0)

    assert info is None
    assert status == "not_found"


def test_geocode_cache_key_contains_algorithm_version(monkeypatch):
    captured = {}

    def fake_cache_get(namespace, **kwargs):
        captured.update(kwargs)
        return {
            "lat": 37.5,
            "lng": 127.0,
            "property_category": "주거용",
            "category_source": "user",
        }

    monkeypatch.setattr(geocoding, "cache_get", fake_cache_get)

    result = geocoding.geocode_cached("서울 강남구", confirmed_category="주거용")

    assert result is not None
    assert captured["algorithm_version"] == geocoding._GEOCODE_ALGORITHM_VERSION


def test_category_conflict_is_included_in_report_warning():
    from appraisal_report import report_node

    state = {
        "intent": SimpleNamespace(
            category="상업용",
            category_detail="상가",
            area_raw="",
            dong_no="",
            ho_no="",
            floor_inferred=None,
            transaction_type="매매",
            price_max=None,
            price_min=None,
            appraisal_date="",
        ),
        "geocoding_result": {
            "address_name": "서울 강남구 테헤란로 152",
            "category_conflict_message": "선택한 유형과 건축물대장 유형이 다릅니다.",
        },
        "analysis_result": {
            "estimated_value": 100_000,
            "value_min": 90_000,
            "value_max": 110_000,
            "valuation_method": "비교사례법",
        },
    }

    result = report_node(state)

    assert "## 유형 확인 필요" in result["final_report"]
    assert result["report_output"].structured.warnings == [
        "선택한 유형과 건축물대장 유형이 다릅니다."
    ]


def test_exact_place_candidates_are_scored(monkeypatch):
    monkeypatch.setattr(
        geocoding,
        "_keyword_search",
        lambda *args, **kwargs: [{
            "place_name": "테스트아파트",
            "category_name": "부동산 > 주거시설 > 아파트",
            "road_address_name": "서울 강남구 테헤란로 152",
            "x": "127.036508620542",
            "y": "37.5000242405515",
        }],
    )

    kakao, category, detail, score = geocoding._get_category_from_exact_place(
        "테스트아파트",
        expected_address="서울 강남구 테헤란로 152",
        lat=37.5000242405515,
        lng=127.036508620542,
    )

    assert (category, detail) == ("주거용", "아파트")
    assert kakao.endswith("아파트")
    assert score >= 55


def test_close_competing_place_categories_are_not_auto_selected(monkeypatch):
    common = {
        "place_name": "테스트타워",
        "road_address_name": "서울 강남구 테헤란로 152",
        "x": "127.036508620542",
        "y": "37.5000242405515",
    }
    monkeypatch.setattr(
        geocoding,
        "_keyword_search",
        lambda *args, **kwargs: [
            {**common, "category_name": "부동산 > 주거시설 > 아파트"},
            {**common, "category_name": "가정,생활 > 상가"},
        ],
    )

    _, category, detail, score = geocoding._get_category_from_exact_place(
        "테스트타워",
        expected_address="서울 강남구 테헤란로 152",
        lat=37.5000242405515,
        lng=127.036508620542,
    )

    assert (category, detail) == ("", "")
    assert score >= 55
