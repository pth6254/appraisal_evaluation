"""
test_schemas.py — schemas 패키지 Pydantic 모델 단위 테스트
"""

import pytest
from schemas.property_query import PropertyQuery
from schemas.appraisal_result import AppraisalResult, ComparableTransaction
from schemas.property_listing import PropertyListing
from schemas.recommendation_result import RecommendationResult


class TestPropertyQuery:
    def test_minimal(self):
        q = PropertyQuery(intent="price_analysis")
        assert q.intent == "price_analysis"
        assert q.region is None
        assert q.area_m2 is None

    def test_full_fields(self):
        q = PropertyQuery(
            intent="buy_decision",
            property_type="주거용",
            region="마포구",
            complex_name="마포래미안푸르지오",
            area_m2=84.0,
            asking_price=1_200_000_000,
            purpose="live",
            budget_min=800_000_000,
            budget_max=1_300_000_000,
        )
        assert q.area_m2 == 84.0
        assert q.asking_price == 1_200_000_000

    def test_invalid_intent_raises(self):
        with pytest.raises(Exception):
            PropertyQuery(intent="invalid_intent_value")


class TestComparableTransaction:
    def test_defaults(self):
        c = ComparableTransaction()
        assert c.complex_name is None
        assert c.match_level is None

    def test_valid_match_levels(self):
        for level in ["same_complex", "same_dong", "same_gu", "nearby", "fallback"]:
            c = ComparableTransaction(match_level=level)
            assert c.match_level == level

    def test_invalid_match_level_raises(self):
        with pytest.raises(Exception):
            ComparableTransaction(match_level="unknown_level")


class TestAppraisalResult:
    def test_defaults(self):
        r = AppraisalResult(judgement="적정")
        assert r.estimated_price is None
        assert r.confidence == 0.0
        assert r.comparables == []
        assert r.warnings == []
        assert r.data_source == []

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            AppraisalResult(judgement="", confidence=1.5)
        with pytest.raises(Exception):
            AppraisalResult(judgement="", confidence=-0.1)

    def test_full_construction(self):
        r = AppraisalResult(
            estimated_price=500_000_000,
            low_price=450_000_000,
            high_price=550_000_000,
            asking_price=520_000_000,
            gap_rate=0.04,
            judgement="소폭 고평가",
            confidence=0.75,
            comparables=[ComparableTransaction(deal_price=500_000_000, match_level="same_complex")],
            warnings=["실거래 3건 미만"],
            data_source=["국토부 실거래가"],
        )
        assert r.gap_rate == 0.04
        assert len(r.comparables) == 1
        assert r.comparables[0].deal_price == 500_000_000


class TestPropertyListing:
    def test_minimal_required(self):
        listing = PropertyListing(
            listing_id="test-001",
            address="서울시 마포구 아현동 123",
            property_type="주거용",
            asking_price=900_000_000,
        )
        assert listing.listing_id == "test-001"
        assert listing.lat is None

    def test_optional_fields(self):
        listing = PropertyListing(
            listing_id="test-002",
            address="서울시 서초구 반포동 1",
            property_type="주거용",
            asking_price=2_000_000_000,
            area_m2=84.5,
            floor=15,
            built_year=2021,
            lat=37.5,
            lng=127.0,
            station_distance_m=250,
        )
        assert listing.area_m2 == 84.5
        assert listing.station_distance_m == 250


class TestRecommendationResult:
    def _make_listing(self):
        return PropertyListing(
            listing_id="rec-001",
            address="서울 마포구 신촌동 1",
            property_type="주거용",
            asking_price=800_000_000,
        )

    def test_defaults(self):
        r = RecommendationResult(listing=self._make_listing())
        assert r.total_score == 0.0
        assert r.reasons == []
        assert r.risks == []
        assert r.appraisal is None

    def test_mutable_default_isolation(self):
        """두 인스턴스가 reasons/risks 리스트를 공유하지 않아야 함"""
        r1 = RecommendationResult(listing=self._make_listing())
        r2 = RecommendationResult(listing=self._make_listing())
        r1.reasons.append("이유1")
        assert r2.reasons == []

    def test_with_appraisal(self):
        appraisal = AppraisalResult(judgement="저평가", confidence=0.8)
        r = RecommendationResult(
            listing=self._make_listing(),
            appraisal=appraisal,
            total_score=8.5,
            recommendation_label="적극 추천",
            reasons=["가격 저평가"],
        )
        assert r.appraisal.judgement == "저평가"
        assert r.total_score == 8.5


class TestSchemasPackageInit:
    def test_top_level_imports(self):
        import schemas
        assert hasattr(schemas, "PropertyQuery")
        assert hasattr(schemas, "AppraisalResult")
        assert hasattr(schemas, "ComparableTransaction")
        assert hasattr(schemas, "PropertyListing")
        assert hasattr(schemas, "RecommendationResult")
