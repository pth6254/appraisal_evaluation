"""
test_comparison_service.py — comparison_service 단위 테스트 (Phase 5)
"""

from __future__ import annotations

import pytest

# ─────────────────────────────────────────
#  경로 설정 (conftest가 없는 경우 대비)
# ─────────────────────────────────────────

import os
import sys

_TESTS_DIR    = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT    = os.path.dirname(_TESTS_DIR)
_BACKEND_DIR  = os.path.join(_REPO_ROOT, "backend")
for _p in [_REPO_ROOT, _BACKEND_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)


# ─────────────────────────────────────────
#  픽스처 헬퍼
# ─────────────────────────────────────────

def _make_listing(
    listing_id: str = "L001",
    address: str = "서울시 마포구 공덕동 1",
    property_type: str = "주거용",
    asking_price: int = 500_000_000,
    area_m2: float | None = 84.0,
    jeonse_price: int | None = 350_000_000,
    station_distance_m: int | None = 350,
    complex_name: str | None = "공덕래미안",
    floor: int | None = 10,
    built_year: int | None = 2018,
):
    from schemas.property_listing import PropertyListing
    return PropertyListing(
        listing_id          = listing_id,
        address             = address,
        property_type       = property_type,
        asking_price        = asking_price,
        area_m2             = area_m2,
        jeonse_price        = jeonse_price,
        station_distance_m  = station_distance_m,
        complex_name        = complex_name,
        floor               = floor,
        built_year          = built_year,
    )


def _make_rec(listing, total_score: float = 7.0, label: str = "추천",
              reasons: list | None = None, risks: list | None = None):
    from schemas.recommendation_result import RecommendationResult
    return RecommendationResult(
        listing              = listing,
        total_score          = total_score,
        price_score          = total_score,
        location_score       = total_score,
        investment_score     = total_score,
        risk_score           = 3.0,
        recommendation_label = label,
        reasons              = reasons or ["가격 적정", "역세권"],
        risks                = risks   or ["노후 건물"],
    )


# ─────────────────────────────────────────
#  스키마 테스트
# ─────────────────────────────────────────

class TestComparisonSchemas:
    def test_comparison_input_importable(self):
        from schemas.comparison import ComparisonInput
        assert ComparisonInput is not None

    def test_comparison_result_importable(self):
        from schemas.comparison import ComparisonResult
        assert ComparisonResult is not None

    def test_property_comparison_row_importable(self):
        from schemas.comparison import PropertyComparisonRow
        assert PropertyComparisonRow is not None

    def test_comparison_input_defaults(self):
        from schemas.comparison import ComparisonInput
        l1 = _make_listing("L1")
        l2 = _make_listing("L2", asking_price=600_000_000)
        inp = ComparisonInput(listings=[l1, l2])
        assert inp.recommendation_results is None
        assert inp.simulation_results is None
        assert inp.budget_max is None

    def test_comparison_result_defaults(self):
        from schemas.comparison import ComparisonResult, PropertyComparisonRow
        from schemas.property_listing import PropertyListing
        l = _make_listing()
        row = PropertyComparisonRow(rank=1, listing=l)
        r = ComparisonResult(rows=[row])
        assert r.winner_idx is None
        assert r.decision_report == ""

    def test_property_comparison_row_defaults(self):
        from schemas.comparison import PropertyComparisonRow
        l = _make_listing()
        row = PropertyComparisonRow(rank=1, listing=l)
        assert row.total_score == 0.0
        assert row.is_winner is False
        assert row.highlights == []
        assert row.warnings == []

    def test_schemas_init_exports(self):
        from schemas import ComparisonInput, ComparisonResult, PropertyComparisonRow
        assert ComparisonInput is not None
        assert ComparisonResult is not None
        assert PropertyComparisonRow is not None


# ─────────────────────────────────────────
#  compare_listings 테스트
# ─────────────────────────────────────────

class TestCompareListings:
    def test_importable(self):
        from services.comparison_service import compare_listings
        assert callable(compare_listings)

    def test_empty_listings_raises(self):
        from services.comparison_service import compare_listings
        with pytest.raises(ValueError, match="비교할 매물이 없습니다"):
            compare_listings([])

    def test_single_listing_raises(self):
        from services.comparison_service import compare_listings
        l = _make_listing()
        with pytest.raises(ValueError, match="2개 이상"):
            compare_listings([l])

    def test_returns_comparison_result(self):
        from services.comparison_service import compare_listings
        from schemas.comparison import ComparisonResult
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        result = compare_listings([l1, l2])
        assert isinstance(result, ComparisonResult)

    def test_rows_count_matches_input(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        l3 = _make_listing("L3", asking_price=700_000_000)
        result = compare_listings([l1, l2, l3])
        assert len(result.rows) == 3

    def test_winner_is_marked(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        result = compare_listings([l1, l2])
        winners = [r for r in result.rows if r.is_winner]
        assert len(winners) == 1

    def test_winner_has_highest_score(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        result = compare_listings([l1, l2])
        winner = next(r for r in result.rows if r.is_winner)
        assert winner.total_score == max(r.total_score for r in result.rows)

    def test_rows_sorted_by_score_descending(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        l3 = _make_listing("L3", asking_price=700_000_000)
        result = compare_listings([l1, l2, l3])
        scores = [r.total_score for r in result.rows]
        assert scores == sorted(scores, reverse=True)

    def test_rank_reflects_sort_order(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        result = compare_listings([l1, l2])
        assert result.rows[0].rank == 1
        assert result.rows[1].rank == 2

    def test_winner_idx_zero(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        result = compare_listings([l1, l2])
        assert result.winner_idx == 0

    def test_price_per_m2_computed(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000, area_m2=100.0)
        l2 = _make_listing("L2", asking_price=600_000_000, area_m2=100.0)
        result = compare_listings([l1, l2])
        row1 = next(r for r in result.rows if r.listing.listing_id == "L1")
        assert row1.price_per_m2 == 5_000_000

    def test_price_per_m2_none_without_area(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000, area_m2=None)
        l2 = _make_listing("L2", asking_price=600_000_000, area_m2=None)
        result = compare_listings([l1, l2])
        for row in result.rows:
            assert row.price_per_m2 is None

    def test_jeonse_ratio_computed(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000, jeonse_price=350_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000, jeonse_price=300_000_000)
        result = compare_listings([l1, l2])
        row1 = next(r for r in result.rows if r.listing.listing_id == "L1")
        assert row1.jeonse_ratio == pytest.approx(70.0, abs=0.1)

    def test_jeonse_ratio_none_without_jeonse(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000, jeonse_price=None)
        l2 = _make_listing("L2", asking_price=600_000_000, jeonse_price=None)
        result = compare_listings([l1, l2])
        for row in result.rows:
            assert row.jeonse_ratio is None

    def test_with_recommendation_results_uses_score(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        r1 = _make_rec(l1, total_score=8.0)
        r2 = _make_rec(l2, total_score=6.0)
        result = compare_listings([l1, l2], recommendation_results=[r1, r2])
        winner = next(r for r in result.rows if r.is_winner)
        assert winner.listing.listing_id == "L1"
        assert winner.total_score == pytest.approx(8.0)

    def test_without_recommendation_computes_score(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        result = compare_listings([l1, l2])
        for row in result.rows:
            assert 0.0 <= row.total_score <= 10.0

    def test_highlights_from_recommendations(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        r1 = _make_rec(l1, reasons=["역세권", "신축"])
        r2 = _make_rec(l2, reasons=["학군"])
        result = compare_listings([l1, l2], recommendation_results=[r1, r2])
        row1 = next(r for r in result.rows if r.listing.listing_id == "L1")
        assert "역세권" in row1.highlights

    def test_warnings_from_recommendations(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        r1 = _make_rec(l1, risks=["노후 건물"])
        r2 = _make_rec(l2, risks=[])
        result = compare_listings([l1, l2], recommendation_results=[r1, r2])
        row1 = next(r for r in result.rows if r.listing.listing_id == "L1")
        assert "노후 건물" in row1.warnings

    def test_recommendation_results_shorter_than_listings(self):
        """recommendation_results가 listings보다 짧아도 패딩으로 처리"""
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        l3 = _make_listing("L3", asking_price=700_000_000)
        r1 = _make_rec(l1, total_score=9.0)
        result = compare_listings([l1, l2, l3], recommendation_results=[r1])
        assert len(result.rows) == 3

    def test_decision_report_populated(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        result = compare_listings([l1, l2])
        assert isinstance(result.decision_report, str)
        assert len(result.decision_report) > 0

    def test_three_listings_comparison(self):
        from services.comparison_service import compare_listings
        listings = [
            _make_listing("L1", asking_price=500_000_000),
            _make_listing("L2", asking_price=600_000_000),
            _make_listing("L3", asking_price=700_000_000),
        ]
        result = compare_listings(listings)
        assert len(result.rows) == 3
        winners = [r for r in result.rows if r.is_winner]
        assert len(winners) == 1


# ─────────────────────────────────────────
#  generate_decision_report 테스트
# ─────────────────────────────────────────

class TestGenerateDecisionReport:
    def _make_result(self):
        from services.comparison_service import compare_listings
        l1 = _make_listing("L1", asking_price=500_000_000, complex_name="매물A")
        l2 = _make_listing("L2", asking_price=600_000_000, complex_name="매물B")
        r1 = _make_rec(l1, total_score=8.0, reasons=["역세권", "신축"])
        r2 = _make_rec(l2, total_score=6.5, risks=["노후 건물"])
        return compare_listings([l1, l2], recommendation_results=[r1, r2])

    def test_importable(self):
        from services.comparison_service import generate_decision_report
        assert callable(generate_decision_report)

    def test_returns_string(self):
        from services.comparison_service import generate_decision_report
        result = self._make_result()
        report = generate_decision_report(result)
        assert isinstance(report, str)

    def test_contains_header(self):
        result = self._make_result()
        assert "매물 비교 최종 판단 리포트" in result.decision_report

    def test_contains_disclaimer(self):
        result = self._make_result()
        assert "간이 분석" in result.decision_report

    def test_contains_winner_section(self):
        result = self._make_result()
        assert "최종 추천 매물" in result.decision_report
        assert "🏆" in result.decision_report

    def test_contains_winner_name(self):
        result = self._make_result()
        assert "매물A" in result.decision_report

    def test_contains_summary_table(self):
        result = self._make_result()
        assert "비교 대상" in result.decision_report

    def test_contains_detail_section(self):
        result = self._make_result()
        assert "매물별 상세 비교" in result.decision_report

    def test_winner_mark_in_report(self):
        result = self._make_result()
        assert "1위 🏆" in result.decision_report

    def test_both_listings_mentioned(self):
        result = self._make_result()
        assert "매물A" in result.decision_report
        assert "매물B" in result.decision_report

    def test_scores_in_report(self):
        result = self._make_result()
        assert "8.0" in result.decision_report

    def test_highlights_in_report(self):
        result = self._make_result()
        assert "역세권" in result.decision_report

    def test_warnings_in_report(self):
        result = self._make_result()
        assert "노후 건물" in result.decision_report


# ─────────────────────────────────────────
#  router.run_comparison 테스트
# ─────────────────────────────────────────

class TestRunComparison:
    def test_importable(self):
        from router import run_comparison
        assert callable(run_comparison)

    def test_with_listings_list(self):
        from router import run_comparison
        from schemas.property_listing import PropertyListing
        listings = [
            _make_listing("L1", asking_price=500_000_000),
            _make_listing("L2", asking_price=600_000_000),
        ]
        state = run_comparison(listings=listings)
        assert state.get("result") is not None
        assert not state.get("error")

    def test_with_comparison_input_object(self):
        from router import run_comparison
        from schemas.comparison import ComparisonInput
        inp = ComparisonInput(listings=[
            _make_listing("L1", asking_price=500_000_000),
            _make_listing("L2", asking_price=600_000_000),
        ])
        state = run_comparison(data=inp)
        assert state.get("result") is not None

    def test_with_raw_dict(self):
        from router import run_comparison
        data = {
            "listings": [
                {
                    "listing_id": "L1", "address": "서울시 마포구 1",
                    "property_type": "주거용", "asking_price": 500_000_000,
                },
                {
                    "listing_id": "L2", "address": "서울시 서대문구 1",
                    "property_type": "주거용", "asking_price": 600_000_000,
                },
            ]
        }
        state = run_comparison(data=data)
        assert state.get("result") is not None

    def test_error_on_no_listings(self):
        from router import run_comparison
        state = run_comparison(data={"listings": []})
        assert state.get("error")

    def test_error_on_single_listing(self):
        from router import run_comparison
        listings = [_make_listing("L1", asking_price=500_000_000)]
        state = run_comparison(listings=listings)
        assert state.get("error")

    def test_returns_report_string(self):
        from router import run_comparison
        listings = [
            _make_listing("L1", asking_price=500_000_000),
            _make_listing("L2", asking_price=600_000_000),
        ]
        state = run_comparison(listings=listings)
        assert isinstance(state.get("report"), str)
        assert "매물 비교" in state["report"]

    def test_with_recommendation_results(self):
        from router import run_comparison
        from schemas.comparison import ComparisonInput
        l1 = _make_listing("L1", asking_price=500_000_000)
        l2 = _make_listing("L2", asking_price=600_000_000)
        r1 = _make_rec(l1, total_score=9.0)
        r2 = _make_rec(l2, total_score=5.0)
        inp = ComparisonInput(listings=[l1, l2], recommendation_results=[r1, r2])
        state = run_comparison(data=inp)
        result = state["result"]
        winner = next(r for r in result.rows if r.is_winner)
        assert winner.listing.listing_id == "L1"

    def test_cmp_graph_singleton(self):
        from router import _get_cmp_graph
        g1 = _get_cmp_graph()
        g2 = _get_cmp_graph()
        assert g1 is g2
