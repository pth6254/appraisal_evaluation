"""
pages/5_투자시뮬레이션.py — 부동산 투자 시뮬레이션 (Phase 4-4)

매수가·대출·보유 기간·임대 수입을 입력하면 router.run_simulation()을 호출해
취득비용·월 현금흐름·수익률 시나리오를 계산하고 표시한다.

연동:
  - 4_매물추천.py에서 "📈 이 매물로 시뮬레이션" 버튼 클릭 시
    session_state["sim_from_listing"]에 매물 dict가 담겨 이 페이지로 전달된다.
    페이지 로드 시 해당 정보로 입력 폼을 자동 채운다.

⚠️  간이 계산 고지:
    취득세·중개보수는 2024년 기준 간이 세율을 적용한다.
    실제 세율은 취득 시점·보유 주택 수·지역 등에 따라 달라질 수 있다.
    이 결과를 실제 투자 의사결정에 직접 사용하지 마라.
"""

from __future__ import annotations

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

import streamlit as st
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# ─────────────────────────────────────────────────────────────────────────────
#  페이지 설정
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="투자 시뮬레이션 — AppraisalAI",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

.sim-header {
    background: linear-gradient(135deg, #0d3b2e 0%, #1a7a52 100%);
    border-radius: 12px;
    padding: 24px 28px;
    color: white;
    margin-bottom: 24px;
}
.sim-header h2 { margin: 0 0 6px; font-size: 1.5rem; font-weight: 700; }
.sim-header p  { margin: 0; opacity: 0.82; font-size: 0.92rem; }

.section-label {
    font-size: 0.75rem; font-weight: 600; color: #1a7a52;
    letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 6px;
}
.sim-notice {
    border-left: 4px solid #e5c100; background: #fffbe6;
    padding: 10px 14px; border-radius: 0 6px 6px 0;
    font-size: 0.83rem; color: #555; margin-bottom: 16px;
}
.verdict-box {
    border-radius: 10px; padding: 14px 18px; margin-top: 12px;
    font-size: 0.95rem; font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  상수
# ─────────────────────────────────────────────────────────────────────────────

PROP_TYPES   = ["아파트", "오피스텔", "상가", "오피스", "공장", "토지"]
REPAY_LABELS = {
    "equal_payment":   "원리금균등상환",
    "equal_principal": "원금균등상환",
    "interest_only":   "만기일시상환",
}
RENTAL_MODES = ["없음 (자가 거주)", "전세", "월세"]

# 매물 추천 property_type → PROP_TYPES 매핑
_LISTING_TYPE_MAP = {
    "주거용": "아파트",
    "상업용": "상가",
    "업무용": "오피스",
    "산업용": "공장",
    "토지":   "토지",
}

# 폼 위젯 기본값 (session_state 미초기화 시 사용)
_WIDGET_DEFAULTS: dict = {
    "sim_pp_str":       "",
    "sim_prop_type":    "아파트",
    "sim_loan_ratio":   50,
    "sim_interest_rate": 4.0,
    "sim_loan_years":   30,
    "sim_repay_type":   "equal_payment",
    "sim_holding_years": 3,
    "sim_growth_rate":  0.0,
    "sim_rental_mode":  "없음 (자가 거주)",
    "sim_jeonse_str":   "",
    "sim_rent_man":     0,
    "sim_mgmt_man":     0,
}


# ─────────────────────────────────────────────────────────────────────────────
#  유틸
# ─────────────────────────────────────────────────────────────────────────────

def _parse_price_to_won(text: str) -> int:
    """'5억', '5억3000만', '10억5천' 등 → 원 단위 int (실패 시 0)"""
    if not text or not text.strip():
        return 0
    text = text.strip().replace(",", "").replace(" ", "").replace("천", "000")
    try:
        if "억" in text:
            parts = text.replace("만원", "").replace("만", "").split("억")
            eok = float(parts[0]) * 1_0000_0000
            man = float(parts[1]) * 10_000 if parts[1] else 0
            return int(eok + man)
        if "만원" in text or "만" in text:
            return int(float(text.replace("만원", "").replace("만", "")) * 10_000)
        val = float(text)
        return int(val) if val >= 10_000_000 else int(val * 10_000)
    except (ValueError, IndexError):
        return 0


def _won_to_str(won: int) -> str:
    """원 단위 int → '5억', '5억3000만' 형태의 입력용 문자열"""
    if won <= 0:
        return ""
    eok = won // 1_0000_0000
    man = (won % 1_0000_0000) // 10_000
    if eok and man:
        return f"{eok}억{man:,}만"
    if eok:
        return f"{eok}억"
    return f"{man:,}만"


def _fmt_won(won: int | None) -> str:
    if won is None:
        return "—"
    sign = "-" if won < 0 else ""
    won  = abs(won)
    eok  = won // 1_0000_0000
    man  = (won % 1_0000_0000) // 10_000
    if eok and man:
        return f"{sign}{eok}억 {man:,}만원"
    if eok:
        return f"{sign}{eok}억원"
    return f"{sign}{man:,}만원"


def _verdict_color(aroi: float) -> str:
    if aroi >= 10:  return "#27AE60"
    if aroi >= 5:   return "#2980B9"
    if aroi >= 0:   return "#E67E22"
    return "#E74C3C"


def _apply_listing_defaults(data: dict) -> None:
    """매물 dict → 폼 위젯 session_state 키 설정 (pre-population)"""
    price = data.get("asking_price", 0)
    if price > 0:
        st.session_state["sim_pp_str"] = _won_to_str(price)

    ptype = data.get("property_type", "주거용")
    mapped = _LISTING_TYPE_MAP.get(ptype, ptype)
    if mapped in PROP_TYPES:
        st.session_state["sim_prop_type"] = mapped

    jeonse = data.get("jeonse_price") or 0
    if jeonse > 0:
        st.session_state["sim_rental_mode"] = "전세"
        st.session_state["sim_jeonse_str"]  = _won_to_str(jeonse)

    mgmt = data.get("maintenance_fee") or 0
    if mgmt > 0:
        st.session_state["sim_mgmt_man"] = max(0, mgmt // 10_000)


# ─────────────────────────────────────────────────────────────────────────────
#  헤더
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="sim-header">
  <h2>📈 부동산 투자 시뮬레이션</h2>
  <p>매수가·대출 조건·보유 기간을 입력하면 취득비용·월 현금흐름·수익률 시나리오를 계산합니다.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sim-notice">
  ⚠️ <b>간이 계산 안내</b>: 취득세·중개보수는 2024년 기준 간이 세율을 적용합니다.
  실제 세율은 취득 시점·보유 주택 수·지역에 따라 다를 수 있습니다.
  이 결과를 실제 투자 의사결정에 직접 사용하지 마세요.
  <br>투자 전 반드시 전문가(공인중개사·세무사)와 상담하세요.
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  session_state 초기화
# ─────────────────────────────────────────────────────────────────────────────

for _k, _v in _WIDGET_DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

if "sim5_result" not in st.session_state:
    st.session_state["sim5_result"] = None
if "sim5_inp" not in st.session_state:
    st.session_state["sim5_inp"] = None


# ─────────────────────────────────────────────────────────────────────────────
#  추천 매물 연동 — pre-population
# ─────────────────────────────────────────────────────────────────────────────

listing_data: dict | None = st.session_state.get("sim_from_listing")

if listing_data and not st.session_state.get("sim_listing_applied"):
    _apply_listing_defaults(listing_data)
    st.session_state["sim_listing_applied"] = True

if listing_data:
    name  = listing_data.get("complex_name") or listing_data.get("address", "매물")
    price = listing_data.get("asking_price", 0)
    col_info, col_clear = st.columns([5, 1])
    with col_info:
        st.info(
            f"🏠 **{name}** 매물 정보가 입력 폼에 자동 반영되었습니다.  \n"
            f"호가: **{_fmt_won(price)}** — 조건을 조정한 뒤 시뮬레이션을 실행하세요.",
        )
    with col_clear:
        if st.button("해제", key="clear_listing", use_container_width=True,
                     help="매물 연동 해제 (폼 값은 유지됨)"):
            st.session_state.pop("sim_from_listing", None)
            st.session_state["sim_listing_applied"] = False
            st.rerun()
    st.markdown("")


# ─────────────────────────────────────────────────────────────────────────────
#  임대 방식 선택 — 폼 외부에서 선택해야 즉시 리렌더링됨
# ─────────────────────────────────────────────────────────────────────────────

st.markdown('<div class="section-label">💰 임대 방식</div>', unsafe_allow_html=True)
rental_mode = st.radio(
    "임대 방식",
    RENTAL_MODES,
    key="sim_rental_mode",
    horizontal=True,
    label_visibility="collapsed",
)


# ─────────────────────────────────────────────────────────────────────────────
#  입력 폼
# ─────────────────────────────────────────────────────────────────────────────

# 폼 바깥에서 초기화 — rental_mode가 바뀌면 이 변수들은 재정의됨
jeonse_str    = ""
monthly_rent_man = 0

with st.form("sim5_form"):
    col_left, col_right = st.columns([1, 1], gap="large")

    # ── 왼쪽: 매수·대출 조건 ─────────────────────────────────────────────────
    with col_left:
        st.markdown('<div class="section-label">🏠 매물 정보</div>', unsafe_allow_html=True)
        purchase_price_str = st.text_input(
            "매수가",
            placeholder="예) 5억, 7억5천, 12억",
            key="sim_pp_str",
        )
        property_type = st.selectbox(
            "매물 유형", PROP_TYPES, key="sim_prop_type"
        )

        st.markdown("")
        st.markdown('<div class="section-label">🏦 대출 조건</div>', unsafe_allow_html=True)
        loan_ratio = st.slider(
            "대출 비율 (%)", min_value=0, max_value=90, step=5,
            key="sim_loan_ratio",
            help="매수가 대비 대출금 비율",
        )
        annual_interest_rate = st.number_input(
            "연이율 (%)", min_value=0.0, max_value=20.0, step=0.1, format="%.1f",
            key="sim_interest_rate",
        )
        loan_years = st.selectbox(
            "대출 기간", [10, 15, 20, 25, 30, 35, 40],
            key="sim_loan_years",
        )
        repayment_type = st.selectbox(
            "상환 방식",
            options=list(REPAY_LABELS.keys()),
            format_func=lambda k: REPAY_LABELS[k],
            key="sim_repay_type",
        )

    # ── 오른쪽: 보유·임대 조건 ───────────────────────────────────────────────
    with col_right:
        st.markdown('<div class="section-label">📅 보유 계획</div>', unsafe_allow_html=True)
        holding_years = st.slider(
            "보유 기간 (년)", min_value=1, max_value=20,
            key="sim_holding_years",
        )
        expected_annual_growth_rate = st.slider(
            "예상 연 시세 상승률 (%)",
            min_value=-10.0, max_value=20.0, step=0.5,
            key="sim_growth_rate",
            help="0%는 시세 변동 없음 (간이 계산)",
        )

        st.markdown("")
        st.markdown(
            f'<div class="section-label">💰 임대 수입 '
            f'<span style="font-weight:400;color:#888">({rental_mode})</span></div>',
            unsafe_allow_html=True,
        )
        if rental_mode == "전세":
            jeonse_str = st.text_input(
                "전세 보증금",
                placeholder="예) 3억, 4억5천",
                key="sim_jeonse_str",
            )
        elif rental_mode == "월세":
            monthly_rent_man = st.number_input(
                "월세 (만원)", min_value=0, max_value=99_999, step=10,
                key="sim_rent_man",
            )

        st.markdown("")
        st.markdown('<div class="section-label">🔧 기타</div>', unsafe_allow_html=True)
        monthly_mgmt_man = st.number_input(
            "월 관리비 (만원)", min_value=0, max_value=9_999, step=1,
            key="sim_mgmt_man",
        )

    submitted = st.form_submit_button(
        "📊  시뮬레이션 계산", type="primary", use_container_width=True
    )


# ─────────────────────────────────────────────────────────────────────────────
#  계산 실행
# ─────────────────────────────────────────────────────────────────────────────

if submitted:
    purchase_price = _parse_price_to_won(purchase_price_str)
    if purchase_price <= 0:
        st.error("매수가를 올바르게 입력해주세요. 예) '5억', '7억5천', '12억3000만'")
        st.stop()

    loan_amount = int(purchase_price * loan_ratio / 100)
    if loan_amount >= purchase_price:
        loan_amount = purchase_price - 1  # 유효성 방어

    jeonse_won = _parse_price_to_won(jeonse_str) if rental_mode == "전세" else None
    rent_won   = int(monthly_rent_man) * 10_000 if rental_mode == "월세" and monthly_rent_man > 0 else None
    mgmt_won   = int(monthly_mgmt_man) * 10_000 if monthly_mgmt_man > 0 else None

    with st.spinner("계산 중..."):
        try:
            from schemas.simulation import SimulationInput
            from router import run_simulation

            inp = SimulationInput(
                purchase_price              = purchase_price,
                loan_amount                 = loan_amount,
                annual_interest_rate        = float(annual_interest_rate),
                loan_years                  = int(loan_years),
                repayment_type              = repayment_type,
                holding_years               = int(holding_years),
                expected_annual_growth_rate = float(expected_annual_growth_rate),
                jeonse_deposit              = jeonse_won,
                monthly_rent                = rent_won,
                monthly_management_fee      = mgmt_won,
                property_type               = property_type,
            )

            state = run_simulation(data=inp)

            if state.get("error"):
                st.error(f"시뮬레이션 오류: {state['error']}")
                st.stop()

            st.session_state["sim5_result"] = state["result"]
            st.session_state["sim5_inp"]    = state["built_input"] or inp

        except Exception as exc:
            st.error(f"계산 중 오류가 발생했습니다: {exc}")
            import traceback
            with st.expander("상세 오류"):
                st.code(traceback.format_exc())
            st.stop()


# ─────────────────────────────────────────────────────────────────────────────
#  결과 표시
# ─────────────────────────────────────────────────────────────────────────────

result = st.session_state.get("sim5_result")
inp    = st.session_state.get("sim5_inp")

if result and inp:
    st.divider()

    tab_dashboard, tab_report = st.tabs(["📊 대시보드", "📄 리포트 (마크다운)"])

    # ── 대시보드 탭 ────────────────────────────────────────────────────────
    with tab_dashboard:

        # 핵심 지표
        st.markdown('<div class="section-label">💎 핵심 지표</div>', unsafe_allow_html=True)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("매수가",   _fmt_won(result.purchase_price))
        m2.metric("대출금",   _fmt_won(result.loan_amount))
        m3.metric("필요 현금", _fmt_won(result.required_cash))
        m4.metric("실투자금", _fmt_won(result.equity),
                  help="필요 현금 − 전세 보증금")

        st.markdown("")

        # 취득 비용
        st.markdown('<div class="section-label">🧾 취득 비용 (간이)</div>',
                    unsafe_allow_html=True)
        acq = result.acquisition_cost
        a1, a2, a3, a4 = st.columns(4)
        a1.metric("취득세",           _fmt_won(acq.acquisition_tax))
        a2.metric("중개보수",          _fmt_won(acq.brokerage_fee))
        a3.metric("기타 (등기·인지세)", _fmt_won(acq.other_cost))
        a4.metric("취득 비용 합계",    _fmt_won(acq.total))

        st.markdown("")

        # 대출 정보
        if result.loan_amount > 0:
            st.markdown('<div class="section-label">🏦 대출 정보</div>',
                        unsafe_allow_html=True)
            l1, l2, l3 = st.columns(3)
            l1.metric("월 상환액", _fmt_won(result.loan.monthly_payment))
            l2.metric("총 상환액", _fmt_won(result.loan.total_repayment))
            l3.metric("총 이자",   _fmt_won(result.loan.total_interest))
            st.markdown("")

        # 월 현금흐름
        st.markdown('<div class="section-label">💵 월 현금흐름</div>',
                    unsafe_allow_html=True)
        cf = result.cash_flow
        cf1, cf2, cf3, cf4 = st.columns(4)
        if cf.monthly_rental_income:
            cf1.metric("월 임대 수입", _fmt_won(cf.monthly_rental_income))
        cf2.metric("월 대출 상환",     _fmt_won(cf.monthly_loan_payment))
        if cf.monthly_management_fee:
            cf3.metric("월 관리비",   _fmt_won(cf.monthly_management_fee))
        net_label = "적자" if cf.monthly_net < 0 else "흑자"
        cf4.metric(
            "순 월 현금흐름",
            _fmt_won(cf.monthly_net),
            delta=net_label,
            delta_color="inverse" if cf.monthly_net < 0 else "normal",
        )

        st.markdown("")

        # 시나리오 비교
        st.markdown('<div class="section-label">📈 시나리오 비교</div>',
                    unsafe_allow_html=True)

        sb, sm, su = result.scenario_bear, result.scenario_base, result.scenario_bull

        import pandas as pd

        rows = [
            ("연 상승률",       f"{sb.annual_growth_rate:.1f}%",
                                f"{sm.annual_growth_rate:.1f}%",
                                f"{su.annual_growth_rate:.1f}%"),
            ("예상 매도가",     _fmt_won(sb.expected_sale_price),
                                _fmt_won(sm.expected_sale_price),
                                _fmt_won(su.expected_sale_price)),
            ("시세 차익",       _fmt_won(sb.capital_gain),
                                _fmt_won(sm.capital_gain),
                                _fmt_won(su.capital_gain)),
            ("총 임대 수입",    _fmt_won(sb.total_rental_income),
                                _fmt_won(sm.total_rental_income),
                                _fmt_won(su.total_rental_income)),
            ("순손익",          _fmt_won(sb.net_profit),
                                _fmt_won(sm.net_profit),
                                _fmt_won(su.net_profit)),
            ("자기자본 수익률", f"{sb.equity_roi:+.2f}%",
                                f"{sm.equity_roi:+.2f}%",
                                f"{su.equity_roi:+.2f}%"),
            ("연환산 수익률",   f"{sb.annual_equity_roi:+.2f}%",
                                f"{sm.annual_equity_roi:+.2f}%",
                                f"{su.annual_equity_roi:+.2f}%"),
        ]
        scenario_df = pd.DataFrame(rows,
            columns=["지표", "비관 시나리오", "기본 시나리오", "낙관 시나리오"])
        st.dataframe(scenario_df, width=820, hide_index=True)

        # 투자 판단
        aroi  = sm.annual_equity_roi
        color = _verdict_color(aroi)
        if aroi >= 10:
            verdict = "✅ 우수한 투자 수익률 (연 10% 이상)"
        elif aroi >= 5:
            verdict = "🟡 양호한 투자 수익률 (연 5~10%)"
        elif aroi >= 0:
            verdict = "🟠 낮은 수익률 (연 0~5%) — 시세 상승 가정에 의존"
        else:
            verdict = "🔴 마이너스 수익률 — 투자 재검토 필요"

        st.markdown("")
        st.markdown(
            f'<div class="verdict-box" style="'
            f'background:{color}22; border-left:4px solid {color};">'
            f"기본 시나리오 연환산 수익률: <b>{aroi:+.2f}%</b>"
            f"&nbsp;|&nbsp; {verdict}"
            f"</div>",
            unsafe_allow_html=True,
        )

        if cf.monthly_net < 0:
            st.warning(
                f"⚠️ 월 현금흐름 적자 {_fmt_won(abs(cf.monthly_net))} "
                "— 보유 기간 동안 추가 현금이 필요합니다."
            )

    # ── 리포트 탭 ──────────────────────────────────────────────────────────
    with tab_report:
        from services.simulation_service import generate_simulation_report
        st.markdown(generate_simulation_report(result, inp))

    st.divider()
    if st.button("🔄 다시 계산", use_container_width=True,
                 help="결과를 지우고 조건을 수정합니다"):
        st.session_state["sim5_result"] = None
        st.session_state["sim5_inp"]    = None
        st.rerun()
