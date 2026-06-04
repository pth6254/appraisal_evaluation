# Property Concierge — 부동산 감정평가 & 매물 추천 & 투자 시뮬레이션 진행하는 부동산 종합 컨시어지 서비스

AI 기반 부동산 서비스. 자연어 입력으로 실거래가 데이터와 LLM 추론을 결합한 전문 감정평가 의견서를 생성하고, 조건 기반 매물 추천 점수를 산출한다.

---

## 아키텍처 개요

```
[Next.js 프론트엔드 :3000]
         │  HTTP (REST)
[FastAPI 백엔드 :8000]  ←→  [PostgreSQL + pgvector :5432]
         │
[LangGraph 파이프라인 (backend/)]
```

- **프론트엔드**: Next.js 14 (App Router, TypeScript)
- **백엔드 API**: FastAPI (`api/`) — uvicorn으로 실행
- **파이프라인**: LangGraph (`backend/`) — 감정평가·추천·시뮬레이션·비교
- **DB**: PostgreSQL + pgvector (Docker), SQLite (히스토리 캐시)

---

## 빠른 시작 (Docker Compose)

```bash
# 1. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력

# 2. 전체 서비스 실행 (백엔드 + 프론트엔드 + DB)
docker compose up --build

# 서비스 주소
# 프론트엔드: http://localhost:3000
# 백엔드 API: http://localhost:8000
# API 문서:   http://localhost:8000/docs
```

### 로컬 개발 (Docker 없이)

```bash
# 1. Python 패키지 설치
pip install -r requirements.txt

# 2. Ollama 모델 다운로드 (감정평가 기능에 필요)
ollama pull exaone3.5:7.8b
ollama pull nomic-embed-text

# 3. FastAPI 백엔드 실행
uvicorn api.main:app --reload --port 8000

# 4. Next.js 프론트엔드 실행 (별도 터미널)
cd frontend
npm install
npm run dev
# http://localhost:3000
```

---

## 폴더 구조

```
property_concierge/
│
├── api/                            FastAPI 진입점 & 라우터
│   ├── main.py                     FastAPI 앱 설정, CORS, 라우터 등록
│   ├── history_db.py               히스토리 SQLite DB 관리
│   └── routes/
│       ├── appraisal.py            POST /api/appraisal
│       ├── recommendation.py       POST /api/recommendation
│       ├── simulation.py           POST /api/simulation
│       ├── comparison.py           POST /api/comparison
│       ├── history.py              GET/DELETE /api/history
│       └── address.py              GET /api/address/search
│
├── frontend/                       Next.js 14 (App Router, TypeScript)
│   ├── src/app/
│   │   ├── appraisal/page.tsx      감정평가 입력 페이지
│   │   ├── report/page.tsx         감정평가 결과 리포트 페이지
│   │   ├── recommendation/page.tsx 매물 추천 페이지
│   │   ├── simulation/page.tsx     투자 시뮬레이션 페이지
│   │   ├── comparison/page.tsx     매물 비교 페이지
│   │   └── dashboard/page.tsx      이력 대시보드 페이지
│   ├── src/components/
│   │   └── Navbar.tsx              공통 내비게이션 바
│   └── src/lib/
│       ├── api.ts                  API 요청 유틸리티 함수
│       └── types.ts                TypeScript 타입 정의
│
├── backend/                        비즈니스 로직 + LangGraph 파이프라인
│   ├── router.py                   공개 API — run_appraisal() / run_recommendation() / run_simulation() / run_comparison()
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
│   │   ├── simulation_graph.py     투자 시뮬레이션 파이프라인 그래프
│   │   └── comparison_graph.py     매물 비교 파이프라인 그래프
│   │
│   ├── services/                   비즈니스 서비스 레이어
│   │   ├── price_analysis_service.py  PropertyQuery → AppraisalResult
│   │   ├── recommendation_service.py  PropertyQuery → list[RecommendationResult]
│   │   ├── simulation_service.py      SimulationInput → SimulationResult + 마크다운 리포트
│   │   └── comparison_service.py      list[PropertyListing] → ComparisonResult + 결정 리포트
│   │
│   └── tools/                      도구 모음
│       ├── listing_tool.py         샘플 CSV 매물 조회
│       └── scoring_tool.py         매물 종합 점수 산출
│
├── schemas/                        Pydantic 스키마 (단위: 원·㎡)
│   ├── property_query.py           검색 요청 스키마
│   ├── property_listing.py         매물 1건 스키마
│   ├── appraisal_result.py         감정평가 결과 스키마
│   ├── recommendation_result.py    매물 추천 결과 스키마
│   ├── simulation.py               투자 시뮬레이션 입출력 스키마
│   └── comparison.py               매물 비교 입출력 스키마
│
├── data/
│   └── sample_listings.csv         개발·테스트용 가상 매물 43건
│
├── tests/                          pytest 테스트
│   ├── conftest.py
│   ├── test_models.py
│   ├── test_schemas.py
│   ├── test_price_engine_calc.py
│   ├── test_price_analysis_service.py
│   ├── test_listing_tool.py
│   ├── test_scoring_tool.py
│   ├── test_recommendation_service.py
│   ├── test_recommendation_graph.py
│   ├── test_rec_ui_smoke.py
│   ├── test_simulation_tool.py
│   ├── test_simulation_service.py
│   ├── test_simulation_graph.py
│   ├── test_sim_ui_smoke.py
│   ├── test_comparison_service.py
│   └── test_comparison_ui_smoke.py
│
├── docker/
│   └── init.sql                    PostgreSQL 초기화 스크립트
├── Dockerfile.backend              FastAPI 백엔드 이미지 (python:3.11-slim)
├── Dockerfile.frontend             Next.js 프론트엔드 이미지 (node:22-alpine, 멀티스테이지)
├── docker-compose.yml              pgvector + api + frontend 3서비스 구성
├── .dockerignore                   Docker 빌드 제외 목록
├── .env.example                    API 키 템플릿
├── .env                            실제 API 키 (Git 제외)
└── requirements.txt                Python 패키지 목록
```

---

## Docker Compose 서비스 구성

| 서비스 | 이미지 | 포트 | 설명 |
|--------|--------|------|------|
| `pgvector` | `ankane/pgvector:latest` | 5432 | PostgreSQL + pgvector 익스텐션 |
| `api` | `property_concierge_backend:latest` | 8000 | FastAPI 백엔드 (Dockerfile.backend) |
| `frontend` | `property_concierge_frontend:latest` | 3000 | Next.js 프론트엔드 (Dockerfile.frontend) |

- `api` 서비스는 `pgvector` 헬스체크 통과 후 시작
- `frontend` 서비스는 `api` 헬스체크 통과 후 시작
- 환경변수 `NEXT_PUBLIC_API_URL=http://api:8000` 으로 프론트↔백엔드 연결

---

## REST API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/health` | 헬스체크 |
| `POST` | `/api/appraisal` | 감정평가 실행 |
| `POST` | `/api/recommendation` | 매물 추천 실행 |
| `POST` | `/api/simulation` | 투자 시뮬레이션 실행 |
| `POST` | `/api/comparison` | 매물 비교 실행 |
| `GET` | `/api/history` | 감정평가 이력 조회 |
| `DELETE` | `/api/history/{id}` | 이력 삭제 |
| `GET` | `/api/address/search` | 주소 검색 (카카오 API) |

> 전체 API 명세: `http://localhost:8000/docs` (Swagger UI)

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

### 시뮬레이션 파이프라인

```
입력 (세 방식 중 하나):
  A. dict (raw_input)
  B. SimulationInput 객체
  C. PropertyListing + overrides dict

  → simulation_graph.py   입력준비 — 세 방식을 SimulationInput으로 정규화
  → simulation_tool.py    시뮬레이션실행 — 취득세·대출·현금흐름·시나리오 계산
  → simulation_service.py 리포트생성 — 마크다운 리포트 생성
```

### 비교 파이프라인

```
입력 (두 방식 중 하나):
  A. dict (raw_input)          → ComparisonInput 변환
  B. ComparisonInput 객체      → 그대로 사용

  → comparison_graph.py   입력정규화 — listings + optional recs/sims
  → comparison_service.py 비교실행  — 점수 산출, 우승자 선정, 지표 계산
  → comparison_service.py 리포트생성 — 마크다운 결정 리포트
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
| `PropertyListing` | `listing_id`, `address`, `region`, `property_type`, `area_m2`, `asking_price`, `deposit_price`, `monthly_rent_income`, `station_distance_m`, `built_year` |
| `AppraisalResult` | `estimated_price`, `gap_rate`, `judgement`, `confidence`, `comparables`, `warnings` |
| `RecommendationResult` | `listing`, `appraisal`, `total_score`, `price_score`, `location_score`, `investment_score`, `risk_score`, `recommendation_label`, `reasons`, `risks` |
| `ComparisonInput` | `listings`, `recommendation_results`, `simulation_results`, `budget_max` |
| `ComparisonResult` | `rows` (list[PropertyComparisonRow]), `winner_idx`, `decision_report` |

### PropertyListing 필드 변경 (2026-06-01)

| 이전 필드명 | 변경 후 | 설명 |
|------------|---------|------|
| `jeonse_price` | `deposit_price` | 임대 보증금 (원) |

### SimulationInput 필드 변경 (2026-06-01)

| 이전 필드명 | 변경 후 | 설명 |
|------------|---------|------|
| `jeonse_deposit` | `rent_deposit` | 전세 보증금 (원) |
| `monthly_rent` | `rent_fee` | 월세 (원) |

---

## 공개 API (Python)

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

### 투자 시뮬레이션

```python
from router import run_simulation
from schemas.simulation import SimulationInput

# 방식 A: dict 입력
state = run_simulation(data={"purchase_price": 500_000_000, "loan_amount": 250_000_000})

# 방식 B: SimulationInput 객체
inp   = SimulationInput(
    purchase_price=1_000_000_000,
    loan_amount=500_000_000,
    annual_interest_rate=4.0,
    loan_years=30,
    holding_years=3,
    expected_annual_growth_rate=3.0,
    rent_fee=2_000_000,       # 월세 200만원 (구: monthly_rent)
    owned_homes=1,            # 보유 주택 수 (취득세 중과 산정)
)
state = run_simulation(data=inp)

# 방식 C: 매물 + overrides
state = run_simulation(listing=listing, overrides={"loan_ratio": 0.6, "holding_years": 5})

print(state["result"].scenario_base.annual_equity_roi)  # 연환산 수익률 (%)
print(state["report"])                                   # 마크다운 리포트
```

### 매물 비교

```python
from router import run_comparison
from schemas.property_listing import PropertyListing

listings = [
    PropertyListing(listing_id="L1", address="서울 마포구 1", property_type="주거용", asking_price=500_000_000),
    PropertyListing(listing_id="L2", address="서울 서대문구 1", property_type="주거용", asking_price=600_000_000),
]

state = run_comparison(listings=listings)
print(state["result"].rows[0].listing.complex_name)  # 최종 추천 매물명
print(state["report"])                               # 마크다운 결정 리포트
```

---

## 투자 시뮬레이션 모델

`schemas/simulation.py` + `backend/tools/simulation_tool.py` + `backend/services/simulation_service.py`

외부 API 호출 없는 순수 계산 엔진.

### SimulationInput 주요 필드

| 필드 | 기본값 | 설명 |
|------|--------|------|
| `purchase_price` | — | 매수가 (원) |
| `loan_amount` | 0 | 대출금 (원) |
| `annual_interest_rate` | 4.0 | 연이율 (%) |
| `loan_years` | 30 | 대출 기간 (년) |
| `repayment_type` | `equal_payment` | 원리금균등 / 원금균등 / 만기일시 |
| `holding_years` | 3 | 보유 기간 (년) |
| `expected_annual_growth_rate` | 0.0 | 연간 예상 상승률 (%) |
| `rent_deposit` | None | 전세 보증금 (원) — `rent_fee`와 동시 입력 불가 |
| `rent_fee` | None | 월세 (원) |
| `monthly_management_fee` | None | 월 관리비 (원) |
| `property_type` | `아파트` | 매물 유형 (취득세율 결정) |
| `owned_homes` | 1 | 현재 보유 주택 수 (취득 전 기준, 취득세 중과 산정용) |
| `scenario_spread` | 5.0 | 강세/약세 시나리오 편차 (%p) |
| `jeonse_opportunity_rate` | 3.5 | 전세 보증금 기회수익률 (%) |

### SimulationResult 구조

```
SimulationResult
├── acquisition_cost   취득세 + 중개보수 + 기타 비용 합계
├── required_cash      필요 현금 = 매수가 − 대출 + 취득비용
├── equity             실투자금 = 필요 현금 − 전세 보증금
├── loan               월 상환액 / 총 이자 / 총 상환액
├── cash_flow          월 임대수입 − 월 상환 − 관리비 = 순 현금흐름
├── scenario_base      입력 성장률 기준 수익성
├── scenario_bull      성장률 +scenario_spread %p
└── scenario_bear      성장률 −scenario_spread %p

각 ScenarioResult:
  expected_sale_price, capital_gain, total_rental_income,
  net_profit, equity_roi (%), annual_equity_roi (%), rental_yield (%)
```

### 취득세 간이 세율 (주거용, 취득세 + 지방교육세)

| 매수가 구간 | 1주택 | 다주택 (owned_homes ≥ 2) |
|------------|-------|--------------------------|
| 6억 이하 | 1.1% | 중과 적용 |
| 6억 초과 ~ 9억 이하 | 2.2% | 중과 적용 |
| 9억 초과 | 3.3% | 중과 적용 |
| 상업용·업무용·산업용·토지 | 4.4% | 4.4% |

> ⚠️ 간이 계산 — 실제 세율은 보유 주택 수·취득 시점·조정대상지역 여부에 따라 달라집니다.

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
pytest tests/test_schemas.py
pytest tests/test_models.py
pytest tests/test_price_engine_calc.py
pytest tests/test_price_analysis_service.py
pytest tests/test_listing_tool.py
pytest tests/test_scoring_tool.py
pytest tests/test_recommendation_service.py
pytest tests/test_recommendation_graph.py
pytest tests/test_simulation_tool.py
pytest tests/test_simulation_service.py
pytest tests/test_comparison_service.py
```
