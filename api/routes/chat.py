"""POST /api/chat — 부동산 법률·세금 AI 정보 안내 챗봇"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)
router = APIRouter(tags=["chat"])


class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant)$")
    content: str


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list[ChatMessage] = Field(default_factory=list, max_length=20)


@router.post("/chat")
async def chat_endpoint(req: ChatRequest):
    from backend.services.chat_service import answer_question

    logger.info("챗봇 질문 — %s", req.message[:80])
    return await asyncio.to_thread(
        answer_question,
        req.message,
        [m.model_dump() for m in req.history],
    )
