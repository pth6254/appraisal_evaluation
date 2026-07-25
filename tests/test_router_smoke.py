"""
test_router_smoke.py — backend.router 공개 API 엔드투엔드 smoke 테스트

그래프 내부 노드는 test_*_graph.py 가 개별 검증한다. 여기서는 외부에 노출되는
run_simulation / run_recommendation 진입점이 실제로 결과와 리포트까지
만들어내는지만 확인한다 (외부 API·LLM 미사용 경로).

(구 test_sim_ui_smoke.py / test_rec_ui_smoke.py 의 TestBackendSmoke 에서 이관 —
 원본은 삭제된 Streamlit 페이지 소스를 문자열 검사하던 파일이었다.)
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────
#  투자 시뮬레이션
# ─────────────────────────────────────────

class TestRunSimulation:
    def test_dict_mode(self):
        from router import run_simulation
        state = run_simulation(data={
            "purchase_price": 500_000_000,
            "loan_amount":    250_000_000,
        })
        assert state.get("result") is not None
        assert not state.get("error")

    def test_object_mode(self):
        from router import run_simulation
        from schemas.simulation import SimulationInput
        inp   = SimulationInput(purchase_price=500_000_000, loan_amount=200_000_000)
        state = run_simulation(data=inp)
        assert state.get("result") is not None

    def test_returns_report(self):
        from router import run_simulation
        state = run_simulation(data={
            "purchase_price": 700_000_000,
            "loan_amount":    350_000_000,
        })
        assert isinstance(state.get("report"), str)
        assert "부동산 투자 시뮬레이션" in state["report"]

    def test_listing_mode(self):
        """매물 dict 를 직접 넘기는 listing 모드"""
        from router import run_simulation
        listing = {"asking_price": 600_000_000, "property_type": "주거용"}
        state   = run_simulation(listing=listing)
        assert state.get("result") is not None
        assert not state.get("error")

    def test_jeonse_reduces_equity(self):
        from router import run_simulation
        state = run_simulation(data={
            "purchase_price": 700_000_000,
            "loan_amount":    350_000_000,
            "rent_deposit":   300_000_000,
        })
        result = state["result"]
        assert result.equity < result.required_cash

    def test_monthly_rent_reflected_in_cash_flow(self):
        from router import run_simulation
        state = run_simulation(data={
            "purchase_price": 500_000_000,
            "loan_amount":    250_000_000,
            "rent_fee":       1_000_000,
        })
        assert state["result"].cash_flow.monthly_rental_income == 1_000_000

    def test_invalid_input_sets_error(self):
        from router import run_simulation
        state = run_simulation(data={"purchase_price": -1, "loan_amount": 0})
        assert state.get("error")

    def test_generate_simulation_report_importable(self):
        from services.simulation_service import generate_simulation_report
        assert callable(generate_simulation_report)


# ─────────────────────────────────────────
#  매물 추천
# ─────────────────────────────────────────

@pytest.fixture(autouse=True)
def _clear_listing_cache():
    """샘플 매물 CSV 로더가 lru_cache 라 테스트 간 상태를 공유한다."""
    from tools.listing_tool import _load_listings
    _load_listings.cache_clear()
    yield
    _load_listings.cache_clear()


class TestRunRecommendation:
    def test_basic(self):
        from router import run_recommendation
        from schemas.property_query import PropertyQuery
        state = run_recommendation(
            PropertyQuery(intent="recommendation", region="마포구"),
            limit=3, run_appraisal=False,
        )
        assert isinstance(state.get("results"), list)
        assert isinstance(state.get("report"), str)
        assert len(state["results"]) > 0

    def test_results_sorted_by_score_desc(self):
        from router import run_recommendation
        from schemas.property_query import PropertyQuery
        results = run_recommendation(
            PropertyQuery(intent="recommendation", region="마포구"),
            limit=5, run_appraisal=False,
        )["results"]
        scores = [r.total_score for r in results]
        assert scores == sorted(scores, reverse=True)

    def test_budget_filter_applied(self):
        from router import run_recommendation
        from schemas.property_query import PropertyQuery
        budget  = 800_000_000
        results = run_recommendation(
            PropertyQuery(intent="recommendation", region="마포구", budget_max=budget),
            limit=10, run_appraisal=False,
        )["results"]
        assert all(r.listing.asking_price <= budget for r in results if r.listing.asking_price)

    def test_no_match_returns_empty(self):
        from router import run_recommendation
        from schemas.property_query import PropertyQuery
        state = run_recommendation(
            PropertyQuery(intent="recommendation", region="존재하지않는지역"),
            limit=5, run_appraisal=False,
        )
        assert not (state.get("results") or [])
