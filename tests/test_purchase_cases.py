"""매수 검토 케이스 CRUD와 소유자 격리 회귀 테스트."""
from __future__ import annotations

import os
import pytest

os.environ.setdefault("DISABLE_RATE_LIMIT", "1")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-for-purchase-cases")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:password@localhost:5432/real_estate_db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from db.models import CandidateAnalysis, CandidateChecklistItem, CaseProperty, CaseRegion, HistoryRecord, PurchaseCase, User
    from tests.conftest import truncate_tables

    truncate_tables(CandidateAnalysis, CandidateChecklistItem, CaseProperty, CaseRegion, PurchaseCase, HistoryRecord, User)
    from api.main import app
    with TestClient(app) as value:
        yield value


def _register(client, email: str) -> int:
    response = client.post("/api/auth/register", json={
        "email": email, "password": "test-password-1234", "name": email.split("@")[0],
    })
    assert response.status_code == 201, response.text
    return response.json()["id"]


def test_case_crud_and_history_link(client):
    from api import history_db

    user_id = _register(client, "case-owner@example.com")
    history_id = history_db.save(
        "서울특별시 서초구 아파트", {"analysis_result": {"estimated_value": 1_500_000_000}}, user_id=user_id,
    )
    created = client.post("/api/cases", json={
        "title": "서초구 실거주 매수", "budget_max": 1_700_000_000, "target_regions": ["서울특별시 서초구"],
    })
    assert created.status_code == 201
    case_id = created.json()["id"]

    added = client.post(f"/api/cases/{case_id}/properties", json={
        "name": "후보 아파트", "address": "서울특별시 서초구", "asking_price": 1_600_000_000,
        "history_id": history_id, "source": "appraisal",
    })
    assert added.status_code == 201
    assert added.json()["appraisal"]["estimated_value"] == 1_500_000_000

    detail = client.get(f"/api/cases/{case_id}")
    assert detail.status_code == 200
    assert detail.json()["property_count"] == 1
    assert client.patch(f"/api/cases/{case_id}", json={"status": "reviewing"}).json()["status"] == "reviewing"


def test_other_user_gets_404_for_case_and_history_link(client):
    from api import history_db

    owner_id = _register(client, "case-owner2@example.com")
    history_id = history_db.save("소유자 분석", {"analysis_result": {}}, user_id=owner_id)
    case_id = client.post("/api/cases", json={"title": "소유자 케이스"}).json()["id"]

    client.cookies.clear()
    _register(client, "case-attacker@example.com")
    assert client.get(f"/api/cases/{case_id}").status_code == 404
    assert client.patch(f"/api/cases/{case_id}", json={"status": "reviewing"}).status_code == 404
    assert client.delete(f"/api/cases/{case_id}").status_code == 404
    assert client.post(f"/api/cases/{case_id}/properties", json={
        "name": "침입 후보", "history_id": history_id,
    }).status_code == 404


def test_cannot_link_other_users_history(client):
    from api import history_db

    owner_id = _register(client, "history-owner@example.com")
    history_id = history_db.save("타인 분석", {"analysis_result": {}}, user_id=owner_id)
    client.cookies.clear()
    _register(client, "case-owner3@example.com")
    case_id = client.post("/api/cases", json={"title": "내 케이스"}).json()["id"]
    response = client.post(f"/api/cases/{case_id}/properties", json={
        "name": "후보", "history_id": history_id,
    })
    assert response.status_code == 404


def test_cases_require_login(client):
    client.cookies.clear()
    assert client.get("/api/cases").status_code == 401


def test_candidate_checklist_and_owner_scoped_updates(client):
    from api import case_db, history_db

    user_id = _register(client, "workspace-owner@example.com")
    case_id = client.post("/api/cases", json={"title": "매수 검토"}).json()["id"]
    candidate = client.post(f"/api/cases/{case_id}/properties", json={"name": "후보 A"}).json()
    assert len(candidate["checklist"]) == 5

    checklist_id = candidate["checklist"][0]["id"]
    updated = client.patch(
        f"/api/cases/{case_id}/properties/{candidate['id']}/checklist/{checklist_id}",
        json={"status": "done", "evidence": "검토 완료"},
    )
    assert updated.status_code == 200
    assert updated.json()["completed_at"]
    detail = client.get(f"/api/cases/{case_id}").json()
    assert detail["workspace"]["checklist_done"] == 1
    assert detail["properties"][0]["review_progress"] == 20

    history_id = history_db.save("후보 A 시세", {"analysis_result": {"estimated_value": 900_000_000}}, user_id=user_id)
    assert case_db.link_appraisal(case_id, candidate["id"], history_id, user_id, {
        "analysis_result": {"estimated_value": 900_000_000, "valuation_verdict": "적정"}
    })
    linked = client.get(f"/api/cases/{case_id}").json()["properties"][0]
    assert linked["history_id"] == history_id
    assert linked["analyses"][0]["analysis_type"] == "appraisal"

    assert case_db.link_candidate_analysis(
        case_id, candidate["id"], user_id, "simulation",
        {"purchase_price": 1_000_000_000, "loan_amount": 500_000_000},
        evidence="금융 조건 입력 완료",
    )
    assert case_db.link_candidate_analysis(
        case_id, candidate["id"], user_id, "rights",
        {"risk_grade": "caution", "risk_score": 45},
        checklist_status="warning", evidence="권리 위험 확인 필요",
    )
    linked = client.get(f"/api/cases/{case_id}").json()["properties"][0]
    assert {value["analysis_type"] for value in linked["analyses"]} == {"appraisal", "simulation", "rights"}
    statuses = {value["category"]: value["status"] for value in linked["checklist"]}
    assert statuses["funding"] == "done"
    assert statuses["rights"] == "warning"

    client.cookies.clear()
    _register(client, "workspace-attacker@example.com")
    assert client.patch(
        f"/api/cases/{case_id}/properties/{candidate['id']}", json={"status": "selected"}
    ).status_code == 404
    assert client.patch(
        f"/api/cases/{case_id}/properties/{candidate['id']}/checklist/{checklist_id}",
        json={"status": "done"},
    ).status_code == 404
    assert client.post("/api/simulation", json={
        "purchase_price": 1_000_000_000, "case_id": case_id, "candidate_id": candidate["id"],
    }).status_code == 404
    assert client.post("/api/rights/analyze", json={
        "registry_pdf_b64": "data:application/pdf;base64,JVBERi0=",
        "case_id": case_id, "candidate_id": candidate["id"],
    }).status_code == 404
