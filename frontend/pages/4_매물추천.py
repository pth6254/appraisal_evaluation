"""
pages/4_매물추천.py — 조건 기반 매물 추천 서비스
용도·지역·예산·면적·특수조건 입력 → RAG 검색 → 유사 매물 Top-5 카드 + 지도
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import streamlit as st
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# ── 페이지 설정 ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="매물 추천 — AppraisalAI",
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
    margin-bottom: 12px;
}
.card-title {
    font-weight: 700;
    font-size: 1.0rem;
    color: var(--text-color);
}
.card-location {
    font-size: 0.85rem;
    color: var(--text-color);
    opacity: 0.6;
    margin-left: 8px;
}
.card-price {
    font-size: 1.15rem;
    font-weight: 700;
    color: #185FA5;
}
.card-detail {
    margin-top: 8px;
    font-size: 0.85rem;
    color: var(--text-color);
    opacity: 0.75;
}
.card-reason {
    margin-top: 8px;
    font-size: 0.82rem;
    color: var(--text-color);
    opacity: 0.7;
    background: var(--secondary-background-color);
    padding: 8px 12px;
    border-radius: 6px;
}
</style>
""", unsafe_allow_html=True)

# ── 예산 파싱 함수 ────────────────────────────────────────────────────────────
def parse_price(text: str) -> int:
    """'5억', '5억3000', '53000만원', '530000000' 등 → 만원 단위 int"""
    if not text or not text.strip():
        return 0
    text = text.strip().replace(",", "").replace(" ", "")
    try:
        if "억" in text:
            parts = text.replace("만원", "").replace("만", "").split("억")
            uk  = float(parts[0]) * 10000
            man = float(parts[1]) if parts[1] else 0
            return int(uk + man)
        if "만원" in text or "만" in text:
            return int(float(text.replace("만원", "").replace("만", "")))
        val = float(text)
        if val >= 100000000:   # 원 단위로 입력한 경우
            return int(val / 10000)
        return int(val)
    except (ValueError, IndexError):
        return 0

def format_price_display(won: int) -> str:
    """만원 단위 숫자 → '5억 3,000만원' 형태 표시"""
    if won <= 0:
        return ""
    uk  = won // 10000
    man = won % 10000
    if uk > 0 and man > 0:
        return f"{uk}억 {man:,}만원"
    elif uk > 0:
        return f"{uk}억"
    else:
        return f"{won:,}만원"

# ── 헤더 ─────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="rec-header">
  <h2>🏠 매물 추천 서비스</h2>
  <p>원하는 조건을 입력하면 AI가 실거래 데이터에서 가장 적합한 매물을 찾아드립니다.</p>
</div>
""", unsafe_allow_html=True)

# ── 특수조건 태그 옵션 (유형별) ───────────────────────────────────────────────
CONDITION_OPTIONS = {
    "주거용": ["역세권", "초품아", "남향", "신축", "올수리", "주차", "조용", "한강뷰", "고층"],
    "상업용": ["1층", "코너", "유동인구", "권리금없음", "주차", "역세권"],
    "업무용": ["역세권", "주차", "신축", "고층", "강남"],
    "산업용": ["층고높음", "트럭진입", "3상전력", "냉동창고", "냉장창고", "물류"],
    "토지":   ["개발호재", "도로접함", "전원주택", "맹지아님", "농지전용가능"],
}

# ── 세션 상태 초기화 ──────────────────────────────────────────────────────────
if "rec_selected_conditions" not in st.session_state:
    st.session_state["rec_selected_conditions"] = []
if "rec_result" not in st.session_state:
    st.session_state["rec_result"] = None
if "rec_category" not in st.session_state:
    st.session_state["rec_category"] = "주거용"

# ── 입력 폼 ──────────────────────────────────────────────────────────────────
with st.form("rec_form"):
    col1, col2 = st.columns(2)

    with col1:
        st.markdown('<div class="section-label">🏢 용도 선택</div>', unsafe_allow_html=True)
        category = st.selectbox(
            "용도",
            ["주거용", "상업용", "업무용", "산업용", "토지"],
            index=["주거용", "상업용", "업무용", "산업용", "토지"].index(
                st.session_state.get("rec_category", "주거용")
            ),
            label_visibility="collapsed"
        )

        st.markdown('<div class="section-label">📍 지역 입력</div>', unsafe_allow_html=True)
        location = st.text_input(
            "지역",
            placeholder="예) 서울 서초구, 경기 성남시 분당구",
            label_visibility="collapsed"
        )

    with col2:
        st.markdown('<div class="section-label">💰 예산 범위</div>', unsafe_allow_html=True)
        price_col1, price_col2 = st.columns(2)
        with price_col1:
            price_min_str = st.text_input(
                "최소 예산",
                placeholder="예) 3억, 5억5000",
                label_visibility="collapsed"
            )
        with price_col2:
            price_max_str = st.text_input(
                "최대 예산",
                placeholder="예) 10억, 15억",
                label_visibility="collapsed"
            )

        st.markdown('<div class="section-label">📐 면적 범위 (㎡)</div>', unsafe_allow_html=True)
        area_col1, area_col2 = st.columns(2)
        with area_col1:
            area_min = st.number_input(
                "최소 면적", min_value=0.0, max_value=99999.0,
                value=0.0, step=10.0, label_visibility="collapsed",
                placeholder="최소 (㎡)"
            )
        with area_col2:
            area_max = st.number_input(
                "최대 면적", min_value=0.0, max_value=99999.0,
                value=0.0, step=10.0, label_visibility="collapsed",
                placeholder="최대 (㎡)"
            )

    # 특수조건 태그
    st.markdown('<div class="section-label">✨ 특수조건 (선택)</div>', unsafe_allow_html=True)
    conditions_options = CONDITION_OPTIONS.get(category, [])
    selected_conditions = st.multiselect(
        "특수조건",
        options=conditions_options,
        default=[c for c in st.session_state.get("rec_selected_conditions", [])
                 if c in conditions_options],
        label_visibility="collapsed",
        placeholder="원하는 조건을 선택하세요 (복수 선택 가능)"
    )

    submitted = st.form_submit_button("🔍  매물 추천받기", type="primary", use_container_width=True)

# ── 검색 실행 ────────────────────────────────────────────────────────────────
if submitted:
    if not location.strip():
        st.error("지역을 입력해주세요. 예) 서울 서초구, 마포구")
        st.stop()

    # 예산 파싱
    price_min = parse_price(price_min_str)
    price_max = parse_price(price_max_str)

    # 예산 입력값 검증 피드백
    if price_min_str.strip() and price_min == 0:
        st.warning(f"최소 예산 '{price_min_str}' 을 인식하지 못했습니다. '5억', '50000만원' 형태로 입력해주세요.")
    if price_max_str.strip() and price_max == 0:
        st.warning(f"최대 예산 '{price_max_str}' 을 인식하지 못했습니다. '10억', '100000만원' 형태로 입력해주세요.")
    if price_min > 0 and price_max > 0:
        st.info(f"💰 예산 범위: {format_price_display(price_min)} ~ {format_price_display(price_max)}")
    elif price_max > 0:
        st.info(f"💰 최대 예산: {format_price_display(price_max)}")
    elif price_min > 0:
        st.info(f"💰 최소 예산: {format_price_display(price_min)} 이상")

    st.session_state["rec_category"] = category
    st.session_state["rec_selected_conditions"] = selected_conditions

    with st.spinner("🔍 조건에 맞는 매물을 검색하고 있습니다..."):
        try:
            # ── 백엔드 임포트 ──────────────────────────────────────────────
            from intent_agent import PropertyIntent
            from geocoding import geocode
            from price_engine import fetch_real_transaction_prices
            from cache_db import init_cache_db, cached_api_call
            from rag_pipeline import run_rag_pipeline

            init_cache_db()

            # ── 1. PropertyIntent 직접 구성 ────────────────────────────────
            intent = PropertyIntent(
                category=category,
                category_detail="",
                location_raw=location.strip(),
                location_normalized=location.strip(),
                transaction_type="매매",
                price_min=price_min if price_min > 0 else None,
                price_max=price_max if price_max > 0 else None,
                area_min=float(area_min) if area_min > 0 else None,
                area_max=float(area_max) if area_max > 0 else None,
                special_conditions=selected_conditions,
                confidence=0.9,
            )

            # ── 2. 지오코딩 ────────────────────────────────────────────────
            geo_result = geocode(location.strip(), category=category)
            if not geo_result:
                st.error(f"'{location}' 지역을 찾을 수 없습니다. 더 구체적인 주소를 입력해주세요.")
                st.stop()

            region_2depth = geo_result.region_2depth
            region_1depth = geo_result.region_1depth
            region_3depth = geo_result.region_3depth

            # ── 3. 실거래가 API 조회 ───────────────────────────────────────
            price_data = cached_api_call(
                func=fetch_real_transaction_prices,
                namespace="molit",
                ttl=86400,
                category=category,
                region_2depth=region_2depth,
            )

            avg_price = price_data.get("avg", 0)
            count     = price_data.get("count", 0)

            # ── 4. RAG 파이프라인 실행 ─────────────────────────────────────
            state = {
                "intent": intent,
                "geocoding_result": geo_result.model_dump(),
                "rag_top_matches": [],
                "rag_query": "",
                "rag_match_count": 0,
            }

            state = run_rag_pipeline(state, price_data)

            # ── 5. 결과 저장 ────────────────────────────────────────────────
            st.session_state["rec_result"] = {
                "rag_top_matches": state.get("rag_top_matches", []),
                "rag_query":       state.get("rag_query", ""),
                "rag_match_count": state.get("rag_match_count", 0),
                "avg_price":       avg_price,
                "count":           count,
                "geo":             geo_result.model_dump(),
                "intent":          intent,
                "category":        category,
                "location":        location.strip(),
                "region_1depth":   region_1depth,
                "region_2depth":   region_2depth,
                "price_min":       price_min if price_min > 0 else None,
                "price_max":       price_max if price_max > 0 else None,
                "area_min":        float(area_min) if area_min > 0 else None,
                "area_max":        float(area_max) if area_max > 0 else None,
                "conditions":      selected_conditions,
            }

        except Exception as e:
            st.error(f"검색 중 오류가 발생했습니다: {e}")
            import traceback
            st.code(traceback.format_exc())
            st.stop()

# ── 결과 표시 ─────────────────────────────────────────────────────────────────
result = st.session_state.get("rec_result")

if result:
    rag_matches   = result.get("rag_top_matches", [])
    avg_price     = result.get("avg_price", 0)
    count         = result.get("count", 0)
    conditions    = result.get("conditions", [])
    location_disp = result.get("location", "")
    category_disp = result.get("category", "")
    region_2depth = result.get("region_2depth", "")
    geo           = result.get("geo", {})

    st.divider()

    # 검색 조건 요약
    cond_str  = "  ·  ".join(conditions) if conditions else "없음"
    price_min_v = result.get("price_min")
    price_max_v = result.get("price_max")

    if price_min_v and price_max_v:
        price_str = f"{format_price_display(price_min_v)} ~ {format_price_display(price_max_v)}"
    elif price_max_v:
        price_str = f"~{format_price_display(price_max_v)}"
    elif price_min_v:
        price_str = f"{format_price_display(price_min_v)}~"
    else:
        price_str = "제한 없음"

    area_str = ""
    if result.get("area_min") and result.get("area_max"):
        area_str = f"{result['area_min']:.0f} ~ {result['area_max']:.0f}㎡"
    elif result.get("area_max"):
        area_str = f"~{result['area_max']:.0f}㎡"
    elif result.get("area_min"):
        area_str = f"{result['area_min']:.0f}㎡~"
    else:
        area_str = "제한 없음"

    with st.expander("📋 검색 조건 요약", expanded=False):
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("용도", category_disp)
        c2.metric("지역", location_disp)
        c3.metric("예산", price_str)
        c4.metric("면적", area_str)
        if conditions:
            st.info(f"✨ 특수조건: {cond_str}")

    # 지역 시세 정보
    if avg_price > 0:
        st.info(
            f"📊 **{region_2depth}** {category_disp} 최근 3개월 실거래 평균: "
            f"**{format_price_display(avg_price)}** ({count}건)"
        )

    st.markdown("")

    # 탭 구성
    tab1, tab2 = st.tabs(["🏠 추천 매물 Top-5", "🗺️ 지도"])

    with tab1:
        if not rag_matches:
            st.warning("검색 조건에 맞는 매물이 없습니다. 조건을 넓혀서 다시 검색해보세요.")
        else:
            st.markdown(f"**{len(rag_matches)}개 매물**을 찾았습니다.")
            st.markdown("")

            # 중복 제거
            seen = set()
            unique_matches = []
            for m in rag_matches:
                meta = m.get("metadata", {})
                key  = f"{meta.get('place_name', '')}_{meta.get('price', 0)}"
                if key not in seen:
                    seen.add(key)
                    unique_matches.append(m)

            for i, match in enumerate(unique_matches[:5]):
                meta       = match.get("metadata", {})
                score      = match.get("rag_score", 0)
                reason     = match.get("reason", "")
                price      = meta.get("price", 0)
                area       = meta.get("area", 0)
                floor_v    = meta.get("floor", "")
                year_built = meta.get("year_built", 0)
                place_name = meta.get("place_name", "")
                sub_region = meta.get("sub_region", "")
                region_v   = meta.get("region", "")

                if score >= 80:
                    score_color  = "🟢"
                    border_color = "#27AE60"
                elif score >= 60:
                    score_color  = "🟡"
                    border_color = "#F39C12"
                else:
                    score_color  = "🔴"
                    border_color = "#E74C3C"

                display_location = f"{region_v} {sub_region}".strip() if sub_region else region_v
                age_str = f" · {2025 - year_built}년차" if year_built and year_built > 1900 else ""
                detail_parts = []
                if area:
                    detail_parts.append(f"면적: {area:.1f}㎡")
                if floor_v and str(floor_v).strip():
                    detail_parts.append(f"{floor_v}층")
                if age_str:
                    detail_parts.append(age_str.strip(" ·"))
                detail_str = "  |  ".join(detail_parts)

                st.markdown(f"""
                <div class="card-wrap" style="
                    border: 1.5px solid {border_color};
                    border-left: 5px solid {border_color};
                ">
                    <div style="display:flex; justify-content:space-between; align-items:flex-start;">
                        <div>
                            <span class="card-title">
                                {score_color} {i+1}위{f' — {place_name}' if place_name else ''}
                            </span>
                            <span class="card-location">{display_location}</span>
                        </div>
                        <span class="card-price">{format_price_display(price)}</span>
                    </div>
                    <div class="card-detail">{detail_str}</div>
                    <div class="card-reason">💬 {reason}</div>
                </div>
                """, unsafe_allow_html=True)

                col_l, col_r = st.columns([4, 1])
                with col_r:
                    st.metric("충족도", f"{score:.0f}점")

    with tab2:
        try:
            import folium
            import streamlit.components.v1 as components
            from geocoding import geocode as _geocode

            lat = geo.get("lat", 0)
            lng = geo.get("lng", 0)

            if lat and lng:
                m = folium.Map(location=[lat, lng], zoom_start=14)

                folium.Circle(
                    location=[lat, lng],
                    radius=1000,
                    color="#185FA5",
                    fill=True,
                    fill_opacity=0.05,
                    tooltip=f"{location_disp} 반경 1km"
                ).add_to(m)

                folium.Marker(
                    location=[lat, lng],
                    popup=folium.Popup(f"📍 {location_disp}", max_width=200),
                    tooltip="검색 지역",
                    icon=folium.Icon(color="blue", icon="search", prefix="fa"),
                ).add_to(m)

                COLORS = ["red", "green", "purple", "orange", "darkred"]
                placed = 0
                placed_coords = set()

                for i, match in enumerate(rag_matches[:5]):
                    meta       = match.get("metadata", {})
                    place_name = meta.get("place_name", "")
                    sub_region = meta.get("sub_region", "")
                    region_v   = meta.get("region", "")
                    price      = meta.get("price", 0)
                    score      = match.get("rag_score", 0)

                    if not place_name:
                        continue

                    if sub_region and sub_region in place_name:
                        query = place_name
                    elif sub_region:
                        query = f"{sub_region} {place_name}".strip()
                    else:
                        query = f"{region_v} {place_name}".strip()

                    try:
                        r = _geocode(query)
                        if not r or not r.lat:
                            continue
                        coord_key = f"{r.lat:.4f},{r.lng:.4f}"
                        if coord_key in placed_coords:
                            continue
                        placed_coords.add(coord_key)

                        folium.Marker(
                            location=[r.lat, r.lng],
                            popup=folium.Popup(
                                f"<b>{placed+1}위 {place_name}</b><br>"
                                f"가격: {format_price_display(price)}<br>"
                                f"충족도: {score:.0f}점",
                                max_width=200
                            ),
                            tooltip=f"{placed+1}위 {place_name} ({score:.0f}점)",
                            icon=folium.Icon(
                                color=COLORS[placed % len(COLORS)],
                                icon="building", prefix="fa"
                            ),
                        ).add_to(m)
                        placed += 1
                    except Exception:
                        continue

                components.html(m._repr_html_(), height=480)
            else:
                st.info("지도를 표시할 좌표 정보가 없습니다.")

        except ImportError:
            st.warning("지도 기능을 사용하려면 folium을 설치해주세요: pip install folium")

    st.divider()
    if st.button("🔄 새로 검색", use_container_width=True):
        st.session_state["rec_result"] = None
        st.session_state["rec_selected_conditions"] = []
        st.rerun()