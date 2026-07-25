"""
test_comparison_graph.py — 매물 비교 LangGraph 노드 단위 테스트

노드(normalize_input / compare / report / error_handler)와 조건부 엣지 라우팅을
그래프 실행 없이 직접 호출해 검증한다.

(구 test_comparison_ui_smoke.py 에서 이관 — 원본은 삭제된 Streamlit 페이지
 소스를 문자열 검사하던 파일이라, 실제 코드를 검증하는 부분만 남겼다.)
"""
from __future__ import annotations

import pytest


def _make_listings():
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


# ─────────────────────────────────────────
#  임포트 / 컴파일 smoke
# ─────────────────────────────────────────

class TestComparisonGraphBuild:
    def test_compare_listings_importable(self):
        from services.comparison_service import compare_listings
        assert callable(compare_listings)

    def test_generate_decision_report_importable(self):
        from services.comparison_service import generate_decision_report
        assert callable(generate_decision_report)

    def test_build_comparison_graph_importable(self):
        from graphs.comparison_graph import build_comparison_graph
        assert callable(build_comparison_graph)

    def test_graph_compiles(self):
        from graphs.comparison_graph import build_comparison_graph
        assert build_comparison_graph() is not None

    def test_router_run_comparison_importable(self):
        from router import run_comparison
        assert callable(run_comparison)


# ─────────────────────────────────────────
#  노드 단위 동작
# ─────────────────────────────────────────

class TestComparisonGraphNodes:
    def test_normalize_input_node_with_comparison_input(self):
        from graphs.comparison_graph import normalize_input_node
        from schemas.comparison import ComparisonInput
        inp = ComparisonInput(listings=_make_listings())
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
        inp = ComparisonInput(listings=_make_listings())
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
        inp = ComparisonInput(listings=_make_listings())
        state = report_node(compare_node({"comparison_input": inp, "error": "", "report": ""}))
        assert isinstance(state.get("report"), str)
        assert len(state["report"]) > 0

    def test_error_handler_node_creates_fallback_report(self):
        from graphs.comparison_graph import error_handler_node
        state = error_handler_node({"error": "테스트 오류", "report": "", "comparison_input": None})
        assert "테스트 오류" in state.get("report", "")


# ─────────────────────────────────────────
#  조건부 엣지 라우팅
# ─────────────────────────────────────────

class TestComparisonGraphRouting:
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
