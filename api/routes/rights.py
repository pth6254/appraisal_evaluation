"""POST /api/rights/analyze — 등기부등본·건축물대장 PDF 권리관계 위험 점검"""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from api import activity_db
from api.deps import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["rights"])

MAX_PDF_BYTES = 10 * 1024 * 1024   # 10MB


class RightsAnalyzeRequest(BaseModel):
    """PDF는 base64 인코딩 문자열로 전달 (multipart 불필요)"""
    registry_pdf_b64: Optional[str] = None   # 등기사항전부증명서
    building_pdf_b64: Optional[str] = None   # 건축물대장
    my_deposit: int = Field(0, ge=0, description="내 보증금 (원)")
    market_price: int = Field(0, ge=0, description="시세 (원) — AVM 추정치 또는 직접 입력")


def _decode(b64: Optional[str], name: str) -> bytes | None:
    if not b64:
        return None
    try:
        raw = base64.b64decode(b64.split(",")[-1])   # dataURL 접두사 허용
    except Exception:
        raise HTTPException(status_code=400, detail=f"{name}: base64 디코딩 실패")
    if len(raw) > MAX_PDF_BYTES:
        raise HTTPException(status_code=413, detail=f"{name}: 10MB 초과")
    if not raw.startswith(b"%PDF"):
        raise HTTPException(status_code=400, detail=f"{name}: PDF 파일이 아닙니다")
    return raw


@router.post("/rights/analyze")
async def analyze_rights_endpoint(req: RightsAnalyzeRequest):
    from backend.services.rights_analysis_service import analyze_rights

    registry = _decode(req.registry_pdf_b64, "등기부등본")
    building = _decode(req.building_pdf_b64, "건축물대장")
    if registry is None and building is None:
        raise HTTPException(status_code=400, detail="분석할 PDF가 없습니다")

    logger.info("권리 점검 요청 — 등기부 %s / 대장 %s / 보증금 %s",
                bool(registry), bool(building), req.my_deposit or "-")
    return await asyncio.to_thread(
        analyze_rights, registry, building, req.my_deposit, req.market_price,
    )
