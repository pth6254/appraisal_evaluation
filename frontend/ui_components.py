"""
ui_components.py — 재사용 Streamlit UI 컴포넌트
개선:
  - 실거래가 데이터 없을 때(count=0, avg=0) "데이터 없음" 표시
  - price_error 필드 있으면 원인 표시
  - _get() 헬퍼로 중첩 구조 안전 접근
"""

import streamlit as st

CARD_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

.prop-card {
    background: #F7F9FC; border: 1px solid #D3D9E8;
    border-radius: 12px; padding: 20px 24px; margin-bottom: 8px;
}
.prop-card-title {
    font-size: 0.72rem; font-weight: 600; color: #185FA5;
    letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 12px;
}
.prop-row { display: flex; flex-wrap: wrap; gap: 24px; }
.prop-item { display: flex; flex-direction: column; }
.prop-item-label { font-size: 0.75rem; color: #888; margin-bottom: 2px; }
.prop-item-value { font-size: 0.97rem; font-weight: 600; color: #0A2540; }

.section-label {
    font-size: 0.75rem; font-weight: 600; color: #185FA5;
    letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px;
}
.no-data-box {
    background: #FFF8F0; border: 1px solid #F5C97A;
    border-radius: 10px; padding: 16px 20px;
    font-size: 0.88rem; color: #7A5C00;
}
.nearby-chip {
    display: inline-flex; align-items: center; gap: 6px;
    background: #F0F4FA; border-radius: 8px;
    padding: 6px 12px; font-size: 0.83rem; color: #333;
}
</style>
"""

VERDICT_STYLE = {
    "저평가":     {"icon": "🟢", "delta_color": "normal"},
    "적정":       {"icon": "🔵", "delta_color": "off"},
    "소폭 고평가": {"icon": "🟡", "delta_color": "inverse"},
    "고평가":     {"icon": "🔴", "delta_color": "inverse"},
}

REC_FN = {
    "매수 적극 고려": st.success,
    "매수 고려":     st.success,
    "관망":          st.warning,
    "매수 비추천":   st.error,
}


def _get(r: dict, key: str, default=0):
    """최상위 → analysis_result 중첩 순으로 안전 접근"""
    if key in r and r[key] not in (None, ""):
        return r[key]
    ar = r.get("analysis_result") or {}
    return ar.get(key, default)


def _fmt_price(val: int) -> str:
    """0이면 '데이터 없음', 아니면 포맷"""
    return f"{val:,} 만원" if val else "데이터 없음"


# ─────────────────────────────────────────
#  매물 정보 카드
# ─────────────────────────────────────────

def render_property_card(r: dict, raw_inputs: dict = None):
    st.markdown(CARD_CSS, unsafe_allow_html=True)
    ri = raw_inputs or {}

    address   = ri.get("address")   or _get(r, "address_name", "") or _get(r, "query", "")
    building  = ri.get("building")  or _get(r, "building_name", "")
    prop_type = ri.get("prop_type") or _get(r, "category", "") or _get(r, "agent_name", "")
    area_raw  = ri.get("area")      or _get(r, "area_raw", "")
    area_m2   = _get(r, "area_pyeong", 0)
    method    = _get(r, "valuation_method", "")
    comp_count = _get(r, "comparable_count", 0)

    items = []
    if address:    items.append(("소재지",     address))
    if building:   items.append(("건물·단지명", building))
    if prop_type and prop_type != "자동 감지":
                   items.append(("유형",        prop_type))
    if area_raw:   items.append(("면적 (입력)", area_raw))
    if area_m2:    items.append(("면적 (환산)", f"{area_m2:.1f}평"))
    if method:     items.append(("평가 방식",   method))
    if comp_count: items.append(("비교사례",    f"{comp_count}건"))

    rows_html = "".join(
        f'<div class="prop-item">'
        f'<span class="prop-item-label">{label}</span>'
        f'<span class="prop-item-value">{value}</span>'
        f'</div>'
        for label, value in items
    )
    st.markdown(f"""
    <div class="prop-card">
      <div class="prop-card-title">📋 매물 정보</div>
      <div class="prop-row">{rows_html}</div>
    </div>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────
#  핵심 4대 지표
# ─────────────────────────────────────────

def render_area_band_ranges(r: dict):
    """면적 미입력 시 면적대별 가격 범위 테이블 표시"""
    band_ranges = _get(r, "area_band_ranges", [])
    if not band_ranges:
        return

    st.markdown('<div class="section-label">📐 면적대별 추정 가격 범위</div>',
                unsafe_allow_html=True)
    st.caption("전용면적을 입력하지 않아 면적대별 범위로 제시합니다.")

    import pandas as pd
    rows = []
    for b in band_ranges:
        rows.append({
            "면적대":        b["label"],
            "추정가 (만원)": f"{b['estimated']:,}",
            "최저 (만원)":   f"{b['price_min']:,}" if b["price_min"] else "—",
            "최고 (만원)":   f"{b['price_max']:,}" if b["price_max"] else "—",
            "실거래 건수":   f"{b['count']}건" if b["count"] else "추정",
        })
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def render_metric_row(r: dict):
    has_area = _get(r, "has_area_input", True)
    col1, col2, col3, col4 = st.columns(4)

    estimated = _get(r, "estimated_value")
    v_min     = _get(r, "value_min")
    v_max     = _get(r, "value_max")
    ppyeong   = _get(r, "price_per_pyeong")
    reg_avg   = _get(r, "regional_avg_per_pyeong")
    verdict   = _get(r, "valuation_verdict", "")
    dev_pct   = _get(r, "deviation_pct", 0.0)
    grade     = _get(r, "investment_grade", "")
    cap_rate  = _get(r, "cap_rate", 0.0)

    # 면적 미입력 시 추정가 표시 방식 변경
    if has_area:
        col1.metric(
            "추정 시장가치",
            _fmt_price(estimated),
            f"범위 {v_min:,} ~ {v_max:,}" if v_min else None,
        )
    else:
        col1.metric(
            "실거래 평균가",
            _fmt_price(estimated),
            "면적 미입력 — 아래 범위 참조",
        )

    delta_pyeong = ppyeong - reg_avg
    col2.metric(
        "㎡당 평균가",
        f"{_get(r, 'price_per_sqm'):,} 만원/㎡" if _get(r, "price_per_sqm") else "데이터 없음",
        f"평당 {ppyeong:,}만원" if ppyeong else None,
    )
    vs = VERDICT_STYLE.get(verdict, {})
    col3.metric(
        "고 / 저평가",
        f"{vs.get('icon','')} {verdict}" if verdict else "—",
        f"괴리율 {dev_pct:+.1f}%" if verdict else None,
        delta_color=vs.get("delta_color", "off"),
    )
    col4.metric(
        "투자등급",
        grade or "—",
        f"Cap Rate {cap_rate:.1f}%" if cap_rate else None,
    )


# ─────────────────────────────────────────
#  실거래가 분석
# ─────────────────────────────────────────

def render_price_analysis(r: dict):
    price_avg    = _get(r, "price_avg")
    price_min    = _get(r, "price_min")
    price_max    = _get(r, "price_max")
    price_count  = _get(r, "price_sample_count") or _get(r, "comparable_count")
    comparables  = _get(r, "comparables", [])
    per_sqm      = _get(r, "price_per_sqm")
    price_error  = _get(r, "price_error", "")

    st.markdown('<div class="section-label">📊 인근 실거래가 분석</div>', unsafe_allow_html=True)

    # 데이터 없음 처리
    if not price_avg and not price_count:
        msg = f"실거래 데이터를 불러오지 못했습니다."
        if price_error:
            msg += f"<br><small style='color:#999'>{price_error}</small>"
        st.markdown(f'<div class="no-data-box">⚠️ {msg}</div>', unsafe_allow_html=True)
        return

    # 조회 기간 확장 안내
    used_months = _get(r, "used_months", 1)
    if used_months and used_months > 1:
        st.caption(f"⚠️ 최근 1개월 데이터 부족 → {used_months}개월로 확장 조회한 결과입니다.")

    c1, c2, c3, c4 = st.columns(4)
    used_months = _get(r, "used_months", 0)
    month_label = f" ({used_months}개월 기준)" if used_months and used_months > 3 else ""

    c1.metric("실거래 평균가" + month_label, _fmt_price(price_avg))
    c2.metric("최저 거래가",   _fmt_price(price_min))
    c3.metric("최고 거래가",   _fmt_price(price_max))
    c4.metric("㎡당 평균가",   f"{per_sqm:,} 만원/㎡" if per_sqm else "—")

    if used_months and used_months > 3:
        st.caption(f"ℹ️ 최근 3개월 데이터 부족 → {used_months}개월 기준으로 산출")

    if comparables:
        st.markdown('<div class="section-label" style="margin-top:16px">비교 사례 목록</div>',
                    unsafe_allow_html=True)
        import pandas as pd
        rows = []
        for c in comparables[:8]:
            rows.append({
                "단지명":       c.get("apt_name", "—"),
                "거래가(만원)": f"{c.get('price', 0):,}",
                "면적(㎡)":     c.get("area_sqm", "—"),
                "층":           c.get("floor", "—"),
                "건축연도":     c.get("year_built", "—"),
                "거래년월":     f"{c.get('deal_year','')}년 {c.get('deal_month','')}월".strip(),
            })
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ─────────────────────────────────────────
#  주변 시설
# ─────────────────────────────────────────

def render_nearby(r: dict):
    nearby = _get(r, "nearby_facilities", {})
    if not nearby:
        return

    st.markdown('<div class="section-label">📍 주변 시설 현황</div>', unsafe_allow_html=True)
    ICONS = {
        "지하철역": "🚇", "학교": "🏫", "편의점": "🏪",
        "마트": "🛒", "병원": "🏥", "음식점": "🍽️",
        "카페": "☕", "주차장": "🅿️", "은행": "🏦",
    }
    chips = ""
    for name, info in nearby.items():
        if not isinstance(info, dict):
            continue
        count   = info.get("count", 0)
        nearest = info.get("nearest_m", 9999)
        icon    = ICONS.get(name, "📌")
        dist    = f"{nearest}m" if nearest < 9999 else "—"
        chips  += f'<div class="nearby-chip">{icon} {name} {count}개 · 최근접 {dist}</div>'

    st.markdown(f'<div style="display:flex;flex-wrap:wrap;gap:8px;">{chips}</div>',
                unsafe_allow_html=True)


# ─────────────────────────────────────────
#  의견서 / 요인 / 추천
# ─────────────────────────────────────────

def render_opinion(r: dict):
    st.markdown('<div class="section-label">📋 감정평가 의견</div>', unsafe_allow_html=True)
    opinion = _get(r, "appraisal_opinion", "")
    st.info(opinion or "의견서를 생성하지 못했습니다.")


def render_factors(r: dict):
    col_l, col_r = st.columns(2)
    with col_l:
        st.markdown('<div class="section-label">✅ 가치 상승 요인</div>', unsafe_allow_html=True)
        strengths = _get(r, "strengths", [])
        for s in (strengths or []):
            st.success(s)
        if not strengths:
            st.caption("—")
    with col_r:
        st.markdown('<div class="section-label">⚠️ 리스크 요인</div>', unsafe_allow_html=True)
        risks = _get(r, "risk_factors", [])
        for s in (risks or []):
            st.warning(s)
        if not risks:
            st.caption("—")


def render_recommendation(r: dict):
    rec = _get(r, "recommendation", "")
    fn  = REC_FN.get(rec, st.info)
    fn(f"**🎯 종합 추천: {rec}**" if rec else "추천 정보 없음")


def render_investment_detail(r: dict):
    with st.expander("📈 투자 수익성 상세"):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("연 임대수입 추정", _fmt_price(_get(r, "annual_income")))
        c2.metric("5년 수익률 추정", f"{_get(r, 'roi_5yr', 0.0):.1f}%")
        c3.metric("비교사례 평균가", _fmt_price(_get(r, "comparable_avg")))
        c4.metric("비교사례 건수",   f"{_get(r, 'comparable_count')} 건")


# ─────────────────────────────────────────
#  전체 리포트
# ─────────────────────────────────────────

def render_full_report(r: dict, query: str, raw_inputs: dict = None):
    ar     = r.get("analysis_result") or {}
    merged = {**ar, **r}

    st.markdown(CARD_CSS, unsafe_allow_html=True)

    render_property_card(merged, raw_inputs)
    st.divider()

    st.markdown('<div class="section-label">💎 감정평가 핵심 지표</div>', unsafe_allow_html=True)
    render_metric_row(merged)

    # 면적 미입력 시 면적대별 범위 표시
    render_area_band_ranges(merged)

    st.divider()
    render_price_analysis(merged)
    st.divider()

    render_nearby(merged)
    if merged.get("nearby_facilities"):
        st.divider()

    render_opinion(merged)
    st.markdown("")
    render_factors(merged)
    st.divider()

    render_recommendation(merged)
    render_investment_detail(merged)