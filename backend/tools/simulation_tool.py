"""
simulation_tool.py — 부동산 투자 시뮬레이션 계산 엔진 (Phase 4-1)

순수 계산 함수 모음. 외부 API 호출 없음.

단위 규칙:
  금액  — 원 (int), 소수점 이하 반올림
  비율  — % (float, 예: 4.0 = 4%)
  기간  — 년 (int) 또는 개월 수 (int)

간이 계산 고지:
  취득세·중개보수는 2024년 기준 간이 세율을 적용한다.
  실제 세율은 취득 시점·보유 주택 수·지역 등에 따라 달라질 수 있으므로
  이 결과를 실제 투자 의사결정에 직접 사용하지 마라.
"""

from __future__ import annotations

import math
import os
import sys

_TOOLS_DIR    = os.path.dirname(os.path.abspath(__file__))
_BACKEND_DIR  = os.path.dirname(_TOOLS_DIR)
_PROJECT_ROOT = os.path.dirname(_BACKEND_DIR)
for _p in [_BACKEND_DIR, _PROJECT_ROOT]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from schemas.simulation import (
    AcquisitionCost,
    CashFlowSummary,
    LoanSummary,
    ScenarioResult,
    SimulationInput,
    SimulationResult,
)


# ─────────────────────────────────────────
#  취득세 (간이)
# ─────────────────────────────────────────

# 매물 유형 → 세율 버킷
_COMMERCIAL_TYPES = {"상가", "오피스", "사무실", "업무용", "상업용", "공장", "창고", "산업용", "토지"}


def calc_acquisition_tax(purchase_price: int, property_type: str | None) -> int:
    """
    취득세 간이 계산 (취득세 + 지방교육세 포함).

    주거용 (아파트·오피스텔 등):
      ≤ 6억      : 1.1%
      6억 초과~9억 : 2.2%
      9억 초과    : 3.3%

    상업용·업무용·산업용·토지: 4.4%
    """
    ptype = (property_type or "").strip()
    is_commercial = any(kw in ptype for kw in _COMMERCIAL_TYPES)

    if is_commercial:
        rate = 0.044
    elif purchase_price <= 600_000_000:
        rate = 0.011
    elif purchase_price <= 900_000_000:
        rate = 0.022
    else:
        rate = 0.033

    return round(purchase_price * rate)


# ─────────────────────────────────────────
#  중개보수 (간이)
# ─────────────────────────────────────────

_BROKERAGE_BRACKETS = [
    (50_000_000,    0.006, 250_000),
    (200_000_000,   0.005, 800_000),
    (900_000_000,   0.004, None),
    (1_200_000_000, 0.005, None),
    (1_500_000_000, 0.006, None),
    (float("inf"),  0.007, None),
]


def calc_brokerage_fee(purchase_price: int) -> int:
    """
    공인중개사 중개보수 간이 계산 (매매 기준, VAT 별도).

    매매가 구간별 상한 요율 적용.
    괄호 안의 한도액이 있는 구간은 min(요율 계산값, 한도액)을 적용한다.
    """
    for threshold, rate, cap in _BROKERAGE_BRACKETS:
        if purchase_price <= threshold:
            fee = round(purchase_price * rate)
            if cap is not None:
                fee = min(fee, cap)
            return fee
    # fallback (shouldn't reach)
    return round(purchase_price * 0.007)


# ─────────────────────────────────────────
#  기타 취득 비용
# ─────────────────────────────────────────

def calc_other_acquisition_cost(purchase_price: int) -> int:
    """
    등기 비용·인지세 등 기타 취득 비용 간이 계산.
    매수가의 0.1%, 최소 300,000원, 최대 2,000,000원.
    """
    raw = round(purchase_price * 0.001)
    return max(300_000, min(raw, 2_000_000))


# ─────────────────────────────────────────
#  총 취득 비용
# ─────────────────────────────────────────

def calc_total_acquisition_cost(
    purchase_price: int,
    property_type: str | None,
) -> AcquisitionCost:
    acq_tax  = calc_acquisition_tax(purchase_price, property_type)
    brok_fee = calc_brokerage_fee(purchase_price)
    other    = calc_other_acquisition_cost(purchase_price)
    return AcquisitionCost(
        acquisition_tax = acq_tax,
        brokerage_fee   = brok_fee,
        other_cost      = other,
        total           = acq_tax + brok_fee + other,
    )


# ─────────────────────────────────────────
#  대출 월 상환액
# ─────────────────────────────────────────

def calc_monthly_payment(
    loan_amount: int,
    annual_interest_rate: float,
    loan_years: int,
    repayment_type: str = "equal_payment",
) -> int:
    """
    대출 첫 달 월 상환액 계산.

    equal_payment  (원리금균등): 매달 동일 금액
    equal_principal (원금균등) : 첫 달 상환액 (이후 줄어듦)
    interest_only  (만기일시)  : 이자만 납부
    """
    if loan_amount <= 0:
        return 0

    r = annual_interest_rate / 100 / 12
    n = loan_years * 12

    if repayment_type == "equal_payment":
        if r == 0:
            return round(loan_amount / n)
        m = loan_amount * r * (1 + r) ** n / ((1 + r) ** n - 1)
        return round(m)

    if repayment_type == "equal_principal":
        principal_part = loan_amount / n
        interest_part  = loan_amount * r
        return round(principal_part + interest_part)

    if repayment_type == "interest_only":
        return round(loan_amount * r)

    raise ValueError(f"알 수 없는 상환 방식: {repayment_type}")


def calc_loan_summary(
    loan_amount: int,
    annual_interest_rate: float,
    loan_years: int,
    repayment_type: str = "equal_payment",
) -> LoanSummary:
    """대출 요약 (월 상환액·총 상환액·총 이자)."""
    if loan_amount <= 0:
        return LoanSummary(monthly_payment=0, total_repayment=0, total_interest=0)

    r = annual_interest_rate / 100 / 12
    n = loan_years * 12
    monthly = calc_monthly_payment(loan_amount, annual_interest_rate, loan_years, repayment_type)

    if repayment_type == "equal_payment":
        total_repayment = monthly * n
        total_interest  = total_repayment - loan_amount

    elif repayment_type == "equal_principal":
        principal_per_month = loan_amount / n
        total_interest = sum(
            (loan_amount - principal_per_month * i) * r
            for i in range(n)
        )
        total_repayment = loan_amount + round(total_interest)
        total_interest  = round(total_interest)

    elif repayment_type == "interest_only":
        total_interest  = round(loan_amount * r * n)
        total_repayment = loan_amount + total_interest

    else:
        raise ValueError(f"알 수 없는 상환 방식: {repayment_type}")

    return LoanSummary(
        monthly_payment = monthly,
        total_repayment = round(total_repayment),
        total_interest  = round(total_interest),
    )


# ─────────────────────────────────────────
#  현금흐름
# ─────────────────────────────────────────

def calc_cash_flow(
    monthly_rent: int | None,
    monthly_payment: int,
    monthly_management_fee: int | None,
) -> CashFlowSummary:
    """
    월 현금흐름 계산.

    전세의 경우 monthly_rent=None → 임대 수입 0으로 계산.
    """
    income   = monthly_rent or 0
    mgmt_fee = monthly_management_fee or 0
    net      = income - monthly_payment - mgmt_fee

    return CashFlowSummary(
        monthly_rental_income  = income,
        monthly_loan_payment   = monthly_payment,
        monthly_management_fee = mgmt_fee,
        monthly_net            = net,
    )


# ─────────────────────────────────────────
#  미래 예상 매도가
# ─────────────────────────────────────────

def calc_expected_sale_price(
    purchase_price: int,
    annual_growth_rate: float,
    holding_years: int,
) -> int:
    """복리 적용 예상 매도가."""
    return round(purchase_price * (1 + annual_growth_rate / 100) ** holding_years)


# ─────────────────────────────────────────
#  시나리오 수익성 계산
# ─────────────────────────────────────────

def calc_scenario(
    purchase_price: int,
    equity: int,
    annual_growth_rate: float,
    holding_years: int,
    total_acquisition_cost: int,
    total_interest: int,
    monthly_rent: int | None,
    jeonse_deposit: int | None,
) -> ScenarioResult:
    """
    단일 성장률 시나리오 수익성 계산.

    순손익 = 시세차익 + 총 임대 수입 − 총 이자 − 취득 비용
    자기자본 수익률 = 순손익 / equity × 100
    """
    expected_price  = calc_expected_sale_price(purchase_price, annual_growth_rate, holding_years)
    capital_gain    = expected_price - purchase_price

    # 총 임대 수입 (전세는 보증금 이자 효과 미계산 — 간이 계산)
    total_rental    = (monthly_rent or 0) * 12 * holding_years

    # 임대 수익률 (연)
    annual_rent     = (monthly_rent or 0) * 12
    rental_yield    = round(annual_rent / purchase_price * 100, 2) if purchase_price > 0 else 0.0

    net_profit      = capital_gain + total_rental - total_interest - total_acquisition_cost
    equity_safe     = equity if equity > 0 else 1  # 0 나눔 방지

    equity_roi      = round(net_profit / equity_safe * 100, 2)

    # 연환산 (CAGR 방식)
    if holding_years > 0 and equity_safe > 0:
        total_value    = equity_safe + net_profit
        if total_value > 0:
            annual_roi = round((math.pow(total_value / equity_safe, 1 / holding_years) - 1) * 100, 2)
        else:
            annual_roi = round(-100 + (total_value / equity_safe) * 100, 2)
    else:
        annual_roi = 0.0

    return ScenarioResult(
        annual_growth_rate   = round(annual_growth_rate, 2),
        expected_sale_price  = expected_price,
        capital_gain         = capital_gain,
        total_rental_income  = total_rental,
        net_profit           = net_profit,
        equity_roi           = equity_roi,
        annual_equity_roi    = annual_roi,
        rental_yield         = rental_yield,
    )


# ─────────────────────────────────────────
#  공개 인터페이스
# ─────────────────────────────────────────

def run_simulation(inp: SimulationInput) -> SimulationResult:
    """
    SimulationInput → SimulationResult 변환.

    모든 계산은 순수 함수이며 외부 API를 호출하지 않는다.
    """
    # 취득 비용
    acq = calc_total_acquisition_cost(inp.purchase_price, inp.property_type)

    # 필요 현금 / 실투자금
    required_cash = inp.purchase_price - inp.loan_amount + acq.total
    jeonse        = inp.jeonse_deposit or 0
    equity        = required_cash - jeonse

    # 대출 요약
    loan = calc_loan_summary(
        inp.loan_amount,
        inp.annual_interest_rate,
        inp.loan_years,
        inp.repayment_type,
    )

    # 현금흐름
    cash_flow = calc_cash_flow(
        inp.monthly_rent,
        loan.monthly_payment,
        inp.monthly_management_fee,
    )

    # 시나리오 공통 인자
    _scenario_kwargs = dict(
        purchase_price        = inp.purchase_price,
        equity                = equity,
        holding_years         = inp.holding_years,
        total_acquisition_cost= acq.total,
        total_interest        = loan.total_interest,
        monthly_rent          = inp.monthly_rent,
        jeonse_deposit        = inp.jeonse_deposit,
    )

    base_rate = inp.expected_annual_growth_rate
    scenario_base = calc_scenario(annual_growth_rate=base_rate,       **_scenario_kwargs)
    scenario_bull = calc_scenario(annual_growth_rate=base_rate + 5.0, **_scenario_kwargs)
    scenario_bear = calc_scenario(annual_growth_rate=base_rate - 5.0, **_scenario_kwargs)

    return SimulationResult(
        purchase_price   = inp.purchase_price,
        loan_amount      = inp.loan_amount,
        required_cash    = required_cash,
        equity           = equity,
        acquisition_cost = acq,
        loan             = loan,
        cash_flow        = cash_flow,
        scenario_base    = scenario_base,
        scenario_bull    = scenario_bull,
        scenario_bear    = scenario_bear,
    )
