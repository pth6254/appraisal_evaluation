"""
test_scoring_tool.py — scoring_tool 단위 테스트

외부 API 없음. 모든 입력을 직접 생성해 검증한다.
"""

import pytest
from schemas.appraisal_result import AppraisalResult
from schemas.property_listing import PropertyListing
from schemas.property_query import PropertyQuery
from tools.scoring_tool import (
    _calc_total_score,
    _recommendation_label,
    _score_investment,
    _score_location,
    _score_price,
    _score_risk,
    calculate_listing_score,
)


# ─────────────────────────────────────────
#  헬퍼 픽스처
# ─────────────────────────────────────────

def _listing(**kwargs) -> PropertyListing:
    defaults = {
        "listing_id":    "T001",
        "address":       "서울시 테스트구 테스트동 1",
        "property_type": "주거용",
        "asking_price":  1_000_000_000,
        "built_year":    2015,
        "floor":         10,
        "station_distance_m": 400,
        "school_distance_m":  500,
        "jeonse_price":  650_000_000,
    }
    defaults.update(kwargs)
    return PropertyListing(**defaults)


def _query(**kwargs) -> PropertyQuery:
    defaults = {"intent": "recommendation"}
    defaults.update(kwargs)
    return PropertyQuery(**defaults)


def _appraisal(**kwargs) -> AppraisalResult:
    defaults = {
        "judgement":  "적정",
        "confidence": 0.8,
        "gap_rate":   0.0,
    }
    defaults.update(kwargs)
    return AppraisalResult(**defaults)


# ─────────────────────────────────────────
#  _calc_total_score
# ─────────────────────────────────────────

class TestCalcTotalScore:
    def test_all_max(self):
        assert _calc_total_score(10.0, 10.0, 10.0, 0.0) == 10.0

    def test_all_min(self):
        assert _calc_total_score(0.0, 0.0, 0.0, 10.0) == 0.0

    def test_weights_sum_to_one(self):
        # price*0.35 + location*0.30 + investment*0.20 + (10-risk)*0.15
        # all at 5 and risk=5: 5*0.35 + 5*0.30 + 5*0.20 + 5*0.15 = 5.0
        assert _calc_total_score(5.0, 5.0, 5.0, 5.0) == 5.0

    def test_bounded_above_10(self):
        # 이미 클램프
        assert _calc_total_score(10.0, 10.0, 10.0, 0.0) <= 10.0

    def test_bounded_below_0(self):
        assert _calc_total_score(0.0, 0.0, 0.0, 10.0) >= 0.0

    def test_price_weight(self):
        # price만 10, 나머지 0, risk=10 → price*0.35 + 0 + 0 + 0
        result = _calc_total_score(10.0, 0.0, 0.0, 10.0)
        assert abs(result - 3.5) < 0.01

    def test_location_weight(self):
        result = _calc_total_score(0.0, 10.0, 0.0, 10.0)
        assert abs(result - 3.0) < 0.01

    def test_investment_weight(self):
        result = _calc_total_score(0.0, 0.0, 10.0, 10.0)
        assert abs(result - 2.0) < 0.01

    def test_safety_weight(self):
        result = _calc_total_score(0.0, 0.0, 0.0, 0.0)
        assert abs(result - 1.5) < 0.01


# ─────────────────────────────────────────
#  _recommendation_label
# ─────────────────────────────────────────

class TestRecommendationLabel:
    def test_best(self):
        assert _recommendation_label(8.0) == "적극 추천"

    def test_above_8(self):
        assert _recommendation_label(9.5) == "적극 추천"

    def test_recommend(self):
        assert _recommendation_label(6.5) == "추천"

    def test_between_65_80(self):
        assert _recommendation_label(7.9) == "추천"

    def test_review(self):
        assert _recommendation_label(5.0) == "검토 필요"

    def test_between_50_65(self):
        assert _recommendation_label(6.4) == "검토 필요"

    def test_not_recommend(self):
        assert _recommendation_label(4.9) == "비추천"

    def test_zero(self):
        assert _recommendation_label(0.0) == "비추천"


# ─────────────────────────────────────────
#  _score_price
# ─────────────────────────────────────────

class TestScorePrice:
    def test_returns_tuple_of_three(self):
        result = _score_price(_listing(), _query(), None)
        assert isinstance(result, tuple) and len(result) == 3

    def test_score_in_range(self):
        score, _, _ = _score_price(_listing(), _query(), _appraisal())
        assert 0.0 <= score <= 10.0

    def test_no_appraisal_neutral(self):
        score, _, _ = _score_price(_listing(), _query(), None)
        assert score == 5.0

    def test_undervalued_gives_high_score(self):
        a = _appraisal(judgement="저평가", confidence=1.0, gap_rate=-0.15)
        score, _, _ = _score_price(_listing(), _query(), a)
        assert score > 6.5

    def test_overvalued_gives_low_score(self):
        a = _appraisal(judgement="고평가", confidence=1.0, gap_rate=0.20)
        score, _, _ = _score_price(_listing(), _query(), a)
        assert score < 5.0

    def test_low_confidence_pulls_toward_center(self):
        a_high = _appraisal(judgement="저평가", confidence=1.0)
        a_low  = _appraisal(judgement="저평가", confidence=0.0)
        s_high, _, _ = _score_price(_listing(), _query(), a_high)
        s_low,  _, _ = _score_price(_listing(), _query(), a_low)
        assert s_high > s_low

    def test_over_budget_penalty(self):
        q = _query(budget_max=800_000_000)
        l = _listing(asking_price=1_000_000_000)
        score, _, risks = _score_price(l, q, None)
        assert score < 5.0
        assert any("초과" in r for r in risks)

    def test_within_budget_bonus(self):
        q = _query(budget_min=800_000_000, budget_max=1_200_000_000)
        l = _listing(asking_price=1_000_000_000)
        score_in, _, _ = _score_price(l, q, None)
        score_no, _, _ = _score_price(l, _query(), None)
        assert score_in > score_no

    def test_undervalued_reason_generated(self):
        a = _appraisal(judgement="저평가", confidence=0.9)
        _, reasons, _ = _score_price(_listing(), _query(), a)
        assert any("저평가" in r for r in reasons)

    def test_overvalued_risk_generated(self):
        a = _appraisal(judgement="고평가", confidence=0.9)
        _, _, risks = _score_price(_listing(), _query(), a)
        assert any("고평가" in r for r in risks)


# ─────────────────────────────────────────
#  _score_location
# ─────────────────────────────────────────

class TestScoreLocation:
    def test_returns_tuple_of_three(self):
        result = _score_location(_listing(), _query())
        assert isinstance(result, tuple) and len(result) == 3

    def test_score_in_range(self):
        score, _, _ = _score_location(_listing(), _query())
        assert 0.0 <= score <= 10.0

    def test_super_station_access(self):
        l = _listing(station_distance_m=150)
        score, reasons, _ = _score_location(l, _query())
        assert score >= 7.0
        assert any("초역세권" in r for r in reasons)

    def test_far_station_penalty(self):
        l = _listing(station_distance_m=1500)
        score_far, _, risks = _score_location(l, _query())
        l_near = _listing(station_distance_m=300)
        score_near, _, _ = _score_location(l_near, _query())
        assert score_far < score_near
        assert any("지하철" in r for r in risks)

    def test_new_build_bonus(self):
        l_new = _listing(built_year=2022)
        l_old = _listing(built_year=1985)
        s_new, reasons, _ = _score_location(l_new, _query())
        s_old, _, risks   = _score_location(l_old, _query())
        assert s_new > s_old
        assert any("신축" in r for r in reasons)
        assert any("노후" in r for r in risks)

    def test_high_floor_bonus(self):
        l_hi  = _listing(floor=15)
        l_low = _listing(floor=2)
        s_hi,  reasons, _ = _score_location(l_hi,  _query())
        s_low, _,       _ = _score_location(l_low, _query())
        assert s_hi > s_low
        assert any("층" in r for r in reasons)

    def test_none_fields_still_returns_score(self):
        l = _listing(station_distance_m=None, school_distance_m=None,
                     built_year=None, floor=None)
        score, _, _ = _score_location(l, _query())
        assert 0.0 <= score <= 10.0

    def test_commercial_school_neutral(self):
        l_com = _listing(property_type="상업용", school_distance_m=100)
        l_res = _listing(property_type="주거용",  school_distance_m=100)
        s_com, reasons_com, _ = _score_location(l_com, _query())
        s_res, reasons_res, _ = _score_location(l_res, _query())
        # 상업용은 학교 거리에 따른 추가 reason이 없어야 함
        school_reasons_com = [r for r in reasons_com if "학교" in r]
        school_reasons_res = [r for r in reasons_res if "학교" in r]
        assert len(school_reasons_com) == 0
        assert len(school_reasons_res) > 0

    def test_max_score_does_not_exceed_10(self):
        l = _listing(station_distance_m=100, school_distance_m=200,
                     built_year=2023, floor=20)
        score, _, _ = _score_location(l, _query())
        assert score <= 10.0


# ─────────────────────────────────────────
#  _score_investment
# ─────────────────────────────────────────

class TestScoreInvestment:
    def test_returns_tuple_of_three(self):
        result = _score_investment(_listing(), None)
        assert isinstance(result, tuple) and len(result) == 3

    def test_score_in_range(self):
        score, _, _ = _score_investment(_listing(), None)
        assert 0.0 <= score <= 10.0

    def test_high_jeonse_ratio_high_score(self):
        l = _listing(asking_price=1_000_000_000, jeonse_price=800_000_000)  # 80%
        score, reasons, _ = _score_investment(l, None)
        assert score >= 7.0
        assert any("전세가율" in r for r in reasons)

    def test_low_jeonse_ratio_low_score(self):
        l = _listing(asking_price=1_000_000_000, jeonse_price=250_000_000)  # 25%
        score, _, risks = _score_investment(l, None)
        assert score < 5.0
        assert any("갭" in r for r in risks)

    def test_no_jeonse_neutral(self):
        l = _listing(jeonse_price=None)
        score, _, _ = _score_investment(l, None)
        assert score == 5.0

    def test_undervalued_appraisal_bonus(self):
        l = _listing(jeonse_price=None)
        a_under = _appraisal(gap_rate=-0.15)
        a_over  = _appraisal(gap_rate= 0.20)
        s_under, reasons, _ = _score_investment(l, a_under)
        s_over,  _,       _ = _score_investment(l, a_over)
        assert s_under > s_over
        assert any("저평가" in r for r in reasons)

    def test_overvalued_appraisal_penalty(self):
        l = _listing(jeonse_price=None)
        a = _appraisal(gap_rate=0.20)
        _, _, risks = _score_investment(l, a)
        assert any("고평가" in r for r in risks)

    def test_small_gap_rate_no_adjustment(self):
        l = _listing(jeonse_price=None)
        a_before = _appraisal(gap_rate=0.0)
        a_after  = _appraisal(gap_rate=0.03)
        s1, _, _ = _score_investment(l, a_before)
        s2, _, _ = _score_investment(l, a_after)
        # ±5% 이내는 조정 없음
        assert s1 == s2 == 5.0

    def test_score_capped_at_10(self):
        l = _listing(asking_price=1_000_000_000, jeonse_price=800_000_000)
        a = _appraisal(gap_rate=-0.20)
        score, _, _ = _score_investment(l, a)
        assert score <= 10.0

    def test_score_floor_at_0(self):
        l = _listing(asking_price=1_000_000_000, jeonse_price=100_000_000)
        a = _appraisal(gap_rate=0.30)
        score, _, _ = _score_investment(l, a)
        assert score >= 0.0


# ─────────────────────────────────────────
#  _score_risk
# ─────────────────────────────────────────

class TestScoreRisk:
    def test_returns_tuple_of_three(self):
        result = _score_risk(_listing(), None)
        assert isinstance(result, tuple) and len(result) == 3

    def test_score_in_range(self):
        score, _, _ = _score_risk(_listing(), None)
        assert 0.0 <= score <= 10.0

    def test_new_build_low_risk(self):
        l = _listing(built_year=2024)
        score, reasons, _ = _score_risk(l, _appraisal(confidence=0.9))
        assert score < 3.0
        assert any("신축" in r for r in reasons)

    def test_very_old_high_risk(self):
        l = _listing(built_year=1980)
        score, _, risks = _score_risk(l, _appraisal(confidence=0.9))
        assert score >= 3.0
        assert any("노후" in r or "재건축" in r for r in risks)

    def test_no_appraisal_increases_risk(self):
        l = _listing()
        s_no,  _, risks_no  = _score_risk(l, None)
        s_yes, _, risks_yes = _score_risk(l, _appraisal(confidence=0.9))
        assert s_no > s_yes
        assert any("미제공" in r for r in risks_no)

    def test_low_confidence_increases_risk(self):
        l = _listing()
        s_low,  _, _ = _score_risk(l, _appraisal(confidence=0.2))
        s_high, _, _ = _score_risk(l, _appraisal(confidence=0.9))
        assert s_low > s_high

    def test_warnings_increase_risk(self):
        l = _listing()
        a_clean = _appraisal(warnings=[])
        a_warn  = _appraisal(warnings=["경고1", "경고2", "경고3"])
        s_clean, _, _     = _score_risk(l, a_clean)
        s_warn,  _, risks = _score_risk(l, a_warn)
        assert s_warn > s_clean
        assert any("주의사항" in r for r in risks)

    def test_overvalued_increases_risk(self):
        l = _listing()
        a_over  = _appraisal(judgement="고평가", confidence=0.9)
        a_under = _appraisal(judgement="저평가", confidence=0.9)
        s_over,  _, _ = _score_risk(l, a_over)
        s_under, _, _ = _score_risk(l, a_under)
        assert s_over > s_under

    def test_score_capped_at_10(self):
        l = _listing(built_year=1970)
        a = _appraisal(confidence=0.1, warnings=["w1","w2","w3","w4"],
                       judgement="고평가")
        score, _, _ = _score_risk(l, a)
        assert score <= 10.0

    def test_score_floor_at_0(self):
        l = _listing(built_year=2024)
        a = _appraisal(confidence=1.0, warnings=[], judgement="저평가")
        score, _, _ = _score_risk(l, a)
        assert score >= 0.0


# ─────────────────────────────────────────
#  calculate_listing_score (통합)
# ─────────────────────────────────────────

class TestCalculateListingScore:
    def test_returns_dict_with_required_keys(self):
        result = calculate_listing_score(_listing(), _query())
        expected_keys = {
            "total_score", "price_score", "location_score",
            "investment_score", "risk_score",
            "recommendation_label", "reasons", "risks",
        }
        assert set(result.keys()) == expected_keys

    def test_scores_are_floats_in_range(self):
        result = calculate_listing_score(_listing(), _query())
        for key in ("total_score", "price_score", "location_score",
                    "investment_score", "risk_score"):
            assert isinstance(result[key], float)
            assert 0.0 <= result[key] <= 10.0

    def test_reasons_and_risks_are_lists(self):
        result = calculate_listing_score(_listing(), _query())
        assert isinstance(result["reasons"], list)
        assert isinstance(result["risks"],   list)

    def test_recommendation_label_is_valid(self):
        result = calculate_listing_score(_listing(), _query())
        valid = {"적극 추천", "추천", "검토 필요", "비추천"}
        assert result["recommendation_label"] in valid

    def test_no_appraisal_still_runs(self):
        result = calculate_listing_score(_listing(), _query(), appraisal=None)
        assert 0.0 <= result["total_score"] <= 10.0

    def test_premium_listing_high_score(self):
        """초역세권 신축 저평가 매물 → 높은 종합 점수"""
        l = _listing(
            built_year=2022, floor=20,
            station_distance_m=150, school_distance_m=200,
            asking_price=1_000_000_000, jeonse_price=800_000_000,
        )
        a = _appraisal(judgement="저평가", confidence=0.95, gap_rate=-0.12)
        result = calculate_listing_score(l, _query(budget_max=1_200_000_000), a)
        assert result["total_score"] >= 7.0
        assert result["recommendation_label"] in ("추천", "적극 추천")

    def test_bad_listing_low_score(self):
        """구축·원거리·고평가 매물 → 낮은 종합 점수"""
        l = _listing(
            built_year=1975, floor=2,
            station_distance_m=1800, school_distance_m=1500,
            asking_price=2_000_000_000, jeonse_price=300_000_000,
        )
        a = _appraisal(judgement="고평가", confidence=0.3, gap_rate=0.25,
                       warnings=["실거래 2건 미만", "공시가 역산"])
        result = calculate_listing_score(l, _query(budget_max=1_000_000_000), a)
        assert result["total_score"] < 5.0
        assert result["recommendation_label"] in ("검토 필요", "비추천")

    def test_total_score_equals_formula(self):
        """total_score 가 가중치 공식과 일치하는지 직접 검증"""
        result = calculate_listing_score(_listing(), _query(), _appraisal())
        expected = (
            result["price_score"]      * 0.35
            + result["location_score"] * 0.30
            + result["investment_score"] * 0.20
            + (10.0 - result["risk_score"]) * 0.15
        )
        assert abs(result["total_score"] - round(expected, 2)) < 0.01

    def test_reasons_not_empty_for_good_listing(self):
        l = _listing(station_distance_m=150, built_year=2022, floor=15,
                     jeonse_price=750_000_000)
        a = _appraisal(judgement="저평가", confidence=0.9, gap_rate=-0.10)
        result = calculate_listing_score(l, _query(), a)
        assert len(result["reasons"]) > 0

    def test_risks_not_empty_for_bad_listing(self):
        l = _listing(built_year=1975, station_distance_m=2000,
                     jeonse_price=200_000_000)
        a = _appraisal(judgement="고평가", confidence=0.2,
                       warnings=["경고1"])
        result = calculate_listing_score(l, _query(budget_max=500_000_000), a)
        assert len(result["risks"]) > 0

    def test_commercial_listing_no_jeonse(self):
        l = _listing(
            property_type="상업용",
            asking_price=2_000_000_000,
            jeonse_price=None,
        )
        result = calculate_listing_score(l, _query(property_type="상업용"))
        assert 0.0 <= result["total_score"] <= 10.0

    def test_scores_rounded_to_2dp(self):
        result = calculate_listing_score(_listing(), _query(), _appraisal())
        for key in ("total_score", "price_score", "location_score",
                    "investment_score", "risk_score"):
            val = result[key]
            assert val == round(val, 2)
