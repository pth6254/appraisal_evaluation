# Property Concierge — 부동산 AI 시세추정 · 매물 추천 · 투자 시뮬레이션 종합 컨시어지

AI 기반 부동산 종합 분석 서비스. 자연어 입력으로 국토부 실거래가 데이터와 LLM 추론을 결합한
**AI 시세추정(AVM, Automated Valuation Model) 리포트**를 생성하고,
조건 기반 매물 추천 · 투자 수익성 시뮬레이션 · 매물 비교를 제공한다.

> ⚖️ **법적 고지**: 본 서비스의 시세추정은 자동가치산정(AVM) 기반 **참고용 분석**이며,
> 「감정평가 및 감정평가사에 관한 법률」에 따른 감정평가가 아니다.
> 담보·소송·과세 등 법적 효력이 필요한 가치 판단은 감정평가사에게 의뢰해야 한다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| 🏡 **컨시어지 홈** | 사용자 여정(매물 탐색 → 가치 분석 → 안전 점검 → 법률·세금 상담) 기반 홈 화면. 주소 검색 히어로에서 바로 시세추정으로 연결, 시세추정·권리점검·상담을 합친 최근 활동 피드 |
| 🏠 **AI 시세추정** | 자연어/단계별 입력 → 실거래 비교·수익환원·원가법 기반 추정 시세 산출, 공식 문서 형식 리포트 |
| 📊 **리포트 영속화** | 결과가 이력 DB에 저장되어 `/report/{id}` URL로 재열람·공유·인쇄(PDF) 가능 |
| ⏱ **비동기 작업 큐** | 30초~2분 걸리는 파이프라인을 job으로 실행, 단계별 진행 상황 실시간 표시 |
| ✨ **매물 추천** | **실거래 기반 단지 추천 (전국 시군구)** — 예산·면적 조건으로 실거래 데이터를 집계·점수화. 샘플 매물 모드 병행 |
| 📈 **투자 시뮬레이션** | 취득세·대출 상환·현금흐름·3개 시나리오(기준/강세/약세) 수익률 계산 |
| ⚖️ **매물 비교** | 복수 매물 점수 비교 + 우승 매물 선정 결정 리포트 |
| 🔍 **권리관계 위험 점검** | 등기부등본·건축물대장 **PDF 업로드** → 가압류·신탁·근저당 검출, 깡통전세 위험도(경매 배당 시뮬레이션), 소액임차인 최우선변제 판정 |
| 💬 **법률·세금 AI 안내** | RAG(법령·분쟁사례) + 세금 계산기 도구 호출(증여·상속·양도·보유세) 챗봇 — 수치 가드레일로 계산기 값만 인용, `tools/build_law_corpus.py`로 법령·판례 코퍼스 확장 |
| 📋 **이력 대시보드** | 사용자별 시세추정 이력 검색·통계 차트·리포트 재열람 |
| 🔐 **인증** | 이메일/비밀번호 + Google OAuth, JWT 쿠키 세션, 사용자별 이력 분리 |
| 🗄 **실거래가 로컬 스토어** | MOLIT API 응답을 SQLite에 적재 — 반복 조회 시 API 호출 없이 즉시 응답, 배치 수집 CLI 제공 |

---

## 아키텍처 개요

```
[Next.js 16 프론트엔드 :3000]
         │  HTTP (REST) · JWT 쿠키
[FastAPI 백엔드 :8000]
   ├── 작업 큐 (api/jobs.py — 인프로세스 스레드, 동시 4개)
   ├── 인증 (api/auth_db.py — SQLite)
   ├── 이력 (api/history_db.py — SQLite, 리포트 영속화)
   ├── 활동 피드 (api/activity_db.py — SQLite, 권리점검·상담 활동 기록 → 홈 통합 피드)
   │
[LangGraph 파이프라인 (backend/)]
   ├── 실거래가 로컬 스토어 (backend/transaction_store.py — SQLite)
   │        ↑ 미스 시 폴백           ↑ 배치 수집
   ├── 국토부 MOLIT API      backend/tools/ingest_transactions.py
   ├── 카카오 지오코딩 · Vworld 용도지역
   └── LLM (Ollama exaone3.5 / OpenAI / Anthropic — model_factory)
```

- **프론트엔드**: Next.js 16 (App Router, TypeScript, Tailwind v4) — 딥 그린 브랜드 디자인 토큰,
  Pretendard 가변 폰트(`next/font/local` 셀프호스팅), lucide-react 아이콘, 모바일 반응형 내비게이션
- **백엔드 API**: FastAPI (`api/`) — uvicorn 실행, 비동기 job + 동기 엔드포인트 병행
- **파이프라인**: LangGraph (`backend/`) — 시세추정·추천·시뮬레이션·비교 4개 그래프
- **저장소**: SQLite 4개 (`cache.db` 캐시·지역코드 / `auth.db` 사용자 / `history.db` 이력 / `transactions.db` 실거래가)
  + PostgreSQL·pgvector (Docker, RAG 벡터스토어)

### 시세추정 실행 흐름 (비동기 job)

```
POST /api/appraisal/jobs               → { job_id } 즉시 반환
  └─ 백그라운드: LangGraph 파이프라인 실행
GET  /api/appraisal/jobs/{job_id}      → { status, step, ... }  (프론트 2초 폴링)
  └─ 완료 시: history DB 저장 → { status: done, history_id, result }
프론트 → /report/{history_id}          → 영속 리포트 (새로고침·공유 가능)
```

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

# 2. Ollama 모델 다운로드 (시세추정 LLM 의견 생성에 필요)
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

### 실거래가 배치 수집 (선택 — 응답 속도 대폭 개선)

시세추정은 로컬 스토어를 우선 조회하고, 미스 시에만 MOLIT API를 호출한 뒤 자동 적재한다(write-through).
자주 조회하는 지역을 미리 수집해두면 API 호출 없이 즉시 응답한다.

```bash
# 서초구·강남구 주거용 최근 12개월
python backend/tools/ingest_transactions.py --regions 서초구,강남구 --months 12

# 등록된 전체 지역(수도권+광역시 약 60개), 주거용+상업용 6개월
python backend/tools/ingest_transactions.py --all --categories 주거용,상업용

# 강제 재수집 / 스토어 현황 확인
python backend/tools/ingest_transactions.py --regions 서초구 --force
python backend/transaction_store.py
```

> 공공데이터포털 개발계정은 일일 트래픽 제한(보통 1,000건)이 있다.
> 실행 전 출력되는 예상 호출 수(지역 × 엔드포인트 × 월)를 확인할 것.

**신선도(TTL) 정책**: 완결 월(기준 2개월 이전)은 30일, 최근 월(당월·전월)은 12시간 후 재수집
— 실거래 신고 기한(30일) 내 데이터 유입을 반영한다.

---

## 폴더 구조

```
property_concierge/
│
├── api/                            FastAPI 진입점 & 라우터
│   ├── main.py                     FastAPI 앱 설정, CORS, 라우터 등록
│   ├── jobs.py                     인프로세스 작업 큐 (시세추정 비동기 실행)
│   ├── auth_db.py                  사용자 인증 SQLite DB
│   ├── auth_utils.py               JWT 발급·검증
│   ├── deps.py                     인증 의존성 (get_current_user / get_optional_user)
│   ├── history_db.py               시세추정 이력 SQLite DB (리포트 영속화)
│   ├── activity_db.py              권리점검·상담 활동 SQLite DB (홈 통합 피드 데이터 소스)
│   └── routes/
│       ├── appraisal.py            POST /api/appraisal (동기) · /api/appraisal/jobs (비동기)
│       ├── auth.py                 회원가입 / 로그인 / Google OAuth / me / logout
│       ├── recommendation.py       POST /api/recommendation
│       ├── simulation.py           POST /api/simulation
│       ├── comparison.py           POST /api/comparison
│       ├── history.py              GET/DELETE /api/history, GET /api/history/{id}
│       ├── activity.py             GET /api/activity (시세추정+권리점검+상담 통합 피드)
│       ├── rights.py               POST /api/rights/analyze (등기부·건축물대장 PDF 권리 점검)
│       ├── chat.py                 POST /api/chat (법률·세금 AI 안내 챗봇)
│       └── address.py              GET /api/address/search
│
├── frontend/                       Next.js 16 (App Router, TypeScript, Tailwind v4)
│   ├── src/app/
│   │   ├── page.tsx                홈 — 컨시어지 데스크(주소 검색) + 여정 4단계 서비스 + 통합 활동 피드
│   │   ├── appraisal/page.tsx      시세추정 입력 (3단계 폼 + 진행 단계 표시)
│   │   ├── report/page.tsx         방금 실행한 결과 (sessionStorage)
│   │   ├── report/[id]/page.tsx    저장된 리포트 재열람 (영속 URL)
│   │   ├── dashboard/page.tsx      이력 대시보드 (검색·차트·리포트 링크)
│   │   ├── recommendation/page.tsx 매물 추천
│   │   ├── simulation/page.tsx     투자 시뮬레이션
│   │   ├── comparison/page.tsx     매물 비교
│   │   ├── rights/page.tsx         권리관계 위험 점검 (PDF 업로드 → 위험도 리포트)
│   │   ├── chat/page.tsx           법률·세금 AI 안내 챗봇
│   │   ├── login/ · register/      인증 페이지
│   │   ├── fonts/                  Pretendard 가변 폰트 (셀프호스팅)
│   │   └── api/auth/               Next.js API 라우트 (인증 프록시)
│   ├── src/components/
│   │   ├── AppraisalReport.tsx     시세추정 리포트 문서 렌더러 (공용, 인쇄 지원)
│   │   └── Navbar.tsx              사이드바 내비게이션 (분석/안전·상담/내 기록 그룹, 모바일 드로어)
│   └── src/lib/
│       ├── api.ts                  API 클라이언트 (job 폴링 포함)
│       ├── auth.tsx                인증 컨텍스트
│       └── types.ts                TypeScript 타입 정의
│
├── backend/                        비즈니스 로직 + LangGraph 파이프라인
│   ├── router.py                   공개 API — run_appraisal(progress_cb 지원) 외 3종
│   ├── state.py                    LangGraph 공유 상태 (AgentState)
│   ├── intent_agent.py             자연어 → PropertyIntent 구조화
│   ├── geocoding.py                지명 → 좌표 (카카오 + Vworld)
│   ├── agents.py                   5개 유형별 가치 분석 에이전트
│   ├── price_engine.py             가격 계산 엔진 (로컬 스토어 우선 → MOLIT API 폴백)
│   ├── transaction_store.py        실거래가 로컬 스토어 (SQLite, TTL 기반)
│   ├── appraisal_report.py         시세추정 마크다운 리포트 노드
│   ├── deep_analysis.py            심층 분석 노드
│   ├── rag_pipeline.py             RAG 검색 파이프라인
│   ├── chat_corpus.py              법률·세금 상담 RAG 코퍼스 (시드 청크 + 임베딩 검색, data/chat_corpus.db)
│   ├── tax_rules.py                세금·규제 법령 테이블 (증여·상속·양도·보유세, 기준일 명시)
│   ├── llm_utils.py                LLM 의견 생성 (수치 창작 금지 가드레일)
│   ├── model_factory.py            LLM 프로바이더 선택 (ollama/openai/anthropic)
│   ├── cache_db.py                 SQLite 캐시 + 지역코드 룩업
│   ├── building_info.py            건물 정보 조회
│   ├── models.py                   내부 모델 (ValuationResult)
│   │
│   ├── graphs/                     LangGraph 그래프 4종 (appraisal/recommendation/simulation/comparison)
│   ├── services/
│   │   ├── chat_service.py             법률·세금 챗봇 서비스 (RAG 검색 + 세금 계산기 도구 라우팅)
│   │   └── rights_analysis_service.py  권리관계 위험 점검 서비스 (등기부·건축물대장 파싱·위험도 산정)
│   └── tools/
│       ├── ingest_transactions.py  실거래가 배치 수집 CLI
│       ├── build_law_corpus.py     국가법령정보센터 법령·판례 수집 → chat_corpus 확장
│       ├── listing_tool.py         샘플 CSV 매물 조회
│       ├── scoring_tool.py         매물 종합 점수 산출
│       └── simulation_tool.py      시뮬레이션 계산
│
├── schemas/                        Pydantic 스키마 (단위: 원·㎡)
├── data/
│   ├── sample_listings.csv         개발·테스트용 가상 매물 43건
│   ├── transactions.db             실거래가 로컬 스토어 (자동 생성, Git 제외)
│   ├── auth.db · history.db        사용자·이력·활동 DB (자동 생성, Git 제외)
│   ├── chat_corpus.db              법률·세금 상담 RAG 코퍼스 (자동 생성, Git 제외)
│   └── ...
├── tests/                          pytest 테스트 (18개 파일 — test_rights_and_chat.py 포함)
├── docker/init.sql                 PostgreSQL 초기화 스크립트
├── Dockerfile.backend / .frontend  서비스 이미지
├── docker-compose.yml              pgvector + api + frontend
└── requirements.txt
```

---

## REST API 엔드포인트

| 메서드 | 경로 | 설명 |
|--------|------|------|
| `GET` | `/health` | 헬스체크 |
| `POST` | `/api/appraisal` | 시세추정 실행 (동기, 하위 호환) |
| `POST` | `/api/appraisal/jobs` | 시세추정 작업 생성 → `{job_id}` |
| `GET` | `/api/appraisal/jobs/{id}` | 작업 상태 폴링 → `{status, step, history_id?, result?}` |
| `POST` | `/api/auth/register` | 회원가입 (이메일/비밀번호) |
| `POST` | `/api/auth/login` | 로그인 → JWT 쿠키 |
| `GET` | `/api/auth/google` → `/callback` | Google OAuth |
| `GET` | `/api/auth/me` | 현재 사용자 조회 |
| `POST` | `/api/auth/logout` | 로그아웃 |
| `POST` | `/api/recommendation` | 샘플 매물 추천 실행 |
| `POST` | `/api/recommendation/complexes` | **실거래 기반 단지 추천 (전국)** |
| `POST` | `/api/simulation` | 투자 시뮬레이션 실행 (세후·DSR·민감도 포함) |
| `GET` | `/api/simulation/market-rate` | 최신 주담대 평균금리 (한국은행 ECOS) |
| `POST` | `/api/comparison` | 매물 비교 실행 |
| `GET` | `/api/history` | 시세추정 이력 목록 (사용자별) |
| `GET` | `/api/history/{id}` | 저장된 리포트 1건 (영속 리포트 데이터 소스) |
| `DELETE` | `/api/history/{id}` | 이력 삭제 |
| `GET` | `/api/activity` | 시세추정·권리점검·상담을 합친 홈 최근 활동 피드 (사용자별) |
| `GET` | `/api/address/search` | 주소 검색 (카카오 API) |
| `POST` | `/api/rights/analyze` | 등기부·건축물대장 PDF 권리 위험 점검 (base64) |
| `POST` | `/api/chat` | 법률·세금 AI 정보 안내 챗봇 |

> 전체 API 명세: `http://localhost:8000/docs` (Swagger UI)

---

## 파이프라인 흐름

### 시세추정 파이프라인 (LangGraph)

```
사용자 자연어 입력
  → intent_agent.py       의도 분석 (카테고리/위치/면적/호가/기준시점)
  → 검증                   필수 정보 확인 (미비 시 오류처리)
  → geocoding.py          좌표 변환 + 용도지역·공시지가
  → deep_analysis.py      심층 분석 (실거래 + RAG)
  │     └─ price_engine.py: transaction_store 조회 → 미스 시 MOLIT API → write-through 적재
  → 라우터                 카테고리별 에이전트 분기
  → agents.py             유형별 가치 분석 (주거/상업/업무/산업/토지)
  │     └─ llm_utils.py: LLM 분석 의견 생성 (계산 수치만 인용, 재생성 금지)
  → appraisal_report.py   마크다운 리포트 + 구조화 결과 (AppraisalReport)
```

각 노드 완료 시 `progress_cb`가 호출되어 job의 `step`이 갱신되고,
프론트엔드가 5단계(요청 분석 → 주소 확인 → 실거래 수집 → AI 분석 → 리포트 생성)로 표시한다.

### 매물 추천 파이프라인

```
PropertyQuery (지역·예산·면적·유형)
  → 쿼리 검증 → 후보 필터링 (listing_tool, 샘플 CSV)
  → scoring_tool.py 4축 점수 (가격 35% · 입지 30% · 투자 20% · 위험 15%)
  → 마크다운 추천 리포트
```

### 시뮬레이션 · 비교 파이프라인

```
시뮬레이션: dict | SimulationInput | listing+overrides
  → 입력 정규화 → 취득세·대출·현금흐름·시나리오 계산 → 리포트

비교: listings (+recs/sims)
  → 입력 정규화 → 점수 산출·우승자 선정 → 결정 리포트
```

---

## 필수 API 키

| 키 이름 | 용도 | 발급처 |
|--------|------|--------|
| `KAKAO_REST_API_KEY` | 지오코딩 + 주변시설 | [developers.kakao.com](https://developers.kakao.com) |
| `MOLIT_API_KEY` | 국토부 실거래가 | [data.go.kr](https://www.data.go.kr) |
| `RBONE_API_KEY` (또는 `REB_API_KEY`) | 부동산원 R-ONE 월간지수 — 시점수정 정밀화 (선택) | [reb.or.kr/r-one](https://www.reb.or.kr/r-one/portal/openapi/openApiIntroPage.do) |
| `ECOS_API_KEY` | 한국은행 금리 — 시뮬레이션 금리 자동 세팅 (선택, 없으면 sample 키 시도) | [ecos.bok.or.kr](https://ecos.bok.or.kr) |
| `LAW_OC_KEY` | 국가법령정보 — 챗봇 코퍼스 확장용 법령·판례 수집 (선택, 시드 코퍼스만으로도 동작) | [open.law.go.kr](https://open.law.go.kr) |
| `TAVILY_API_KEY` | 웹 시세 검색 (선택) | [tavily.com](https://tavily.com) |
| `VWORLD_API_KEY` | 토지 용도지역 (선택) | [vworld.kr](https://www.vworld.kr) |
| `GOOGLE_CLIENT_ID/SECRET` | Google OAuth (선택) | [console.cloud.google.com](https://console.cloud.google.com) |
| `JWT_SECRET_KEY` | 세션 토큰 서명 (미설정 시 개발용 기본값) | 임의 문자열 |

LLM 프로바이더 (`model_factory.py`):

| 환경변수 | 기본값 |
|---------|--------|
| `LLM_PROVIDER` | `ollama` (`openai` / `anthropic` / `google` 지원) |
| `OLLAMA_MODEL` | `exaone3.5:7.8b` |
| `OPENAI_MODEL` / `ANTHROPIC_MODEL` | 프로바이더 전환 시 |

> **카카오 403 오류** 발생 시: 개발자 콘솔 → 플랫폼 → Web → `http://localhost` 등록

---

## 스키마

모든 스키마는 `schemas/` 디렉터리의 Pydantic 모델. **금액 단위: 원(int), 면적 단위: ㎡(float).**
(단, `backend/models.py`의 `ValuationResult`는 만원 단위 — 리포트 생성 시 변환)

| 스키마 | 핵심 필드 |
|--------|----------|
| `PropertyQuery` | `intent`, `region`, `property_type`, `area_m2`, `budget_min/max`, `purpose` |
| `PropertyListing` | `listing_id`, `address`, `property_type`, `area_m2`, `asking_price`, `deposit_price`, `station_distance_m`, `built_year` |
| `AppraisalResult` | `estimated_price`, `low/high_price`, `confidence`, `appraisal_date`, `land_use_zone`, `official_land_price`, `exclusive_area_m2`, `valuation_breakdown`, `comparables`, `legal_restrictions`, `warnings` |
| `ComparableTransaction` | 시점수정(`time_adj_factor`)·지역/개별요인 보정 포함 비교사례 |
| `RecommendationResult` | `listing`, `total_score`, 4축 점수, `recommendation_label`, `reasons`, `risks` |
| `SimulationResult` | `acquisition_cost`, `loan`, `cash_flow`, `scenario_base/bull/bear` |
| `ComparisonResult` | `rows`, `decision_report` |

---

## 공개 API (Python)

### 시세추정

```python
from backend.router import run_appraisal

result = run_appraisal("마포구 아파트 84㎡", building_name="마포래미안푸르지오")
# result["final_report"]              — 마크다운 리포트
# result["analysis_result"]           — 수치 데이터 dict
# result["report_output"].structured  — AppraisalResult (구조화)

# 진행 콜백 (노드 완료마다 호출 — job 큐가 사용)
result = run_appraisal("서초구 아파트 59㎡", progress_cb=lambda node: print(node))
```

### 매물 추천 / 시뮬레이션 / 비교

```python
from backend.router import run_recommendation, run_simulation, run_comparison
from schemas.property_query import PropertyQuery
from schemas.simulation import SimulationInput

state = run_recommendation(PropertyQuery(region="마포구", budget_max=1_200_000_000), limit=5)
# state["results"] — total_score 내림차순

state = run_simulation(data=SimulationInput(
    purchase_price=1_000_000_000, loan_amount=500_000_000,
    annual_interest_rate=4.0, holding_years=3, rent_fee=2_000_000, owned_homes=1,
))
# state["result"].scenario_base.annual_equity_roi — 연환산 수익률 (%)

state = run_comparison(listings=[...])
# state["result"].rows[0] — 우승 매물
```

---

## 시세추정 모델

| 출력물 | 산출 방식 |
|--------|----------|
| 추정 시장가치 | 인근 실거래 평균 ㎡당 단가 × 면적 (±10% 범위) |
| 시점수정 | **부동산원 월간 매매가격지수** (`RBONE_API_KEY` 설정 시, 시군구 단위) → 미공표·미지원 시 유형별 근사 변동률 폴백 |
| 실거래 폴백 | 실거래 없을 시 공시가격 ÷ 현실화율 역산 (주거용) |
| 고/저평가 판단 | (추정가 − 인근 평균) / 인근 평균 × 100 |
| 투자 수익률 | 추정가 × 유형별 Cap Rate |
| 신뢰도 | **다요인 모델 + 백테스트 보정** (`confidence.py`) — 매칭수준·표본수·산포(CV)·신선도·시점수정 방식 기반점에, 백테스트 실측 적중률(`data/avm_calibration.json`)을 버킷별로 블렌딩. 정의: "유사 조건에서 추정치가 실거래가 ±10% 이내에 들 확률" |
| AI 분석 의견 | LLM 생성 + **수치 가드레일** (`opinion_guard.py`) — 컨텍스트로 주입한 수치 외의 숫자가 든 문장은 자동 삭제, 위반 시 1회 재시도 후 결정론적 폴백. 출력은 프로바이더 무관 OpinionOutput 스키마로 강제 |

### 시점수정 상세 (부동산원 지수 기반)

`backend/reb_index.py` — R-ONE OpenAPI `SttsApiTblData` 사용, 통계표 `A_2024_00045` (월간 아파트 매매가격지수, 시군구 단위).

```
시점수정 계수 = 기준시점 월 지수 / 거래 월 지수
```

- **지역 매칭**: 시군구 정확 매칭 (동명이구는 시도로 판별) → 시도 → 전국 순 폴백
- **공표 시차 처리**: 지수는 익월 중순 공표 — 기준시점 월이 미공표면 최근 공표월까지 지수로 보정하고, 잔여 월수는 근사 변동률로 이어서 보정
- **캐싱**: 월별 전 지역 지수를 `cache.db`에 캐시 (완결 월 30일 / 최근 월 24시간)
- **동작 확인**: `python backend/reb_index.py 서초구` — 키 상태·지수 조회·계수 산출 진단
- 통계표 교체: env `REB_STATBL_RESIDENTIAL` (주거용), `REB_STATBL_LAND` (토지)

### 비교사례 매칭 전략 (단계적 확장)

```
1) 단지명 정확/공백제거/부분 매칭 (3 → 6 → 12개월)
2) 동 필터링 (3 → 6개월)
3) 구 전체 (3 → 6개월)
4) 공시가격 역산 폴백 (주거용 한정)
```

### 백테스트 (AVM 정확도 실측)

`backend/tools/backtest_avm.py` — 대상 월 거래를 이전 데이터만으로 추정(홀드아웃)해
실거래가와 비교하고, 버킷(매칭수준×표본수)별 적중률을 신뢰도 보정테이블로 저장한다.

```bash
python backend/tools/ingest_transactions.py --regions 서초구 --months 12 --yes
python backend/tools/backtest_avm.py --regions 서초구 --target-months 3
# → data/avm_calibration.json 생성 → confidence.py 가 자동 반영
```

서초구 434건 실측 예시: 동일단지 매칭은 ±10% 적중률 69~84%로 양호하지만,
동일동/구 매칭은 8~33%에 불과 — 휴리스틱만으로는 과대평가되던 신뢰도가
실측 기반으로 하향 보정된다.

### 유형별 Cap Rate

| 주거용 | 상업용 | 업무용 | 산업용 | 토지 |
|-------|-------|-------|-------|------|
| 3.5% | 5.0% | 4.5% | 6.0% | 2.5% |

---

## 투자 시뮬레이션 모델

순수 계산 엔진 (`simulation_tool.py`) + 법령 규칙 테이블 (`tax_rules.py`, 기준일 명시) + 한국은행 금리 (`bok_rates.py`).

```
SimulationResult
├── acquisition_cost   취득세 + 중개보수 + 기타 비용
├── required_cash / equity / loan / cash_flow
├── scenario_base/bull/bear   성장률 ±spread — 세후 순손익
│     └── 세전 순손익 − 양도소득세 − 보유세(재산세+종부세) − 매도 중개보수
├── finance_check      LTV·스트레스 DSR 검증 (연소득 입력 시)
├── breakeven_growth_rate   세후 손익분기 연 상승률 (이분탐색)
└── rate_sensitivity   금리(±1%p) × 상승률(±spread) 3×3 민감도
```

### 세금·규제 규칙 (`tax_rules.py` — 세법 기준일 명시, 골든 테스트로 개정 감지)

| 항목 | 규칙 | 데이터 |
|------|------|--------|
| 양도소득세 | 1주택 12억 비과세·고가 안분·장특공(최대 80%)·단기 70/60%·누진 6~45%·지방세 10% | 법령 테이블 |
| 보유세 | 재산세(공정시장가액비율·1주택 특례세율) + 종부세(공제 12억/9억) — 연도별 합산 | 공시가격 (입력 or 시세×현실화율 추정) |
| 취득세 | 1주택 1.1~3.3% / 2주택 8% / 3주택+ 12% / 비주거 4.4% | 법령 테이블 |
| DSR | 스트레스 금리(+1.5%p) 원리금균등 환산, 한도 40%, 가능 대출액 역산 | 연소득 (사용자 입력) |
| LTV | 무주택·1주택 70% / 다주택 60% / 조정지역 50%·30% | 규정 테이블 |
| 공실률 | 월세 수입 × (1 − 공실률), 기본 5% | 사용자 입력 |
| 금리 기본값 | 예금은행 주담대 가중평균금리 (월별, 24h 캐시) | **한국은행 ECOS** (`ECOS_API_KEY`, 없으면 4.0% 폴백) |

> ⚠️ 간이 계산 — 감면 특례·1세대 판정 등 개별 사정 미반영. 실제 세액은 세무사 상담 필요.
> 무자본 갭투자(실투자금 ≤ 0)는 수익률 대신 "무한 레버리지"로 표시하고 역전세 리스크를 경고한다.

---

## 매물 추천 점수 모델

```
total = 가격적정성×0.35 + 입지×0.30 + 투자가치×0.20 + (10 − 위험도)×0.15
```

| 총점 | 8.0+ | 6.5+ | 5.0+ | 5.0 미만 |
|------|------|------|------|---------|
| 레이블 | 적극 추천 | 추천 | 검토 필요 | 비추천 |

### ⚠️ 샘플 매물 데이터 고지

추천·비교·시뮬레이션의 매물 데이터(`data/sample_listings.csv`)는 **개발·테스트 전용 가상 데이터**
(서울 8개 구 43건)다. 가격·좌표·단지명은 임의 생성 값이며 실제 거래 판단에 사용할 수 없다.
반면 **시세추정은 국토부 실거래가 실데이터**를 사용한다.

---

## 테스트

```bash
pytest tests/                              # 전체 실행

# 주요 파일
pytest tests/test_price_engine_calc.py    # 가격 계산
pytest tests/test_transaction_store.py    # 실거래가 로컬 스토어 (TTL·멱등·동시성)
pytest tests/test_simulation_service.py   # 시뮬레이션
pytest tests/test_comparison_service.py   # 비교
pytest tests/test_rights_and_chat.py      # 권리관계 위험 점검 · 법률·세금 챗봇
```

---

## 알려진 제약

- **작업 큐**는 인프로세스 메모리 기반 — 멀티 워커(uvicorn `--workers N`) 배포 시 Redis 등 외부 저장소로 교체 필요 (현재 docker-compose는 단일 워커)
- **시점수정**은 주거용·토지만 부동산원 지수 적용 — 상업·업무·산업용은 적합한 월간 시군구 지수가 없어 근사 변동률 사용. 주거용은 아파트 지수를 연립·단독에도 대표 적용
- **시세추정·단지 추천은 전국 시군구 지원** — 지오코딩 시군구코드 직접 사용 + 전국 250개 지역코드 시드(`tools/seed_region_codes.py`) + 지오코딩 자동 등록
- **단지 추천**은 실거래 기반 추정 시세 — 실제 매물 존재 여부·호가는 미포함 (호가 매물은 데이터 제휴 필요). 샘플 매물 모드는 개발용 가상 데이터 유지
- SQLite WAL 모드는 WSL `/mnt/c` 등 일부 파일시스템에서 미지원 — 자동으로 기본 저널 모드로 폴백함
