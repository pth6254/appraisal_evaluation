"""화면의 추천 요청이 실제 그래프와 내부 스키마까지 연결되는지 확인한다."""
import pytest
from tests.test_purchase_cases import client


@pytest.mark.parametrize("purpose, expected", [
    (None, None), ("실거주", "live"), ("투자", "investment"),
    ("매도", "sell"), ("보유", "hold"), ("live", "live"),
])
def test_recommendation_request_runs_real_sample_pipeline(client, purpose, expected):
    response = client.post("/api/recommendation", json={"purpose": purpose, "limit": 3})
    assert response.status_code == 200, response.text
    body = response.json()
    assert not body.get("error"), body
    assert len(body["results"]) == 3
    assert body["query"]["intent"] == "recommendation"
    assert body["query"]["purpose"] == expected


@pytest.mark.parametrize("payload", [
    {"purpose": "invalid"}, {"limit": 0}, {"area_m2": -1},
    {"budget_min": 100, "budget_max": 50},
])
def test_invalid_recommendation_input_is_422_not_server_error(client, payload):
    assert client.post("/api/recommendation", json=payload).status_code == 422
