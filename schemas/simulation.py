"""
simulation.py — 부동산 시뮬레이션 입출력 스키마

금액 단위: 원 (int)
비율 단위: % (float, 예: 4.0 = 4%)
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


# ─────────────────────────────────────────
#  입력
# ─────────────────────────────────────────

class SimulationInput(BaseModel):
    """시뮬레이션 입력 파라미터"""

    # 매수 조건
    purchase_price: int = Field(..., gt=0, description="매수가 (원)")
    cash_available: Optional[int] = Field(None, ge=0, description="보유 현금 (원). None이면 purchase_price − loan_amount")
    loan_amount: int = Field(0, ge=0, description="대출금 (원)")

    # 대출 조건
    annual_interest_rate: float = Field(4.0, ge=0.0, le=30.0, description="연이율 (%)")
    loan_years: int = Field(30, ge=1, le=50, description="대출 기간 (년)")
    repayment_type: Literal[
        "equal_payment",    # 원리금균등상환
        "equal_principal",  # 원금균등상환
        "interest_only",    # 만기일시상환
    ] = "equal_payment"

    # 보유·매도 계획
    holding_years: int = Field(3, ge=1, le=50, description="보유 기간 (년)")
    expected_annual_growth_rate: float = Field(0.0, ge=-20.0, le=50.0, description="연간 예상 상승률 (%)")

    # 임대 수입
    jeonse_deposit: Optional[int] = Field(None, ge=0, description="전세 보증금 (원)")
    monthly_rent: Optional[int] = Field(None, ge=0, description="월세 (원)")
    monthly_management_fee: Optional[int] = Field(None, ge=0, description="월 관리비 (원)")

    # 물건 정보 (취득세율 결정)
    property_type: Optional[str] = Field("아파트", description="매물 유형 (아파트·오피스텔·상가·토지 등)")

    @model_validator(mode="after")
    def _validate_loan(self) -> "SimulationInput":
        if self.loan_amount >= self.purchase_price:
            raise ValueError("loan_amount는 purchase_price보다 작아야 합니다.")
        if self.jeonse_deposit and self.monthly_rent:
            raise ValueError("jeonse_deposit과 monthly_rent는 동시에 입력할 수 없습니다.")
        return self


# ─────────────────────────────────────────
#  출력 — 중간 집계 모델
# ─────────────────────────────────────────

class AcquisitionCost(BaseModel):
    """취득 시 발생 비용"""
    acquisition_tax: int    # 취득세 (원)
    brokerage_fee: int      # 중개보수 (원)
    other_cost: int         # 기타 비용 (등기·인지세 등, 원)
    total: int              # 합계 (원)


class LoanSummary(BaseModel):
    """대출 요약"""
    monthly_payment: int    # 첫 달 월 상환액 (원)
    total_repayment: int    # 총 상환액 (원) = 원금 + 이자
    total_interest: int     # 총 이자 납부액 (원)


class CashFlowSummary(BaseModel):
    """월 현금흐름 요약"""
    monthly_rental_income: int      # 월 임대 수입 (원)
    monthly_loan_payment: int       # 월 대출 상환 (원)
    monthly_management_fee: int     # 월 관리비 (원)
    monthly_net: int                # 순 월 현금흐름 = 수입 − 상환 − 관리비 (원)


class ScenarioResult(BaseModel):
    """단일 시나리오 수익성 결과"""
    annual_growth_rate: float       # 적용된 연간 상승률 (%)
    expected_sale_price: int        # 보유 기간 후 예상 매도가 (원)
    capital_gain: int               # 시세 차익 = 매도가 − 매수가 (원)
    total_rental_income: int        # 보유 기간 총 임대 수입 (원)
    net_profit: int                 # 순손익 (원)
    equity_roi: float               # 자기자본 수익률 (%)
    annual_equity_roi: float        # 연환산 자기자본 수익률 (%)
    rental_yield: float             # 연 임대 수익률 = 연 임대수입 / 매수가 × 100 (%)


# ─────────────────────────────────────────
#  출력 — 최종 결과
# ─────────────────────────────────────────

class SimulationResult(BaseModel):
    """시뮬레이션 최종 결과"""

    # 입력 요약 (검증용 echo)
    purchase_price: int
    loan_amount: int
    equity: int             # 실투자금 = 필요 현금 − 전세 보증금 (원)
    required_cash: int      # 필요 현금 = 매수가 − 대출 + 취득 비용 (원)

    # 취득 비용
    acquisition_cost: AcquisitionCost

    # 대출
    loan: LoanSummary

    # 현금흐름
    cash_flow: CashFlowSummary

    # 시나리오
    scenario_base: ScenarioResult   # 입력 growth_rate 그대로
    scenario_bull: ScenarioResult   # growth_rate + 5%p
    scenario_bear: ScenarioResult   # growth_rate − 5%p
