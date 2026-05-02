# AppraisalAI — 부동산 감정평가 & 매물 추천 서비스

AI 기반 부동산 서비스. 자연어 입력으로 실거래가 데이터와 LLM 추론을 결합한 전문 감정평가 의견서를 생성하고, 조건 기반 매물 추천 점수를 산출한다.

---

## 빠른 시작

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. Ollama 모델 다운로드 (감정평가 기능에 필요)
ollama pull exaone3.5:7.8b
ollama pull nomic-embed-text

# 3. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력

# 4. DB 초기화 (최초 1회)
python backend/cache_db.py

# 5. 앱 실행
streamlit run frontend/app.py
```

---

## 폴더 구조

```
appraisal_evaluation/
│
├── frontend/                       Streamlit UI
│   ├── app.py                      진입점 — API 키 상태·사이드바
│   ├── pipeline.py                 Streamlit ↔ LangGraph 연결 래퍼
│   ├── history_db.py               감정평가 이력 저장소
│   ├── ui_components.py            재사용 Streamlit 컴포넌트
│   ├── map_view.py                 지도 뷰 컴포넌트
│   └── pages/
│       ├── 1_평가하기.py           자연어 입력 + 건물 검색
│       ├── 2_결과리포트.py         파이프라인 실행 + 결과 표시
│       ├── 3_대시보드.py           이력 조회 (페이지네이션·검색)
│       └── 4_매물추천.py           AI 매물 추천 UI
│
├── backend/                        비즈니스 로직 + LangGraph 파이프라인
│   ├── router.py                   공개 API — run_appraisal() / run_recommendation()
│   ├── state.py                    LangGraph 공유 상태 (AgentState)
│   ├── intent_agent.py             자연어 → PropertyIntent 구조화
│   ├── geocoding.py                지명 → 위도/경도 (카카오 API + Vworld)
│   ├── agents.py                   5개 유형별 감정평가 에이전트
│   ├── analysis_tools.py           실거래가 API · 계산 함수 · LLM 의견서
│   ├── appraisal_report.py         감정평가 마크다운 리포트 노드
│   ├── deep_analysis.py            심층 분석 노드
│   ├── rag_pipeline.py             RAG 검색 파이프라인
│   ├── price_engine.py             가격 계산 엔진
│   ├── llm_utils.py                LLM 유틸리티
│   ├── models.py                   내부 모델 정의
│   ├── cache_db.py                 SQLite 캐시 + 지역코드 룩업 (WAL 모드)
│   ├── building_info.py            건물 정보 조회
│   │
│   ├── graphs/                     LangGraph 그래프 모음
│   │   ├── appraisal_graph.py      감정평가 파이프라인 그래프
│   │   ├── recommendation_graph.py 매물 추천 파이프라인 그래프
│   │   └── simulation_graph.py     대출/수익률 시뮬레이션 (구현 예정)
│   │
│   ├── services/                   비즈니스 서비스 레이어
│   │   ├── price_analysis_service.py  PropertyQuery → AppraisalResult
│   │   └── recommendation_service.py  PropertyQuery → list[RecommendationResult]
│   │
│   └── tools/                      도구 모음
│       ├── listing_tool.py         샘플 CSV 매물 조회
│       └── scoring_tool.py         매물 종합 점수 산출
│
├── schemas/                        Pydantic 스키마 (단위: 원·㎡)
│   ├── property_query.py           검색 요청 스키마
│   ├── property_listing.py         매물 1건 스키마
│   ├── appraisal_result.py         감정평가 결과 스키마
│   └── recommendation_result.py    매물 추천 결과 스키마
│
├── data/
│   └── sample_listings.csv         개발·테스트용 가상 매물 43건
│
├── tests/                          pytest 테스트 (314개)
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_schemas.py
│   ├── test_price_engine_calc.py
│   ├── test_price_analysis_service.py
│   ├── test_listing_tool.py
│   ├── test_scoring_tool.py
│   ├── test_recommendation_service.py
│   ├── test_recommendation_graph.py
│   └── test_rec_ui_smoke.py
│
├── .env.example                    API 키 템플릿
├── .env                            실제 API 키 (Git 제외)
├── config.toml                     Streamlit 테마·서버 설정
└── requirements.txt                패키지 목록
```

---

## 파이프라인 흐름

### 감정평가 파이프라인

```
사용자 자연어 입력
  → intent_agent.py       의도 분석 (카테고리/위치/면적/호가)
  → geocoding.py          좌표 변환 (지명 → 위도/경도)
  → deep_analysis.py      심층 분석
  → appraisal_graph.py    카테고리별 에이전트 분기
  → agents.py             감정평가 계산 (추정가치/평당가/고저평가/수익률)
  → appraisal_report.py   마크다운 리포트 생성
```

### 매물 추천 파이프라인

```
PropertyQuery 입력 (지역·예산·면적·유형)
  → recommendation_graph.py   쿼리 검증
  → recommendation_service.py 후보 매물 필터링 (listing_tool)
  → scoring_tool.py           4축 점수 산출 (가격·입지·투자·위험)
  → recommendation_service.py 마크다운 리포트 생성
```

---

## 필수 API 키

| 키 이름 | 용도 | 발급처 |
|--------|------|--------|
| `KAKAO_REST_API_KEY` | 지오코딩 + 주변시설 | [developers.kakao.com](https://developers.kakao.com) |
| `MOLIT_API_KEY` | 국토부 실거래가 | [data.go.kr](https://www.data.go.kr) |
| `TAVILY_API_KEY` | 웹 시세 검색 (선택) | [tavily.com](https://tavily.com) |
| `VWORLD_API_KEY` | 토지 용도지역 (선택) | [vworld.kr](https://www.vworld.kr) |

> **카카오 403 오류** 발생 시: 개발자 콘솔 → 플랫폼 → Web → `http://localhost` 등록

> **매물 추천 기능**은 API 키 없이도 동작한다. 샘플 CSV 기반이므로 별도 키 불필요.

---

## 스키마

모든 스키마는 `schemas/` 디렉터리의 Pydantic 모델이다. **금액 단위: 원(int), 면적 단위: ㎡(float).**

| 스키마 | 핵심 필드 |
|--------|----------|
| `PropertyQuery` | `intent`, `region`, `property_type`, `area_m2`, `asking_price`, `budget_min/max`, `purpose` |
| `PropertyListing` | `listing_id`, `address`, `region`, `property_type`, `area_m2`, `asking_price`, `jeonse_price`, `station_distance_m`, `built_year` |
| `AppraisalResult` | `estimated_price`, `gap_rate`, `judgement`, `confidence`, `comparables`, `warnings` |
| `RecommendationResult` | `listing`, `appraisal`, `total_score`, `price_score`, `location_score`, `investment_score`, `risk_score`, `recommendation_label`, `reasons`, `risks` |

---

## 공개 API

### 감정평가

```python
from router import run_appraisal

result = run_appraisal("마포구 아파트 84㎡", building_name="마포래미안푸르지오")
# result["final_report"]  — 마크다운 의견서
# result["analysis_result"] — 수치 데이터 dict
```

### 매물 추천

```python
from router import run_recommendation
from schemas.property_query import PropertyQuery

query = PropertyQuery(
    intent="recommendation",
    region="마포구",
    property_type="주거용",
    budget_max=1_200_000_000,
)

state = run_recommendation(query, limit=5, run_appraisal=False)
# state["results"] — list[RecommendationResult], total_score 내림차순
# state["report"]  — 마크다운 추천 리포트
```

| 파라미터 | 기본값 | 설명 |
|----------|--------|------|
| `query` | — | PropertyQuery 객체 |
| `limit` | 5 | 반환 최대 건수 |
| `run_appraisal` | False | True 시 매물별 실거래가 API 호출 (API 키 필요) |

### 서비스 레이어 직접 호출

```python
# 가격 분석만
from services.price_analysis_service import analyze_price
appraisal = analyze_price(query)   # AppraisalResult 반환

# 추천 목록만 (그래프 없이)
from services.recommendation_service import recommend_listings, format_recommendation_report
results = recommend_listings(query, limit=5, run_appraisal=False)
report  = format_recommendation_report(results, query)

# 매물 점수만
from tools.scoring_tool import calculate_listing_score
score = calculate_listing_score(listing, query, appraisal=None)
# score["total_score"], score["recommendation_label"], score["reasons"], score["risks"]
```

---

## 매물 추천 점수 모델

### 가중치

| 축 | 가중치 | 내용 |
|----|--------|------|
| 가격 적정성 (`price_score`) | 35% | 감정평가 판정 + 신뢰도 + 예산 적합도 |
| 입지 (`location_score`) | 30% | 역세권·학교·건축연도·층수 |
| 투자 가치 (`investment_score`) | 20% | 전세가율 + gap_rate |
| 위험도 (`risk_score`) | 15% | 노후화·신뢰도·경고·고평가 (낮을수록 안전) |

```
total = price×0.35 + location×0.30 + investment×0.20 + (10 − risk)×0.15
```

### 추천 레이블

| 총점 | 레이블 |
|------|--------|
| 8.0 이상 | 적극 추천 |
| 6.5 이상 | 추천 |
| 5.0 이상 | 검토 필요 |
| 5.0 미만 | 비추천 |

---

## 감정평가 모델

| 출력물 | 산출 방식 |
|--------|----------|
| 추정 시장가치 | 인근 실거래 평균 ㎡당 단가 × 면적 (±10% 범위) |
| 평당가 분석 | ㎡당 단가 × 3.3058, 지역 평균과 비교 |
| 고/저평가 판단 | (추정가 − 인근 평균) / 인근 평균 × 100 |
| 투자 수익률 | 추정가 × Cap Rate, 유형별 기준 상이 |

### 고/저평가 판정 기준

| 괴리율 | 판정 |
|--------|------|
| −10% 이하 | 저평가 |
| −10% ~ +5% | 적정 |
| +5% ~ +15% | 소폭 고평가 |
| +15% 초과 | 고평가 |

### 유형별 Cap Rate

| 유형 | Cap Rate |
|------|----------|
| 주거용 | 3.5% |
| 상업용 | 5.0% |
| 업무용 | 4.5% |
| 산업용 | 6.0% |
| 토지 | 2.5% |

---

## 샘플 매물 데이터 고지

`data/sample_listings.csv` 파일은 **개발·테스트 전용 가상 데이터**다.

| 항목 | 내용 |
|------|------|
| 수록 지역 | 마포구·서대문구·강서구·성동구·송파구·강남구·서초구·영등포구 |
| 매물 수 | 43건 (아파트 37 + 오피스텔 3 + 상가 3) |
| 가격 단위 | 원 (`PropertyListing.asking_price`) |
| 용도 분류 | 주거용 / 상업용 |

> ⚠️ 가격·면적·좌표·단지명은 참고 목적으로 임의 생성된 값이다. 실제 거래 판단에 사용하지 마라.

---

## 테스트

```bash
# 전체 실행
pytest tests/

# 파일별
pytest tests/test_schemas.py                  # Pydantic 스키마 (15개)
pytest tests/test_models.py                   # 내부 모델 (8개)
pytest tests/test_price_engine_calc.py        # 가격 계산 엔진 (28개)
pytest tests/test_price_analysis_service.py   # 가격 분석 서비스 (37개)
pytest tests/test_listing_tool.py             # 매물 조회 도구 (46개)
pytest tests/test_scoring_tool.py             # 점수 산출 도구 (68개)
pytest tests/test_recommendation_service.py   # 추천 서비스 (47개)
pytest tests/test_recommendation_graph.py     # 추천 그래프 (38개)
pytest tests/test_rec_ui_smoke.py             # UI smoke (27개)
```

현재 **314개 테스트 전부 통과**.

---

## 단계별 실행 확인

```bash
# 백엔드 개별 모듈
python backend/intent_agent.py      # 의도 분석 출력 확인
python backend/geocoding.py         # 위도/경도 반환 확인
python backend/analysis_tools.py    # 실거래가 + 감정평가 계산 확인
python backend/agents.py            # 5개 에이전트 출력 확인
python backend/router.py            # 감정평가 end-to-end 실행

# 추천 파이프라인 확인
python -c "
from router import run_recommendation
from schemas.property_query import PropertyQuery
q = PropertyQuery(intent='recommendation', region='마포구')
s = run_recommendation(q, limit=3)
print(s['report'])
"

# UI 실행
streamlit run frontend/app.py
```
