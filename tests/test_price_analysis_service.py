"""
test_price_analysis_service.py — services.price_analysis_service.analyze_price 단위 테스트

fetch_real_transaction_prices를 mock해 외부 API 없이 검증.
"""

from unittest.mock import patch

import pytest
from schemas.property_query import PropertyQuery
from services.price_analysis_service import (
    _calc_confidence,
    _collect_warnings,
    _to_comparables,
    _to_manwon,
    _to_won,
    analyze_price,
)


# ─────────────────────────────────────────
#  단위 변환 헬퍼
# ─────────────────────────────────────────

class TestUnitConversion:
    def test_to_won(self):
        assert _to_won(50000) == 500_000_000
        assert _to_won(0) is None
        assert _to_won(None) is None

    def test_to_manwon(self):
        assert _to_manwon(500_000_000) == 50000
        assert _to_manwon(0) is None
        assert _to_manwon(None) is None

    def test_roundtrip(self):
        original = 80000
        assert _to_manwon(_to_won(original)) == original


# ─────────────────────────────────────────
#  신뢰도 계산
# ─────────────────────────────────────────

class TestCalcConfidence:
    @pytest.mark.parametrize("count,expected_range", [
        (0,  (0.09, 0.11)),
        (1,  (0.29, 0.31)),
        (3,  (0.44, 0.46)),
        (7,  (0.64, 0.66)),
        (12, (0.79, 0.81)),
        (25, (0.89, 0.91)),
    ])
    def test_count_based_confidence(self, count, expected_range):
        data = {"avg": 50000, "count": count}
        c    = _calc_confidence(data)
        assert expected_range[0] <= c <= expected_range[1]

    def test_fallback_source_caps_at_040(self):
        for source in ["공시가격 역산", "수익환원법 사용", "건축원가법 기반"]:
            data = {"avg": 50000, "count": 30, "source": source}
            assert _calc_confidence(data) <= 0.40

    def test_error_returns_010(self):
        data = {"avg": 0, "count": 0, "error": "API 오류"}
        assert _calc_confidence(data) == 0.10


# ─────────────────────────────────────────
#  경고 메시지
# ─────────────────────────────────────────

class TestCollectWarnings:
    def test_no_transaction_data(self):
        warnings = _collect_warnings({"avg": 0, "count": 0}, area_m2=84.0)
        assert any("실거래 데이터 없음" in w for w in warnings)

    def test_few_samples_warning(self):
        warnings = _collect_warnings({"avg": 50000, "count": 3}, area_m2=84.0)
        assert any("표본 부족" in w or "미만" in w for w in warnings)

    def test_no_area_warning(self):
        warnings = _collect_warnings({"avg": 50000, "count": 10}, area_m2=None)
        assert any("면적" in w for w in warnings)

    def test_no_warnings_for_good_data(self):
        warnings = _collect_warnings({"avg": 50000, "count": 20, "used_months": 3}, area_m2=84.0)
        assert len(warnings) == 0

    def test_extended_months_warning(self):
        warnings = _collect_warnings({"avg": 50000, "count": 8, "used_months": 6}, area_m2=84.0)
        assert any("6개월" in w for w in warnings)


# ─────────────────────────────────────────
#  _to_comparables
# ─────────────────────────────────────────

class TestToComparables:
    def _sample(self, apt_name="래미안", price=50000, area=84.0, dong="아현동"):
        return {
            "apt_name":    apt_name,
            "price":       price,
            "area_sqm":    area,
            "per_sqm":     round(price / area),
            "dong":        dong,
            "deal_year":   "2025",
            "deal_month":  "3",
        }

    def test_basic_conversion(self):
        price_data = {"samples": [self._sample()]}
        comps      = _to_comparables(price_data, "래미안")
        assert len(comps) == 1
        assert comps[0].deal_price == 50000 * 10_000    # 만원 → 원
        assert comps[0].deal_date  == "2025-03"

    def test_match_level_same_complex(self):
        price_data = {"samples": [self._sample(apt_name="래미안")]}
        comps      = _to_comparables(price_data, "래미안")
        assert comps[0].match_level == "same_complex"

    def test_match_level_same_dong(self):
        price_data = {"samples": [self._sample(apt_name="다른단지", dong="아현동")]}
        comps      = _to_comparables(price_data, "래미안")
        assert comps[0].match_level == "same_dong"

    def test_match_level_same_gu(self):
        price_data = {"samples": [self._sample(apt_name="다른단지", dong="")]}
        comps      = _to_comparables(price_data, "래미안")
        assert comps[0].match_level == "same_gu"

    def test_empty_samples(self):
        comps = _to_comparables({"samples": []}, "")
        assert comps == []


# ─────────────────────────────────────────
#  analyze_price (통합 — fetch mock)
# ─────────────────────────────────────────

MOCK_PRICE_DATA = {
    "avg": 80000, "min": 72000, "max": 88000,
    "count": 12, "per_sqm_avg": 952,
    "samples": [
        {
            "apt_name":   "마포래미안푸르지오",
            "price":      80000,
            "area_sqm":   84.0,
            "per_sqm":    952,
            "dong":       "아현동",
            "deal_year":  "2025",
            "deal_month": "2",
        }
    ],
    "apt_name_matched": "마포래미안푸르지오",
    "used_months":      3,
    "error":            "",
    "source":           "",
}


class TestAnalyzePrice:
    def _query(self, **kwargs):
        defaults = {
            "intent":        "price_analysis",
            "property_type": "주거용",
            "region":        "마포구",
            "area_m2":       84.0,
        }
        defaults.update(kwargs)
        return PropertyQuery(**defaults)

    @patch("services.price_analysis_service.fetch_real_transaction_prices",
           return_value=MOCK_PRICE_DATA)
    def test_returns_appraisal_result(self, _mock):
        result = analyze_price(self._query())
        assert result.estimated_price is not None
        assert result.estimated_price > 0

    @patch("services.price_analysis_service.fetch_real_transaction_prices",
           return_value=MOCK_PRICE_DATA)
    def test_price_unit_is_won(self, _mock):
        result = analyze_price(self._query())
        # price_engine 반환은 만원 → 서비스 레이어에서 원으로 변환
        assert result.estimated_price >= 10_000   # 최소 1만원 이상 (원 단위)

    @patch("services.price_analysis_service.fetch_real_transaction_prices",
           return_value=MOCK_PRICE_DATA)
    def test_confidence_reasonable(self, _mock):
        result = analyze_price(self._query())
        assert 0.0 <= result.confidence <= 1.0

    @patch("services.price_analysis_service.fetch_real_transaction_prices",
           return_value=MOCK_PRICE_DATA)
    def test_comparables_populated(self, _mock):
        result = analyze_price(self._query())
        assert len(result.comparables) > 0

    @patch("services.price_analysis_service.fetch_real_transaction_prices",
           return_value=MOCK_PRICE_DATA)
    def test_asking_price_preserved(self, _mock):
        result = analyze_price(self._query(asking_price=900_000_000))
        assert result.asking_price == 900_000_000

    @patch("services.price_analysis_service.fetch_real_transaction_prices",
           return_value=MOCK_PRICE_DATA)
    def test_gap_rate_type(self, _mock):
        result = analyze_price(self._query(asking_price=900_000_000))
        if result.gap_rate is not None:
            assert isinstance(result.gap_rate, float)
            assert -1.0 <= result.gap_rate <= 5.0   # 합리적인 범위

    def test_no_region_returns_analysis_fail(self):
        query  = self._query(region=None)
        result = analyze_price(query)
        assert result.confidence == 0.0
        assert any("region" in w.lower() or "지역" in w for w in result.warnings)

    @patch("services.price_analysis_service.fetch_real_transaction_prices",
           return_value={"avg": 0, "count": 0, "per_sqm_avg": 0,
                         "samples": [], "apt_name_matched": "", "error": "API 오류"})
    def test_empty_price_data_low_confidence(self, _mock):
        result = analyze_price(self._query())
        assert result.confidence <= 0.10
