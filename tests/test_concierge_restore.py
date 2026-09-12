"""대화 복원은 소유한 기록만 읽고 금융 조건과 결과를 보존해야 한다."""
from uuid import uuid4

from tests.test_market_explorer import client
from tests.test_concierge_decision_tools import setup_candidates, router


def test_restore_keeps_responses_and_financial_context(client, monkeypatch):
    case_id, candidates = setup_candidates(client)
    router(monkeypatch, [{"intent": "simulate", "funding": {"cash_available": 300000000}}], [])
    first = client.post("/api/concierge/messages", json={"case_id": case_id,
        "candidate_id": candidates[0]["id"], "message": "보유 현금은 3억이야"}).json()
    path = f"/api/concierge/conversations/{first['conversation_id']}"
    restored = client.get(path)
    assert restored.status_code == 200
    body = restored.json()
    assert body["messages"][1]["response"] == first
    assert body["candidate_context"]["candidate_id"] == candidates[0]["id"]
    followup = client.post("/api/concierge/messages", json={"conversation_id": first["conversation_id"],
        "message": "자금 분석해줘"}).json()
    assert followup["data"]["funding_inputs"]["cash_available"] == 300000000
    # 조회와 새 대화는 기존 케이스 분석을 변경하지 않는다.
    assert len(client.get(path).json()["messages"]) == 4


def test_restore_is_private_and_missing_ids_are_rejected(client):
    first = client.post("/api/concierge/messages", json={"message": "자금 분석해줘"}).json()
    path = f"/api/concierge/conversations/{first['conversation_id']}"
    assert client.get(f"/api/concierge/conversations/{uuid4()}").status_code == 404
    assert client.get("/api/concierge/conversations/invalid").status_code == 422
    client.cookies.clear()
    assert client.get(path).status_code == 401
    client.post("/api/auth/register", json={"email": "restore-other@example.com", "password": "test-password-1234", "name": "다른 사용자"})
    assert client.get(path).status_code == 404


def test_restore_expired_or_deleted_candidate_does_not_revive_context(client):
    from db.redis_client import get_redis
    from backend.services.concierge_service import _conversation_key
    case_id, candidates = setup_candidates(client)
    first = client.post("/api/concierge/messages", json={"case_id": case_id,
        "candidate_id": candidates[0]["id"], "message": "자금 분석해줘"}).json()
    path = f"/api/concierge/conversations/{first['conversation_id']}"
    user_id = client.get("/api/auth/me").json()["id"]
    key = _conversation_key(user_id, first["conversation_id"])
    get_redis().expire(key, 60)
    assert client.get(path).status_code == 200
    assert get_redis().ttl(key) <= 60
    client.delete(f"/api/cases/{case_id}/properties/{candidates[0]['id']}")
    assert client.get(path).status_code == 404
    get_redis().delete(key)
    assert client.get(path).status_code == 404
