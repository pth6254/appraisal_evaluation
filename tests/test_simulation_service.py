"""
tests/test_simulation_service.py — Phase 4-2 시뮬레이션 서비스 테스트
"""

from __future__ import annotations

import os
import sys

_TESTS_DIR    = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_TESTS_DIR)
_BACKEND_DIR  = os.path.join(_PROJECT_ROOT, "backend")
for _p in [_PROJECT_ROOT, _BACKEND_DIR]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

import pytest

from schemas.simulation import SimulationInput, SimulationResult
from services.simulation_service import (
    _fmt_won,
    _fmt_pct,
    _fmt_pct_plain,
    _sign_label,
    listing_to_simulation_input,
    run_property_simulation,
    generate_simulation_report,
)


# ─────────────────────────────────────────
#  포맷 헬퍼
# ─────────────────────────────────────────

class TestFmtWon:
    def test_none_returns_dash(self):
        assert _fmt_won(None) == "—"

    def test_zero(self):
        assert _fmt_won(0) == "0만원"

    def test_man_only(self):
        assert _fmt_won(50_000_000) == "5,000만원"

    def test_eok_only(self):
        assert _fmt_won(1_0000_0000) == "1억원"

    def test_eok_and_man(self):
        assert _fmt_won(1_5000_0000) == "1억 5,000만원"

    def test_large(self):
        result = _fmt_won(10_5000_0000)
        assert "10억" in result
        assert "5,000만원" in result

    def test_negative(self):
        result = _fmt_won(-1_0000_0000)
        assert result.startswith("-")
        assert "1억원" in result

    def test_negative_small(self):
        result = _fmt_won(-5_000_0000)
        assert result.startswith("-")


class TestFmtPct:
    def test_none_returns_dash(self):
        assert _fmt_pct(None) == "—"

    def test_zero(self):
        assert _fmt_pct(0) == "0.00%"

    def test_positive_has_plus(self):
        result = _fmt_pct(3.5)
        assert result.startswith("+")
        assert "3.50%" in result

    def test_negative_has_minus(self):
        result = _fmt_pct(-2.0)
        assert result.startswith("-")
        assert "2.00%" in result

    def test_custom_decimals(self):
        result = _fmt_pct(1.0, decimals=1)
        assert "1.0%" in result


class TestFmtPctPlain:
    def test_none_returns_dash(self):
        assert _fmt_pct_plain(None) == "—"

    def test_no_sign(self):
        result = _fmt_pct_plain(3.5)
        assert not result.startswith("+")
        assert "3.50%" in result

    def test_zero(self):
        assert _fmt_pct_plain(0) == "0.00%"

    def test_custom_decimals(self):
        result = _fmt_pct_plain(5.123, decimals=1)
        assert "5.1%" in result


class TestSignLabel:
    def test_positive(self):
        assert _sign_label(100) == "▲"

    def test_negative(self):
        assert _sign_label(-1) == "▼"

    def test_zero(self):
        assert _sign_label(0) == "─"

    def test_float_positive(self):
        assert _sign_label(0.001) == "▲"

    def test_float_negative(self):
        assert _sign_label(-0.001) == "▼"


# ─────────────────────────────────────────
#  listing_to_simulation_input
# ─────────────────────────────────────────

def _make_dict_listing(**kwargs):
    defaults = {
        "asking_price": 500_000_000,
        "property_type": "주거용",
        "jeonse_price": 300_000_000,
        "maintenance_fee": None,
    }
    defaults.update(kwargs)
    return defaults


class MockListing:
    def __init__(self, **kwargs):
        self.asking_price   = kwargs.get("asking_price", 500_000_000)
        self.property_type  = kwargs.get("property_type", "주거용")
        self.jeonse_price   = kwargs.get("jeonse_price", None)
        self.maintenance_fee = kwargs.get("maintenance_fee", None)


class TestListingToSimulationInput:
    def test_dict_basic(self):
        listing = _make_dict_listing()
        inp = listing_to_simulation_input(listing)
        assert isinstance(inp, SimulationInput)
        assert inp.purchase_price == 500_000_000

    def test_loan_ratio_applied(self):
        listing = _make_dict_listing(asking_price=1_000_000_000)
        inp = listing_to_simulation_input(listing, loan_ratio=0.6)
        assert inp.loan_amount == 600_000_000

    def test_default_loan_ratio_50pct(self):
        listing = _make_dict_listing(asking_price=400_000_000)
        inp = listing_to_simulation_input(listing)
        assert inp.loan_amount == 200_000_000

    def test_property_type_mapping_residential(self):
        listing = _make_dict_listing(property_type="주거용")
        inp = listing_to_simulation_input(listing)
        assert inp.property_type == "아파트"

    def test_property_type_mapping_commercial(self):
        listing = _make_dict_listing(property_type="상업용")
        inp = listing_to_simulation_input(listing)
        assert inp.property_type == "상가"

    def test_property_type_mapping_office(self):
        listing = _make_dict_listing(property_type="업무용")
        inp = listing_to_simulation_input(listing)
        assert inp.property_type == "오피스"

    def test_property_type_mapping_industrial(self):
        listing = _make_dict_listing(property_type="산업용")
        inp = listing_to_simulation_input(listing)
        assert inp.property_type == "공장"

    def test_property_type_mapping_land(self):
        listing = _make_dict_listing(property_type="토지")
        inp = listing_to_simulation_input(listing)
        assert inp.property_type == "토지"

    def test_jeonse_from_dict(self):
        listing = _make_dict_listing(jeonse_price=300_000_000)
        inp = listing_to_simulation_input(listing)
        assert inp.jeonse_deposit == 300_000_000

    def test_monthly_rent_overrides_jeonse(self):
        listing = _make_dict_listing(jeonse_price=300_000_000)
        inp = listing_to_simulation_input(listing, monthly_rent=800_000)
        assert inp.monthly_rent == 800_000
        assert inp.jeonse_deposit is None

    def test_monthly_management_fee_from_dict(self):
        listing = _make_dict_listing(maintenance_fee=200_000)
        inp = listing_to_simulation_input(listing)
        assert inp.monthly_management_fee == 200_000

    def test_monthly_management_fee_param_override(self):
        listing = _make_dict_listing(maintenance_fee=None)
        inp = listing_to_simulation_input(listing, monthly_management_fee=150_000)
        assert inp.monthly_management_fee == 150_000

    def test_object_listing(self):
        listing = MockListing(asking_price=600_000_000, property_type="주거용")
        inp = listing_to_simulation_input(listing)
        assert inp.purchase_price == 600_000_000
        assert inp.property_type == "아파트"

    def test_object_listing_jeonse(self):
        listing = MockListing(asking_price=600_000_000, jeonse_price=400_000_000)
        inp = listing_to_simulation_input(listing)
        assert inp.jeonse_deposit == 400_000_000

    def test_object_listing_maintenance(self):
        listing = MockListing(maintenance_fee=300_000)
        inp = listing_to_simulation_input(listing)
        assert inp.monthly_management_fee == 300_000

    def test_custom_interest_rate(self):
        listing = _make_dict_listing()
        inp = listing_to_simulation_input(listing, annual_interest_rate=5.5)
        assert inp.annual_interest_rate == 5.5

    def test_custom_loan_years(self):
        listing = _make_dict_listing()
        inp = listing_to_simulation_input(listing, loan_years=20)
        assert inp.loan_years == 20

    def test_custom_holding_years(self):
        listing = _make_dict_listing()
        inp = listing_to_simulation_input(listing, holding_years=5)
        assert inp.holding_years == 5

    def test_custom_growth_rate(self):
        listing = _make_dict_listing()
        inp = listing_to_simulation_input(listing, expected_annual_growth_rate=3.0)
        assert inp.expected_annual_growth_rate == 3.0

    def test_repayment_type_passthrough(self):
        listing = _make_dict_listing()
        inp = listing_to_simulation_input(listing, repayment_type="interest_only")
        assert inp.repayment_type == "interest_only"


# ─────────────────────────────────────────
#  run_property_simulation
# ─────────────────────────────────────────

def _minimal_input_dict():
    return {
        "purchase_price": 500_000_000,
        "loan_amount":    250_000_000,
        "annual_interest_rate": 4.0,
        "loan_years": 30,
        "repayment_type": "equal_payment",
        "holding_years": 3,
        "expected_annual_growth_rate": 2.0,
    }


class TestRunPropertySimulation:
    def test_returns_simulation_result(self):
        result = run_property_simulation(_minimal_input_dict())
        assert isinstance(result, SimulationResult)

    def test_dict_input(self):
        result = run_property_simulation(_minimal_input_dict())
        assert result.purchase_price == 500_000_000

    def test_simulation_input_object(self):
        inp = SimulationInput(**_minimal_input_dict())
        result = run_property_simulation(inp)
        assert isinstance(result, SimulationResult)

    def test_loan_amount_preserved(self):
        result = run_property_simulation(_minimal_input_dict())
        assert result.loan_amount == 250_000_000

    def test_required_cash_positive(self):
        result = run_property_simulation(_minimal_input_dict())
        assert result.required_cash > 0

    def test_scenarios_present(self):
        result = run_property_simulation(_minimal_input_dict())
        assert result.scenario_base is not None
        assert result.scenario_bull is not None
        assert result.scenario_bear is not None

    def test_bull_rate_higher_than_base(self):
        result = run_property_simulation(_minimal_input_dict())
        assert result.scenario_bull.annual_growth_rate > result.scenario_base.annual_growth_rate

    def test_bear_rate_lower_than_base(self):
        result = run_property_simulation(_minimal_input_dict())
        assert result.scenario_bear.annual_growth_rate < result.scenario_base.annual_growth_rate

    def test_invalid_input_raises(self):
        bad = {**_minimal_input_dict(), "purchase_price": -1}
        with pytest.raises(Exception):
            run_property_simulation(bad)

    def test_zero_loan(self):
        data = {**_minimal_input_dict(), "loan_amount": 0}
        result = run_property_simulation(data)
        assert result.loan.monthly_payment == 0

    def test_with_jeonse(self):
        data = {**_minimal_input_dict(), "jeonse_deposit": 200_000_000}
        result = run_property_simulation(data)
        assert result.equity < result.required_cash

    def test_with_monthly_rent(self):
        data = {**_minimal_input_dict(), "monthly_rent": 1_000_000}
        result = run_property_simulation(data)
        assert result.cash_flow.monthly_rental_income == 1_000_000


# ─────────────────────────────────────────
#  generate_simulation_report
# ─────────────────────────────────────────

def _run_default() -> tuple:
    inp = SimulationInput(**_minimal_input_dict())
    from tools.simulation_tool import run_simulation
    result = run_simulation(inp)
    return result, inp


class TestGenerateSimulationReport:
    def test_returns_string(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert isinstance(report, str)

    def test_title_present(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "부동산 투자 시뮬레이션 리포트" in report

    def test_disclaimer_present(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "간이 계산" in report

    def test_acquisition_cost_section(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "취득 비용" in report
        assert "취득세" in report

    def test_required_cash_section(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "필요 자금" in report

    def test_loan_section_present(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "대출 정보" in report
        assert "월 상환액" in report

    def test_cash_flow_section(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "월 현금흐름" in report

    def test_scenario_comparison_section(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "시나리오 비교" in report
        assert "비관" in report
        assert "낙관" in report

    def test_verdict_section(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "투자 판단 요약" in report

    def test_input_conditions_shown_with_inp(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "입력 조건" in report
        assert "매수가" in report

    def test_no_input_conditions_without_inp(self):
        result, _ = _run_default()
        report = generate_simulation_report(result)
        assert "입력 조건" not in report

    def test_jeonse_section_shown(self):
        data = {**_minimal_input_dict(), "jeonse_deposit": 200_000_000}
        inp = SimulationInput(**data)
        from tools.simulation_tool import run_simulation
        result = run_simulation(inp)
        report = generate_simulation_report(result, inp)
        assert "전세 보증금" in report
        assert "실투자금" in report

    def test_monthly_rent_shown(self):
        data = {**_minimal_input_dict(), "monthly_rent": 1_000_000}
        inp = SimulationInput(**data)
        from tools.simulation_tool import run_simulation
        result = run_simulation(inp)
        report = generate_simulation_report(result, inp)
        assert "월세" in report
        assert "월 임대 수입" in report

    def test_no_loan_section_when_zero_loan(self):
        data = {**_minimal_input_dict(), "loan_amount": 0}
        inp = SimulationInput(**data)
        from tools.simulation_tool import run_simulation
        result = run_simulation(inp)
        report = generate_simulation_report(result, inp)
        assert "대출 정보" not in report

    def test_management_fee_shown(self):
        data = {**_minimal_input_dict(), "monthly_management_fee": 300_000}
        inp = SimulationInput(**data)
        from tools.simulation_tool import run_simulation
        result = run_simulation(inp)
        report = generate_simulation_report(result, inp)
        assert "관리비" in report

    def test_high_growth_verdict_excellent(self):
        data = {**_minimal_input_dict(), "expected_annual_growth_rate": 15.0}
        inp = SimulationInput(**data)
        from tools.simulation_tool import run_simulation
        result = run_simulation(inp)
        report = generate_simulation_report(result, inp)
        assert "우수한" in report or "양호한" in report or "낮은" in report or "마이너스" in report

    def test_verdict_present(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        verdicts = ["우수한", "양호한", "낮은", "마이너스"]
        assert any(v in report for v in verdicts)

    def test_won_format_in_report(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "억" in report or "만원" in report

    def test_pct_format_in_report(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "%" in report

    def test_markdown_table_syntax(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "|" in report

    def test_negative_cashflow_warning(self):
        # 대출 있고 월세 없으면 현금흐름 적자 가능
        data = {**_minimal_input_dict(), "loan_amount": 490_000_000}
        inp = SimulationInput(**data)
        from tools.simulation_tool import run_simulation
        result = run_simulation(inp)
        if result.cash_flow.monthly_net < 0:
            report = generate_simulation_report(result, inp)
            assert "월 현금흐름 적자" in report

    def test_repayment_label_shown(self):
        result, inp = _run_default()
        report = generate_simulation_report(result, inp)
        assert "원리금균등상환" in report

    def test_repayment_interest_only_label(self):
        data = {**_minimal_input_dict(), "repayment_type": "interest_only"}
        inp = SimulationInput(**data)
        from tools.simulation_tool import run_simulation
        result = run_simulation(inp)
        report = generate_simulation_report(result, inp)
        assert "만기일시상환" in report

    def test_repayment_equal_principal_label(self):
        data = {**_minimal_input_dict(), "repayment_type": "equal_principal"}
        inp = SimulationInput(**data)
        from tools.simulation_tool import run_simulation
        result = run_simulation(inp)
        report = generate_simulation_report(result, inp)
        assert "원금균등상환" in report
