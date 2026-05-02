"""
recommendation_graph.py — 매물 추천 파이프라인 (구현 예정)

입력: PropertyQuery (schemas/property_query.py)
출력: list[RecommendationResult] (schemas/recommendation_result.py)

구현 계획:
  1. 조건 파싱 노드   — PropertyQuery → 필터 조건 추출
  2. 매물 수집 노드   — price_engine.fetch_real_transaction_prices() 재사용
  3. 감정평가 노드    — appraisal_graph의 가격 분석 엔진 재사용
  4. 스코어링 노드    — 가격 적정성·입지·투자수익 점수 계산
  5. 정렬·반환 노드   — RecommendationResult 리스트 반환
"""

from __future__ import annotations


def build_recommendation_graph():
    raise NotImplementedError(
        "recommendation_graph는 아직 구현되지 않았습니다. Phase 3에서 구현 예정."
    )
