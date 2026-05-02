"""
simulation_graph.py — 대출·수익률 시뮬레이션 파이프라인 (구현 예정)

입력: PropertyQuery + 대출 조건 (LTV, 금리, 기간)
출력: SimulationResult (schemas 추가 예정)

구현 계획:
  1. 감정평가 노드       — appraisal_graph 재사용 → 담보 가치 산출
  2. 대출 한도 계산 노드 — LTV × 감정가 → 최대 대출 가능액
  3. 상환 시뮬레이션 노드 — 원리금 균등 / 원금 균등 / 만기 일시
  4. 수익률 분석 노드    — price_engine.calc_investment_return() 재사용
  5. 리포트 생성 노드    — 현금 흐름표 + 손익분기점 계산
"""

from __future__ import annotations


def build_simulation_graph():
    raise NotImplementedError(
        "simulation_graph는 아직 구현되지 않았습니다. Phase 3에서 구현 예정."
    )
