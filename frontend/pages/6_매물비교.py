"""
pages/6_매물비교.py — 매물 비교 · 최종 판단 (Phase 5)

사용자가 4_매물추천.py의 비교 바구니에 담은 매물들을 나란히 비교하고
AI가 최종 추천 매물을 판단해준다.

⚠️ 샘플 데이터 고지:
    비교 결과는 추천 페이지의 가상 테스트 데이터를 기반으로 한다.
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
    page_title="매물 비교 — AppraisalAI",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

.cmp-header {
    background: linear-gradient(135deg, #1a3a5c 0%, #2d6a9f 100%);
    border-radius: 12px;
    padding: 24px 28px;
    color: white;
    margin-bottom: 24px;
}
.cmp-header h2 { margin: 0 0 6px; font-size: 1.5rem; font-weight: 700; }
.cmp-header p  { margin: 0; opacity: 0.82; font-size: 0.92rem; }

.winner-card {
    border: 2px solid #27AE60;
    border-radius: 12px;
    padding: 20px 24px;
    background: #f0faf4;
    margin-bottom: 20px;
}
.winner-card h3 { color: #1a8c3c; margin: 0 0 8px; }

.listing-card {
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
    background: var(--secondary-background-color);
    border-left: 4px solid #185FA5;
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

def _fmt_won(won: int | None) -> str:
    if not won:
        return "—"
    eok = won // 1_0000_0000
    man = (won % 1_0000_0000) // 10_000
    if eok and man:
        return f"{eok}억 {man:,}만원"
    if eok:
        return f"{eok}억원"
    return f"{man:,}만원"


def _fmt_pct(pct: float | None) -> str:
    if pct is None:
        return "—"
    sign = "+" if pct > 0 else ""
    return f"{sign}{pct:.2f}%"


def _score_color(score: float) -> str:
    if score >= 7.5:
        return "#27AE60"
    if score >= 5.5:
        return "#F39C12"
    return "#E74C3C"


# ─────────────────────────────────────────────────────────────────────────────
#  헤더
# ─────────────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="cmp-header">
  <h2>📊 매물 비교 · 최종 판단</h2>
  <p>추천 페이지에서 선택한 매물들을 나란히 비교하고 AI가 최적 매물을 판단합니다.</p>
</div>
""", unsafe_allow_html=True)

st.markdown("""
<div class="sample-notice">
  ⚠️ <b>샘플 데이터 안내</b>: 비교 결과는 <b>가상 테스트 매물</b>을 기반으로 합니다.
  실제 투자·거래 판단에 사용하지 마세요.
</div>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
#  세션 초기화
# ─────────────────────────────────────────────────────────────────────────────

if "compare_basket" not in st.session_state:
    st.session_state["compare_basket"] = []
if "cmp6_result" not in st.session_state:
    st.session_state["cmp6_result"] = None


# ─────────────────────────────────────────────────────────────────────────────
#  바구니 없음 처리
# ─────────────────────────────────────────────────────────────────────────────

basket = st.session_state.get("compare_basket", [])

if len(basket) < 2:
    st.warning("비교할 매물이 2개 이상 필요합니다. 추천 페이지에서 매물을 비교 바구니에 담아주세요.")
    if st.button("🏠 매물 추천 페이지로 이동", use_container_width=True):
        st.switch_page("pages/4_매물추천.py")
    st.stop()


# ─────────────────────────────────────────────────────────────────────────────
#  바구니 요약
# ─────────────────────────────────────────────────────────────────────────────

n_basket = len(basket)
names    = [item.get("complex_name") or item.get("address", "")[:12] for item in basket]

st.markdown(f"### 비교 대상 {n_basket}건")
cols = st.columns(n_basket)
for i, (col, item) in enumerate(zip(cols, basket)):
    name  = item.get("complex_name") or item.get("address", "")[:15]
    price = _fmt_won(item.get("asking_price"))
    score = item.get("score")
    with col:
        st.markdown(f"**{i+1}. {name}**")
        st.caption(f"호가: {price}")
        if score is not None:
            st.caption(f"추천 점수: {score:.1f} / 10")

st.markdown("")

col_run, col_clear = st.columns([3, 1])
with col_run:
    run_btn = st.button("📊 비교 분석 실행", type="primary", use_container_width=True)
with col_clear:
    if st.button("🗑️ 바구니 초기화", use_container_width=True):
        st.session_state["compare_basket"] = []
        st.session_state["cmp6_result"]    = None
        st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
#  비교 분석 실행
# ─────────────────────────────────────────────────────────────────────────────

if run_btn:
    with st.spinner("📊 매물 비교 분석 중..."):
        try:
            from schemas.property_listing import PropertyListing
            from schemas.recommendation_result import RecommendationResult
            from router import run_comparison

            listings: list[PropertyListing] = []
            recs: list[RecommendationResult] = []

            for item in basket:
                listing = PropertyListing(
                    listing_id         = item.get("listing_id", f"cmp_{len(listings)}"),
                    address            = item.get("address", "주소 미입력"),
                    property_type      = item.get("property_type", "주거용"),
                    asking_price       = item.get("asking_price", 0),
                    complex_name       = item.get("complex_name"),
                    region             = item.get("region"),
                    area_m2            = item.get("area_m2"),
                    floor              = item.get("floor"),
                    built_year         = item.get("built_year"),
                    jeonse_price       = item.get("jeonse_price"),
                    maintenance_fee    = item.get("maintenance_fee"),
                    station_distance_m = item.get("station_distance_m"),
                )
                listings.append(listing)

                rec = RecommendationResult(
                    listing              = listing,
                    total_score          = item.get("score", 0.0),
                    price_score          = item.get("price_score", 0.0),
                    location_score       = item.get("location_score", 0.0),
                    investment_score     = item.get("investment_score", 0.0),
                    risk_score           = item.get("risk_score", 0.0),
                    recommendation_label = item.get("label", ""),
                    reasons              = item.get("reasons", []),
                    risks                = item.get("risks", []),
                )
                recs.append(rec)

            state = run_comparison(
                listings               = listings,
                recommendation_results = recs,
            )
            st.session_state["cmp6_result"] = state

        except Exception as exc:
            st.error(f"비교 분석 중 오류가 발생했습니다: {exc}")
            import traceback
            with st.expander("상세 오류"):
                st.code(traceback.format_exc())
            st.stop()


# ─────────────────────────────────────────────────────────────────────────────
#  결과 표시
# ─────────────────────────────────────────────────────────────────────────────

cmp_state = st.session_state.get("cmp6_result")

if cmp_state:
    result = cmp_state.get("result")
    report = cmp_state.get("report", "")
    error  = cmp_state.get("error", "")

    if error:
        st.error(f"오류: {error}")

    st.divider()

    if result:
        rows = result.rows

        # ── 최종 추천 우승자 카드 ──────────────────────────────────────────────
        if rows:
            winner = rows[0]
            w      = winner.listing
            wname  = w.complex_name or w.address

            st.markdown(f"""
<div class="winner-card">
  <h3>🏆 최종 추천 매물: {wname}</h3>
  <p><strong>주소</strong>: {w.address} &nbsp;·&nbsp;
     <strong>호가</strong>: {_fmt_won(w.asking_price)} &nbsp;·&nbsp;
     <strong>종합 점수</strong>: {winner.total_score:.1f} / 10</p>
</div>
""", unsafe_allow_html=True)

        # ── 탭 ──────────────────────────────────────────────────────────────
        tab_table, tab_detail, tab_report = st.tabs([
            "📋 비교 표", "🏠 매물 상세", "📄 결정 리포트",
        ])

        with tab_table:
            st.markdown("#### 핵심 지표 비교")
            st.markdown("")

            # 비교 표 (컬럼 기반)
            header_cols = st.columns([2] + [2] * len(rows))
            header_cols[0].markdown("**항목**")
            for i, row in enumerate(rows):
                name = row.listing.complex_name or row.listing.address[:10]
                mark = " 🏆" if row.is_winner else ""
                header_cols[i + 1].markdown(f"**{row.rank}위{mark}**  \n{name}")

            st.divider()

            metrics = [
                ("호가",         lambda r: _fmt_won(r.listing.asking_price)),
                ("종합 점수",    lambda r: f"{r.total_score:.1f} / 10"),
                ("㎡당 가격",    lambda r: _fmt_won(r.price_per_m2) if r.price_per_m2 else "—"),
                ("전세가율",     lambda r: f"{r.jeonse_ratio:.0f}%" if r.jeonse_ratio else "—"),
                ("월 순현금흐름", lambda r: _fmt_won(r.monthly_net) if r.monthly_net is not None else "—"),
                ("연 수익률",    lambda r: _fmt_pct(r.annual_equity_roi) if r.annual_equity_roi is not None else "—"),
                ("면적",         lambda r: f"{r.listing.area_m2:.0f}㎡" if r.listing.area_m2 else "—"),
                ("준공연도",     lambda r: f"{r.listing.built_year}년" if r.listing.built_year else "—"),
                ("역까지 거리",  lambda r: f"{r.listing.station_distance_m:,}m" if r.listing.station_distance_m else "—"),
            ]

            for label, getter in metrics:
                row_cols = st.columns([2] + [2] * len(rows))
                row_cols[0].markdown(f"**{label}**")
                for i, row in enumerate(rows):
                    row_cols[i + 1].markdown(getter(row))

        with tab_detail:
            for row in rows:
                l     = row.listing
                name  = l.complex_name or l.address
                color = _score_color(row.total_score)
                mark  = " 🏆" if row.is_winner else ""

                st.markdown(f"""
<div class="listing-card" style="border-left-color:{color};">
  <strong>{row.rank}위{mark} — {name}</strong>
  <span style="float:right; color:{color}; font-weight:600;">{row.total_score:.1f}점</span>
  <div style="font-size:0.83rem; opacity:0.65; margin-top:2px;">{l.address}</div>
</div>
""", unsafe_allow_html=True)

                with st.expander(f"상세 정보 — {name}", expanded=row.is_winner):
                    d1, d2, d3, d4 = st.columns(4)
                    d1.metric("종합 점수",   f"{row.total_score:.1f} / 10")
                    d2.metric("호가",        _fmt_won(l.asking_price))
                    d3.metric("전세가율",    f"{row.jeonse_ratio:.0f}%" if row.jeonse_ratio else "—")
                    d4.metric("연 수익률",   _fmt_pct(row.annual_equity_roi) if row.annual_equity_roi is not None else "—")

                    if row.recommendation:
                        st.markdown("")
                        r4c1, r4c2, r4c3, r4c4 = st.columns(4)
                        r4c1.metric("가격 적정성", f"{row.recommendation.price_score:.1f}")
                        r4c2.metric("입지",        f"{row.recommendation.location_score:.1f}")
                        r4c3.metric("투자 가치",   f"{row.recommendation.investment_score:.1f}")
                        r4c4.metric("위험도",      f"{row.recommendation.risk_score:.1f}")

                    if row.highlights:
                        st.markdown("")
                        st.markdown("**강점**:")
                        for h in row.highlights:
                            st.markdown(f"- ✅ {h}")
                    if row.warnings:
                        st.markdown("**주의사항**:")
                        for w in row.warnings:
                            st.markdown(f"- ⚠️ {w}")

                    st.markdown("")
                    if st.button(
                        "📈 이 매물로 시뮬레이션",
                        key=f"cmp_sim_btn_{row.rank}",
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
    col_back, col_reset = st.columns(2)
    with col_back:
        if st.button("🏠 추천 페이지로 돌아가기", use_container_width=True):
            st.switch_page("pages/4_매물추천.py")
    with col_reset:
        if st.button("🔄 비교 초기화", use_container_width=True):
            st.session_state["compare_basket"] = []
            st.session_state["cmp6_result"]    = None
            st.rerun()
