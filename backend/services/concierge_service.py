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


def restore_conversation(user_id: int, conversation_id: str) -> dict:
    from api import case_db
    conversation_id = str(UUID(conversation_id))
    saved = get_redis().get(_conversation_key(user_id, conversation_id))
    if not saved:
        raise LookupError("conversation_not_found")
    previous = json.loads(saved)
    context = previous.get("candidate_context") or {}
    if context.get("case_id"):
        if not case_db.get_case(context["case_id"], user_id):
            raise LookupError("case_not_found")
        if context.get("candidate_id") and not case_db.validate_candidate(context["case_id"], context["candidate_id"], user_id):
            raise LookupError("candidate_not_found")
    # 조회만으로 보존 기한을 늘리지 않는다. 다른 사용자의 키를 탐색하지 않는다.
    return {"conversation_id": conversation_id, "candidate_context": context,
            "messages": previous.get("messages", previous.get("history", []))}


def handle_message(*, user_id: int, message: str, conversation_id: str | None, case_id: int | None = None, candidate_id: int | None = None, clear_context: bool = False) -> ConciergeMessageResponse:
    from api import case_db
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
    context = {} if clear_context else previous.get("candidate_context", {})
    if case_id is not None:
        context = {"case_id": case_id, "candidate_id": candidate_id}
    elif candidate_id is not None:
        raise LookupError("candidate_not_found")
    # Redis에 저장된 ID도 매 턴 재검증한다. 삭제·소유권 변경 후 과거 맥락을 실행하지 않는다.
    if context.get("case_id"):
        case = case_db.get_case(context["case_id"], user_id)
        if not case:
            raise LookupError("case_not_found")
        if context.get("candidate_id") and not case_db.validate_candidate(context["case_id"], context["candidate_id"], user_id):
            raise LookupError("candidate_not_found")
    same_candidate = context == previous.get("candidate_context", {})
    funding = previous.get("funding", {}) if same_candidate else {}
    history = previous.get("history", []) if same_candidate else []

    state = run_concierge(
        user_id=user_id, message=message,
        previous_criteria=previous.get("criteria") or {},
        candidate_context=context, funding=funding, history=history,
        last_result=previous.get("last_result", {}) if same_candidate else {},
    )
    decision = state["decision"]
    result = state["tool_result"]
    response = ConciergeMessageResponse(
        conversation_id=conversation_id, status=result.status,
        intent=decision.intent, answer=state["answer"], criteria=decision.criteria,
        data=result.data, missing_fields=result.missing_fields, tool_used=result.tool,
    )
    redis.set(
        key,
        json.dumps({"criteria": decision.criteria.model_dump(), "intent": decision.intent.value,
                    "candidate_context": context, "funding": state.get("funding", funding),
                    "messages": (previous.get("messages", previous.get("history", [])) + [
                        {"role": "user", "content": message},
                        {"role": "assistant", "content": state["answer"], "response": response.model_dump(mode="json")},
                    ])[-40:],
                    "history": (history + [{"role": "user", "content": message},
                                {"role": "assistant", "content": state["answer"][:2000]}])[-8:],
                    "last_result": {"tool": result.tool, "status": result.status,
                                    "missing_fields": result.missing_fields}}, ensure_ascii=False),
        ex=_TTL_SECONDS,
    )

    return response
