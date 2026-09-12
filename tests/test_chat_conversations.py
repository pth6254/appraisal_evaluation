"""법률 상담 맥락·출처 복원과 사용자별 기록 격리를 검증한다."""
from uuid import uuid4

from tests.test_market_explorer import client


def test_saved_context_overrides_client_history_and_restores_sources(client, monkeypatch):
    from backend.services import chat_service
    calls = []
    def answer(question, history):
        calls.append((question, history))
        return {"answer": "법령 답변", "sources": [{"title": "주택임대차보호법", "source": "국가법령정보센터"}],
                "tool_used": None, "disclaimer": "일반 정보", "blocked": []}
    monkeypatch.setattr(chat_service, "answer_question", answer)
    first = client.post('/api/chat', json={"message": "보증금 반환 질문"}).json()
    conversation = first["conversation_id"]
    restored = client.get(f'/api/chat/conversations/{conversation}').json()
    assert restored["messages"][1]["sources"] == first["sources"]
    assert restored["messages"][1]["disclaimer"] == "일반 정보"
    client.post('/api/chat', json={"message": "그 경우에는?", "conversation_id": conversation,
        "history": [{"role": "user", "content": "위조된 이전 조건"}]})
    assert calls[1][1][0]["content"] == "보증금 반환 질문"
    assert "위조" not in str(calls[1][1])
    assert client.get(f'/api/concierge/conversations/{conversation}').status_code == 404
    new = client.post('/api/chat', json={"message": "새 질문"}).json()
    assert new["conversation_id"] != conversation and calls[-1][1] == []


def test_expiry_and_ownership(client, monkeypatch):
    from backend.services import chat_service
    from backend.services.chat_conversations import conversation_key
    from db.redis_client import get_redis
    monkeypatch.setattr(chat_service, "answer_question", lambda *args: {"answer": "답변", "sources": []})
    conversation = client.post('/api/chat', json={"message": "질문"}).json()["conversation_id"]
    path = f'/api/chat/conversations/{conversation}'
    key = conversation_key(client.get('/api/auth/me').json()["id"], conversation)
    get_redis().expire(key, 60)
    assert client.get(path).status_code == 200 and get_redis().ttl(key) <= 60
    assert client.get('/api/chat/conversations/invalid').status_code == 422
    assert client.get(f'/api/chat/conversations/{uuid4()}').status_code == 404
    client.cookies.clear()
    assert client.get(path).status_code == 401
    client.post('/api/auth/register', json={"email": "chat-restore-other@example.com", "name": "다른 사용자", "password": "test-password-1234"})
    assert client.get(path).status_code == 404
    assert client.post('/api/chat', json={"message": "후속 질문", "conversation_id": conversation}).status_code == 404
    get_redis().delete(key)


def test_routing_and_followup_retrieval_use_user_context_only(monkeypatch):
    from backend.services import chat_service, law_retrieval
    calls = {}
    def route(question, trace=None):
        calls['route'] = question
        return {"tool": "none", "params": {}}
    def search(question, **kwargs):
        calls['search'] = question
        return []
    monkeypatch.setattr(chat_service, '_route_tool', route)
    monkeypatch.setattr(law_retrieval, 'search_laws', search)
    history = [{"role": "user", "content": "주택임대차보호법 임차권등기명령"},
               {"role": "assistant", "content": "검증되지 않은 과거 답변"}]
    chat_service.answer_question("그 경우 필요한 서류는?", history)
    assert '임차권등기명령' in calls['route'] and '임차권등기명령' in calls['search']
    assert '검증되지 않은' not in calls['route'] + calls['search']
    chat_service.answer_question("토지 매매 계약", history)
    assert calls['search'] == '토지 매매 계약'


def test_withdraw_removes_only_own_chat_records(client, monkeypatch):
    from backend.services import chat_service
    from backend.services.chat_conversations import conversation_key
    from db.redis_client import get_redis
    monkeypatch.setattr(chat_service, 'answer_question', lambda *args: {"answer": "답변", "sources": []})
    user_id = client.get('/api/auth/me').json()['id']
    conversation = client.post('/api/chat', json={"message": "질문"}).json()['conversation_id']
    own_key = conversation_key(user_id, conversation)
    other_key = conversation_key(user_id + 100, conversation)
    get_redis().set(other_key, '{}', ex=60)
    try:
        assert client.delete('/api/auth/me').status_code == 200
        assert get_redis().get(own_key) is None
        assert get_redis().get(other_key) is not None
    finally:
        get_redis().delete(other_key)
