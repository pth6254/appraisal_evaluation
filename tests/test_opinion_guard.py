"""
test_opinion_guard.py — LLM 의견 수치 가드레일 단위 테스트
"""

from __future__ import annotations

import pytest

import opinion_guard as og


# 컨텍스트: 추정 621,144만원 / 평당가 5,043만원 / 지역평균 4,800만원 / Cap 3.5%
CONTEXT = """
추정 시장가치: 621,144만원 (범위 590,000만원 ~ 650,000만원)
평당가: 5,043만원/평 (지역 평균: 4,800만원/평)
Cap Rate: 3.5% / 5년 예상 수익률: 12.0%
주변 환경: 지하철역 4개 (최근접 320m) / 학교 10개
"""

ALLOWED = og.extract_numbers(CONTEXT)


# ─────────────────────────────────────────
#  수치 추출·정규화
# ─────────────────────────────────────────

def test_extract_krw_composite():
    assert 621144.0 in og.extract_numbers("62억 1,144만원입니다")


def test_extract_krw_simple_eok():
    assert 62000.0 in og.extract_numbers("약 6.2억 규모")


def test_context_numbers_extracted():
    assert 621144.0 in ALLOWED and 5043.0 in ALLOWED and 3.5 in ALLOWED


# ─────────────────────────────────────────
#  허용 판정
# ─────────────────────────────────────────

def test_exact_quote_allowed():
    assert og.find_violations("추정 시세는 621,144만원입니다.", ALLOWED) == []


def test_rounded_eok_allowed():
    """'약 62억' — 0.2% 반올림은 허용."""
    assert og.find_violations("약 62억 수준입니다.", ALLOWED) == []


def test_fabricated_number_blocked():
    """608,871만원 — 컨텍스트에 없는 근접 위조 수치(≈2%) 차단."""
    assert og.find_violations("시장가치 608,871만원으로 판단됩니다.", ALLOWED) == [608871.0]


def test_counts_and_years_innocuous():
    assert og.find_violations("지하철역 4개소와 학교 10개소, 2026년 기준 5년 전망.", ALLOWED) == []


def test_won_scale_variant_allowed():
    """원 단위 표기 (만원×10,000) 허용."""
    assert og.find_violations("6,211,440,000원 상당.", ALLOWED) == []


# ─────────────────────────────────────────
#  문장 정화
# ─────────────────────────────────────────

def test_sanitize_drops_only_bad_sentence():
    text = "입지가 우수합니다. 시세는 608,871만원입니다. 교통 접근성이 뛰어납니다."
    clean, blocked = og.sanitize_text(text, ALLOWED)
    assert "608,871" not in clean
    assert "입지가 우수합니다." in clean and "교통 접근성이 뛰어납니다." in clean
    assert blocked == [608871.0]


# ─────────────────────────────────────────
#  추천 등급 정규화
# ─────────────────────────────────────────

@pytest.mark.parametrize("raw,expected", [
    ("매수 적극 고려", "매수 적극 고려"),
    ("적극적인 매수를 권합니다", "매수 적극 고려"),
    ("매수 비추천", "매수 비추천"),
    ("당분간 관망을 권장", "관망"),
    ("신중한 접근 필요", "관망"),
    ("매수 고려해볼 만함", "매수 고려"),
    ("", "관망"),
    ("이상한 텍스트", "관망"),
])
def test_normalize_recommendation(raw, expected):
    assert og.normalize_recommendation(raw) == expected


# ─────────────────────────────────────────
#  스키마 강제 + 통합 검증
# ─────────────────────────────────────────

def test_validate_schema_coercion():
    """문자열 strengths, 리스트 opinion, 누락 키 전부 수렴."""
    raw = {
        "appraisal_opinion": ["문장1.", "문장2."],
        "strengths": "단일 문자열 요인",
        "recommendation": None,
    }
    clean, report = og.validate(raw, ALLOWED)
    assert clean["appraisal_opinion"] == "문장1. 문장2."
    assert clean["strengths"] == ["단일 문자열 요인"]
    assert clean["risk_factors"] == []
    assert clean["recommendation"] == "관망"


def test_validate_drops_bad_list_item():
    raw = {
        "appraisal_opinion": "입지가 우수합니다.",
        "strengths": ["역세권 입지", "평당가 7,777만원으로 저렴"],   # 위조 수치
        "risk_factors": ["시장 변동성"],
        "recommendation": "매수 고려",
    }
    clean, report = og.validate(raw, ALLOWED)
    assert clean["strengths"] == ["역세권 입지"]
    assert report["dropped_items"] == 1
    assert 7777.0 in report["blocked"]


def test_validate_empty_opinion_signals_retry():
    """의견 전체가 위조 수치면 opinion이 비어 재시도 신호가 된다."""
    raw = {"appraisal_opinion": "시세 777억원.", "recommendation": "매수 고려"}
    clean, report = og.validate(raw, ALLOWED)
    assert clean["appraisal_opinion"] == ""
    assert report["blocked"]


def test_validate_garbage_input():
    clean, _ = og.validate(None, ALLOWED)
    assert clean["recommendation"] == "관망"
    clean, _ = og.validate({"junk": 1}, ALLOWED)
    assert clean["appraisal_opinion"] == ""


# ─────────────────────────────────────────
#  llm_utils 통합 (가짜 LLM)
# ─────────────────────────────────────────

class _FakeResponse:
    def __init__(self, content): self.content = content


class _FakeLLM:
    """호출 순서대로 준비된 응답을 반환."""
    def __init__(self, responses): self.responses = list(responses); self.calls = 0
    def invoke(self, _msgs):
        self.calls += 1
        return _FakeResponse(self.responses.pop(0))


VAL_DATA = {
    "estimated_value": 621144, "cap_rate": 3.5,
    "price_per_pyeong": 5043, "regional_avg_per_pyeong": 4800,
    "roi_5yr": 12.0, "annual_income": 2100, "value_min": 590000, "value_max": 650000,
}


def test_generate_opinion_retry_then_success(monkeypatch):
    import llm_utils
    fake = _FakeLLM([
        '{"appraisal_opinion": "시세 777억원으로 평가.", "recommendation": "매수 고려"}',   # 전량 차단 → 재시도
        '{"appraisal_opinion": "추정 시세 621,144만원, 입지 우수.", "strengths": ["역세권"], "recommendation": "매수 고려"}',
    ])
    monkeypatch.setattr(llm_utils, "get_llm_json", lambda: fake)
    out = llm_utils.generate_appraisal_opinion("주거용", "서초구", VAL_DATA, {}, "")
    assert fake.calls == 2
    assert "621,144" in out["appraisal_opinion"]
    assert out["recommendation"] == "매수 고려"


def test_generate_opinion_fallback_after_all_blocked(monkeypatch):
    import llm_utils
    fake = _FakeLLM([
        '{"appraisal_opinion": "시세 777억원."}',
        '{"appraisal_opinion": "그래도 888억원."}',
    ])
    monkeypatch.setattr(llm_utils, "get_llm_json", lambda: fake)
    out = llm_utils.generate_appraisal_opinion("주거용", "서초구", VAL_DATA, {}, "")
    assert fake.calls == 2
    assert "621,144만원" in out["appraisal_opinion"]      # 결정론적 폴백
    assert out["recommendation"] == "관망"
