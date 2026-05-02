"""
llm_utils.py — LLM·외부 검색 유틸리티 v1.0

analysis_tools.py에서 분리된 LLM/API 호출 모듈.
외부 의존: Ollama (로컬 LLM), Kakao REST API, Tavily 웹검색.

공개 인터페이스:
  generate_appraisal_opinion() — Ollama 감정평가 의견서 생성
  search_nearby_facilities()   — Kakao POI 주변 시설 조회
  search_web_tavily()          — Tavily 웹 검색 요약
"""

from __future__ import annotations

import json
import os
import re
import time

import requests
from dotenv import find_dotenv, load_dotenv
from langchain_ollama import ChatOllama

load_dotenv(find_dotenv())

KAKAO_API_KEY  = os.getenv("KAKAO_REST_API_KEY", "")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY", "")

if not KAKAO_API_KEY:
    print("[llm_utils] ⚠️  KAKAO_REST_API_KEY 없음 → 주변시설 조회 불가")


# ─────────────────────────────────────────
#  Kakao 주변 시설 검색
# ─────────────────────────────────────────

KAKAO_CATEGORY_URL   = "https://dapi.kakao.com/v2/local/search/category.json"
KAKAO_CATEGORY_CODES = {
    "지하철역": "SW8", "학교": "SC4", "마트": "MT1",
    "편의점": "CS2",  "병원": "HP8", "음식점": "FD6",
    "카페": "CE7",    "주차장": "PK6", "은행": "BK9",
}


def search_nearby_facilities(lat: float, lng: float,
                              categories: list[str], radius: int = 1000) -> dict:
    if not KAKAO_API_KEY:
        return {}
    headers = {"Authorization": f"KakaoAK {KAKAO_API_KEY}"}
    result  = {}
    for cat_name in categories:
        cat_code = KAKAO_CATEGORY_CODES.get(cat_name)
        if not cat_code:
            continue
        try:
            res  = requests.get(KAKAO_CATEGORY_URL, headers=headers, params={
                "category_group_code": cat_code,
                "x": lng, "y": lat, "radius": radius, "size": 15, "sort": "distance",
            }, timeout=5)
            docs = res.json().get("documents", [])
            result[cat_name] = {
                "count":        len(docs),
                "nearest_m":    int(docs[0].get("distance", 9999)) if docs else 9999,
                "nearest_name": docs[0].get("place_name", "") if docs else "",
            }
            time.sleep(0.05)
        except Exception as e:
            print(f"[kakao_nearby] {cat_name} 오류: {e}")
    return result


# ─────────────────────────────────────────
#  Tavily 웹 검색
# ─────────────────────────────────────────

def search_web_tavily(query: str, max_results: int = 3) -> str:
    if not TAVILY_API_KEY:
        return ""
    try:
        res  = requests.post(
            "https://api.tavily.com/search",
            json={"api_key": TAVILY_API_KEY, "query": query,
                  "max_results": max_results, "search_depth": "basic",
                  "include_answer": True},
            timeout=10,
        )
        data = res.json()
        if data.get("answer"):
            return data["answer"]
        return " / ".join(r.get("content", "")[:200] for r in data.get("results", []))
    except Exception as e:
        print(f"[tavily] 오류: {e}")
        return ""


# ─────────────────────────────────────────
#  Ollama 감정평가 의견서 생성
# ─────────────────────────────────────────

APPRAISAL_PROMPT = """당신은 국가공인 부동산 감정평가사입니다.
아래 데이터를 바탕으로 전문적인 감정평가 의견서를 작성하세요.

반드시 아래 JSON 형식으로만 응답하세요:
{
  "appraisal_opinion": "3~4문장의 전문 감정평가 의견",
  "strengths": ["가치 상승 요인1", "요인2", "요인3"],
  "risk_factors": ["리스크 요인1", "요인2"],
  "recommendation": "매수 적극 고려 | 매수 고려 | 관망 | 매수 비추천"
}"""


def generate_appraisal_opinion(category, location, valuation_data, nearby_data, web_summary) -> dict:
    llm = ChatOllama(
        model=os.getenv("OLLAMA_MODEL", "exaone3.5:7.8b"),
        base_url=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
        temperature=0.1, format="json", num_predict=1024,
    )
    estimated   = valuation_data.get("estimated_value", 0)
    verdict     = valuation_data.get("valuation_verdict", "")
    deviation   = valuation_data.get("deviation_pct", 0)
    cap_rate    = valuation_data.get("cap_rate", 0)
    ppyeong     = valuation_data.get("price_per_pyeong", 0)
    reg_ppyeong = valuation_data.get("regional_avg_per_pyeong", 0)

    nearby_text = "\n".join(
        f"  {k}: {v.get('count', 0)}개 (최근접 {v.get('nearest_m', 0)}m)"
        for k, v in nearby_data.items() if isinstance(v, dict) and v.get("count", 0) > 0
    ) or "주변 시설 정보 없음"

    user_content = f"""
감정평가 대상: {category} / {location}
추정 시장가치: {estimated:,}만원
평당가: {ppyeong:,}만원/평 (지역 평균: {reg_ppyeong:,}만원/평)
고저평가 판정: {verdict} ({deviation:+.1f}%)
Cap Rate: {cap_rate}%
주변 환경: {nearby_text}
시장 동향: {web_summary or '정보 없음'}
"""
    try:
        response = llm.invoke([("system", APPRAISAL_PROMPT), ("human", user_content)])
        raw   = response.content.strip()
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception as e:
        print(f"[appraisal_llm] 오류: {e}")
        import traceback
        traceback.print_exc()

    return {
        "appraisal_opinion": f"{location} {category} 추정 시장가치 {estimated:,}만원. 인근 실거래 대비 {verdict} 수준.",
        "strengths":    ["실거래 데이터 기반 분석 완료"],
        "risk_factors": ["LLM 의견서 생성 실패 — 수치 기반 결과만 제공"],
        "recommendation": "관망",
    }
