"""POST /api/chat — 부동산 법률·세금 AI 정보 안내 챗봇"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from api import activity_db
from api.deps import get_optional_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


@router.post("/chat")
async def chat_endpoint(
    req: ChatRequest,
    user: Optional[dict] = Depends(get_optional_user),
):
    from backend.services.chat_service import answer_question

    logger.info("챗봇 질문 — %s", req.message[:80])
    result = await asyncio.to_thread(
        answer_question,
        req.message,
        [m.model_dump() for m in req.history],
    )

    # 홈 '최근 활동' 피드용 기록 (실패해도 답변 반환에는 영향 없음)
    try:
        activity_db.save(
            "chat",
            req.message[:120],
            summary=result.get("tool_used") or "",
            meta={"tool_used": result.get("tool_used")},
            user_id=user["id"] if user else None,
        )
    except Exception:
        logger.warning("상담 활동 기록 실패", exc_info=True)

    return result
