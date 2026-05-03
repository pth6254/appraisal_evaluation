"""
test_simulation_tool.py — simulation_tool 단위 테스트

외부 API 호출 없음. 순수 계산 함수만 검증한다.
"""

from __future__ import annotations

import math

import pytest

from schemas.simulation import SimulationInput, SimulationResult
from tools.simulation_tool import (
    calc_acquisition_tax,
    calc_brokerage_fee,
    calc_cash_flow,
    calc_expected_sale_price,
    calc_loan_summary,
    calc_monthly_payment,
    calc_other_acquisition_cost,
    calc_scenario,
    calc_total_acquisition_cost,
    run_simulation,
)


# ─────────────────────────────────────────
#  헬퍼
# ─────────────────────────────────────────

def _inp(**kwargs) -> SimulationInput:
    defaults = {
        "purchase_price": 1_000_000_000,  # 10억
        "loan_amount":    500_000_000,    # 5억
        "annual_interest_rate": 4.0,
        "loan_years": 30,
        "holding_years": 3,
        "expected_annual_growth_rate": 3.0,
    }
    defaults.update(kwargs)
    return SimulationInput(**defaults)


# ─────────────────────────────────────────
#  SimulationInput 유효성
# ─────────────────────────────────────────

class TestSimulationInput:
    def test_valid_input_creates_model(self):
        inp = _inp()
        assert inp.purchase_price == 1_000_000_000

    def test_loan_equal_to_price_raises(self):
        with pytest.raises(Exception):
            _inp(purchase_price=1_000_000_000, loan_amount=1_000_000_000)

    def test_loan_greater_than_price_raises(self):
        with pytest.raises(Exception):
            _inp(purchase_price=1_000_000_000, loan_amount=1_100_000_000)

    def test_jeonse_and_monthly_rent_together_raises(self):
        with pytest.raises(Exception):
            _inp(jeonse_deposit=500_000_000, monthly_rent=1_000_000)

    def test_zero_loan_allowed(self):
        inp = _inp(loan_amount=0)
        assert inp.loan_amount == 0

    def test_negative_growth_allowed(self):
        inp = _inp(expected_annual_growth_rate=-5.0)
        assert inp.expected_annual_growth_rate == -5.0

    def test_default_repayment_type(self):
        assert _inp().repayment_type == "equal_payment"

    def test_default_property_type(self):
        assert _inp().property_type == "아파트"


# ─────────────────────────────────────────
#  calc_acquisition_tax
# ─────────────────────────────────────────

class TestCalcAcquisitionTax:
    def test_under_600m_residential(self):
        tax = calc_acquisition_tax(500_000_000, "아파트")
        assert tax == round(500_000_000 * 0.011)

    def test_exactly_600m_residential(self):
        tax = calc_acquisition_tax(600_000_000, "아파트")
        assert tax == round(600_000_000 * 0.011)

    def test_over_600m_under_900m(self):
        tax = calc_acquisition_tax(700_000_000, "아파트")
        assert tax == round(700_000_000 * 0.022)

    def test_exactly_900m_residential(self):
        tax = calc_acquisition_tax(900_000_000, "아파트")
        assert tax == round(900_000_000 * 0.022)

    def test_over_900m_residential(self):
        tax = calc_acquisition_tax(1_000_000_000, "아파트")
        assert tax == round(1_000_000_000 * 0.033)

    def test_commercial_type(self):
        for ptype in ["상가", "오피스", "사무실", "공장", "창고", "토지"]:
            tax = calc_acquisition_tax(500_000_000, ptype)
            assert tax == round(500_000_000 * 0.044), f"{ptype} 상업용 세율 오류"

    def test_none_type_treated_as_residential(self):
        tax = calc_acquisition_tax(500_000_000, None)
        assert tax == round(500_000_000 * 0.011)

    def test_tax_positive(self):
        assert calc_acquisition_tax(1_000_000, "아파트") > 0


# ─────────────────────────────────────────
#  calc_brokerage_fee
# ─────────────────────────────────────────

class TestCalcBrokerageFee:
    def test_under_50m_capped(self):
        fee = calc_brokerage_fee(30_000_000)
        assert fee <= 250_000

    def test_under_200m_capped(self):
        fee = calc_brokerage_fee(150_000_000)
        assert fee <= 800_000

    def test_under_900m_rate(self):
        fee = calc_brokerage_fee(500_000_000)
        assert fee == round(500_000_000 * 0.004)

    def test_over_900m_under_1200m(self):
        fee = calc_brokerage_fee(1_000_000_000)
        assert fee == round(1_000_000_000 * 0.005)

    def test_over_1200m_under_1500m(self):
        fee = calc_brokerage_fee(1_300_000_000)
        assert fee == round(1_300_000_000 * 0.006)

    def test_over_1500m(self):
        fee = calc_brokerage_fee(2_000_000_000)
        assert fee == round(2_000_000_000 * 0.007)

    def test_fee_positive(self):
        assert calc_brokerage_fee(100_000_000) > 0


# ─────────────────────────────────────────
#  calc_other_acquisition_cost
# ─────────────────────────────────────────

class TestCalcOtherAcquisitionCost:
    def test_minimum_floor(self):
        cost = calc_other_acquisition_cost(100_000_000)  # 0.1% = 100_000 < 300_000
        assert cost == 300_000

    def test_standard_range(self):
        cost = calc_other_acquisition_cost(1_000_000_000)  # 0.1% = 1_000_000
        assert cost == 1_000_000

    def test_maximum_cap(self):
        cost = calc_other_acquisition_cost(5_000_000_000)  # 0.1% = 5_000_000 > 2_000_000
        assert cost == 2_000_000

    def test_cost_in_bounds(self):
        for price in [50_000_000, 500_000_000, 3_000_000_000]:
            cost = calc_other_acquisition_cost(price)
            assert 300_000 <= cost <= 2_000_000


# ─────────────────────────────────────────
#  calc_total_acquisition_cost
# ─────────────────────────────────────────

class TestCalcTotalAcquisitionCost:
    def test_total_equals_sum(self):
        acq = calc_total_acquisition_cost(1_000_000_000, "아파트")
        assert acq.total == acq.acquisition_tax + acq.brokerage_fee + acq.other_cost

    def test_all_fields_positive(self):
        acq = calc_total_acquisition_cost(500_000_000, "아파트")
        assert acq.acquisition_tax > 0
        assert acq.brokerage_fee > 0
        assert acq.other_cost > 0

    def test_commercial_higher_than_residential(self):
        acq_res = calc_total_acquisition_cost(1_000_000_000, "아파트")
        acq_com = calc_total_acquisition_cost(1_000_000_000, "상가")
        assert acq_com.acquisition_tax > acq_res.acquisition_tax


# ─────────────────────────────────────────
#  calc_monthly_payment
# ─────────────────────────────────────────

class TestCalcMonthlyPayment:
    def test_zero_loan_returns_zero(self):
        assert calc_monthly_payment(0, 4.0, 30) == 0

    def test_equal_payment_positive(self):
        m = calc_monthly_payment(500_000_000, 4.0, 30, "equal_payment")
        assert m > 0

    def test_equal_payment_zero_rate(self):
        loan, years = 300_000_000, 10
        m = calc_monthly_payment(loan, 0.0, years, "equal_payment")
        assert m == round(loan / (years * 12))

    def test_equal_principal_first_month(self):
        m = calc_monthly_payment(500_000_000, 4.0, 30, "equal_principal")
        assert m > 0

    def test_interest_only(self):
        loan = 500_000_000
        r    = 4.0 / 100 / 12
        m    = calc_monthly_payment(loan, 4.0, 30, "interest_only")
        assert m == round(loan * r)

    def test_equal_payment_vs_interest_only(self):
        # 원리금균등 ≥ 이자만 (원금도 상환하므로)
        m_ep = calc_monthly_payment(500_000_000, 4.0, 30, "equal_payment")
        m_io = calc_monthly_payment(500_000_000, 4.0, 30, "interest_only")
        assert m_ep >= m_io

    def test_unknown_type_raises(self):
        with pytest.raises(ValueError):
            calc_monthly_payment(500_000_000, 4.0, 30, "unknown_type")

    def test_higher_rate_higher_payment(self):
        m_low  = calc_monthly_payment(500_000_000, 3.0, 30)
        m_high = calc_monthly_payment(500_000_000, 6.0, 30)
        assert m_high > m_low

    def test_longer_term_lower_payment(self):
        m_short = calc_monthly_payment(500_000_000, 4.0, 10)
        m_long  = calc_monthly_payment(500_000_000, 4.0, 30)
        assert m_short > m_long


# ─────────────────────────────────────────
#  calc_loan_summary
# ─────────────────────────────────────────

class TestCalcLoanSummary:
    def test_zero_loan(self):
        s = calc_loan_summary(0, 4.0, 30)
        assert s.monthly_payment == 0
        assert s.total_repayment == 0
        assert s.total_interest == 0

    def test_total_repayment_equals_principal_plus_interest(self):
        loan = 500_000_000
        s = calc_loan_summary(loan, 4.0, 30, "equal_payment")
        assert abs(s.total_repayment - (loan + s.total_interest)) <= 1  # 반올림 허용

    def test_interest_only_total_principal_preserved(self):
        loan = 500_000_000
        s = calc_loan_summary(loan, 4.0, 30, "interest_only")
        assert s.total_repayment == loan + s.total_interest

    def test_equal_principal_less_interest_than_equal_payment(self):
        loan = 500_000_000
        s_ep = calc_loan_summary(loan, 4.0, 30, "equal_payment")
        s_epp= calc_loan_summary(loan, 4.0, 30, "equal_principal")
        assert s_epp.total_interest < s_ep.total_interest

    def test_interest_most_expensive(self):
        # 이자만 납부가 총 이자 가장 큼
        loan = 500_000_000
        s_io  = calc_loan_summary(loan, 4.0, 30, "interest_only")
        s_ep  = calc_loan_summary(loan, 4.0, 30, "equal_payment")
        s_epp = calc_loan_summary(loan, 4.0, 30, "equal_principal")
        assert s_io.total_interest >= s_ep.total_interest >= s_epp.total_interest


# ─────────────────────────────────────────
#  calc_cash_flow
# ─────────────────────────────────────────

class TestCalcCashFlow:
    def test_positive_cash_flow(self):
        cf = calc_cash_flow(monthly_rent=3_000_000, monthly_payment=1_500_000,
                            monthly_management_fee=200_000)
        assert cf.monthly_net == 3_000_000 - 1_500_000 - 200_000

    def test_no_rent_negative_flow(self):
        cf = calc_cash_flow(monthly_rent=None, monthly_payment=1_500_000,
                            monthly_management_fee=None)
        assert cf.monthly_net == -1_500_000

    def test_no_loan_no_mgmt(self):
        cf = calc_cash_flow(monthly_rent=2_000_000, monthly_payment=0,
                            monthly_management_fee=None)
        assert cf.monthly_net == 2_000_000

    def test_all_none_except_payment(self):
        cf = calc_cash_flow(None, 1_000_000, None)
        assert cf.monthly_rental_income == 0
        assert cf.monthly_management_fee == 0
        assert cf.monthly_net == -1_000_000


# ─────────────────────────────────────────
#  calc_expected_sale_price
# ─────────────────────────────────────────

class TestCalcExpectedSalePrice:
    def test_zero_growth(self):
        assert calc_expected_sale_price(1_000_000_000, 0.0, 5) == 1_000_000_000

    def test_positive_growth(self):
        price = calc_expected_sale_price(1_000_000_000, 3.0, 1)
        assert price == round(1_000_000_000 * 1.03)

    def test_compounding(self):
        price = calc_expected_sale_price(1_000_000_000, 3.0, 3)
        assert price == round(1_000_000_000 * (1.03 ** 3))

    def test_negative_growth(self):
        price = calc_expected_sale_price(1_000_000_000, -5.0, 2)
        assert price == round(1_000_000_000 * (0.95 ** 2))
        assert price < 1_000_000_000


# ─────────────────────────────────────────
#  calc_scenario
# ─────────────────────────────────────────

class TestCalcScenario:
    def _base_kwargs(self, **overrides):
        defaults = dict(
            purchase_price=1_000_000_000,
            equity=600_000_000,
            annual_growth_rate=3.0,
            holding_years=3,
            total_acquisition_cost=30_000_000,
            total_interest=50_000_000,
            monthly_rent=None,
            jeonse_deposit=None,
        )
        defaults.update(overrides)
        return defaults

    def test_returns_scenario_result(self):
        from schemas.simulation import ScenarioResult
        s = calc_scenario(**self._base_kwargs())
        assert isinstance(s, ScenarioResult)

    def test_positive_growth_positive_capital_gain(self):
        s = calc_scenario(**self._base_kwargs(annual_growth_rate=5.0))
        assert s.capital_gain > 0

    def test_zero_growth_zero_capital_gain(self):
        s = calc_scenario(**self._base_kwargs(annual_growth_rate=0.0))
        assert s.capital_gain == 0

    def test_negative_growth_negative_capital_gain(self):
        s = calc_scenario(**self._base_kwargs(annual_growth_rate=-5.0))
        assert s.capital_gain < 0

    def test_rental_income_accumulated(self):
        s = calc_scenario(**self._base_kwargs(monthly_rent=2_000_000))
        assert s.total_rental_income == 2_000_000 * 12 * 3

    def test_no_rent_zero_rental_income(self):
        s = calc_scenario(**self._base_kwargs(monthly_rent=None))
        assert s.total_rental_income == 0

    def test_rental_yield_calculated(self):
        s = calc_scenario(**self._base_kwargs(monthly_rent=3_000_000))
        expected = round(3_000_000 * 12 / 1_000_000_000 * 100, 2)
        assert s.rental_yield == expected

    def test_net_profit_formula(self):
        kw = self._base_kwargs()
        s  = calc_scenario(**kw)
        expected = s.capital_gain + 0 - kw["total_interest"] - kw["total_acquisition_cost"]
        assert s.net_profit == expected

    def test_equity_roi_sign_matches_net_profit(self):
        s_pos = calc_scenario(**self._base_kwargs(annual_growth_rate=10.0))
        s_neg = calc_scenario(**self._base_kwargs(annual_growth_rate=-20.0))
        assert s_pos.equity_roi > 0
        assert s_neg.equity_roi < 0

    def test_annual_roi_consistent_with_holding_years(self):
        s = calc_scenario(**self._base_kwargs(annual_growth_rate=5.0))
        if s.equity_roi > 0:
            # 연환산 < 총 수익률 (기간 > 1년)
            assert abs(s.annual_equity_roi) < abs(s.equity_roi)


# ─────────────────────────────────────────
#  run_simulation (통합)
# ─────────────────────────────────────────

class TestRunSimulation:
    def test_returns_simulation_result(self):
        result = run_simulation(_inp())
        assert isinstance(result, SimulationResult)

    def test_required_cash_formula(self):
        inp    = _inp(purchase_price=1_000_000_000, loan_amount=500_000_000)
        result = run_simulation(inp)
        expected = inp.purchase_price - inp.loan_amount + result.acquisition_cost.total
        assert result.required_cash == expected

    def test_equity_without_jeonse(self):
        result = run_simulation(_inp(jeonse_deposit=None))
        assert result.equity == result.required_cash

    def test_equity_with_jeonse(self):
        inp    = _inp(jeonse_deposit=300_000_000)
        result = run_simulation(inp)
        assert result.equity == result.required_cash - 300_000_000

    def test_zero_loan_zero_monthly_payment(self):
        result = run_simulation(_inp(loan_amount=0))
        assert result.loan.monthly_payment == 0
        assert result.loan.total_interest == 0

    def test_scenario_bull_higher_than_base(self):
        result = run_simulation(_inp(expected_annual_growth_rate=3.0))
        assert result.scenario_bull.net_profit > result.scenario_base.net_profit
        assert result.scenario_base.net_profit > result.scenario_bear.net_profit

    def test_scenario_growth_rates(self):
        base = 3.0
        result = run_simulation(_inp(expected_annual_growth_rate=base))
        assert result.scenario_base.annual_growth_rate == base
        assert result.scenario_bull.annual_growth_rate == base + 5.0
        assert result.scenario_bear.annual_growth_rate == base - 5.0

    def test_with_monthly_rent(self):
        result = run_simulation(_inp(monthly_rent=2_000_000))
        assert result.cash_flow.monthly_rental_income == 2_000_000
        assert result.scenario_base.total_rental_income == 2_000_000 * 12 * 3  # holding=3

    def test_interest_only_repayment(self):
        result = run_simulation(_inp(repayment_type="interest_only"))
        # 만기일시상환: 월 상환액 = 이자만
        loan   = 500_000_000
        rate   = 4.0 / 100 / 12
        assert result.loan.monthly_payment == round(loan * rate)

    def test_commercial_higher_acquisition_tax(self):
        r_apt  = run_simulation(_inp(property_type="아파트"))
        r_shop = run_simulation(_inp(property_type="상가"))
        assert r_shop.acquisition_cost.acquisition_tax > r_apt.acquisition_cost.acquisition_tax

    def test_acquisition_total_equals_sum_of_parts(self):
        result = run_simulation(_inp())
        acq = result.acquisition_cost
        assert acq.total == acq.acquisition_tax + acq.brokerage_fee + acq.other_cost

    def test_loan_echo(self):
        inp    = _inp(loan_amount=400_000_000)
        result = run_simulation(inp)
        assert result.loan_amount == 400_000_000

    def test_purchase_price_echo(self):
        inp    = _inp(purchase_price=800_000_000)
        result = run_simulation(inp)
        assert result.purchase_price == 800_000_000

    def test_all_score_fields_present(self):
        result = run_simulation(_inp())
        for attr in ("scenario_base", "scenario_bull", "scenario_bear"):
            s = getattr(result, attr)
            assert hasattr(s, "equity_roi")
            assert hasattr(s, "annual_equity_roi")
            assert hasattr(s, "net_profit")

    def test_equal_principal_less_interest(self):
        r_ep  = run_simulation(_inp(repayment_type="equal_payment"))
        r_epp = run_simulation(_inp(repayment_type="equal_principal"))
        assert r_epp.loan.total_interest < r_ep.loan.total_interest

    def test_longer_holding_more_rental_income(self):
        r3 = run_simulation(_inp(holding_years=3, monthly_rent=2_000_000))
        r5 = run_simulation(_inp(holding_years=5, monthly_rent=2_000_000))
        assert r5.scenario_base.total_rental_income > r3.scenario_base.total_rental_income
