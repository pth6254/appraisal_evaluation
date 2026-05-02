"""
test_models.py — models.ValuationResult, _intent_summary 단위 테스트
외부 API 없이 순수 데이터 모델만 검증.
"""

import pytest
from models import ValuationResult, _intent_summary


class TestValuationResult:
    def test_defaults(self):
        r = ValuationResult(agent_name="테스트")
        assert r.agent_name == "테스트"
        assert r.estimated_value == 0
        assert r.value_unit == "만원"
        assert r.comparables == []
        assert r.strengths == []
        assert r.risk_factors == []

    def test_model_dump_roundtrip(self):
        r = ValuationResult(
            agent_name="주거용",
            estimated_value=50000,
            value_min=45000,
            value_max=55000,
            cap_rate=3.5,
            investment_grade="C",
        )
        d = r.model_dump()
        assert d["estimated_value"] == 50000
        assert d["cap_rate"] == 3.5
        assert d["investment_grade"] == "C"

    def test_price_error_field(self):
        r = ValuationResult(agent_name="상업용", price_error="API 오류")
        assert r.price_error == "API 오류"

    def test_invalid_type_raises(self):
        with pytest.raises(Exception):
            ValuationResult(agent_name="테스트", estimated_value="not_an_int")


class TestIntentSummary:
    class _MockIntent:
        location_normalized = "마포구"
        transaction_type    = "매매"
        price_min           = None
        price_max           = 80000
        price_raw           = ""
        area_raw            = "84㎡"
        special_conditions  = ["역세권", "남향"]

    def test_basic_summary(self):
        summary = _intent_summary(self._MockIntent())
        assert "마포구" in summary
        assert "매매" in summary
        assert "84㎡" in summary
        assert "역세권" in summary

    def test_price_range_display(self):
        class IntentWithRange(self._MockIntent):
            price_min = 50000
            price_max = 80000
            price_raw = ""
        summary = _intent_summary(IntentWithRange())
        assert "50,000만원" in summary or "50000" in summary

    def test_none_returns_empty(self):
        assert _intent_summary(None) == ""

    def test_empty_parts_excluded(self):
        class MinimalIntent:
            location_normalized = "강남구"
            transaction_type    = ""
            price_min           = None
            price_max           = None
            price_raw           = ""
            area_raw            = ""
            special_conditions  = []
        summary = _intent_summary(MinimalIntent())
        assert "강남구" in summary
        assert "거래:" not in summary   # 빈 값은 제외됨
