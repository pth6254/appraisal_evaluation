"""
pages/1_평가하기.py — 주소 입력 → 카카오 주소검색 building_name 으로 정확한 건물명 도출
"""

import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..', 'backend'))

import requests
import streamlit as st
from dotenv import load_dotenv, find_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', '..', '.env'))

KAKAO_API_KEY  = os.getenv("KAKAO_REST_API_KEY", "")
KAKAO_ADDR_URL = "https://dapi.kakao.com/v2/local/search/address.json"
KAKAO_KWD_URL  = "https://dapi.kakao.com/v2/local/search/keyword.json"

KAKAO_CATEGORY_MAP = [
    ("아파트",       "주거용", "아파트"),
    ("오피스텔",     "주거용", "오피스텔"),
    ("빌라",         "주거용", "빌라"),
    ("연립",         "주거용", "연립다세대"),
    ("다세대",       "주거용", "연립다세대"),
    ("단독주택",     "주거용", "단독다가구"),
    ("다가구",       "주거용", "단독다가구"),
    ("주거시설",     "주거용", "아파트"),
    ("공장",         "산업용", "공장"),
    ("창고",         "산업용", "창고"),
    ("물류",         "산업용", "창고"),
    ("지식산업센터", "산업용", "공장"),
    ("사무",         "업무용", "사무실"),
    ("오피스",       "업무용", "사무실"),
    ("상가",         "상업용", "상가"),
    ("마트",         "상업용", "상가"),
    ("백화점",       "상업용", "상가"),
    ("토지",         "토지",   "토지"),
    ("농지",         "토지",   "토지"),
    ("임야",         "토지",   "토지"),
]

PROP_ICON = {
    "주거용": "🏠", "상업용": "🏬",
    "업무용": "🏢", "산업용": "🏭", "토지": "🌿",
}


def _map_category(category_name: str) -> tuple[str, str]:
    for kw, prop, detail in KAKAO_CATEGORY_MAP:
        if kw in category_name:
            return prop, detail
    return "", ""


def _kakao_headers() -> dict:
    return {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}


def search_buildings(query: str) -> list[dict]:
    """
    주소 또는 건물명 입력 → 건물 목록 반환.

    1순위: 카카오 주소검색 API
           road_address.building_name → 정확한 건물명 1:1 대응
           예) "서울시 서초구 반포대로 333" → building_name: "래미안원베일리"

    2순위: 주소검색 결과 없거나 building_name 없을 때
           카카오 키워드검색 API 폴백
           예) "마포래미안푸르지오" 처럼 건물명 직접 입력 시
    """
    if not KAKAO_API_KEY or not query.strip():
        return []

    results = []

    # ── 1순위: 주소검색 → building_name 직접 추출 ─────────────────────────
    try:
        res = requests.get(
            KAKAO_ADDR_URL,
            headers=_kakao_headers(),
            params={"query": query, "size": 5},
            timeout=5,
        )
        res.raise_for_status()
        docs = res.json().get("documents", [])

        for doc in docs:
            road = doc.get("road_address") or {}
            jibun = doc.get("address") or {}

            # building_name: 도로명 주소 응답에 포함된 건물명
            building_name = road.get("building_name", "").strip()
            road_addr     = road.get("address_name", "")
            jibun_addr    = jibun.get("address_name", "")
            address_name  = road_addr or jibun_addr

            # 건물명 없으면 주소 자체를 place_name으로
            place_name = building_name or address_name

            results.append({
                "place_name":        place_name,
                "building_name":     building_name,
                "address_name":      jibun_addr,
                "road_address_name": road_addr,
                "category_name":     "",
                "property_category": "",
                "category_detail":   "",
                "source":            "address",
                "x": doc.get("x", ""),
                "y": doc.get("y", ""),
            })

    except Exception as e:
        print(f"[search_buildings] 주소검색 오류: {e}")

    # 주소검색에서 결과가 있으면 반환
    if results:
        # building_name 있는 항목 먼저, 없는 항목 나중
        results.sort(key=lambda x: (0 if x["building_name"] else 1))
        return results

    # ── 2순위: 키워드검색 폴백 (건물명 직접 입력 시) ──────────────────────
    try:
        res = requests.get(
            KAKAO_KWD_URL,
            headers=_kakao_headers(),
            params={"query": query, "size": 10},
            timeout=5,
        )
        res.raise_for_status()
        docs = res.json().get("documents", [])

        for doc in docs:
            cat_name         = doc.get("category_name", "")
            prop_cat, detail = _map_category(cat_name)
            addr             = doc.get("road_address_name") or doc.get("address_name", "")
            results.append({
                "place_name":        doc.get("place_name", ""),
                "building_name":     doc.get("place_name", ""),
                "address_name":      doc.get("address_name", ""),
                "road_address_name": doc.get("road_address_name", ""),
                "category_name":     cat_name,
                "property_category": prop_cat,
                "category_detail":   detail,
                "source":            "keyword",
                "x": doc.get("x", ""),
                "y": doc.get("y", ""),
            })

    except Exception as e:
        print(f"[search_buildings] 키워드검색 오류: {e}")

    return results


# ── 스타일 ───────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@300;400;500;700&display=swap');
html, body, [class*="css"] { font-family: 'Noto Sans KR', sans-serif; }

.hero {
    background: linear-gradient(135deg, #0f2544 0%, #185FA5 60%, #1e7fd4 100%);
    border-radius: 16px; padding: 40px 36px 32px;
    margin-bottom: 28px; color: white;
}
.hero h1 { font-size: 2rem; font-weight: 700; margin: 0 0 6px; letter-spacing: -0.5px; }
.hero p  { font-size: 1rem; opacity: 0.82; margin: 0; }

.section-label {
    font-size: 0.75rem; font-weight: 600; color: #185FA5;
    letter-spacing: 0.08em; text-transform: uppercase; margin-bottom: 8px;
}
.building-card {
    border: 1px solid #D3D9E8; border-radius: 10px;
    padding: 12px 16px; margin-bottom: 8px; background: #fff;
}
.building-name { font-size: 0.97rem; font-weight: 600; color: #0A2540; }
.building-addr { font-size: 0.82rem; color: #666; margin-top: 2px; }
.building-badge {
    display: inline-block; background: #EBF3FC; color: #185FA5;
    border-radius: 12px; padding: 2px 10px;
    font-size: 0.75rem; font-weight: 600; margin-top: 4px;
}
.selected-box {
    background: #EBF3FC; border: 1.5px solid #185FA5;
    border-radius: 12px; padding: 16px 20px; margin-bottom: 16px;
}
.selected-box .label { font-size: 0.75rem; color: #185FA5; font-weight: 600; }
.selected-box .value { font-size: 1rem; font-weight: 700; color: #0A2540; margin-top: 2px; }
.info-box {
    background: #F7F9FC; border-left: 3px solid #185FA5;
    border-radius: 0 8px 8px 0; padding: 14px 18px;
    font-size: 0.87rem; color: #444; margin-top: 16px; line-height: 1.7;
}
</style>
""", unsafe_allow_html=True)

# ── 히어로 ───────────────────────────────────────────────────────────────
st.markdown("""
<div class="hero">
  <h1>🏢 AI 부동산 감정평가</h1>
  <p>도로명 주소를 입력하면 건물명을 자동으로 찾아 정확한 감정평가를 제공합니다</p>
</div>
""", unsafe_allow_html=True)

# ── 예시 버튼 ────────────────────────────────────────────────────────────
EXAMPLES = [
    {"label": "🏠 아파트",    "query": "서울시 서초구 반포대로 333"},
    {"label": "🏠 아파트 2",  "query": "서울시 마포구 백범로 192"},
    {"label": "🏢 오피스",    "query": "서울시 영등포구 여의대로 108"},
    {"label": "🏭 지식산업",  "query": "경기도 성남시 분당구 판교역로 235"},
    {"label": "🏬 상가",      "query": "부산시 해운대구 해운대해변로 264"},
]

st.markdown('<div class="section-label">빠른 예시</div>', unsafe_allow_html=True)
cols = st.columns(len(EXAMPLES))
for col, ex in zip(cols, EXAMPLES):
    if col.button(ex["label"], use_container_width=True):
        st.session_state["search_query"]      = ex["query"]
        st.session_state["selected_building"] = None
        st.rerun()

st.divider()

# ── 검색창 ───────────────────────────────────────────────────────────────
st.markdown('<div class="section-label">📍 도로명 주소 또는 건물명 입력</div>',
            unsafe_allow_html=True)

search_query = st.text_input(
    label="주소 검색",
    value=st.session_state.get("search_query", ""),
    placeholder="예) 서울시 서초구 반포대로 333  /  마포래미안푸르지오",
    label_visibility="collapsed",
)

if search_query != st.session_state.get("search_query", ""):
    st.session_state["search_query"]      = search_query
    st.session_state["selected_building"] = None

# ── 검색 결과 ─────────────────────────────────────────────────────────────
selected = st.session_state.get("selected_building")

if search_query.strip() and not selected:
    buildings = search_buildings(search_query)

    if buildings:
        st.markdown('<div class="section-label">🔍 검색 결과 — 선택하세요</div>',
                    unsafe_allow_html=True)

        for i, b in enumerate(buildings):
            prop_cat = b["property_category"]
            icon     = PROP_ICON.get(prop_cat, "🏗️")
            addr     = b["road_address_name"] or b["address_name"]
            name     = b["place_name"] or addr

            # 배지: 카테고리 있으면 유형, 없으면 주소검색 결과임을 표시
            if prop_cat:
                badge = f"{icon} {prop_cat} · {b['category_detail']}"
            elif b["building_name"]:
                badge = "🏗️ 건물명 확인됨"
            else:
                badge = "📍 주소"

            col_info, col_btn = st.columns([5, 1])
            with col_info:
                st.markdown(f"""
                <div class="building-card">
                  <div class="building-name">{name}</div>
                  <div class="building-addr">{addr}</div>
                  <span class="building-badge">{badge}</span>
                </div>
                """, unsafe_allow_html=True)
            with col_btn:
                st.markdown("<div style='height:18px'></div>", unsafe_allow_html=True)
                if st.button("선택", key=f"sel_{i}", use_container_width=True):
                    st.session_state["selected_building"] = b
                    st.rerun()
    else:
        st.warning("검색 결과가 없습니다. 도로명 주소 또는 건물명을 다시 확인해주세요.")

# ── 선택된 건물 ───────────────────────────────────────────────────────────
if selected:
    prop_cat = selected.get("property_category", "")
    icon     = PROP_ICON.get(prop_cat, "🏗️")
    addr     = selected.get("road_address_name") or selected.get("address_name", "")
    name     = selected.get("place_name") or addr

    st.markdown(f"""
    <div class="selected-box">
      <div class="label">✅ 선택된 건물</div>
      <div class="value">{icon} {name}</div>
      <div style="font-size:0.85rem; color:#555; margin-top:4px">{addr}</div>
      {f'<span class="building-badge" style="margin-top:6px;display:inline-block">{prop_cat} · {selected.get("category_detail","")}</span>' if prop_cat else ""}
    </div>
    """, unsafe_allow_html=True)

    if st.button("🔄 다시 검색", use_container_width=False):
        st.session_state["selected_building"] = None
        st.rerun()

    st.divider()
    st.markdown("")

    if st.button("감정평가 시작 →", type="primary", use_container_width=True):
        place  = selected.get("building_name") or selected.get("place_name", "")
        detail = selected.get("category_detail", "")

        parts = [place or addr]
        if detail and detail not in parts[0]:
            parts.append(detail)

        for k in ("result", "result_id"):
            st.session_state.pop(k, None)

        st.session_state["query"]         = " ".join(parts)
        st.session_state["building_name"] = place
        st.session_state["raw_inputs"] = {
            "address":   addr,
            "building":  place,
            "price":     "",
            "prop_type": prop_cat,
            "area":      "",   # 면적 입력 없음 → 면적대별 범위로 제시
        }
        st.switch_page("pages/2_결과리포트.py")

# ── 안내 박스 ─────────────────────────────────────────────────────────────
if not selected and not search_query.strip():
    st.markdown("""
    <div class="info-box">
      <b>사용 방법</b><br>
      • <b>도로명 주소</b>를 입력하면 해당 주소의 건물명을 자동으로 찾습니다.<br>
      &nbsp;&nbsp;예) 서울시 서초구 반포대로 333 → <b>래미안원베일리</b><br>
      • <b>건물명·단지명</b>을 직접 입력해도 됩니다.<br>
      &nbsp;&nbsp;예) 마포래미안푸르지오<br>
      • 검색 결과에서 <b>[선택]</b> 버튼을 눌러 확정하세요.<br>
      • 면적 입력 없이도 감정평가가 진행되며, <b>면적대별 가격 범위</b>로 결과를 제시합니다.
    </div>
    """, unsafe_allow_html=True)