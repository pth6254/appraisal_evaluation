"""
test_price_engine_calc.py — price_engine 순수 계산 함수 단위 테스트

외부 API(MOLIT, R-ONE)를 호출하는 fetch_* 함수는 제외.
"""

from datetime import datetime

import pytest
from price_engine import (
    _calc_residual_rate,
    _empty_price_data,
    _get_recent_deal_ymds,
    calc_cost_approach,
    calc_estimated_value,
    calc_investment_return,
    calc_valuation_verdict,
)


# ─────────────────────────────────────────
#  _empty_price_data
# ─────────────────────────────────────────

class TestEmptyPriceData:
    def test_structure(self):
        d = _empty_price_data("테스트")
        assert d["avg"] == 0
        assert d["count"] == 0
        assert "samples" in d
        assert d["error"] == "테스트"

    def test_empty_reason(self):
        d = _empty_price_data()
        assert d["error"] == ""


# ─────────────────────────────────────────
#  _get_recent_deal_ymds
# ─────────────────────────────────────────

class TestGetRecentDealYmds:
    def test_returns_correct_count(self):
        ymds = _get_recent_deal_ymds(3)
        assert len(ymds) == 3

    def test_format_yyyymm(self):
        for ymd in _get_recent_deal_ymds(6):
            assert len(ymd) == 6
            assert ymd[:4].isdigit()
            assert 1 <= int(ymd[4:]) <= 12

    def test_most_recent_is_last(self):
        ymds = _get_recent_deal_ymds(3)
        now  = datetime.now()
        expected_last = f"{now.year}{now.month:02d}"
        assert ymds[-1] == expected_last

    def test_chronological_order(self):
        ymds = _get_recent_deal_ymds(4)
        assert ymds == sorted(ymds)


# ─────────────────────────────────────────
#  calc_estimated_value
# ─────────────────────────────────────────

class TestCalcEstimatedValue:
    def _price_data(self, avg=50000, per_sqm=600, count=10):
        return {
            "avg": avg, "min": avg - 5000, "max": avg + 5000,
            "per_sqm_avg": per_sqm, "count": count, "samples": [],
        }

    def test_with_area(self):
        result = calc_estimated_value(self._price_data(per_sqm=600), 84.0, "주거용")
        assert result["estimated_value"] == round(600 * 84.0)
        assert result["value_min"] == round(600 * 84.0 * 0.90)
        assert result["value_max"] == round(600 * 84.0 * 1.10)
        assert result["has_area_input"] is True

    def test_without_area_uses_avg(self):
        result = calc_estimated_value(self._price_data(avg=50000), 0.0, "주거용")
        assert result["estimated_value"] == 50000
        assert result["has_area_input"] is False

    def test_price_per_pyeong(self):
        result = calc_estimated_value(self._price_data(per_sqm=1000), 84.0, "주거용")
        # 평당가 = per_sqm * 3.3058
        assert result["price_per_pyeong"] == round(1000 * 3.3058)

    def test_area_pyeong_conversion(self):
        result = calc_estimated_value(self._price_data(), 33.058, "주거용")
        assert abs(result["area_pyeong"] - 10.0) < 0.1

    def test_zero_price_data(self):
        result = calc_estimated_value(_empty_price_data(), 0.0, "주거용")
        assert result["estimated_value"] == 0


# ─────────────────────────────────────────
#  calc_valuation_verdict
# ─────────────────────────────────────────

class TestCalcValuationVerdict:
    def _price_data(self, avg=50000, count=10):
        return {"avg": avg, "count": count, "samples": []}

    def test_low_evaluation(self):
        # 호가가 평균 대비 15% 낮으면 저평가
        r = calc_valuation_verdict(50000, self._price_data(avg=60000), asking_price=50000)
        assert r["valuation_verdict"] == "저평가"
        assert r["deviation_pct"] < -10

    def test_appropriate(self):
        r = calc_valuation_verdict(50000, self._price_data(avg=50000), asking_price=50000)
        assert r["valuation_verdict"] == "적정"
        assert r["deviation_pct"] == 0.0

    def test_slightly_high(self):
        # 호가가 평균 대비 10% 높으면 소폭 고평가
        r = calc_valuation_verdict(55000, self._price_data(avg=50000), asking_price=55000)
        assert r["valuation_verdict"] == "소폭 고평가"

    def test_overvalued(self):
        r = calc_valuation_verdict(70000, self._price_data(avg=50000), asking_price=70000)
        assert r["valuation_verdict"] == "고평가"

    def test_no_asking_uses_estimated(self):
        # asking_price 없으면 estimated_value 기준
        r = calc_valuation_verdict(55000, self._price_data(avg=50000))
        assert r["deviation_pct"] == pytest.approx(10.0, abs=0.1)

    def test_zero_comparable_avg(self):
        r = calc_valuation_verdict(50000, self._price_data(avg=0))
        assert r["deviation_pct"] == 0.0

    def test_comparable_fields(self):
        r = calc_valuation_verdict(50000, self._price_data(avg=50000, count=15))
        assert r["comparable_avg"] == 50000
        assert r["comparable_count"] == 15


# ─────────────────────────────────────────
#  calc_investment_return
# ─────────────────────────────────────────

class TestCalcInvestmentReturn:
    @pytest.mark.parametrize("category,expected_cap,expected_grade", [
        ("주거용", 3.5, "C"),
        ("상업용", 5.0, "B"),
        ("업무용", 4.5, "B"),
        ("산업용", 6.0, "A"),
        ("토지",   2.5, "D"),
    ])
    def test_cap_rate_by_category(self, category, expected_cap, expected_grade):
        r = calc_investment_return(100000, category, 84.0)
        assert r["cap_rate"] == expected_cap
        assert r["investment_grade"] == expected_grade

    def test_annual_income_calculation(self):
        r = calc_investment_return(100000, "상업용", 100.0)
        # 상업용 cap_rate = 5.0% → annual_income = 100000 * 5.0 / 100 = 5000
        assert r["annual_income"] == 5000

    def test_roi_5yr(self):
        r = calc_investment_return(100000, "산업용", 100.0)
        # 산업용 cap_rate = 6.0 → roi_5yr = 6.0 * 5 = 30.0
        assert r["roi_5yr"] == 30.0

    def test_zero_value(self):
        r = calc_investment_return(0, "주거용", 0.0)
        assert r["annual_income"] == 0


# ─────────────────────────────────────────
#  _calc_residual_rate (건축원가법 내부 헬퍼)
# ─────────────────────────────────────────

class TestCalcResidualRate:
    def test_new_building(self):
        rate = _calc_residual_rate(0, 35, 0.10)
        assert rate == 1.0

    def test_at_useful_life(self):
        rate = _calc_residual_rate(35, 35, 0.10)
        assert rate == pytest.approx(0.10, abs=0.05)

    def test_declining_decreases_over_time(self):
        r1 = _calc_residual_rate(5,  35, 0.10)
        r2 = _calc_residual_rate(15, 35, 0.10)
        r3 = _calc_residual_rate(25, 35, 0.10)
        assert r1 > r2 > r3

    def test_straight_line_method(self):
        rate = _calc_residual_rate(10, 40, 0.10, method="straight")
        expected = 1 - (1 - 0.10) * (10 / 40)
        assert rate == pytest.approx(expected, abs=0.001)

    def test_never_below_residual(self):
        # 어떤 경과연수든 잔가율은 잔존가치율 이상이어야 함
        for age in range(0, 50, 5):
            rate = _calc_residual_rate(age, 30, 0.10)
            assert rate >= 0.10


# ─────────────────────────────────────────
#  calc_cost_approach
# ─────────────────────────────────────────

class TestCalcCostApproach:
    def test_basic_warehouse(self):
        result = calc_cost_approach(
            land_area_sqm=1000,
            official_land_price=100,    # 만원/㎡
            build_area_sqm=600,
            build_year=2015,
            category_detail="창고",
        )
        assert result["avg"] > 0
        assert result["land_value"] == 100 * 1000   # 10만원
        assert result["error"] == ""
        assert "건축원가법" in result["source"]

    def test_no_land_price(self):
        result = calc_cost_approach(
            land_area_sqm=0,
            official_land_price=0,
            build_area_sqm=500,
            build_year=2010,
            category_detail="공장",
        )
        assert result["avg"] > 0
        assert result["land_value"] == 0
        assert "표준건축비만" in result["source"]

    def test_zero_area_returns_empty(self):
        result = calc_cost_approach(
            land_area_sqm=0,
            official_land_price=0,
            build_area_sqm=0,
            build_year=2010,
            category_detail="창고",
        )
        assert result["avg"] == 0
        assert result["error"] != ""

    def test_min_max_range(self):
        result = calc_cost_approach(
            land_area_sqm=500, official_land_price=50,
            build_area_sqm=300, build_year=2018,
            category_detail="창고",
        )
        assert result["min"] == round(result["avg"] * 0.85)
        assert result["max"] == round(result["avg"] * 1.15)

    def test_strct_nm_affects_result(self):
        rc = calc_cost_approach(
            land_area_sqm=0, official_land_price=0,
            build_area_sqm=500, build_year=2015,
            category_detail="창고", strct_nm="철근콘크리트",
        )
        rs = calc_cost_approach(
            land_area_sqm=0, official_land_price=0,
            build_area_sqm=500, build_year=2015,
            category_detail="창고", strct_nm="철골조",
        )
        # 철근콘크리트(65만원/㎡) > 철골조(50만원/㎡) → 전자가 더 큰 값
        assert rc["avg"] > rs["avg"]
