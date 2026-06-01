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


class SimulationFromListingRequest(BaseModel):
    listing_id: str
    overrides: Optional[dict] = None


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
    )

    logger.info("시뮬레이션 요청 — 매수가 %s원, 대출비율 %.0f%%", req.purchase_price, req.loan_ratio * 100)
    result = await asyncio.to_thread(run_simulation, inp)
    return result
