"""
app.py — DeepAgent Streamlit 진입점
개선:
  - API 키 누락 시 사이드바에 경고 표시
  - 캐시 DB 초기화 포함
  - pages/ 폴더 구조 안내
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
from cache_db import init_cache_db
from dotenv import load_dotenv, find_dotenv
import streamlit as st
from history_db import init as init_db

load_dotenv(find_dotenv())

# ── 페이지 설정 (반드시 첫 번째 st 호출) ────────────────────────────────────
st.set_page_config(
    page_title="Appraisal AI — | 부동산 감정평가 서비스",
    page_icon="🏢",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── DB 초기화 (앱 최초 실행 시 테이블 생성) ──────────────────────────────────
init_db()
init_cache_db()

# ── API 키 상태 확인 ──────────────────────────────────────────────────────────
_missing_keys = [
    k for k in ["KAKAO_REST_API_KEY", "MOLIT_API_KEY"]
    if not os.getenv(k)
]
_tavily_ok = bool(os.getenv("TAVILY_API_KEY"))

# ── 사이드바 ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🏢 Appraisal AI ")
    st.caption("AI 부동산 가치 감정평가 서비스")
    st.divider()

    st.markdown("**모델**  EXAONE 3.5 7.8B")
    st.markdown("**거래**  매매 전용")
    st.markdown("**엔진**  LangGraph + Ollama")
    st.divider()

    if st.button("➕  새 감정평가 시작", width="stretch", type="primary"):
        for k in ("query", "result", "result_id", "building_name"):
            st.session_state.pop(k, None)
        st.switch_page("pages/1_평가하기.py")

    if st.button("📋  평가 이력 보기", width="stretch"):
        st.switch_page("pages/3_대시보드.py")

    st.divider()

    # API 키 상태 표시
    if _missing_keys:
        st.warning(
            f"⚠️ API 키 미설정\n\n"
            f"`{', '.join(_missing_keys)}`\n\n"
            "`.env` 파일을 확인해 주세요.\n실거래가 데이터가 더미로 표시됩니다."
        )
    else:
        st.success("✅ API 키 정상")
        if not _tavily_ok:
            st.caption("💡 TAVILY_API_KEY 없음 — 웹 검색 비활성")

    st.caption("v2.1 · 감정평가 전용")

# ── 메인 홈 화면 ─────────────────────────────────────────────────────────────
st.title("Appraisal AI")
st.subheader("AI 부동산 가치 감정평가 서비스")
st.markdown(
    "자연어로 부동산 정보를 입력하면 "
    "실거래가 데이터와 LLM 추론을 결합해 **전문 감정평가사 수준의 의견서**를 제공합니다."
)
st.divider()

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("#### 📊 핵심 출력물")
    st.markdown("""
- **추정 시장가치** — 비교사례법 기반 ±10% 범위
- **평당가 분석** — 지역 평균 대비 비교
- **고/저평가 판단** — 인근 실거래 괴리율
- **투자 수익률** — Cap Rate · 연 임대수입 · 투자등급
    """)

with col2:
    st.markdown("#### 🏗️ 지원 유형")
    st.markdown("""
- 주거용 (아파트 · 연립 · 단독 · 오피스텔)
- 상업용 (상가 · 사무실)
- 업무용 (오피스)
- 산업용 (공장 · 창고)
- 토지
    """)

st.divider()

# API 키 미설정 시 홈에도 경고
if _missing_keys:
    st.warning(
        f"**API 키가 설정되지 않았습니다**: `{', '.join(_missing_keys)}`  \n"
        "프로젝트 루트의 `.env` 파일에 키를 입력한 후 앱을 재시작해 주세요.",
        icon="⚠️",
    )

if st.button("🔍  감정평가 시작하기 →", type="primary"):
    st.switch_page("pages/1_평가하기.py")