"""
map_view.py — folium 지도 시각화 컴포넌트
대상 매물 + 유사 매물 Top-5 핀 표시
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))

import streamlit.components.v1 as components


def render_map(geocoding_result: dict, rag_matches: list):
    try:
        import folium
    except ImportError:
        import streamlit as st
        st.warning("folium 패키지가 필요합니다: pip install folium")
        return

    import streamlit as st
    from geocoding import geocode

    lat = geocoding_result.get("lat", 0)
    lng = geocoding_result.get("lng", 0)

    if not lat or not lng:
        st.info("지도 표시를 위한 좌표 정보가 없습니다.")
        return

    # 지도 생성
    m = folium.Map(location=[lat, lng], zoom_start=15)

    # 대상 매물 — 빨간 핀
    folium.Marker(
        location=[lat, lng],
        popup=folium.Popup("📍 대상 매물", max_width=200),
        tooltip="대상 매물",
        icon=folium.Icon(color="red", icon="home", prefix="fa"),
    ).add_to(m)

    # 반경 500m 원
    folium.Circle(
        location=[lat, lng],
        radius=500,
        color="#185FA5",
        fill=True,
        fill_opacity=0.05,
        tooltip="반경 500m"
    ).add_to(m)

# 유사 매물 — 파란 핀 (실시간 지오코딩)
    COLORS = ["blue", "green", "purple", "orange", "darkred"]
    placed = 0
    placed_coords = set()  # ← 추가

    for i, match in enumerate(rag_matches[:5]):
        meta        = match.get("metadata", {})
        place_name  = meta.get("place_name", "")
        sub_region  = meta.get("sub_region", "")
        region      = meta.get("region", "")
        price       = meta.get("price", 0)
        score       = match.get("rag_score", 0)

        if not place_name:
            continue
        if sub_region and sub_region in place_name:
            query = place_name
        elif sub_region:
            query = f"{sub_region} {place_name}".strip()
        else:
            query = f"{region} {place_name}".strip()
       
        try:
            result = geocode(query)
            if not result or not result.lat:
                print(f"[map] 좌표 조회 실패: {query}")
                continue

            # 같은 좌표 중복 제거
            coord_key = f"{result.lat:.4f},{result.lng:.4f}"
            if coord_key in placed_coords:
                print(f"[map] 중복 좌표 스킵: {place_name}")
                continue
            placed_coords.add(coord_key)

            folium.Marker(
                location=[result.lat, result.lng],
                popup=folium.Popup(
                    f"<b>{placed+1}위 {place_name}</b><br>"
                    f"가격: {price:,}만원<br>"
                    f"충족도: {score:.0f}점",
                    max_width=200
                ),
                tooltip=f"{placed+1}위 {place_name} ({score:.0f}점)",
                icon=folium.Icon(
                    color=COLORS[placed % len(COLORS)],
                    icon="building",
                    prefix="fa"
                ),
            ).add_to(m)
            placed += 1
            print(f"[map] {placed}위 핀 추가: {place_name} → {result.lat:.4f}, {result.lng:.4f}")

        except Exception as e:
            print(f"[map] 핀 추가 실패: {query} → {e}")
            continue

    components.html(m._repr_html_(), height=450)