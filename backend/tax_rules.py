"""
tax_rules.py — 부동산 세금·금융규제 규칙 테이블 (법령 기반)

세율·규제는 실시간 데이터가 아니라 법령이다. 이 모듈은 법령 규칙을
코드로 관리하고, 개정 시 이 파일만 갱신한다.
tests/test_tax_rules.py 의 골든 테스트(홈택스·위택스 모의계산 대조)가
개정 시점을 감지한다.

근거 법령:
  양도소득세 — 소득세법 §89(비과세), §95(장기보유특별공제), §104(세율)
  재산세     — 지방세법 §111, 지방세법 시행령 §109(공정시장가액비율)
  종부세     — 종합부동산세법 §8~9
  DSR/LTV    — 금융위 은행업감독규정 (총량규제)

간이 계산 고지:
  1세대 판정·감면 특례·조정대상지역 이력 등 개별 사정은 반영하지 않는다.
  실제 세액은 세무사 상담이 필요하다.
"""

from __future__ import annotations

TAX_RULES_AS_OF = "2026-01-01"   # 규칙 기준일 — 리포트에 표기

INF = float("inf")


# ═══════════════════════════════════════════
#  1. 양도소득세
# ═══════════════════════════════════════════

CGT_EXEMPT_LIMIT_1HOME = 1_200_000_000   # 1세대1주택 고가주택 기준 12억
CGT_BASIC_DEDUCTION    = 2_500_000       # 연 기본공제 250만원

# 기본세율 (과표 상한, 세율, 누진공제) — 소득세법 §55
CGT_BRACKETS = [
    (14_000_000,     0.06, 0),
    (50_000_000,     0.15, 1_260_000),
    (88_000_000,     0.24, 5_760_000),
    (150_000_000,    0.35, 15_440_000),
    (300_000_000,    0.38, 19_940_000),
    (500_000_000,    0.40, 25_940_000),
    (1_000_000_000,  0.42, 35_940_000),
    (INF,            0.45, 65_940_000),
]

# 단기 양도 세율 (주택) — 보유 1년 미만 70%, 2년 미만 60%
CGT_SHORT_TERM = {1: 0.70, 2: 0.60}

# 다주택 조정대상지역 중과 (+20%p/+30%p) — 현재 중과 배제 유예 상태 → 0 적용
MULTI_HOME_CGT_SURCHARGE_SUSPENDED = True

LOCAL_INCOME_TAX_RATE = 0.10   # 지방소득세 = 양도소득세의 10%


def _progressive_tax(base: int, brackets: list[tuple]) -> int:
    """누진공제 방식 세액 계산."""
    for limit, rate, deduction in brackets:
        if base <= limit:
            return max(0, round(base * rate - deduction))
    return 0


def calc_capital_gains_tax(
    purchase_price: int,
    sale_price: int,
    holding_years: int,
    owned_homes: int = 1,
    expenses: int = 0,          # 필요경비 (취득세·중개보수 등)
    residence_years: int = 0,   # 거주 연수 (1주택 장특공 거주분)
) -> dict:
    """
    주택 양도소득세 간이 계산 (지방소득세 포함).

    반환: {tax, national_tax, local_tax, taxable_gain,
           ltsd_rate(장특공률), exempt(비과세 여부), note}
    """
    gain = sale_price - purchase_price - expenses
    if gain <= 0:
        return {"tax": 0, "national_tax": 0, "local_tax": 0, "taxable_gain": 0,
                "ltsd_rate": 0.0, "exempt": False, "note": "양도차익 없음"}

    # ── 1세대1주택 비과세 (2년 보유) ──
    is_single = owned_homes <= 1
    if is_single and holding_years >= 2:
        if sale_price <= CGT_EXEMPT_LIMIT_1HOME:
            return {"tax": 0, "national_tax": 0, "local_tax": 0, "taxable_gain": 0,
                    "ltsd_rate": 0.0, "exempt": True,
                    "note": f"1세대1주택 비과세 (양도가 {CGT_EXEMPT_LIMIT_1HOME // 100_000_000}억 이하)"}
        # 고가주택: 12억 초과분 안분 과세
        gain = round(gain * (sale_price - CGT_EXEMPT_LIMIT_1HOME) / sale_price)
        note = "1세대1주택 고가주택 — 12억 초과분 과세"
    else:
        note = "일반 과세" if is_single else f"{owned_homes}주택 보유 과세"
        if not is_single and MULTI_HOME_CGT_SURCHARGE_SUSPENDED:
            note += " (다주택 중과 유예 적용)"

    # ── 장기보유특별공제 ──
    ltsd = 0.0
    if holding_years >= 3:
        if is_single and holding_years >= 2 and residence_years >= 2:
            # 1주택 특례: 보유 4%/년 + 거주 4%/년 (각 최대 40%)
            ltsd = min(holding_years, 10) * 0.04 + min(residence_years, 10) * 0.04
            ltsd = min(ltsd, 0.80)
        else:
            # 일반: 2%/년, 최대 30%
            ltsd = min(min(holding_years, 15) * 0.02, 0.30)

    taxable = round(gain * (1 - ltsd)) - CGT_BASIC_DEDUCTION
    if taxable <= 0:
        return {"tax": 0, "national_tax": 0, "local_tax": 0, "taxable_gain": 0,
                "ltsd_rate": ltsd, "exempt": False, "note": note + " — 공제 후 과표 없음"}

    # ── 세율 적용 ──
    if holding_years < 1:
        national = round(taxable * CGT_SHORT_TERM[1])
        note += " · 단기양도 70%"
    elif holding_years < 2:
        national = round(taxable * CGT_SHORT_TERM[2])
        note += " · 단기양도 60%"
    else:
        national = _progressive_tax(taxable, CGT_BRACKETS)

    local = round(national * LOCAL_INCOME_TAX_RATE)
    return {"tax": national + local, "national_tax": national, "local_tax": local,
            "taxable_gain": taxable, "ltsd_rate": ltsd, "exempt": False, "note": note}


# ═══════════════════════════════════════════
#  2. 보유세 (재산세 + 종합부동산세)
# ═══════════════════════════════════════════

# 공정시장가액비율 — 지방세법 시행령 §109
def _fair_market_ratio_property(official_price: int, is_single_home: bool) -> float:
    if not is_single_home:
        return 0.60
    if official_price <= 300_000_000: return 0.43
    if official_price <= 600_000_000: return 0.44
    return 0.45

# 재산세 표준세율 (주택) — 과표 기준
_PROPERTY_TAX_STANDARD = [
    (60_000_000,   0.0010, 0),
    (150_000_000,  0.0015, 30_000),
    (300_000_000,  0.0025, 180_000),
    (INF,          0.0040, 630_000),
]
# 1주택 공시 9억 이하 특례세율
_PROPERTY_TAX_SPECIAL = [
    (60_000_000,   0.0005, 0),
    (150_000_000,  0.0010, 30_000),
    (300_000_000,  0.0020, 180_000),
    (INF,          0.0035, 630_000),
]

URBAN_AREA_TAX_RATE = 0.0014   # 도시지역분 (과표 기준)
LOCAL_EDU_TAX_RATE  = 0.20     # 지방교육세 (재산세액 기준)

# 종부세 — 공제·공정시장가액비율·세율
JONGBU_DEDUCTION_1HOME = 1_200_000_000
JONGBU_DEDUCTION_MULTI = 900_000_000
JONGBU_FAIR_RATIO      = 0.60
_JONGBU_BRACKETS_BASIC = [   # 2주택 이하 (과표 상한, 세율)
    (300_000_000,   0.005), (600_000_000,  0.007), (1_200_000_000, 0.010),
    (2_500_000_000, 0.013), (5_000_000_000, 0.015), (9_400_000_000, 0.020),
    (INF,           0.027),
]
_JONGBU_BRACKETS_MULTI = [   # 3주택 이상
    (300_000_000,   0.005), (600_000_000,  0.007), (1_200_000_000, 0.010),
    (2_500_000_000, 0.020), (5_000_000_000, 0.030), (9_400_000_000, 0.040),
    (INF,           0.050),
]
NONGTEUK_RATE = 0.20   # 농어촌특별세 (종부세액 기준)


def _progressive_cumulative(base: int, brackets: list[tuple]) -> int:
    """구간 누적 방식 세액 계산."""
    tax, prev = 0.0, 0
    for limit, rate in brackets:
        if base <= prev:
            break
        chunk = min(base, limit) - prev
        tax += chunk * rate
        prev = limit
    return round(tax)


def calc_annual_holding_tax(official_price: int, owned_homes: int = 1) -> dict:
    """
    연간 보유세 간이 계산 (주택 1채 기준 공시가격).

    간이 가정: 종부세는 해당 주택 공시가격만으로 산정 (합산 배제),
    재산세 중복분 공제 생략 → 실제보다 약간 보수적(높게) 산출.

    반환: {property_tax, urban_tax, edu_tax, jongbu_tax, nongteuk, total}
    """
    if official_price <= 0:
        return {"property_tax": 0, "urban_tax": 0, "edu_tax": 0,
                "jongbu_tax": 0, "nongteuk": 0, "total": 0}

    is_single = owned_homes <= 1

    # ── 재산세 ──
    base = round(official_price * _fair_market_ratio_property(official_price, is_single))
    brackets = (_PROPERTY_TAX_SPECIAL
                if is_single and official_price <= 900_000_000
                else _PROPERTY_TAX_STANDARD)
    prop_tax  = _progressive_tax(base, brackets)
    urban_tax = round(base * URBAN_AREA_TAX_RATE)
    edu_tax   = round(prop_tax * LOCAL_EDU_TAX_RATE)

    # ── 종부세 ──
    deduction = JONGBU_DEDUCTION_1HOME if is_single else JONGBU_DEDUCTION_MULTI
    jongbu_tax = nongteuk = 0
    if official_price > deduction:
        jb_base    = round((official_price - deduction) * JONGBU_FAIR_RATIO)
        jb_brackets = _JONGBU_BRACKETS_BASIC if owned_homes <= 2 else _JONGBU_BRACKETS_MULTI
        jongbu_tax = _progressive_cumulative(jb_base, jb_brackets)
        nongteuk   = round(jongbu_tax * NONGTEUK_RATE)

    total = prop_tax + urban_tax + edu_tax + jongbu_tax + nongteuk
    return {"property_tax": prop_tax, "urban_tax": urban_tax, "edu_tax": edu_tax,
            "jongbu_tax": jongbu_tax, "nongteuk": nongteuk, "total": total}


# 공시가격 추정 (미입력 시): 시세 × 현실화율
OFFICIAL_PRICE_REALIZATION = 0.69


def estimate_official_price(market_price: int) -> int:
    return round(market_price * OFFICIAL_PRICE_REALIZATION)


# ═══════════════════════════════════════════
#  3. DSR / LTV (금융위 총량규제)
# ═══════════════════════════════════════════

DSR_LIMIT          = 0.40   # 은행권 차주단위 DSR
STRESS_RATE_ADDON  = 1.5    # 스트레스 DSR 가산금리 (%p, 3단계 기준 간이)

# LTV 한도 — (조정대상지역 여부, 보유주택) 기준 간이
LTV_LIMITS = {
    (False, "무주택·1주택"): 0.70,
    (False, "다주택"):       0.60,
    (True,  "무주택·1주택"): 0.50,
    (True,  "다주택"):       0.30,
}


def _annuity_monthly(loan: int, annual_rate: float, years: int) -> float:
    """원리금균등 월 상환액 (DSR 산정은 상환방식 무관 원리금균등 환산)."""
    r = annual_rate / 100 / 12
    n = years * 12
    if r == 0:
        return loan / n
    return loan * r * (1 + r) ** n / ((1 + r) ** n - 1)


def check_dsr(
    loan_amount: int,
    annual_interest_rate: float,
    loan_years: int,
    annual_income: int,
    existing_annual_debt_payment: int = 0,
) -> dict:
    """
    스트레스 DSR 검증.

    반환: {dsr, limit, stress_rate, annual_payment, exceeded, max_loan_amount}
    """
    stress_rate = annual_interest_rate + STRESS_RATE_ADDON
    annual_payment = round(_annuity_monthly(loan_amount, stress_rate, loan_years) * 12)
    dsr = (annual_payment + existing_annual_debt_payment) / annual_income if annual_income > 0 else 0.0

    # 한도 내 최대 대출액 역산
    max_annual = annual_income * DSR_LIMIT - existing_annual_debt_payment
    if max_annual <= 0:
        max_loan = 0
    else:
        unit = _annuity_monthly(100_000_000, stress_rate, loan_years) * 12   # 1억당 연 상환액
        max_loan = round(max_annual / unit * 100_000_000)

    return {
        "dsr":             round(dsr, 4),
        "limit":           DSR_LIMIT,
        "stress_rate":     round(stress_rate, 2),
        "annual_payment":  annual_payment,
        "exceeded":        dsr > DSR_LIMIT,
        "max_loan_amount": max_loan,
    }


def check_ltv(
    purchase_price: int,
    loan_amount: int,
    owned_homes: int = 1,
    adjusted_area: bool = False,
) -> dict:
    """LTV 한도 검증. 반환: {ltv, limit, exceeded, max_loan_amount}"""
    bucket = "다주택" if owned_homes >= 2 else "무주택·1주택"
    limit  = LTV_LIMITS[(adjusted_area, bucket)]
    ltv    = loan_amount / purchase_price if purchase_price > 0 else 0.0
    return {
        "ltv":             round(ltv, 4),
        "limit":           limit,
        "exceeded":        ltv > limit,
        "max_loan_amount": round(purchase_price * limit),
    }
