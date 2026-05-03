"""
comparison.py — 매물 비교·최종 판단 스키마 (Phase 5)
"""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

from schemas.property_listing import PropertyListing
from schemas.recommendation_result import RecommendationResult
from schemas.simulation import SimulationResult


class ComparisonInput(BaseModel):
    """비교 분석 입력"""

    listings: list[PropertyListing]
    recommendation_results: Optional[list[RecommendationResult]] = None
    simulation_results: Optional[list[SimulationResult]] = None
    budget_max: Optional[int] = None


class PropertyComparisonRow(BaseModel):
    """매물 1건의 비교 행"""

    rank: int
    listing: PropertyListing
    recommendation: Optional[RecommendationResult] = None
    simulation: Optional[SimulationResult] = None

    # 계산된 지표
    total_score: float = 0.0
    price_per_m2: Optional[int] = None
    jeonse_ratio: Optional[float] = None
    monthly_net: Optional[int] = None
    annual_equity_roi: Optional[float] = None

    # 최종
    is_winner: bool = False
    highlights: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class ComparisonResult(BaseModel):
    """비교 분석 결과"""

    rows: list[PropertyComparisonRow]
    winner_idx: Optional[int] = None
    decision_report: str = ""
