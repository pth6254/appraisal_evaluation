"""
test_recommendation_graph.py — recommendation_graph 단위·통합 테스트

외부 API 호출 없음.
recommend_listings / analyze_price 는 mock으로 격리한다.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from schemas.appraisal_result import AppraisalResult
from schemas.property_listing import PropertyListing
from schemas.property_query import PropertyQuery
from schemas.recommendation_result import RecommendationResult
from graphs.recommendation_graph import (
    RecommendationState,
    _route_after_validate,
    build_recommendation_graph,
    error_handler_node,
    recommend_node,
    report_node,
    validate_query_node,
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
        "listing_id": "T001",
        "address":    "서울시 테스트구 1",
        "property_type": "주거용",
        "asking_price":  1_000_000_000,
        "complex_name": "테스트아파트",
        "built_year": 2015,
        "floor": 10,
        "station_distance_m": 400,
        "jeonse_price": 650_000_000,
    }
    defaults.update(kwargs)
    return PropertyListing(**defaults)


def _rec_result(**kwargs) -> RecommendationResult:
    defaults = {
        "listing":               _listing(),
        "total_score":           7.5,
        "price_score":           7.0,
        "location_score":        8.0,
        "investment_score":      7.0,
        "risk_score":            2.0,
        "recommendation_label":  "추천",
        "reasons":               ["역세권"],
        "risks":                 [],
    }
    defaults.update(kwargs)
    return RecommendationResult(**defaults)


def _base_state(**kwargs) -> RecommendationState:
    defaults: RecommendationState = {
        "query":         _query(),
        "limit":         5,
        "run_appraisal": False,
        "results":       [],
        "report":        "",
        "error":         "",
    }
    defaults.update(kwargs)
    return defaults


# ─────────────────────────────────────────
#  build_recommendation_graph
# ─────────────────────────────────────────

class TestBuildRecommendationGraph:
    def test_compiles_without_error(self):
        g = build_recommendation_graph()
        assert g is not None

    def test_has_required_nodes(self):
        g = build_recommendation_graph()
        nodes = list(g.get_graph().nodes.keys())
        for name in ("쿼리검증", "추천실행", "리포트생성", "오류처리"):
            assert name in nodes, f"노드 누락: {name}"

    def test_returns_compiled_graph(self):
        from langgraph.graph.state import CompiledStateGraph
        g = build_recommendation_graph()
        assert isinstance(g, CompiledStateGraph)


# ─────────────────────────────────────────
#  _route_after_validate
# ─────────────────────────────────────────

class TestRouteAfterValidate:
    def test_no_error_routes_to_recommend(self):
        state = _base_state(error="")
        assert _route_after_validate(state) == "추천실행"

    def test_error_routes_to_error_handler(self):
        state = _base_state(error="뭔가 잘못됨")
        assert _route_after_validate(state) == "오류처리"

    def test_missing_error_key_routes_to_recommend(self):
        state = {"query": _query(), "limit": 5}
        assert _route_after_validate(state) == "추천실행"


# ─────────────────────────────────────────
#  validate_query_node
# ─────────────────────────────────────────

class TestValidateQueryNode:
    def test_valid_query_passes(self):
        state = validate_query_node(_base_state())
        assert not state.get("error")

    def test_none_query_sets_error(self):
        state = validate_query_node(_base_state(query=None))
        assert state.get("error")

    def test_wrong_type_sets_error(self):
        state = validate_query_node(_base_state(query="문자열"))
        assert state.get("error")

    def test_valid_state_unchanged_except_passthrough(self):
        q = _query(region="마포구")
        state = validate_query_node(_base_state(query=q))
        assert state["query"].region == "마포구"

    def test_error_message_mentions_query(self):
        state = validate_query_node(_base_state(query=None))
        assert "PropertyQuery" in state.get("error", "")


# ─────────────────────────────────────────
#  recommend_node
# ─────────────────────────────────────────

class TestRecommendNode:
    def test_calls_recommend_listings(self):
        mock_results = [_rec_result()]
        with patch(
            "services.recommendation_service.recommend_listings",
            return_value=mock_results,
        ):
            state = recommend_node(_base_state())

        assert state["results"] == mock_results

    def test_passes_limit(self):
        captured = {}
        def fake_recommend(query, limit, run_appraisal):
            captured["limit"] = limit
            return []
        with patch("services.recommendation_service.recommend_listings",
                   side_effect=fake_recommend):
            recommend_node(_base_state(limit=3))
        assert captured["limit"] == 3

    def test_passes_run_appraisal(self):
        captured = {}
        def fake_recommend(query, limit, run_appraisal):
            captured["run_appraisal"] = run_appraisal
            return []
        with patch("services.recommendation_service.recommend_listings",
                   side_effect=fake_recommend):
            recommend_node(_base_state(run_appraisal=True))
        assert captured["run_appraisal"] is True

    def test_exception_sets_error(self):
        with patch(
            "services.recommendation_service.recommend_listings",
            side_effect=RuntimeError("API 실패"),
        ):
            state = recommend_node(_base_state())
        assert state.get("error")
        assert state.get("results") == []

    def test_default_limit_5(self):
        captured = {}
        def fake_recommend(query, limit, run_appraisal):
            captured["limit"] = limit
            return []
        with patch("services.recommendation_service.recommend_listings",
                   side_effect=fake_recommend):
            base = dict(_base_state())
            base.pop("limit", None)
            recommend_node(base)
        assert captured["limit"] == 5


# ─────────────────────────────────────────
#  report_node
# ─────────────────────────────────────────

class TestReportNode:
    def test_calls_format_report(self):
        with patch(
            "services.recommendation_service.format_recommendation_report",
            return_value="# 리포트",
        ) as mock:
            state = report_node(_base_state(results=[_rec_result()]))
        assert state["report"] == "# 리포트"
        mock.assert_called_once()

    def test_passes_results_and_query(self):
        captured = {}
        def fake_format(results, query):
            captured["results"] = results
            captured["query"]   = query
            return "report"
        results = [_rec_result()]
        q = _query(region="강남구")
        with patch("services.recommendation_service.format_recommendation_report",
                   side_effect=fake_format):
            report_node(_base_state(results=results, query=q))
        assert captured["results"] is results
        assert captured["query"] is q

    def test_exception_sets_error(self):
        with patch(
            "services.recommendation_service.format_recommendation_report",
            side_effect=ValueError("렌더링 실패"),
        ):
            state = report_node(_base_state(results=[]))
        assert state.get("error")
        assert state.get("report") == ""

    def test_empty_results_still_generates_report(self):
        with patch(
            "services.recommendation_service.format_recommendation_report",
            return_value="# 결과 없음",
        ):
            state = report_node(_base_state(results=[]))
        assert "결과 없음" in state["report"]


# ─────────────────────────────────────────
#  error_handler_node
# ─────────────────────────────────────────

class TestErrorHandlerNode:
    def test_sets_fallback_report_when_missing(self):
        state = error_handler_node(_base_state(error="연결 오류", report=""))
        assert "추천 실패" in state["report"]
        assert "연결 오류" in state["report"]

    def test_preserves_existing_report(self):
        state = error_handler_node(
            _base_state(error="오류", report="# 기존 리포트")
        )
        assert state["report"] == "# 기존 리포트"

    def test_error_message_in_fallback_report(self):
        msg = "독특한 오류 메시지 XYZ"
        state = error_handler_node(_base_state(error=msg, report=""))
        assert msg in state["report"]


# ─────────────────────────────────────────
#  그래프 end-to-end (run_appraisal=False)
# ─────────────────────────────────────────

class TestGraphEndToEnd:
    def _invoke(self, query: PropertyQuery, limit: int = 3) -> dict:
        """실제 샘플 CSV를 쓰는 end-to-end 실행 (API 호출 없음)"""
        g = build_recommendation_graph()
        return g.invoke({
            "query":         query,
            "limit":         limit,
            "run_appraisal": False,
            "error":         "",
        })

    def test_returns_results_list(self):
        result = self._invoke(_query(region="마포구"))
        assert isinstance(result.get("results"), list)

    def test_returns_report_str(self):
        result = self._invoke(_query(region="마포구"))
        assert isinstance(result.get("report"), str)
        assert len(result["report"]) > 0

    def test_no_error_on_valid_query(self):
        result = self._invoke(_query(region="강남구"))
        assert not result.get("error")

    def test_limit_respected(self):
        result = self._invoke(_query(), limit=3)
        assert len(result.get("results", [])) <= 3

    def test_region_filter_applied(self):
        result = self._invoke(_query(region="서초구"), limit=10)
        for r in result.get("results", []):
            assert r.listing.region and "서초구" in r.listing.region

    def test_sorted_by_score_descending(self):
        result = self._invoke(_query(), limit=5)
        scores = [r.total_score for r in result.get("results", [])]
        assert scores == sorted(scores, reverse=True)

    def test_error_on_none_query(self):
        g = build_recommendation_graph()
        result = g.invoke({"query": None, "limit": 5, "run_appraisal": False})
        assert result.get("error")
        assert "추천 실패" in result.get("report", "")

    def test_empty_region_returns_all_types(self):
        result = self._invoke(_query(), limit=10)
        types = {r.listing.property_type for r in result.get("results", [])}
        assert len(types) >= 1

    def test_budget_filter_applied(self):
        budget = 800_000_000
        result = self._invoke(_query(budget_max=budget), limit=20)
        for r in result.get("results", []):
            assert r.listing.asking_price <= budget

    def test_report_contains_header(self):
        result = self._invoke(_query(region="마포구"))
        assert "매물 추천 리포트" in result.get("report", "")

    def test_run_appraisal_with_mock(self):
        """run_appraisal=True 경로도 그래프 통과 확인"""
        mock_appraisal = AppraisalResult(judgement="적정", confidence=0.8)
        with patch(
            "services.price_analysis_service.analyze_price",
            return_value=mock_appraisal,
        ):
            g = build_recommendation_graph()
            result = g.invoke({
                "query":         _query(region="마포구"),
                "limit":         2,
                "run_appraisal": True,
                "error":         "",
            })
        assert isinstance(result.get("results"), list)
        assert len(result["results"]) > 0


# ─────────────────────────────────────────
#  run_recommendation (router 공개 API)
# ─────────────────────────────────────────

class TestRunRecommendation:
    def test_basic_invocation(self):
        from router import run_recommendation
        result = run_recommendation(_query(region="마포구"), limit=3)
        assert isinstance(result.get("results"), list)
        assert isinstance(result.get("report"), str)

    def test_limit_parameter(self):
        from router import run_recommendation
        result = run_recommendation(_query(), limit=2)
        assert len(result.get("results", [])) <= 2

    def test_no_error_on_valid_input(self):
        from router import run_recommendation
        result = run_recommendation(_query(region="강남구"))
        assert not result.get("error")

    def test_graph_singleton_reused(self):
        """두 번 호출해도 _rec_graph가 재컴파일되지 않는다."""
        import router as r_module
        r_module._rec_graph = None  # 강제 초기화

        from router import run_recommendation
        run_recommendation(_query(region="마포구"), limit=1)
        first_graph = r_module._rec_graph

        run_recommendation(_query(region="강남구"), limit=1)
        second_graph = r_module._rec_graph

        assert first_graph is second_graph
