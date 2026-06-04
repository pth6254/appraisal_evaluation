"""POST /api/appraisal — 감정평가 실행"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from api import history_db
from api.deps import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["appraisal"])


class AppraisalRequest(BaseModel):
    user_input: str
    building_name: str = ""
    save_history: bool = True


@router.post("/appraisal")
async def run_appraisal_endpoint(req: AppraisalRequest, user: Optional[dict] = Depends(get_optional_user)):
    from backend.router import run_appraisal

    logger.info("감정평가 요청 — %s / %s", req.user_input, req.building_name)
    result = await asyncio.to_thread(run_appraisal, req.user_input, req.building_name)

    if req.save_history and not result.get("error"):
        try:
            history_db.save(req.user_input, result, user_id=user["id"] if user else None)
        except Exception as e:
            logger.warning("이력 저장 실패: %s", e)

    return result
