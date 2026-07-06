"""
test_tax_rules.py — 세금·금융규제 규칙 골든 테스트

기대값은 홈택스·위택스 모의계산 방식(누진공제·안분·장특공)으로 수기 산출한
대조값이다. 세법 개정으로 tax_rules.py 를 갱신하면 이 테스트가 깨져서
갱신 시점을 알려준다. (TAX_RULES_AS_OF 확인)
"""

from __future__ import annotations

import pytest

from tax_rules import (
    TAX_RULES_AS_OF,
    calc_annual_holding_tax,
    calc_capital_gains_tax,
    check_dsr,
    check_ltv,
    estimate_official_price,
)


# ─────────────────────────────────────────
#  양도소득세
# ─────────────────────────────────────────

class TestCapitalGainsTax:
    def test_no_gain_no_tax(self):
        r = calc_capital_gains_tax(500_000_000, 480_000_000, 5)
        assert r["tax"] == 0 and r["note"] == "양도차익 없음"

    def test_1home_under_12eok_exempt(self):
        """1세대1주택 2년 보유, 양도가 12억 이하 → 비과세."""
        r = calc_capital_gains_tax(800_000_000, 1_100_000_000, 5, owned_homes=1)
        assert r["exempt"] and r["tax"] == 0

    def test_1home_under_2years_not_exempt(self):
        """1주택이라도 2년 미만 보유 → 과세 (단기 60%)."""
        r = calc_capital_gains_tax(800_000_000, 1_100_000_000, 1, owned_homes=1)
        assert not r["exempt"] and r["tax"] > 0
        assert "60%" in r["note"]

    def test_1home_expensive_proration_and_ltsd80(self):
        """고가 1주택 (취득 8억→양도 15억, 10년 보유+거주):
        12억 초과분 안분 (7억×3/15=1.4억) + 장특공 80% → 과표 2,550만."""
        r = calc_capital_gains_tax(800_000_000, 1_500_000_000, 10,
                                   owned_homes=1, residence_years=10)
        assert r["ltsd_rate"] == 0.80
        expected_national = round(25_500_000 * 0.15 - 1_260_000)   # 15% 구간
        assert abs(r["national_tax"] - expected_national) <= 10
        assert r["local_tax"] == round(r["national_tax"] * 0.10)

    def test_multi_home_general_taxation(self):
        """2주택 (취득 5억→양도 8억, 경비 2천만, 5년): 일반과세 + 장특공 10%."""
        r = calc_capital_gains_tax(500_000_000, 800_000_000, 5,
                                   owned_homes=2, expenses=20_000_000)
        taxable  = round(280_000_000 * 0.90) - 2_500_000
        expected = round(taxable * 0.38 - 19_940_000)               # 38% 구간
        assert r["national_tax"] == expected
        assert "유예" in r["note"]                                   # 다주택 중과 유예 명시

    def test_short_term_70pct(self):
        r = calc_capital_gains_tax(500_000_000, 600_000_000, 0, owned_homes=1)
        assert r["national_tax"] == round((100_000_000 - 2_500_000) * 0.70)


# ─────────────────────────────────────────
#  보유세
# ─────────────────────────────────────────

class TestHoldingTax:
    def test_zero_official_price(self):
        assert calc_annual_holding_tax(0)["total"] == 0

    def test_official_5eok_single_home(self):
        """공시 5억 1주택: 과표 2.2억(44%) → 특례세율 0.2% − 18만 = 26만."""
        r = calc_annual_holding_tax(500_000_000, owned_homes=1)
        assert r["property_tax"] == round(220_000_000 * 0.002 - 180_000)
        assert r["jongbu_tax"] == 0
        assert r["edu_tax"] == round(r["property_tax"] * 0.2)

    def test_official_15eok_jongbu(self):
        """공시 15억 1주택: 종부 과표 (15−12억)×60%=1.8억 → 0.5% = 90만 + 농특 18만."""
        r = calc_annual_holding_tax(1_500_000_000, owned_homes=1)
        assert r["jongbu_tax"] == 900_000
        assert r["nongteuk"]   == 180_000

    def test_multi_home_higher(self):
        """다주택은 공정시장가액비율 60% + 종부 공제 9억 → 세부담 증가."""
        single = calc_annual_holding_tax(1_000_000_000, owned_homes=1)["total"]
        multi  = calc_annual_holding_tax(1_000_000_000, owned_homes=3)["total"]
        assert multi > single

    def test_estimate_official_price(self):
        assert estimate_official_price(1_000_000_000) == 690_000_000


# ─────────────────────────────────────────
#  DSR / LTV
# ─────────────────────────────────────────

class TestFinanceRules:
    def test_dsr_stress_rate_applied(self):
        r = check_dsr(500_000_000, 4.3, 30, 80_000_000)
        assert r["stress_rate"] == 5.8                    # 4.3 + 1.5
        assert 0.42 <= r["dsr"] <= 0.46                   # 스트레스 연상환 ≈ 3,520만/8,000만
        assert r["exceeded"]
        assert 0 < r["max_loan_amount"] < 500_000_000

    def test_dsr_within_limit(self):
        r = check_dsr(200_000_000, 4.0, 30, 100_000_000)
        assert not r["exceeded"]

    def test_dsr_existing_debt_reduces_capacity(self):
        base = check_dsr(300_000_000, 4.0, 30, 80_000_000)
        with_debt = check_dsr(300_000_000, 4.0, 30, 80_000_000,
                              existing_annual_debt_payment=10_000_000)
        assert with_debt["max_loan_amount"] < base["max_loan_amount"]

    def test_ltv_limits(self):
        assert not check_ltv(1_000_000_000, 700_000_000, owned_homes=1)["exceeded"]
        assert check_ltv(1_000_000_000, 700_000_000, owned_homes=2)["exceeded"]
        r = check_ltv(1_000_000_000, 600_000_000, owned_homes=1, adjusted_area=True)
        assert r["limit"] == 0.50 and r["exceeded"]

    def test_rules_dated(self):
        assert TAX_RULES_AS_OF >= "2026-01-01"
