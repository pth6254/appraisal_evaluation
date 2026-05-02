"""
appraisal_result.py — 감정평가·가격 분석 결과 스키마

금액 단위: 원 (int)
면적 단위: m² (float)
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class ComparableTransaction(BaseModel):
    """인근 실거래 사례"""

    complex_name: Optional[str]  = None   # 단지명
    address: Optional[str]       = None   # 주소
    area_m2: Optional[float]     = None   # 전용면적 m²
    deal_price: Optional[int]    = None   # 거래금액 (원)
    deal_date: Optional[str]     = None   # 거래일 (YYYY-MM 또는 YYYY-MM-DD)
    price_per_m2: Optional[int]  = None   # m²당 금액 (원)
    source: Optional[str]        = None   # 데이터 출처 (예: 국토부 실거래가)

    # 현재 평가 대상과의 매칭 수준
    match_level: Optional[Literal[
        "same_complex",   # 동일 단지
        "same_dong",      # 동일 동
        "same_gu",        # 동일 구
        "nearby",         # 인근 지역
        "fallback",       # 폴백 (공시가격 역산 등)
    ]] = None


class AppraisalResult(BaseModel):
    """가격 분석·감정평가 결과"""

    # 추정 가격 범위 (원 단위)
    estimated_price: Optional[int]  = None   # 추정 시장가치 (원)
    low_price: Optional[int]        = None   # 하단 추정가 (원)
    high_price: Optional[int]       = None   # 상단 추정가 (원)
    asking_price: Optional[int]     = None   # 비교 기준 호가 (원)

    # 고저평가 판단
    gap_rate: Optional[float]       = None   # 호가 대비 편차 (예: +0.05 = 5% 고평가)
    judgement: str                  = ""     # 저평가 / 적정 / 소폭 고평가 / 고평가

    # 신뢰도 (0.0 ~ 1.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # 비교 사례
    comparables: list[ComparableTransaction] = Field(default_factory=list)

    # 품질 경고 메시지 (예: "실거래 3건 미만", "공시가격 역산 사용")
    warnings: list[str]      = Field(default_factory=list)

    # 사용된 데이터 출처 (예: ["국토부 실거래가", "공시가격 역산"])
    data_source: list[str]   = Field(default_factory=list)

    # 기존 analysis_result dict 원본 보존 (하위 호환용)
    raw: dict[str, Any]      = Field(default_factory=dict)
