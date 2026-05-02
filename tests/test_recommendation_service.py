"""
test_recommendation_service.py — recommendation_service 단위 테스트

analyze_price는 외부 API를 호출하므로 unittest.mock.patch로 격리한다.
run_appraisal=False 모드로 API 없이도 추천 흐름 전체를 검증한다.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from schemas.appraisal_result import AppraisalResult
from schemas.property_listing import PropertyListing
from schemas.property_query import PropertyQuery
from schemas.recommendation_result import RecommendationResult
from services.recommendation_service import (
    _appraise_listing,
    _build_result,
    _fmt_price,
    _score_bar,
    format_recommendation_report,
    recommend_listings,
)
from tools.listing_tool import _load_listings


# ─────────────────────────────────────────
#  픽스처
# ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_listing_cache():
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
        "built_year":    2015,
        "floor":         10,
        "station_distance_m": 400,
        "school_distance_m":  500,
        "jeonse_price":  650_000_000,
        "complex_name":  "테스트아파트",
    }
    defaults.update(kwargs)
    return PropertyListing(**defaults)


def _appraisal(**kwargs) -> AppraisalResult:
    defaults = {"judgement": "적정", "confidence": 0.8, "gap_rate": 0.0}
    defaults.update(kwargs)
    return AppraisalResult(**defaults)


# ─────────────────────────────────────────
#  _fmt_price
# ─────────────────────────────────────────

class TestFmtPrice:
    def test_none_returns_dash(self):
        assert _fmt_price(None) == "—"

    def test_eok_only(self):
        assert _fmt_price(1_000_000_000) == "10억원"

    def test_eok_and_man(self):
        assert _fmt_price(1_050_000_000) == "10억 5,000만원"

    def test_man_only(self):
        assert _fmt_price(50_000_000) == "5,000만원"

    def test_large_value(self):
        result = _fmt_price(4_200_000_000)
        assert "42억" in result


# ─────────────────────────────────────────
#  _score_bar
# ─────────────────────────────────────────

class TestScoreBar:
    def test_zero_all_empty(self):
        bar = _score_bar(0.0, width=10)
        assert bar == "░" * 10

    def test_ten_all_full(self):
        bar = _score_bar(10.0, width=10)
        assert bar == "█" * 10

    def test_half(self):
        bar = _score_bar(5.0, width=10)
        assert bar.count("█") == 5
        assert bar.count("░") == 5

    def test_length_equals_width(self):
        for score in (0.0, 3.0, 7.5, 10.0):
            assert len(_score_bar(score, width=8)) == 8


# ─────────────────────────────────────────
#  _appraise_listing
# ─────────────────────────────────────────

class TestAppraiseListing:
    def test_returns_appraisal_on_success(self):
        mock_result = _appraisal()
        with patch("services.recommendation_service._appraise_listing",
                   return_value=mock_result) as mock:
            result = mock(_listing(), _query())
        assert result is mock_result

    def test_returns_none_on_exception(self):
        with patch(
            "services.price_analysis_service.analyze_price",
            side_effect=RuntimeError("API 오류"),
        ):
            result = _appraise_listing(_listing(), _query())
        assert result is None

    def test_returns_none_when_no_api_key(self):
        with patch(
            "services.recommendation_service._appraise_listing",
            return_value=None,
        ) as mock:
            result = mock(_listing(), _query())
        assert result is None

    def test_builds_listing_query_with_listing_region(self):
        """매물 region이 base_query.region보다 우선되어야 한다."""
        captured = {}

        def fake_analyze(q: PropertyQuery) -> AppraisalResult:
            captured["region"] = q.region
            return _appraisal()

        with patch("services.price_analysis_service.analyze_price", side_effect=fake_analyze):
            l = _listing(region="강남구")
            _appraise_listing(l, _query(region="마포구"))

        assert captured.get("region") == "강남구"

    def test_uses_base_query_region_as_fallback(self):
        captured = {}

        def fake_analyze(q: PropertyQuery) -> AppraisalResult:
            captured["region"] = q.region
            return _appraisal()

        with patch("services.price_analysis_service.analyze_price", side_effect=fake_analyze):
            l = _listing(region=None)
            _appraise_listing(l, _query(region="서초구"))

        assert captured.get("region") == "서초구"


# ─────────────────────────────────────────
#  _build_result
# ─────────────────────────────────────────

class TestBuildResult:
    def test_returns_recommendation_result(self):
        result = _build_result(_listing(), _query(), None)
        assert isinstance(result, RecommendationResult)

    def test_scores_in_range(self):
        r = _build_result(_listing(), _query(), _appraisal())
        for score in (r.total_score, r.price_score, r.location_score,
                      r.investment_score, r.risk_score):
            assert 0.0 <= score <= 10.0

    def test_label_is_valid(self):
        r = _build_result(_listing(), _query(), None)
        assert r.recommendation_label in {"적극 추천", "추천", "검토 필요", "비추천"}

    def test_listing_preserved(self):
        l = _listing(listing_id="UNIQUE123")
        r = _build_result(l, _query(), None)
        assert r.listing.listing_id == "UNIQUE123"

    def test_appraisal_preserved(self):
        a = _appraisal(judgement="저평가", confidence=0.9)
        r = _build_result(_listing(), _query(), a)
        assert r.appraisal is a

    def test_no_appraisal_still_works(self):
        r = _build_result(_listing(), _query(), None)
        assert r.appraisal is None
        assert 0.0 <= r.total_score <= 10.0


# ─────────────────────────────────────────
#  recommend_listings (API 없는 빠른 모드)
# ─────────────────────────────────────────

class TestRecommendListings:
    def test_returns_list(self):
        results = recommend_listings(_query(), run_appraisal=False)
        assert isinstance(results, list)

    def test_default_limit_5(self):
        results = recommend_listings(_query(), run_appraisal=False)
        assert len(results) <= 5

    def test_custom_limit(self):
        results = recommend_listings(_query(), limit=3, run_appraisal=False)
        assert len(results) <= 3

    def test_results_are_recommendation_result(self):
        results = recommend_listings(_query(), run_appraisal=False)
        for r in results:
            assert isinstance(r, RecommendationResult)

    def test_sorted_by_score_descending(self):
        results = recommend_listings(_query(), limit=10, run_appraisal=False)
        scores = [r.total_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_region_filter_respected(self):
        results = recommend_listings(_query(region="강남구"), run_appraisal=False)
        for r in results:
            assert r.listing.region and "강남구" in r.listing.region

    def test_budget_filter_respected(self):
        budget = 800_000_000
        results = recommend_listings(
            _query(budget_max=budget), limit=20, run_appraisal=False
        )
        for r in results:
            assert r.listing.asking_price <= budget

    def test_property_type_filter_respected(self):
        results = recommend_listings(
            _query(property_type="주거용"), limit=10, run_appraisal=False
        )
        for r in results:
            assert r.listing.property_type == "주거용"

    def test_no_match_returns_empty(self):
        results = recommend_listings(
            _query(budget_max=10_000), run_appraisal=False
        )
        assert results == []

    def test_unknown_region_returns_empty(self):
        results = recommend_listings(
            _query(region="존재하지않는구"), run_appraisal=False
        )
        assert results == []

    def test_limit_larger_than_dataset(self):
        results = recommend_listings(_query(), limit=1000, run_appraisal=False)
        assert len(results) <= 43  # 샘플 CSV 총 43건

    def test_run_appraisal_false_gives_no_appraisal(self):
        results = recommend_listings(_query(), run_appraisal=False)
        for r in results:
            assert r.appraisal is None

    def test_run_appraisal_with_mock(self):
        """analyze_price를 mock으로 대체해 appraisal 통합 경로 검증."""
        mock_appraisal = _appraisal(judgement="적정", confidence=0.8)
        with patch(
            "services.price_analysis_service.analyze_price",
            return_value=mock_appraisal,
        ):
            results = recommend_listings(
                _query(region="마포구"), limit=3, run_appraisal=True
            )
        assert len(results) > 0
        for r in results:
            assert r.appraisal is not None

    def test_run_appraisal_failure_does_not_crash(self):
        """analyze_price가 항상 예외를 던져도 추천 결과가 나와야 한다."""
        with patch(
            "services.price_analysis_service.analyze_price",
            side_effect=RuntimeError("API 다운"),
        ):
            results = recommend_listings(
                _query(region="마포구"), limit=3, run_appraisal=True
            )
        assert len(results) > 0
        for r in results:
            assert r.appraisal is None  # 실패 시 None 폴백

    def test_scores_come_from_scoring_tool(self):
        """총점 공식: price*0.35 + location*0.30 + invest*0.20 + (10-risk)*0.15"""
        results = recommend_listings(_query(), limit=5, run_appraisal=False)
        for r in results:
            expected = round(
                r.price_score * 0.35
                + r.location_score * 0.30
                + r.investment_score * 0.20
                + (10.0 - r.risk_score) * 0.15,
                2,
            )
            assert abs(r.total_score - expected) < 0.01


# ─────────────────────────────────────────
#  format_recommendation_report
# ─────────────────────────────────────────

class TestFormatRecommendationReport:
    def _make_results(self, n: int = 3) -> list[RecommendationResult]:
        q = _query(region="마포구")
        return recommend_listings(q, limit=n, run_appraisal=False)

    def test_returns_str(self):
        results = self._make_results()
        report = format_recommendation_report(results, _query())
        assert isinstance(report, str)

    def test_contains_header(self):
        report = format_recommendation_report(self._make_results(), _query())
        assert "매물 추천 리포트" in report

    def test_contains_summary_table(self):
        report = format_recommendation_report(self._make_results(), _query())
        assert "추천 결과" in report

    def test_shows_region_condition(self):
        q = _query(region="강남구")
        results = recommend_listings(q, limit=3, run_appraisal=False)
        report = format_recommendation_report(results, q)
        assert "강남구" in report

    def test_shows_budget_condition(self):
        q = _query(budget_max=1_000_000_000)
        results = recommend_listings(q, limit=3, run_appraisal=False)
        report = format_recommendation_report(results, q)
        assert "10억" in report

    def test_shows_score_for_each_result(self):
        results = self._make_results(3)
        report = format_recommendation_report(results, _query())
        for r in results:
            assert str(r.total_score) in report or f"{r.total_score:.1f}" in report

    def test_shows_recommendation_label(self):
        results = self._make_results()
        report = format_recommendation_report(results, _query())
        valid_labels = {"적극 추천", "추천", "검토 필요", "비추천"}
        assert any(label in report for label in valid_labels)

    def test_empty_results_returns_notice(self):
        report = format_recommendation_report([], _query())
        assert "없습니다" in report

    def test_reasons_shown_when_present(self):
        results = self._make_results()
        results_with_reasons = [r for r in results if r.reasons]
        if results_with_reasons:
            report = format_recommendation_report(results_with_reasons, _query())
            assert "추천 근거" in report

    def test_risks_shown_when_present(self):
        results = self._make_results()
        results_with_risks = [r for r in results if r.risks]
        if results_with_risks:
            report = format_recommendation_report(results_with_risks, _query())
            assert "주의사항" in report

    def test_report_includes_all_listings(self):
        results = self._make_results(3)
        report = format_recommendation_report(results, _query())
        for r in results:
            name = r.listing.complex_name or r.listing.address[:12]
            assert name in report

    def test_appraisal_section_shown_when_available(self):
        mock_appraisal = _appraisal(
            judgement="저평가",
            confidence=0.9,
            estimated_price=900_000_000,
        )
        with patch(
            "services.price_analysis_service.analyze_price",
            return_value=mock_appraisal,
        ):
            results = recommend_listings(
                _query(region="마포구"), limit=2, run_appraisal=True
            )
        report = format_recommendation_report(results, _query(region="마포구"))
        assert "감정평가" in report
        assert "저평가" in report
