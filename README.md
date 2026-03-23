# AppraisoAI — 부동산 감정평가 서비스 

AI 기반 부동산 감정평가 서비스. 자연어 입력으로 실거래가 데이터와 LLM 추론을 결합한 전문 감정평가 의견서를 생성합니다.

---

## 빠른 시작

```bash
# 1. 패키지 설치
pip install -r requirements.txt

# 2. Ollama 모델 다운로드
ollama pull exaone3.5:7.8b
ollama pull nomic-embed-text

# 3. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 API 키 입력

# 4. DB 초기화 (최초 1회)
python cache_db.py

# 5. 앱 실행
streamlit run app.py
```

---

## 폴더 구조

```
프로젝트/
│
├── app.py                  Streamlit 진입점 + API 키 상태 표시
├── pages/
│   ├── 1_평가하기.py       자연어 입력 화면
│   ├── 2_결과리포트.py     파이프라인 실행 + 결과 표시
│   └── 3_대시보드.py       이력 조회 대시보드 (페이지네이션·검색)
│
├── pipeline.py             Streamlit ↔ LangGraph 연결 래퍼
├── router.py               파이프라인 그래프 + 그래프 캐싱
├── intent_agent.py         자연어 → 구조화 (카테고리/위치/면적/호가)
├── geocoding.py            지명 → 위도/경도 (카카오 API + Vworld)
├── agents.py               5개 유형별 감정평가 에이전트
├── analysis_tools.py       공통 도구 (실거래가 API, 계산 함수, LLM 의견서)
├── appraisal_report.py     마크다운 리포트 생성 노드
├── cache_db.py             SQLite 캐시 + 지역코드 룩업 (WAL 모드)
├── history_db.py           감정평가 이력 저장소 (페이지네이션 지원)
├── ui_components.py        재사용 Streamlit 컴포넌트
│
├── .env.example            API 키 템플릿
├── .env                    실제 API 키 (Git 제외)
├── config.toml             Streamlit 테마·서버 설정
└── requirements.txt        패키지 목록
```

---

## 파이프라인 흐름

```
사용자 자연어 입력
  → intent_agent.py      의도 분석 (카테고리/위치/면적/호가)
  → geocoding.py         좌표 변환 (지명 → 위도/경도)
  → router.py            카테고리별 에이전트 분기
  → agents.py            감정평가 계산 (추정가치/평당가/고저평가/수익률)
  → appraisal_report.py  마크다운 리포트 생성
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

---

## 주요 개선 사항 (v2.1)

| 파일 | 개선 내용 |
|------|----------|
| `pipeline.py` | 더미 데이터 제거 → `router.run_appraisal()` 실제 연결 |
| `router.py` | `_graph` 모듈 레벨 캐싱 (매 요청마다 compile 방지) |
| `router.py` | 시작 시 API 키 누락 경고 출력 |
| `cache_db.py` | WAL 모드 + `check_same_thread=False` 멀티유저 동시성 |
| `cache_db.py` | `@contextmanager` 로 커넥션 항상 close 보장 |
| `history_db.py` | `category`를 `analysis_result.agent_name`에서 올바르게 추출 |
| `history_db.py` | `load_all(limit, offset)` 페이지네이션 추가 |
| `history_db.py` | `search_by_query()`, `load_by_category()` 추가 |
| `history_db.py` | `_row_to_dict()` — `analysis_result` 중첩 필드 자동 flatten |
| `agents.py` | `import re` 파일 최상단으로 이동 |
| `agents.py` | 각 에이전트 `try/except` + `_empty_result()` 폴백 추가 |
| `analysis_tools.py` | `naver_url` 잔여 필드 제거 |
| `analysis_tools.py` | `xml.etree.ElementTree` import 최상단 이동 |
| `analysis_tools.py` | API 키 누락 시 명확한 경고 메시지 |
| `ui_components.py` | `_get()` 헬퍼 — 최상위/중첩 구조 모두 안전 처리 |
| `ui_components.py` | `five_year_return` → `roi_5yr` 키 통일 |
| `app.py` | API 키 상태 사이드바 표시 |
| `pages/1_평가하기.py` | `building_name` 입력 필드 추가 |
| `pages/2_결과리포트.py` | `building_name` pipeline으로 전달 |
| `pages/3_대시보드.py` | 중복 코드 제거, 페이지네이션, 키워드 검색 추가 |
| `config.toml` | `enableCORS` 주석 설명 추가 |

---

## 단계별 테스트 순서

```bash
python intent_agent.py       # 카테고리·위치·면적 한국어 출력 확인
python geocoding.py          # 위도/경도 반환 확인
python analysis_tools.py     # 실거래가 + 감정평가 계산 확인
python agents.py             # 5개 에이전트 출력 확인
python router.py             # 전체 파이프라인 end-to-end 실행
streamlit run app.py         # UI 확인
```

---

## 감정평가 모델

| 출력물 | 산출 방식 |
|--------|----------|
| 추정 시장가치 | 인근 실거래 평균 ㎡당 단가 × 면적 (±10% 범위) |
| 평당가 분석 | ㎡당 단가 × 3.3058, 지역 평균과 비교 |
| 고/저평가 판단 | (추정가 - 인근 평균) / 인근 평균 × 100 |
| 투자 수익률 | 추정가 × Cap Rate, 유형별 기준 상이 |

### 고/저평가 판정 기준

| 괴리율 | 판정 |
|--------|------|
| -10% 이하 | 저평가 |
| -10% ~ +5% | 적정 |
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
