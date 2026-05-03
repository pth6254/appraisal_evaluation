"""
pages/4_매물추천.py — AI 매물 추천 (Phase 3-5)

사용자가 지역·예산·면적·유형·목적을 입력하면
run_recommendation()을 호출해 샘플 데이터 기반 추천 결과를 표시한다.

⚠️  샘플 데이터 고지:
    추천 결과는 data/sample_listings.csv 의 개발·테스트용 가상 데이터에서 산출된다.
    실제 매물 정보와 다르며 투자·거래 판단에 사용하지 마라.
"""

from __future__ import annotations

import sys
import os

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "..", "backend"))

import streamlit as st
from dotenv import load_dotenv, find_dotenv

load_dotenv(find_dotenv())

# ─────────────────────────────────────────────────────────────────────────────
#  페이지 설정
# ─────────────────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="AI 매물 추천 — AppraisalAI",
    page_icon="🏠",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

.rec-header {
    background: linear-gradient(135deg, #0f2544 0%, #185FA5 100%);
    border-radius: 12px;
    padding: 24px 28px;
    color: white;
    margin-bottom: 24px;
}
.rec-header h2 { margin: 0 0 6px; font-size: 1.5rem; font-weight: 700; }
.rec-header p  { margin: 0; opacity: 0.82; font-size: 0.92rem; }

.section-label {
    font-size: 0.75rem;
    font-weight: 600;
    color: #185FA5;
    letter-spacing: 0.08em;
    text-transform: uppercase;
    margin-bottom: 8px;
}

.card-wrap {
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 14px;
    background: var(--secondary-background-color);
}
.card-title {
    font-weight: 700;
    font-size: 1.0rem;
    color: var(--text-color);
}
.card-address {
    font-size: 0.83rem;
    opacity: 0.6;
    margin-top: 2px;
}
.card-price {
    font-size: 1.15rem;
    font-weight: 700;
    color: #185FA5;
}
.card-detail {
    margin-top: 6px;
    font-size: 0.83rem;
    opacity: 0.75;
}
.tag-reason {
    display: inline-block;
    background: #e8f4fd;
    color: #185FA5;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.78rem;
    margin: 2px 2px 0 0;
}
.tag-risk {
    display: inline-block;
    background: #fdf3e8;
    color: #d4720b;
    border-radius: 4px;
    padding: 2px 8px;
    font-size: 0.78rem;
    margin: 2px 2px 0 0;
}
.sample-notice {
    border-left: 4px solid #e5c100;
    background: #fffbe6;
    padding: 10px 14px;
    border-radius: 0 6px 6px 0;
    font-size: 0.83rem;
    color: #555;
    margin-bottom: 16px;
}
</style>
""", unsafe_allow_html=True)


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


def _fmt_won(won: int | None) -> str:
    """원 → '10억 5,000만원' 표기"""
    if not won:
        return "—"
    eok = won // 1_0000_0000
    man = (won % 1_0000_0000) // 10_000
    if eok and man:
        return f"{eok}억 {man:,}만원"
    if eok:
        return f"{eok}억원"
    return f"{man:,}만원"


def _score_color(score: float) -> str:
    if score >= 7.5:
        return "#27AE60"
    if score >= 5.5:
        return "#F39C12"
    return "#E74C3C"


def _label_emoji(label: str) -> str:
    return {"적극 추천": "🟢", "추천": "🟡", "검토 필요": "🟠", "비추천": "🔴"}.get(label, "⚪")


# ─────────────────────────────────────────────────────────────────────────────
#  헤더
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="rec-header">
  <h2>🏠 AI 매물 추천</h2>
  <p>원하는 조건을 입력하면 AI가 가장 적합한 매물을 점수순으로 추천해드립니다.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sample-notice">
  ⚠️ <b>샘플 데이터 안내</b>: 현재 추천 결과는 서울 8개 구 43건의 <b>가상 테스트 매물</b>을 기반으로 합니다.
  실제 매물 정보와 다르며 투자·거래 판단에 사용하지 마세요.
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  세션 초기화
# ─────────────────────────────────────────────────────────────────────────────

if "rec4_result" not in st.session_state:
    st.session_state["rec4_result"] = None
if "rec4_query_snapshot" not in st.session_state:
    st.session_state["rec4_query_snapshot"] = {}


# ─────────────────────────────────────────────────────────────────────────────
#  입력 폼
# ─────────────────────────────────────────────────────────────────────────────

REGIONS = [
    "전체",
    "마포구", "서대문구", "강서구", "성동구",
    "송파구", "강남구", "서초구", "영등포구",
]
PROP_TYPES = ["전체", "주거용", "상업용"]
PURPOSES   = ["전체", "실거주", "투자", "매도", "보유"]

with st.form("rec4_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.markdown('<div class="section-label">📍 지역</div>', unsafe_allow_html=True)
        region = st.selectbox(
            "지역", REGIONS, index=0, label_visibility="collapsed"
        )

        st.markdown('<div class="section-label">🏢 매물 유형</div>', unsafe_allow_html=True)
        prop_type = st.selectbox(
            "유형", PROP_TYPES, index=0, label_visibility="collapsed"
        )

        st.markdown('<div class="section-label">🎯 투자 목적</div>', unsafe_allow_html=True)
        purpose = st.selectbox(
            "목적", PURPOSES, index=0, label_visibility="collapsed"
        )

    with col2:
        st.markdown('<div class="section-label">💰 예산 범위</div>', unsafe_allow_html=True)
        budget_min_str = st.text_input(
            "최소 예산", placeholder="예) 3억, 5억5천", label_visibility="collapsed"
        )
        budget_max_str = st.text_input(
            "최대 예산", placeholder="예) 10억, 15억", label_visibility="collapsed"
        )

        st.markdown('<div class="section-label">📐 면적 (㎡)</div>', unsafe_allow_html=True)
        area_col1, area_col2 = st.columns(2)
        with area_col1:
            area_m2 = st.number_input(
                "면적", min_value=0.0, max_value=999.0, value=0.0, step=10.0,
                label_visibility="collapsed", placeholder="면적 (㎡)"
            )

    with col3:
        st.markdown('<div class="section-label">🔢 추천 개수</div>', unsafe_allow_html=True)
        limit = st.slider("추천 개수", min_value=1, max_value=10, value=5,
                          label_visibility="collapsed")

        st.markdown('<div class="section-label">⚙️ 감정평가 연동</div>', unsafe_allow_html=True)
        run_appraisal = st.toggle(
            "실거래가 감정평가 포함",
            value=False,
            help="활성화하면 매물별 실거래가 API를 호출합니다. API 키가 설정된 경우에만 작동합니다.",
        )
        if run_appraisal:
            st.caption("⚠️ API 키가 없으면 자동으로 비활성화됩니다.")

    submitted = st.form_submit_button(
        "🔍  매물 추천받기", type="primary", use_container_width=True
    )


# ─────────────────────────────────────────────────────────────────────────────
#  검색 실행
# ─────────────────────────────────────────────────────────────────────────────

if submitted:
    budget_min = _parse_price_to_won(budget_min_str)
    budget_max = _parse_price_to_won(budget_max_str)

    # 예산 입력 피드백
    if budget_min_str.strip() and budget_min == 0:
        st.warning(f"최소 예산 '{budget_min_str}' 을 인식하지 못했습니다. '5억', '5억5천' 형태로 입력해주세요.")
    if budget_max_str.strip() and budget_max == 0:
        st.warning(f"최대 예산 '{budget_max_str}' 을 인식하지 못했습니다. '10억', '15억' 형태로 입력해주세요.")
    if budget_min > 0 and budget_max > 0 and budget_min > budget_max:
        st.error("최소 예산이 최대 예산보다 큽니다.")
        st.stop()

    with st.spinner("🔍 조건에 맞는 매물을 분석하고 있습니다..."):
        try:
            from schemas.property_query import PropertyQuery
            from router import run_recommendation

            _PURPOSE_MAP = {
                "실거주": "live", "투자": "investment",
                "매도": "sell", "보유": "hold",
            }

            query_kwargs: dict = {"intent": "recommendation"}
            if region and region != "전체":
                query_kwargs["region"] = region
            if prop_type and prop_type != "전체":
                query_kwargs["property_type"] = prop_type
            if purpose and purpose != "전체":
                query_kwargs["purpose"] = _PURPOSE_MAP.get(purpose)
            if budget_min > 0:
                query_kwargs["budget_min"] = budget_min
            if budget_max > 0:
                query_kwargs["budget_max"] = budget_max
            if area_m2 > 0:
                query_kwargs["area_m2"] = float(area_m2)

            pquery = PropertyQuery(**query_kwargs)
            state  = run_recommendation(pquery, limit=limit, run_appraisal=run_appraisal)

            st.session_state["rec4_result"] = state
            st.session_state["rec4_query_snapshot"] = {
                "region":    region   if region    != "전체" else None,
                "prop_type": prop_type if prop_type != "전체" else None,
                "purpose":   purpose  if purpose   != "전체" else None,
                "budget_min": budget_min or None,
                "budget_max": budget_max or None,
                "area_m2":   float(area_m2) if area_m2 > 0 else None,
                "limit":     limit,
            }

        except Exception as exc:
            st.error(f"추천 실행 중 오류가 발생했습니다: {exc}")
            import traceback
            with st.expander("상세 오류"):
                st.code(traceback.format_exc())
            st.stop()


# ─────────────────────────────────────────────────────────────────────────────
#  결과 표시
# ─────────────────────────────────────────────────────────────────────────────

state = st.session_state.get("rec4_result")

if state:
    results = state.get("results", [])
    report  = state.get("report", "")
    error   = state.get("error", "")
    snap    = st.session_state.get("rec4_query_snapshot", {})

    if error:
        st.error(f"오류: {error}")

    st.divider()

    # 검색 조건 요약
    with st.expander("📋 검색 조건", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("지역",   snap.get("region")    or "전체")
        c2.metric("유형",   snap.get("prop_type") or "전체")
        c3.metric("최대 예산", _fmt_won(snap.get("budget_max")) if snap.get("budget_max") else "제한 없음")
        c4.metric("면적",   f"{snap['area_m2']:.0f}㎡" if snap.get("area_m2") else "제한 없음")

    st.markdown("")

    if not results:
        st.warning("검색 조건에 맞는 매물이 없습니다. 조건을 넓혀서 다시 검색해보세요.")
    else:
        st.markdown(f"### 추천 매물 ({len(results)}건)")
        st.markdown("")

        tab_cards, tab_report = st.tabs(["🏠 추천 카드", "📄 상세 리포트"])

        with tab_cards:
            for rank, r in enumerate(results, 1):
                l = r.listing
                color  = _score_color(r.total_score)
                emoji  = _label_emoji(r.recommendation_label)

                # 카드 헤더
                name_str = l.complex_name or l.address[:20]
                detail_parts = []
                if l.area_m2:
                    detail_parts.append(f"{l.area_m2:.0f}㎡")
                if l.floor:
                    detail_parts.append(f"{l.floor}층")
                if l.built_year:
                    detail_parts.append(f"{l.built_year}년")
                if l.station_distance_m:
                    detail_parts.append(f"역 {l.station_distance_m}m")
                detail_str = "  ·  ".join(detail_parts)

                # reason / risk 태그 HTML
                reason_html = "".join(
                    f'<span class="tag-reason">✅ {r_}</span>'
                    for r_ in r.reasons[:4]
                )
                risk_html = "".join(
                    f'<span class="tag-risk">⚠️ {r_}</span>'
                    for r_ in r.risks[:3]
                )

                st.markdown(f"""
<div class="card-wrap" style="border-left: 5px solid {color};">
  <div style="display:flex; justify-content:space-between; align-items:flex-start; flex-wrap:wrap; gap:8px;">
    <div>
      <span class="card-title">{emoji} {rank}위 — {name_str}</span>
      <div class="card-address">{l.address}</div>
      <div class="card-detail">{detail_str}</div>
    </div>
    <div style="text-align:right;">
      <div class="card-price">{_fmt_won(l.asking_price)}</div>
      <div style="font-size:0.82rem; color:{color}; font-weight:600; margin-top:2px;">
        {r.recommendation_label} ({r.total_score:.1f}점)
      </div>
    </div>
  </div>
  <div style="margin-top:10px;">{reason_html}{risk_html}</div>
</div>
""", unsafe_allow_html=True)

                # 4축 점수 시각화
                with st.expander(f"점수 상세 — {name_str}", expanded=False):
                    sc1, sc2, sc3, sc4 = st.columns(4)
                    sc1.metric("가격 적정성", f"{r.price_score:.1f} / 10")
                    sc2.metric("입지",        f"{r.location_score:.1f} / 10")
                    sc3.metric("투자 가치",   f"{r.investment_score:.1f} / 10")
                    sc4.metric("위험도",      f"{r.risk_score:.1f} / 10",
                               help="낮을수록 안전합니다.")
                    st.progress(r.total_score / 10,
                                text=f"종합 {r.total_score:.1f} / 10 ({r.recommendation_label})")

                    if l.jeonse_price:
                        ratio = l.jeonse_price / l.asking_price * 100
                        st.caption(
                            f"전세가 {_fmt_won(l.jeonse_price)} · "
                            f"전세가율 {ratio:.0f}%"
                        )
                    if r.appraisal and r.appraisal.estimated_price:
                        a = r.appraisal
                        st.caption(
                            f"감정평가 추정가 {_fmt_won(a.estimated_price)} · "
                            f"판정 {a.judgement} · 신뢰도 {a.confidence:.0%}"
                        )

                    st.markdown("")
                    if st.button(
                        "📈 이 매물로 시뮬레이션",
                        key=f"sim_btn_{rank}",
                        use_container_width=True,
                    ):
                        st.session_state["sim_from_listing"] = {
                            "asking_price":    l.asking_price,
                            "property_type":   l.property_type,
                            "jeonse_price":    l.jeonse_price,
                            "maintenance_fee": l.maintenance_fee,
                            "complex_name":    l.complex_name or "",
                            "address":         l.address,
                            "region":          l.region or "",
                        }
                        st.session_state["sim_listing_applied"] = False
                        st.switch_page("pages/5_투자시뮬레이션.py")

        with tab_report:
            if report:
                st.markdown(report)
            else:
                st.info("리포트가 생성되지 않았습니다.")

    st.divider()
    if st.button("🔄 새로 검색", use_container_width=True):
        st.session_state["rec4_result"] = None
        st.session_state["rec4_query_snapshot"] = {}
        st.rerun()
