"""
pages/3_대시보드.py — 평가 이력 조회 대시보드
"""

import sys
import os

from dotenv import load_dotenv, find_dotenv
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import streamlit as st
import pandas as pd
from history_db import load_all, load_one, delete_one, count_all, search_by_query
from ui_components import render_full_report

load_dotenv(find_dotenv())

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }
</style>
""", unsafe_allow_html=True)

st.title("📋 평가 이력 대시보드")

# ── 검색 + 페이지네이션 ───────────────────────────────────────────────────────
search_col, _ = st.columns([2, 3])
keyword = search_col.text_input("🔍 키워드 검색", placeholder="예) 강남구 아파트")

PAGE_SIZE   = 20
total_count = count_all()

if keyword:
    rows = search_by_query(keyword, limit=PAGE_SIZE * 5)
else:
    max_page = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
    page = st.number_input("페이지", min_value=1, max_value=max_page, value=1, step=1,
                           label_visibility="collapsed") if max_page > 1 else 1
    rows = load_all(limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE)

if not rows:
    st.info("아직 저장된 평가 이력이 없습니다.")
    if st.button("첫 감정평가 시작하기 →", type="primary"):
        st.switch_page("pages/1_평가하기.py")
    st.stop()

# ── KPI ───────────────────────────────────────────────────────────────────────
all_rows    = load_all(limit=1000, offset=0)
avg_val     = sum(r.get("estimated_value", 0) for r in all_rows) // len(all_rows) if all_rows else 0
grades      = [r.get("investment_grade", "") for r in all_rows]
top_grade   = max(set(grades), key=grades.count) if any(grades) else "—"
verdicts    = [r.get("valuation_verdict", "") for r in all_rows]
undervalued = sum(1 for v in verdicts if v == "저평가")

k1, k2, k3, k4 = st.columns(4)
k1.metric("총 평가 건수",   f"{total_count} 건")
k2.metric("평균 추정가",    f"{avg_val:,} 만원")
k3.metric("최다 투자등급",  top_grade)
k4.metric("저평가 물건 수", f"{undervalued} 건")

st.divider()

# ── 차트 ─────────────────────────────────────────────────────────────────────
col_chart1, col_chart2 = st.columns(2)
with col_chart1:
    st.markdown("##### 고/저평가 분포")
    verdict_counts = {}
    for v in verdicts:
        if v: verdict_counts[v] = verdict_counts.get(v, 0) + 1
    if verdict_counts:
        st.bar_chart(pd.DataFrame(list(verdict_counts.items()), columns=["판정","건수"]).set_index("판정"), height=200)

with col_chart2:
    st.markdown("##### 투자등급 분포")
    grade_counts = {}
    for g in grades:
        if g: grade_counts[g] = grade_counts.get(g, 0) + 1
    if grade_counts:
        st.bar_chart(pd.DataFrame(sorted(grade_counts.items()), columns=["등급","건수"]).set_index("등급"), height=200)

st.divider()

# ── 필터 + 테이블 ─────────────────────────────────────────────────────────────
st.markdown("##### 이력 목록")
f1, f2, f3 = st.columns(3)
sel_verdict = f1.selectbox("고/저평가 필터", ["전체"] + sorted(set(v for v in verdicts if v)))
sel_grade   = f2.selectbox("투자등급 필터",  ["전체"] + sorted(set(g for g in grades if g)))
all_cats    = sorted(set((r.get("category") or r.get("agent_name","")) for r in all_rows if r.get("category") or r.get("agent_name")))
sel_cat     = f3.selectbox("유형 필터",      ["전체"] + all_cats)

filtered = rows
if sel_verdict != "전체":
    filtered = [r for r in filtered if r.get("valuation_verdict") == sel_verdict]
if sel_grade != "전체":
    filtered = [r for r in filtered if r.get("investment_grade") == sel_grade]
if sel_cat != "전체":
    filtered = [r for r in filtered if (r.get("category") or r.get("agent_name","")) == sel_cat]

VERDICT_ICON = {"저평가":"🟢","적정":"🔵","소폭 고평가":"🟡","고평가":"🔴"}
df = pd.DataFrame([{
    "ID":           r["id"],
    "물건 정보":    r["query"],
    "유형":         r.get("category") or r.get("agent_name",""),
    "추정가(만원)": f"{r.get('estimated_value',0):,}",
    "고/저평가":    f"{VERDICT_ICON.get(r.get('valuation_verdict',''),'⚪')} {r.get('valuation_verdict','')}",
    "투자등급":     r.get("investment_grade",""),
    "Cap Rate":     f"{r.get('cap_rate',0):.1f}%",
    "평가일시":     r.get("created",""),
} for r in filtered])

selected = st.dataframe(
    df, width="stretch", hide_index=True,
    on_select="rerun", selection_mode="single-row",
    column_config={
        "ID":          st.column_config.NumberColumn(width="small"),
        "물건 정보":   st.column_config.TextColumn(width="large"),
        "추정가(만원)":st.column_config.TextColumn(width="medium"),
    },
)

page_label = f"페이지 {page}/{max_page}  ·  " if not keyword and max_page > 1 else ""
st.caption(f"{page_label}총 {len(filtered)} 건 표시 (전체 {total_count} 건)")

# ── 상세 리포트 ───────────────────────────────────────────────────────────────
sel_rows = selected.selection.get("rows", [])
if sel_rows:
    item   = filtered[sel_rows[0]]
    rid    = item["id"]
    detail = load_one(rid)

    if detail:
        st.divider()
        col_h, col_del = st.columns([5, 1])
        col_h.subheader(f"평가 #{rid} 상세 결과")
        if col_del.button("🗑️ 삭제", key=f"del_{rid}"):
            delete_one(rid)
            st.success(f"평가 #{rid} 를 삭제했습니다.")
            st.rerun()

        render_full_report(detail, detail.get("query", item["query"]))

        st.divider()
        if st.button("이 결과를 결과 화면에서 보기 →", key=f"goto_{rid}"):
            st.session_state["query"]     = detail.get("query", item["query"])
            st.session_state["result"]    = detail
            st.session_state["result_id"] = rid
            st.switch_page("pages/2_결과리포트.py")