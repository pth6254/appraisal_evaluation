"""
test_comparison_ui_smoke.py — 6_매물비교.py 및 4_매물추천.py 변경 smoke 테스트 (Phase 5)

Streamlit 렌더링 없이:
  1. 페이지 파일 컴파일 가능 여부 (SyntaxError 없음)
  2. 필수 키워드/임포트 존재 확인
  3. session_state 연동 로직 확인
  4. 비교 서비스 임포트 확인
  5. 4_매물추천.py 비교 바구니 버튼 삽입 여부 확인
"""

from __future__ import annotations

import ast
import os
import sys

import pytest

# ─────────────────────────────────────────
#  경로 설정
# ─────────────────────────────────────────

_REPO_ROOT  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_CMP_PAGE   = os.path.join(_REPO_ROOT, "frontend", "pages", "6_매물비교.py")
_REC_PAGE   = os.path.join(_REPO_ROOT, "frontend", "pages", "4_매물추천.py")


# ─────────────────────────────────────────
#  비교 페이지 컴파일 검사
# ─────────────────────────────────────────

class TestComparisonPageCompiles:
    def test_file_exists(self):
        assert os.path.isfile(_CMP_PAGE), f"파일 없음: {_CMP_PAGE}"

    def test_no_syntax_error(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"SyntaxError in 6_매물비교.py: {e}")

    def test_uses_run_comparison(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "run_comparison" in source

    def test_uses_comparison_input(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "ComparisonInput" in source or "compare_basket" in source

    def test_uses_router_import(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "from router import run_comparison" in source

    def test_has_compare_basket_key(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "compare_basket" in source

    def test_has_cmp6_result_key(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "cmp6_result" in source

    def test_disclaimer_present(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "샘플 데이터" in source or "간이 분석" in source

    def test_winner_section_present(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "최종 추천" in source or "winner" in source or "is_winner" in source

    def test_property_listing_import(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "PropertyListing" in source

    def test_recommendation_result_import(self):
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "RecommendationResult" in source

    def test_has_simulation_button(self):
        """비교 페이지에서 개별 매물 시뮬레이션 연결 버튼"""
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "sim_from_listing" in source
        assert "5_투자시뮬레이션" in source

    def test_min_two_listings_guard(self):
        """2개 미만이면 경고하는 로직 존재 확인"""
        with open(_CMP_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "< 2" in source or "len(basket)" in source


# ─────────────────────────────────────────
#  4_매물추천.py 비교 버튼 삽입 확인
# ─────────────────────────────────────────

class TestRecPageCompareButton:
    def test_rec_page_exists(self):
        assert os.path.isfile(_REC_PAGE)

    def test_no_syntax_error(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as e:
            pytest.fail(f"SyntaxError in 4_매물추천.py: {e}")

    def test_has_compare_basket_init(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "compare_basket" in source

    def test_has_cmp_btn_key(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "cmp_btn_" in source

    def test_has_cmp_go_btn(self):
        """사이드바 비교하러 가기 버튼"""
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "cmp_go_btn" in source

    def test_saves_listing_to_basket(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "compare_basket" in source
        assert "listing_id" in source

    def test_switches_to_comparison_page(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "6_매물비교" in source

    def test_max_five_listings_guard(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert ">= 5" in source or "최대 5" in source

    def test_in_basket_toggle_present(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "in_basket" in source

    def test_sidebar_basket_summary(self):
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "st.sidebar" in source

    def test_rec_page_still_has_sim_button(self):
        """기존 시뮬레이션 버튼 유지 확인"""
        with open(_REC_PAGE, encoding="utf-8") as f:
            source = f.read()
        assert "sim_btn_" in source
        assert "5_투자시뮬레이션" in source


# ─────────────────────────────────────────
#  비교 서비스 임포트 확인
# ─────────────────────────────────────────

class TestComparisonServiceImports:
    def test_compare_listings_importable(self):
        from services.comparison_service import compare_listings
        assert callable(compare_listings)

    def test_generate_decision_report_importable(self):
        from services.comparison_service import generate_decision_report
        assert callable(generate_decision_report)

    def test_comparison_graph_importable(self):
        from graphs.comparison_graph import build_comparison_graph
        assert callable(build_comparison_graph)

    def test_comparison_graph_compiles(self):
        from graphs.comparison_graph import build_comparison_graph
        graph = build_comparison_graph()
        assert graph is not None

    def test_router_run_comparison_importable(self):
        from router import run_comparison
        assert callable(run_comparison)


# ─────────────────────────────────────────
#  비교 그래프 단위 노드 테스트
# ─────────────────────────────────────────

class TestComparisonGraphNodes:
    def _make_listings(self):
        from schemas.property_listing import PropertyListing
        return [
            PropertyListing(
                listing_id="L1", address="서울 마포구 1",
                property_type="주거용", asking_price=500_000_000,
            ),
            PropertyListing(
                listing_id="L2", address="서울 서대문구 1",
                property_type="주거용", asking_price=600_000_000,
            ),
        ]

    def test_normalize_input_node_with_comparison_input(self):
        from graphs.comparison_graph import normalize_input_node
        from schemas.comparison import ComparisonInput
        listings = self._make_listings()
        inp = ComparisonInput(listings=listings)
        state = normalize_input_node({"comparison_input": inp, "error": "", "report": ""})
        assert state.get("comparison_input") is inp
        assert not state.get("error")

    def test_normalize_input_node_from_dict(self):
        from graphs.comparison_graph import normalize_input_node
        raw = {
            "listings": [
                {"listing_id": "L1", "address": "주소1", "property_type": "주거용", "asking_price": 500_000_000},
                {"listing_id": "L2", "address": "주소2", "property_type": "주거용", "asking_price": 600_000_000},
            ]
        }
        state = normalize_input_node({"raw_input": raw, "error": "", "report": ""})
        assert state.get("comparison_input") is not None
        assert not state.get("error")

    def test_normalize_input_node_empty_listings_error(self):
        from graphs.comparison_graph import normalize_input_node
        state = normalize_input_node({"raw_input": {"listings": []}, "error": "", "report": ""})
        assert state.get("error")

    def test_compare_node_produces_result(self):
        from graphs.comparison_graph import compare_node
        from schemas.comparison import ComparisonInput
        listings = self._make_listings()
        inp = ComparisonInput(listings=listings)
        state = compare_node({"comparison_input": inp, "error": "", "report": ""})
        assert state.get("result") is not None
        assert not state.get("error")

    def test_compare_node_none_input_error(self):
        from graphs.comparison_graph import compare_node
        state = compare_node({"comparison_input": None, "error": "", "report": ""})
        assert state.get("error")

    def test_report_node_fills_report(self):
        from graphs.comparison_graph import compare_node, report_node
        from schemas.comparison import ComparisonInput
        listings = self._make_listings()
        inp = ComparisonInput(listings=listings)
        state1 = compare_node({"comparison_input": inp, "error": "", "report": ""})
        state2 = report_node(state1)
        assert isinstance(state2.get("report"), str)
        assert len(state2["report"]) > 0

    def test_error_handler_node_creates_fallback_report(self):
        from graphs.comparison_graph import error_handler_node
        state = error_handler_node({"error": "테스트 오류", "report": "", "comparison_input": None})
        assert "테스트 오류" in state.get("report", "")

    def test_route_after_normalize_ok(self):
        from graphs.comparison_graph import _route_after_normalize
        assert _route_after_normalize({"error": "", "report": ""}) == "비교실행"

    def test_route_after_normalize_error(self):
        from graphs.comparison_graph import _route_after_normalize
        assert _route_after_normalize({"error": "오류", "report": ""}) == "오류처리"

    def test_route_after_compare_ok(self):
        from graphs.comparison_graph import _route_after_compare
        assert _route_after_compare({"error": "", "report": ""}) == "리포트생성"

    def test_route_after_compare_error(self):
        from graphs.comparison_graph import _route_after_compare
        assert _route_after_compare({"error": "오류", "report": ""}) == "오류처리"


# ─────────────────────────────────────────
#  스키마 임포트 smoke
# ─────────────────────────────────────────

class TestSchemaImports:
    def test_comparison_input_importable(self):
        from schemas.comparison import ComparisonInput
        assert ComparisonInput is not None

    def test_comparison_result_importable(self):
        from schemas.comparison import ComparisonResult
        assert ComparisonResult is not None

    def test_property_comparison_row_importable(self):
        from schemas.comparison import PropertyComparisonRow
        assert PropertyComparisonRow is not None

    def test_schemas_init_exports(self):
        from schemas import ComparisonInput, ComparisonResult, PropertyComparisonRow
        assert all([ComparisonInput, ComparisonResult, PropertyComparisonRow])
