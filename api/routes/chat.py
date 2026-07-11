"""POST /api/chat — 부동산 법률·세금 AI 정보 안내 챗봇

개인정보 처리 원칙:
  - 질문 원문은 저장하지 않는다. 활동 피드에는 앞 20자만 축약 기록 (개인 사정 노출 최소화).
  - 남용 방지: IP 기준 분당 10회 + 사용자별 일일 50회 상한.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from api import activity_db
from api.deps import get_optional_user
from api.rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])

DAILY_CHAT_LIMIT = 50   # 사용자별 일일 질문 상한


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


def _truncate_question(q: str, limit: int = 20) -> str:
    q = q.strip()
    return q if len(q) <= limit else q[:limit] + "…"


@router.post("/chat")
@limiter.limit("10/minute")
async def chat_endpoint(
    request: Request,
    req: ChatRequest,
    user: Optional[dict] = Depends(get_optional_user),
):
    from backend.services.chat_service import answer_question

    if user and activity_db.count_today("chat", user["id"]) >= DAILY_CHAT_LIMIT:
        raise HTTPException(
            status_code=429,
            detail=f"오늘 상담 횟수({DAILY_CHAT_LIMIT}회)를 모두 사용했습니다. 내일 다시 이용해주세요.",
        )

    logger.info("챗봇 질문 — %s", req.message[:80])
    result = await asyncio.to_thread(
        answer_question,
        req.message,
        [m.model_dump() for m in req.history],
    )

    # 홈 '최근 활동' 피드용 기록 (실패해도 답변 반환에는 영향 없음)
    # 개인정보 최소화: 질문 원문 대신 앞 20자만 저장
    try:
        activity_db.save(
            "chat",
            _truncate_question(req.message),
            summary=result.get("tool_used") or "",
            meta={"tool_used": result.get("tool_used")},
            user_id=user["id"] if user else None,
        )
    except Exception:
        logger.warning("상담 활동 기록 실패", exc_info=True)

    return result
