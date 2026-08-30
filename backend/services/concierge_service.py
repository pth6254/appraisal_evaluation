"""사용자별 대화 상태와 종합 컨시어지 그래프를 연결한다."""
from __future__ import annotations

import json
from uuid import UUID, uuid4

from backend.graphs.concierge_graph import run_concierge
from db.redis_client import get_redis
from schemas.concierge import ConciergeMessageResponse

_TTL_SECONDS = 24 * 60 * 60


def _conversation_key(user_id: int, conversation_id: str) -> str:
    return f"concierge:{user_id}:{conversation_id}"


def handle_message(*, user_id: int, message: str, conversation_id: str | None) -> ConciergeMessageResponse:
    if conversation_id:
        # Redis 키 경계를 흔드는 임의 문자열을 받지 않고 UUID만 허용한다.
        conversation_id = str(UUID(conversation_id))
    else:
        conversation_id = str(uuid4())

    redis = get_redis()
    key = _conversation_key(user_id, conversation_id)
    saved = redis.get(key)
    if isinstance(saved, bytes):
        saved = saved.decode("utf-8")
    previous = json.loads(saved) if saved else {}

    state = run_concierge(
        user_id=user_id, message=message,
        previous_criteria=previous.get("criteria") or {},
    )
    decision = state["decision"]
    result = state["tool_result"]
    redis.set(
        key,
        json.dumps({"criteria": decision.criteria.model_dump(), "intent": decision.intent.value}, ensure_ascii=False),
        ex=_TTL_SECONDS,
    )

    return ConciergeMessageResponse(
        conversation_id=conversation_id, status=result.status,
        intent=decision.intent, answer=state["answer"], criteria=decision.criteria,
        data=result.data, missing_fields=result.missing_fields, tool_used=result.tool,
    )
