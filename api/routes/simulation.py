"""POST /api/simulation — 투자 시뮬레이션"""
from __future__ import annotations

import asyncio
import logging
from typing import Literal, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["simulation"])


class SimulationRequest(BaseModel):
    purchase_price: int = Field(..., gt=0)
    loan_ratio: float = Field(0.5, ge=0.0, le=0.9)
    annual_interest_rate: float = Field(4.0, ge=0.0, le=30.0)
    loan_years: int = Field(30, ge=1, le=50)
    repayment_type: Literal["equal_payment", "equal_principal", "interest_only"] = "equal_payment"
    holding_years: int = Field(3, ge=1, le=50)
    expected_annual_growth_rate: float = Field(0.0, ge=-20.0, le=50.0)
    rent_deposit: Optional[int] = None
    rent_fee: Optional[int] = None
    monthly_management_fee: Optional[int] = None
    property_type: str = "아파트"
    owned_homes: int = Field(1, ge=1)
    # 세금·규제 (선택)
    official_price: Optional[int] = None            # 공시가격 (원)
    residence_years: Optional[int] = None           # 거주 연수
    vacancy_rate: float = Field(5.0, ge=0.0, le=50.0)
    adjusted_area: bool = False                     # 조정대상지역
    annual_income: Optional[int] = None             # 연소득 (원, DSR)
    existing_loan_annual_payment: int = Field(0, ge=0)


class SimulationFromListingRequest(BaseModel):
    listing_id: str
    overrides: Optional[dict] = None


@router.get("/simulation/market-rate")
async def get_market_rate():
    """최신 주담대 평균금리 (한국은행 ECOS, 24h 캐시). 미연결 시 기본값."""
    import asyncio as _asyncio
    from backend.bok_rates import get_mortgage_rate
    return await _asyncio.to_thread(get_mortgage_rate)


@router.post("/simulation")
async def run_simulation_endpoint(req: SimulationRequest):
    from backend.router import run_simulation
    from schemas.simulation import SimulationInput

    loan_amount = int(req.purchase_price * req.loan_ratio)

    inp = SimulationInput(
        purchase_price              = req.purchase_price,
        loan_amount                 = loan_amount,
        annual_interest_rate        = req.annual_interest_rate,
        loan_years                  = req.loan_years,
        repayment_type              = req.repayment_type,
        holding_years               = req.holding_years,
        expected_annual_growth_rate = req.expected_annual_growth_rate,
        rent_deposit                = req.rent_deposit,
        rent_fee                    = req.rent_fee,
        monthly_management_fee      = req.monthly_management_fee,
        property_type               = req.property_type,
        owned_homes                 = req.owned_homes,
        official_price              = req.official_price,
        residence_years             = req.residence_years,
        vacancy_rate                = req.vacancy_rate,
        adjusted_area               = req.adjusted_area,
        annual_income               = req.annual_income,
        existing_loan_annual_payment = req.existing_loan_annual_payment,
    )

    logger.info("시뮬레이션 요청 — 매수가 %s원, 대출비율 %.0f%%", req.purchase_price, req.loan_ratio * 100)
    result = await asyncio.to_thread(run_simulation, inp)
    return result
