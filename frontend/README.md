# DeepAgent — Streamlit 프론트엔드

## 파일 구조

```
deepagent/
│
├── app.py                  # 진입점 · 사이드바 · 홈 화면
├── pipeline.py             # LangGraph 래퍼 (← 여기에 기존 코드 연결)
├── history_db.py           # SQLite 이력 저장/조회
├── ui_components.py        # 공용 UI 컴포넌트
├── requirements.txt
│
├── pages/
│   ├── 1_평가하기.py        # 자연어 입력 화면
│   ├── 2_결과리포트.py      # 로딩 → 감정평가 결과
│   └── 3_대시보드.py        # 이력 조회 · 차트 · 필터
│
└── .streamlit/
    └── config.toml         # 테마 · 서버 설정
```

## 설치 및 실행

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. 실행
streamlit run app.py
# → http://localhost:8501
```

## 기존 LangGraph 코드 연결

`pipeline.py` 상단의 주석 처리된 부분을 실제 코드로 교체합니다.

```python
# pipeline.py

# ── 주석 해제 ──────────────────────────────────────────────────
from router import graph          # 기존 LangGraph StateGraph

def _invoke(user_input: str) -> dict:
    state = graph.invoke({"user_input": user_input})
    return state.get("analysis_result", {})
# ──────────────────────────────────────────────────────────────
```

`analysis_result` 키 이름이 다르면 실제 키에 맞게 수정하세요.

## ValuationResult 필드 매핑

`ui_components.py` 가 기대하는 딕셔너리 키:

| 키 | 타입 | 설명 |
|---|---|---|
| `estimated_value` | int | 추정 시장가치 (만원) |
| `value_min` | int | 범위 하한 (만원) |
| `value_max` | int | 범위 상한 (만원) |
| `price_per_pyeong` | int | 평당가 (만원) |
| `regional_avg_per_pyeong` | int | 지역 평균 평당가 (만원) |
| `valuation_verdict` | str | 저평가 / 적정 / 소폭 고평가 / 고평가 |
| `deviation_pct` | float | 괴리율 (%) |
| `comparable_avg` | int | 비교사례 평균가 (만원) |
| `comparable_count` | int | 비교사례 건수 |
| `cap_rate` | float | Cap Rate (%) |
| `annual_income` | int | 연 임대수입 추정 (만원) |
| `five_year_return` | float | 5년 수익률 추정 (%) |
| `investment_grade` | str | A / B / C / D |
| `appraisal_opinion` | str | LLM 의견서 (3~4문장) |
| `strengths` | list[str] | 가치 상승 요인 3개 |
| `risk_factors` | list[str] | 리스크 요인 2개 |
| `recommendation` | str | 매수 적극 고려 / 매수 고려 / 관망 / 매수 비추천 |
| `category` | str | 주거용 / 상업용 / 업무용 / 산업용 / 토지 |
| `area_m2` | float | 면적 (㎡) |
