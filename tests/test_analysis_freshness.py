"""후보 분석 최신성 및 비교 반영 회귀 테스트."""
from datetime import datetime

from backend.services.analysis_freshness import analysis_freshness, expiry_for
from backend.services.case_comparison_service import compare_case_candidates


def test_analysis_type_expiry_periods():
    analyzed_at = "2026-08-01 12:00:00"
    assert expiry_for("appraisal", analyzed_at) == "2026-08-31 12:00:00"
    assert expiry_for("simulation", analyzed_at) == "2026-08-15 12:00:00"
    assert expiry_for("rights", analyzed_at) == "2026-08-08 12:00:00"


def test_fresh_analysis_returns_remaining_days():
    result = analysis_freshness(
        "appraisal", "2026-08-01 12:00:00", None,
        now=datetime(2026, 8, 20, 12, 0, 0),
    )
    assert result["status"] == "completed"
    assert result["days_remaining"] == 11


def test_expired_analysis_is_stale():
    result = analysis_freshness(
        "rights", "2026-08-01 12:00:00", None,
        now=datetime(2026, 8, 20, 12, 0, 0),
    )
    assert result["status"] == "stale"
    assert result["days_remaining"] == 0


def test_stale_analysis_blocks_comparison_readiness():
    candidate = {
        "id": 1, "name": "후보", "address": "", "status": "reviewing",
        "asking_price": 900_000_000, "area_sqm": 84.0, "review_progress": 100,
        "checklist": [],
        "analyses": [
            {"analysis_type": "appraisal", "status": "stale", "summary": {"estimated_value": 900_000_000}},
            {"analysis_type": "simulation", "status": "completed", "summary": {}},
            {"analysis_type": "rights", "status": "completed", "summary": {"risk_grade": "safe"}},
        ],
    }
    result = compare_case_candidates({
        "id": 1, "title": "비교", "budget_max": 1_000_000_000,
        "properties": [candidate],
    })
    row = result["rows"][0]
    assert "시세분석 갱신 필요" in row["missing"]
    assert not row["decision_ready"]
