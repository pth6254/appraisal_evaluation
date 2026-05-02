"""
test_listing_tool.py — listing_tool 단위 테스트

data/sample_listings.csv 를 실제 로드해 검증 (외부 API 없음).
"""

import pytest
from schemas.property_listing import PropertyListing
from schemas.property_query import PropertyQuery
from tools.listing_tool import (
    _load_listings,
    _match_area,
    _match_budget,
    _match_property_type,
    _match_region,
    count_listings,
    search_listings,
)


# ─────────────────────────────────────────
#  픽스처
# ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_cache():
    """각 테스트 전에 lru_cache를 비워 독립성 보장."""
    _load_listings.cache_clear()
    yield
    _load_listings.cache_clear()


def _query(**kwargs) -> PropertyQuery:
    defaults = {"intent": "recommendation"}
    defaults.update(kwargs)
    return PropertyQuery(**defaults)


def _listing(**kwargs) -> PropertyListing:
    defaults = {
        "listing_id":    "T001",
        "address":       "서울시 테스트구 테스트동 1",
        "property_type": "주거용",
        "asking_price":  1_000_000_000,
    }
    defaults.update(kwargs)
    return PropertyListing(**defaults)


# ─────────────────────────────────────────
#  CSV 로드 검증
# ─────────────────────────────────────────

class TestLoadListings:
    def test_loads_nonempty(self):
        listings = _load_listings()
        assert len(listings) >= 30, f"샘플 매물이 30개 미만: {len(listings)}개"

    def test_all_are_property_listing(self):
        for l in _load_listings():
            assert isinstance(l, PropertyListing)

    def test_all_have_required_fields(self):
        for l in _load_listings():
            assert l.listing_id
            assert l.address
            assert l.property_type
            assert l.asking_price > 0

    def test_required_regions_present(self):
        regions = {l.region for l in _load_listings() if l.region}
        required = {"마포구", "서대문구", "강서구", "성동구", "송파구", "강남구", "서초구", "영등포구"}
        missing = required - regions
        assert not missing, f"누락된 지역: {missing}"

    def test_contains_commercial(self):
        commercial = [l for l in _load_listings() if l.property_type == "상업용"]
        assert len(commercial) >= 3

    def test_optional_fields_parsed_correctly(self):
        listings = _load_listings()
        # 주거용 매물은 jeonse_price가 있어야 함
        residential = [l for l in listings if l.property_type == "주거용"]
        assert any(l.jeonse_price is not None for l in residential)
        # 상업용 매물은 jeonse_price가 없어야 함
        commercial = [l for l in listings if l.property_type == "상업용"]
        assert all(l.jeonse_price is None for l in commercial)

    def test_lat_lng_present_for_all(self):
        for l in _load_listings():
            assert l.lat is not None and l.lng is not None

    def test_cached_after_first_load(self):
        first  = _load_listings()
        second = _load_listings()
        assert first is second   # 같은 객체 (캐시 반환)


class TestCountListings:
    def test_matches_load_count(self):
        assert count_listings() == len(_load_listings())

    def test_at_least_30(self):
        assert count_listings() >= 30


# ─────────────────────────────────────────
#  필터 헬퍼 단위 테스트
# ─────────────────────────────────────────

class TestMatchRegion:
    def test_no_filter_passes_all(self):
        assert _match_region(_listing(region="마포구"), None) is True

    def test_exact_match(self):
        assert _match_region(_listing(region="마포구"), "마포구") is True

    def test_subset_match(self):
        assert _match_region(_listing(region="서울시 마포구"), "마포구") is True

    def test_no_match(self):
        assert _match_region(_listing(region="강남구"), "마포구") is False

    def test_no_region_on_listing(self):
        assert _match_region(_listing(region=None), "마포구") is False


class TestMatchPropertyType:
    def test_no_filter_passes_all(self):
        assert _match_property_type(_listing(property_type="주거용"), None) is True

    def test_exact_match(self):
        assert _match_property_type(_listing(property_type="주거용"), "주거용") is True

    def test_mismatch(self):
        assert _match_property_type(_listing(property_type="상업용"), "주거용") is False


class TestMatchBudget:
    def test_no_filter_passes_all(self):
        assert _match_budget(_listing(asking_price=1_000_000_000), None, None) is True

    def test_within_range(self):
        assert _match_budget(_listing(asking_price=1_000_000_000),
                             800_000_000, 1_200_000_000) is True

    def test_below_min(self):
        assert _match_budget(_listing(asking_price=500_000_000),
                             800_000_000, None) is False

    def test_above_max(self):
        assert _match_budget(_listing(asking_price=1_500_000_000),
                             None, 1_200_000_000) is False

    def test_exactly_at_min(self):
        assert _match_budget(_listing(asking_price=800_000_000),
                             800_000_000, None) is True

    def test_exactly_at_max(self):
        assert _match_budget(_listing(asking_price=1_200_000_000),
                             None, 1_200_000_000) is True


class TestMatchArea:
    def test_no_filter_passes_all(self):
        assert _match_area(_listing(), None) is True

    def test_within_tolerance(self):
        l = _listing(area_m2=84.0)
        assert _match_area(l, 84.0)  is True   # ±0%
        assert _match_area(l, 75.0)  is True   # 84 ÷ 75 ≈ 1.12 — 12% → 30% 이내
        assert _match_area(l, 100.0) is True   # 84 ÷ 100 = 0.84 — 16% → 30% 이내

    def test_outside_tolerance(self):
        l = _listing(area_m2=84.0)
        assert _match_area(l, 30.0)  is False  # 64% 차이
        assert _match_area(l, 200.0) is False  # 138% 차이

    def test_listing_with_no_area_passes(self):
        assert _match_area(_listing(area_m2=None), 84.0) is True

    def test_tolerance_boundary(self):
        # 쿼리 면적 84㎡ 기준: 허용 구간 = [84×0.70, 84×1.30] = [58.8, 109.2]
        # 경계값 매물이 통과해야 한다.
        l_lo = _listing(area_m2=84.0 * 0.70)   # 58.8 — 정확히 하단 경계
        l_hi = _listing(area_m2=84.0 * 1.30)   # 109.2 — 정확히 상단 경계
        assert _match_area(l_lo, 84.0) is True
        assert _match_area(l_hi, 84.0) is True


# ─────────────────────────────────────────
#  search_listings 통합 테스트
# ─────────────────────────────────────────

class TestSearchListings:
    def test_no_filter_returns_results(self):
        results = search_listings(_query())
        assert len(results) > 0

    def test_default_limit_20(self):
        results = search_listings(_query())
        assert len(results) <= 20

    def test_custom_limit(self):
        results = search_listings(_query(), limit=5)
        assert len(results) <= 5

    def test_limit_larger_than_dataset(self):
        total   = count_listings()
        results = search_listings(_query(), limit=total + 100)
        assert len(results) == total

    def test_sorted_by_price_ascending(self):
        results = search_listings(_query(), limit=100)
        prices  = [r.asking_price for r in results]
        assert prices == sorted(prices)

    def test_region_filter(self):
        results = search_listings(_query(region="마포구"), limit=50)
        assert len(results) > 0
        for r in results:
            assert r.region and "마포구" in r.region

    def test_region_gangnam(self):
        results = search_listings(_query(region="강남구"), limit=50)
        assert len(results) > 0
        for r in results:
            assert r.region and "강남구" in r.region

    def test_property_type_residential(self):
        results = search_listings(_query(property_type="주거용"), limit=50)
        assert len(results) > 0
        assert all(r.property_type == "주거용" for r in results)

    def test_property_type_commercial(self):
        results = search_listings(_query(property_type="상업용"), limit=50)
        assert len(results) >= 3
        assert all(r.property_type == "상업용" for r in results)

    def test_budget_max_filter(self):
        budget_max = 800_000_000   # 8억
        results    = search_listings(_query(budget_max=budget_max), limit=50)
        assert len(results) > 0
        assert all(r.asking_price <= budget_max for r in results)

    def test_budget_min_filter(self):
        budget_min = 2_000_000_000   # 20억
        results    = search_listings(_query(budget_min=budget_min), limit=50)
        assert len(results) > 0
        assert all(r.asking_price >= budget_min for r in results)

    def test_budget_range_filter(self):
        lo, hi  = 600_000_000, 1_000_000_000
        results = search_listings(_query(budget_min=lo, budget_max=hi), limit=50)
        assert len(results) > 0
        for r in results:
            assert lo <= r.asking_price <= hi

    def test_area_filter(self):
        results = search_listings(_query(area_m2=84.0), limit=50)
        assert len(results) > 0
        for r in results:
            if r.area_m2:
                assert 84.0 * 0.70 <= r.area_m2 <= 84.0 * 1.30

    def test_combined_filter(self):
        results = search_listings(_query(
            region="강남구",
            property_type="주거용",
            budget_max=3_000_000_000,
        ), limit=50)
        assert len(results) > 0
        for r in results:
            assert "강남구" in (r.region or "")
            assert r.property_type == "주거용"
            assert r.asking_price <= 3_000_000_000

    def test_no_results_for_impossible_criteria(self):
        # 예산 1만원 이하 → 해당 매물 없음
        results = search_listings(_query(budget_max=10_000), limit=50)
        assert results == []

    def test_unknown_region_returns_empty(self):
        results = search_listings(_query(region="존재하지않는구"), limit=50)
        assert results == []

    def test_returns_property_listing_instances(self):
        results = search_listings(_query(), limit=5)
        for r in results:
            assert isinstance(r, PropertyListing)
