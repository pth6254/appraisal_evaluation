"""
test_simulation_graph.py — simulation_graph 단위·통합 테스트 (Phase 4-3)

외부 API 호출 없음. simulation_tool은 순수 계산이므로 mock 없이 테스트 가능하다.
오류 경로 테스트에서만 mock을 사용한다.
"""

from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch

from schemas.simulation import SimulationInput, SimulationResult
from graphs.simulation_graph import (
    SimulationState,
    _route_after_build,
    _route_after_run,
    build_input_node,
    build_simulation_graph,
    error_handler_node,
    report_node,
    run_simulation_node,
)


# ─────────────────────────────────────────
#  헬퍼 픽스처
# ─────────────────────────────────────────

def _minimal_dict() -> dict:
    return {
        "purchase_price":              500_000_000,
        "loan_amount":                 250_000_000,
        "annual_interest_rate":        4.0,
        "loan_years":                  30,
        "repayment_type":              "equal_payment",
        "holding_years":               3,
        "expected_annual_growth_rate": 2.0,
    }


def _minimal_inp() -> SimulationInput:
    return SimulationInput(**_minimal_dict())


def _base_state(**kwargs) -> SimulationState:
    defaults: SimulationState = {
        "report": "",
        "error":  "",
    }
    defaults.update(kwargs)
    return defaults


def _run_result() -> SimulationResult:
    """실제 계산으로 SimulationResult 생성"""
    from services.simulation_service import run_property_simulation
    return run_property_simulation(_minimal_inp())


# ─────────────────────────────────────────
#  build_simulation_graph
# ─────────────────────────────────────────

class TestBuildSimulationGraph:
    def test_compiles_without_error(self):
        g = build_simulation_graph()
        assert g is not None

    def test_returns_compiled_graph(self):
        from langgraph.graph.state import CompiledStateGraph
        g = build_simulation_graph()
        assert isinstance(g, CompiledStateGraph)

    def test_has_required_nodes(self):
        g = build_simulation_graph()
        nodes = list(g.get_graph().nodes.keys())
        for name in ("입력준비", "시뮬레이션실행", "리포트생성", "오류처리"):
            assert name in nodes, f"노드 누락: {name}"

    def test_multiple_calls_return_independent_graphs(self):
        g1 = build_simulation_graph()
        g2 = build_simulation_graph()
        assert g1 is not g2  # 매번 새 컴파일, 싱글톤은 router.py에서


# ─────────────────────────────────────────
#  라우팅 함수
# ─────────────────────────────────────────

class TestRouteAfterBuild:
    def test_no_error_routes_to_run(self):
        state = _base_state(error="")
        assert _route_after_build(state) == "시뮬레이션실행"

    def test_error_routes_to_handler(self):
        state = _base_state(error="오류 발생")
        assert _route_after_build(state) == "오류처리"

    def test_missing_error_key_routes_to_run(self):
        assert _route_after_build({}) == "시뮬레이션실행"


class TestRouteAfterRun:
    def test_no_error_routes_to_report(self):
        state = _base_state(error="")
        assert _route_after_run(state) == "리포트생성"

    def test_error_routes_to_handler(self):
        state = _base_state(error="계산 실패")
        assert _route_after_run(state) == "오류처리"

    def test_missing_error_key_routes_to_report(self):
        assert _route_after_run({}) == "리포트생성"


# ─────────────────────────────────────────
#  build_input_node
# ─────────────────────────────────────────

class TestBuildInputNode:
    # 방식 B: simulation_input 직접 전달
    def test_simulation_input_passthrough(self):
        inp   = _minimal_inp()
        state = build_input_node(_base_state(simulation_input=inp))
        assert state.get("built_input") is inp
        assert not state.get("error")

    def test_simulation_input_wrong_type_sets_error(self):
        state = build_input_node(_base_state(simulation_input="not_an_input"))
        assert state.get("error")
        assert "simulation_input 타입 오류" in state["error"]

    # 방식 A: raw_input dict
    def test_raw_input_dict_converted(self):
        state = build_input_node(_base_state(raw_input=_minimal_dict()))
        assert isinstance(state.get("built_input"), SimulationInput)
        assert not state.get("error")

    def test_raw_input_purchase_price_preserved(self):
        state = build_input_node(_base_state(raw_input=_minimal_dict()))
        assert state["built_input"].purchase_price == 500_000_000

    def test_raw_input_not_dict_sets_error(self):
        state = build_input_node(_base_state(raw_input=42))
        assert state.get("error")
        assert "dict" in state["error"]

    def test_raw_input_invalid_values_sets_error(self):
        bad = {**_minimal_dict(), "purchase_price": -1}
        state = build_input_node(_base_state(raw_input=bad))
        assert state.get("error")

    # 방식 C: listing
    def test_listing_dict_converted(self):
        listing = {
            "asking_price":  500_000_000,
            "property_type": "주거용",
        }
        state = build_input_node(_base_state(listing=listing))
        assert isinstance(state.get("built_input"), SimulationInput)
        assert not state.get("error")

    def test_listing_overrides_applied(self):
        listing = {"asking_price": 600_000_000, "property_type": "주거용"}
        overrides = {"loan_ratio": 0.6, "holding_years": 5}
        state = build_input_node(_base_state(listing=listing, listing_overrides=overrides))
        assert state["built_input"].loan_amount == int(600_000_000 * 0.6)
        assert state["built_input"].holding_years == 5

    def test_listing_no_overrides_uses_defaults(self):
        listing = {"asking_price": 400_000_000, "property_type": "주거용"}
        state = build_input_node(_base_state(listing=listing))
        # 기본 loan_ratio=0.5
        assert state["built_input"].loan_amount == int(400_000_000 * 0.5)

    # 입력 없음
    def test_no_input_sets_error(self):
        state = build_input_node(_base_state())
        assert state.get("error")
        assert "입력 없음" in state["error"]

    def test_all_none_sets_error(self):
        state = build_input_node(_base_state(
            raw_input=None, simulation_input=None, listing=None
        ))
        assert state.get("error")

    # 우선순위: B > C > A
    def test_simulation_input_takes_priority_over_listing(self):
        inp     = _minimal_inp()
        listing = {"asking_price": 999_000_000, "property_type": "주거용"}
        state   = build_input_node(_base_state(
            simulation_input=inp, listing=listing
        ))
        assert state["built_input"] is inp

    def test_listing_takes_priority_over_raw_input(self):
        listing   = {"asking_price": 400_000_000, "property_type": "주거용"}
        raw_input = _minimal_dict()  # purchase_price=500_000_000
        state = build_input_node(_base_state(listing=listing, raw_input=raw_input))
        assert state["built_input"].purchase_price == 400_000_000


# ─────────────────────────────────────────
#  run_simulation_node
# ─────────────────────────────────────────

class TestRunSimulationNode:
    def test_returns_simulation_result(self):
        state = run_simulation_node(_base_state(built_input=_minimal_inp()))
        assert isinstance(state.get("result"), SimulationResult)
        assert not state.get("error")

    def test_no_built_input_sets_error(self):
        state = run_simulation_node(_base_state())
        assert state.get("error")
        assert "built_input" in state["error"]

    def test_result_purchase_price_matches(self):
        inp   = _minimal_inp()
        state = run_simulation_node(_base_state(built_input=inp))
        assert state["result"].purchase_price == inp.purchase_price

    def test_result_has_scenarios(self):
        state = run_simulation_node(_base_state(built_input=_minimal_inp()))
        r = state["result"]
        assert r.scenario_base is not None
        assert r.scenario_bull is not None
        assert r.scenario_bear is not None

    def test_exception_sets_error(self):
        with patch(
            "services.simulation_service.run_property_simulation",
            side_effect=RuntimeError("계산 실패"),
        ):
            state = run_simulation_node(_base_state(built_input=_minimal_inp()))
        assert state.get("error")
        assert "시뮬레이션 실행 오류" in state["error"]

    def test_zero_loan_allowed(self):
        inp = SimulationInput(**{**_minimal_dict(), "loan_amount": 0})
        state = run_simulation_node(_base_state(built_input=inp))
        assert not state.get("error")
        assert state["result"].loan.monthly_payment == 0


# ─────────────────────────────────────────
#  report_node
# ─────────────────────────────────────────

class TestReportNode:
    def test_returns_report_string(self):
        result = _run_result()
        inp    = _minimal_inp()
        state  = report_node(_base_state(result=result, built_input=inp))
        assert isinstance(state.get("report"), str)
        assert len(state["report"]) > 0

    def test_no_result_sets_error(self):
        state = report_node(_base_state())
        assert state.get("error")
        assert "result" in state["error"]

    def test_report_contains_title(self):
        state = report_node(_base_state(result=_run_result(), built_input=_minimal_inp()))
        assert "부동산 투자 시뮬레이션" in state["report"]

    def test_report_contains_scenario_section(self):
        state = report_node(_base_state(result=_run_result(), built_input=_minimal_inp()))
        assert "시나리오" in state["report"]

    def test_report_without_built_input_still_works(self):
        # built_input=None이어도 generate_simulation_report(result, None) 정상 동작
        state = report_node(_base_state(result=_run_result()))
        assert isinstance(state.get("report"), str)
        assert not state.get("error")

    def test_exception_sets_error_and_empty_report(self):
        result = _run_result()
        with patch(
            "services.simulation_service.generate_simulation_report",
            side_effect=ValueError("렌더링 실패"),
        ):
            state = report_node(_base_state(result=result, built_input=_minimal_inp()))
        assert state.get("error")
        assert state.get("report") == ""


# ─────────────────────────────────────────
#  error_handler_node
# ─────────────────────────────────────────

class TestErrorHandlerNode:
    def test_sets_fallback_report_when_missing(self):
        state = error_handler_node(_base_state(error="계산 오류", report=""))
        assert "시뮬레이션 실패" in state["report"]
        assert "계산 오류" in state["report"]

    def test_preserves_existing_report(self):
        state = error_handler_node(_base_state(error="오류", report="# 기존"))
        assert state["report"] == "# 기존"

    def test_error_message_in_fallback(self):
        msg   = "고유한 오류 메시지 ABC"
        state = error_handler_node(_base_state(error=msg, report=""))
        assert msg in state["report"]

    def test_no_error_key_uses_default(self):
        state = error_handler_node({"report": ""})
        assert "알 수 없는 오류" in state["report"]


# ─────────────────────────────────────────
#  그래프 end-to-end
# ─────────────────────────────────────────

class TestGraphEndToEnd:
    def _g(self):
        return build_simulation_graph()

    # ── 방식 A: raw_input dict ─────────────────────────────────────────────
    def test_raw_input_returns_result(self):
        state = self._g().invoke(_base_state(raw_input=_minimal_dict()))
        assert isinstance(state.get("result"), SimulationResult)
        assert not state.get("error")

    def test_raw_input_returns_report(self):
        state = self._g().invoke(_base_state(raw_input=_minimal_dict()))
        assert isinstance(state.get("report"), str)
        assert "부동산 투자 시뮬레이션" in state["report"]

    def test_raw_input_built_input_echoed(self):
        state = self._g().invoke(_base_state(raw_input=_minimal_dict()))
        assert isinstance(state.get("built_input"), SimulationInput)
        assert state["built_input"].purchase_price == 500_000_000

    # ── 방식 B: simulation_input ───────────────────────────────────────────
    def test_simulation_input_mode(self):
        inp   = _minimal_inp()
        state = self._g().invoke(_base_state(simulation_input=inp))
        assert isinstance(state.get("result"), SimulationResult)
        assert not state.get("error")

    def test_simulation_input_built_input_same_object(self):
        inp   = _minimal_inp()
        state = self._g().invoke(_base_state(simulation_input=inp))
        assert state["built_input"] is inp

    # ── 방식 C: listing ────────────────────────────────────────────────────
    def test_listing_mode(self):
        listing = {"asking_price": 600_000_000, "property_type": "주거용"}
        state   = self._g().invoke(_base_state(listing=listing))
        assert isinstance(state.get("result"), SimulationResult)
        assert not state.get("error")

    def test_listing_overrides_propagated(self):
        listing   = {"asking_price": 800_000_000, "property_type": "주거용"}
        overrides = {"loan_ratio": 0.7, "holding_years": 5}
        state     = self._g().invoke(_base_state(listing=listing, listing_overrides=overrides))
        assert state["built_input"].loan_amount == int(800_000_000 * 0.7)

    # ── 오류 경로 ──────────────────────────────────────────────────────────
    def test_no_input_returns_error(self):
        state = self._g().invoke({"report": "", "error": ""})
        assert state.get("error")
        assert "시뮬레이션 실패" in state.get("report", "")

    def test_invalid_dict_returns_error(self):
        bad = {**_minimal_dict(), "purchase_price": -1}
        state = self._g().invoke(_base_state(raw_input=bad))
        assert state.get("error")

    def test_loan_exceeds_price_returns_error(self):
        bad = {**_minimal_dict(), "loan_amount": 600_000_000}  # > 500M
        state = self._g().invoke(_base_state(raw_input=bad))
        assert state.get("error")

    # ── 결과 정합성 ────────────────────────────────────────────────────────
    def test_bull_profit_gt_bear(self):
        state = self._g().invoke(_base_state(raw_input=_minimal_dict()))
        r = state["result"]
        assert r.scenario_bull.net_profit > r.scenario_bear.net_profit

    def test_report_has_markdown_tables(self):
        state = self._g().invoke(_base_state(raw_input=_minimal_dict()))
        assert "|" in state["report"]

    def test_with_jeonse(self):
        d = {**_minimal_dict(), "jeonse_deposit": 200_000_000}
        state = self._g().invoke(_base_state(raw_input=d))
        assert state["result"].equity < state["result"].required_cash

    def test_with_monthly_rent(self):
        d = {**_minimal_dict(), "monthly_rent": 1_000_000}
        state = self._g().invoke(_base_state(raw_input=d))
        assert state["result"].cash_flow.monthly_rental_income == 1_000_000


# ─────────────────────────────────────────
#  run_simulation (router 공개 API)
# ─────────────────────────────────────────

class TestRunSimulation:
    def test_dict_input(self):
        from router import run_simulation
        state = run_simulation(data=_minimal_dict())
        assert isinstance(state.get("result"), SimulationResult)
        assert not state.get("error")

    def test_simulation_input_object(self):
        from router import run_simulation
        state = run_simulation(data=_minimal_inp())
        assert isinstance(state.get("result"), SimulationResult)

    def test_listing_input(self):
        from router import run_simulation
        listing = {"asking_price": 500_000_000, "property_type": "주거용"}
        state   = run_simulation(listing=listing)
        assert isinstance(state.get("result"), SimulationResult)

    def test_listing_with_overrides(self):
        from router import run_simulation
        listing   = {"asking_price": 600_000_000, "property_type": "주거용"}
        overrides = {"loan_ratio": 0.6, "holding_years": 5}
        state     = run_simulation(listing=listing, overrides=overrides)
        assert state["built_input"].loan_amount == int(600_000_000 * 0.6)

    def test_none_input_returns_error(self):
        from router import run_simulation
        state = run_simulation(data=None)
        assert state.get("error")

    def test_report_returned(self):
        from router import run_simulation
        state = run_simulation(data=_minimal_dict())
        assert isinstance(state.get("report"), str)
        assert len(state["report"]) > 10

    def test_built_input_returned(self):
        from router import run_simulation
        state = run_simulation(data=_minimal_dict())
        assert isinstance(state.get("built_input"), SimulationInput)

    def test_graph_singleton_reused(self):
        """두 번 호출해도 _sim_graph가 재컴파일되지 않는다."""
        import router as r_module
        r_module._sim_graph = None  # 강제 초기화

        from router import run_simulation
        run_simulation(data=_minimal_dict())
        first_graph = r_module._sim_graph

        run_simulation(data=_minimal_dict())
        second_graph = r_module._sim_graph

        assert first_graph is second_graph

    def test_existing_api_run_appraisal_unchanged(self):
        """run_appraisal 시그니처가 깨지지 않는 것을 확인한다."""
        from router import run_appraisal
        import inspect
        sig = inspect.signature(run_appraisal)
        assert "user_input" in sig.parameters
        assert "building_name" in sig.parameters

    def test_existing_api_run_recommendation_unchanged(self):
        """run_recommendation 시그니처가 깨지지 않는 것을 확인한다."""
        from router import run_recommendation
        import inspect
        sig = inspect.signature(run_recommendation)
        assert "query" in sig.parameters
        assert "limit" in sig.parameters
