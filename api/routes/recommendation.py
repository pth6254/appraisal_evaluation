"""POST /api/recommendation — 매물 추천"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(tags=["recommendation"])


class RecommendationRequest(BaseModel):
    region: Optional[str] = None
    property_type: Optional[str] = None
    budget_min: Optional[int] = None
    budget_max: Optional[int] = None
    area_m2: Optional[float] = None
    purpose: Optional[str] = None
    complex_name: Optional[str] = None
    limit: int = 5
    run_appraisal: bool = False


@router.post("/recommendation")
async def run_recommendation_endpoint(req: RecommendationRequest):
    from backend.router import run_recommendation
    from schemas.property_query import PropertyQuery

    query = PropertyQuery(
        region        = req.region,
        property_type = req.property_type,
        budget_min    = req.budget_min,
        budget_max    = req.budget_max,
        area_m2       = req.area_m2,
        purpose       = req.purpose,
        complex_name  = req.complex_name,
    )

    logger.info("매물 추천 요청 — region=%s, type=%s, limit=%d", req.region, req.property_type, req.limit)
    result = await asyncio.to_thread(run_recommendation, query, req.limit, req.run_appraisal)
    return result
