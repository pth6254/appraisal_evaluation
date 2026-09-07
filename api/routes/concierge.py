"""종합 부동산 컨시어지 전용 API."""
from __future__ import annotations

import asyncio

from fastapi import APIRouter, Depends, HTTPException

from api.deps import get_current_user
from schemas.concierge import ConciergeMessageRequest, ConciergeMessageResponse

router = APIRouter(tags=["concierge"])


@router.post("/concierge/messages", response_model=ConciergeMessageResponse)
async def send_message(
    request: ConciergeMessageRequest,
    user: dict = Depends(get_current_user),
):
    from backend.services.concierge_service import handle_message

    try:
        return await asyncio.to_thread(
            handle_message, user_id=user["id"], message=request.message,
            conversation_id=request.conversation_id,
            case_id=request.case_id, candidate_id=request.candidate_id,
        )
    except LookupError:
        raise HTTPException(status_code=404, detail="검토 후보가 없습니다") from None
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="대화 ID가 올바르지 않습니다") from exc
