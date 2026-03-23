"""
pages/2_결과리포트.py — 로딩 진행 + 감정평가 결과 리포트
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import streamlit as st
from pipeline import run_with_progress, STEP_LABELS
from history_db import save
from ui_components import render_full_report

# ── 진입 guard ────────────────────────────────────────────────────────────────
query = st.session_state.get("query", "")
if not query:
    st.error("입력된 물건 정보가 없습니다.")
    if st.button("← 입력 화면으로 돌아가기"):
        st.switch_page("pages/1_평가하기.py")
    st.stop()

building_name = st.session_state.get("building_name", "")
raw_inputs    = st.session_state.get("raw_inputs", {})

# ── 이미 결과가 있으면 로딩 건너뜀 ───────────────────────────────────────────
if "result" not in st.session_state:

    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
    html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }
    </style>
    """, unsafe_allow_html=True)

    st.title("🔍 분석 진행 중...")
    addr_display = raw_inputs.get("address") or query
    st.caption(f"**대상:** {addr_display}" + (f"  |  **단지:** {building_name}" if building_name else ""))
    st.divider()

    with st.status("파이프라인 실행 중", expanded=True) as status:
        result = None
        error  = None

        for event in run_with_progress(query, building_name):
            if event["type"] == "step":
                st.write(f"{event['icon']} **{event['title']}** &nbsp;— {event['desc']}")
            elif event["type"] == "result":
                result = event["data"]
            elif event["type"] == "error":
                error = event["message"]

        if error:
            status.update(label="오류 발생 ❌", state="error")
            st.error(f"파이프라인 오류: {error}")
            st.caption("Ollama 실행 여부와 API 키를 확인해 주세요.")
            if st.button("← 다시 시도하기"):
                st.switch_page("pages/1_평가하기.py")
            st.stop()

        status.update(label="감정평가 완료 ✅", state="complete", expanded=False)

    record_id = save(query, result)
    st.session_state["result"]     = result
    st.session_state["result_id"]  = record_id
    st.rerun()

# ── 결과 렌더링 ───────────────────────────────────────────────────────────────
r   = st.session_state["result"]
rid = st.session_state.get("result_id", "")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }
.result-header {
    background: linear-gradient(135deg, #0f2544 0%, #185FA5 100%);
    border-radius: 12px;
    padding: 24px 28px;
    color: white;
    margin-bottom: 20px;
}
.result-header h2 { margin: 0 0 4px; font-size: 1.5rem; font-weight: 700; }
.result-header p  { margin: 0; opacity: 0.82; font-size: 0.92rem; }
</style>
""", unsafe_allow_html=True)

addr_display = raw_inputs.get("address") or query
building_display = f" · {building_name}" if building_name else ""
st.markdown(f"""
<div class="result-header">
  <h2>📄 감정평가 결과</h2>
  <p>{addr_display}{building_display}</p>
</div>
""", unsafe_allow_html=True)

# 버튼 행
b1, b2, b3 = st.columns([1, 1, 4])
if b1.button("🔄 새 평가", use_container_width=True):
    for k in ("query", "result", "result_id", "building_name", "raw_inputs"):
        st.session_state.pop(k, None)
    st.switch_page("pages/1_평가하기.py")
if b2.button("📋 이력 보기", use_container_width=True):
    st.switch_page("pages/3_대시보드.py")

st.divider()

# 전체 리포트 (raw_inputs 전달 → 매물 정보 카드에 표시)
render_full_report(r, query, raw_inputs=raw_inputs)

if rid:
    st.divider()
    st.caption(f"평가 ID: #{rid}  |  이 결과는 이력에 자동 저장되었습니다.")