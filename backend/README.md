# DeepAgent 부동산 가치 감정평가 — 백엔드 개발 학습 정리

> 이 문서는 백엔드를 구성하면서 배우고 기억해야 할 핵심 개념을 정리한 것입니다.

---

## 목차

1. [프로젝트 구조 이해](#1-프로젝트-구조-이해)
2. [LangGraph — 에이전트 워크플로우](#2-langgraph--에이전트-워크플로우)
3. [LLM 로컬 실행 (Ollama)](#3-llm-로컬-실행-ollama)
4. [Pydantic vs TypedDict — State 설계](#4-pydantic-vs-typeddict--state-설계)
5. [API 연동 핵심 정리](#5-api-연동-핵심-정리)
6. [감정평가 모델 구조](#6-감정평가-모델-구조)
7. [자주 발생한 오류와 해결법](#7-자주-발생한-오류와-해결법)
8. [실행 순서](#8-실행-순서)
9. [파일 구조와 역할](#9-파일-구조와-역할)

---

## 1. 프로젝트 구조 이해

이 시스템은 웹 서비스 4개 레이어 중 **백엔드 비즈니스 로직(Layer 3)** 에 해당한다.

```
Layer 1  프론트엔드     Streamlit / React (미구현)
Layer 2  API 레이어    FastAPI (미구현)
Layer 3  비즈니스 로직  ← 지금 만든 영역
Layer 4  데이터 레이어  국토부 API, 카카오 API, SQLite, pgvector
```

### 핵심 파이프라인 흐름

```
사용자 자연어 입력
  → intent_agent.py      의도 분석 (카테고리/위치/면적/호가 추출)
  → geocoding.py         좌표 변환 (지명 → 위도/경도)
  → router.py            카테고리별 에이전트 분기
  → agents.py            감정평가 계산 (추정가치/평당가/고저평가/수익률)
  → appraisal_report.py  마크다운 리포트 생성
```

---

## 2. LangGraph — 에이전트 워크플로우

### 기본 개념

LangGraph는 **노드(Node)** 와 **엣지(Edge)** 로 에이전트 흐름을 정의한다.

- **노드**: 실제 작업을 수행하는 함수
- **엣지**: 노드 간 연결 (다음에 어떤 노드로 갈지)
- **조건부 엣지**: 상태값에 따라 분기 (라우터가 이걸 사용)

```python
graph = StateGraph(AgentState)
graph.add_node("의도분석", intent_analysis_node)
graph.add_node("검증",     validate_node)
graph.set_entry_point("의도분석")
graph.add_edge("의도분석", "검증")
graph.add_conditional_edges(
    "검증",
    should_retry,
    {"retry": "의도분석", "end": "지오코딩"}
)
app = graph.compile()
result = app.invoke({"user_input": "마포구 아파트 매매 8억", "error": "", "retry_count": 0})
```

### 재시도 로직 — 노드 안에서 직접 재호출 금지

```python
# ❌ 잘못된 방법 — 결과가 중복 출력됨
def validate_node(state):
    if state.get("error"):
        return intent_analysis_node(state)  # 직접 재호출 금지

# ✅ 올바른 방법 — 엣지(should_retry)가 재시도를 담당
def validate_node(state):
    if state.get("error"):
        return state  # 그냥 반환, should_retry 엣지가 처리

def should_retry(state):
    if state.get("error") and state.get("retry_count", 0) <= 2:
        return "retry"
    return "end"
```

---

## 3. LLM 로컬 실행 (Ollama)

### 모델 선택 기준 (한국어 부동산 도메인)

| 모델 | 한국어 | JSON 준수 | 권장 |
|------|--------|-----------|------|
| EXAONE 3.5 7.8B | ★★★★★ | ★★★★ | ✅ |
| Qwen 2.5 7B | ★★★★ | ★★★★★ | 대안 |
| Solar 10.7B | ★★★ | ★★ | ✗ |
| llama3.1 8B | ★★ | ★★★ | ✗ |

Solar는 JSON 구조를 임의로 변경하고 영어로 응답하는 경향이 있음.
EXAONE은 한국어로 사전학습된 유일한 로컬 모델이라 정확도가 높음.

### 핵심 설정

```python
ChatOllama(
    model=os.getenv("OLLAMA_MODEL", "exaone3.5:7.8b"),
    temperature=0.0,   # 결정론적 결과를 위해 0으로 고정
    format="json",     # JSON 모드 강제
    num_predict=1024,  # 반드시 설정 — 없으면 JSON이 중간에 잘림
)
```

### 소형 모델 3중 방어 전략

소형 LLM은 프롬프트를 완벽하게 따르지 않으므로 3가지로 방어해야 한다.

**① 모든 Pydantic 필드에 default 설정**
```python
# ❌ 모델이 필드 빠뜨리면 ValidationError 발생
category_detail: str = Field(description="...")

# ✅ 빠뜨려도 기본값으로 채워짐
category_detail: str = Field(default="")
confidence: float    = Field(default=0.5)
```

**② 프롬프트에 JSON 예시 템플릿 포함**

설명만 쓰면 소형 모델은 필드를 생략하거나 구조를 바꾼다.
프롬프트 끝에 실제 출력 예시를 반드시 포함한다.

```
EXAMPLE OUTPUT:
{"category":"주거용","category_detail":"아파트","location_raw":"마포구",...}
```

**③ normalize_parsed_data() — 정규화 레이어**

LLM 응답을 파싱한 직후, Pydantic에 넣기 전에 실행한다.

```python
# 모델이 배열로 반환한 경우
"category": ["주거용", "아파트"]  →  "category": "주거용"

# 중첩 딕셔너리로 반환한 경우
"location": {"name": "마포구"}    →  "location_raw": "마포구"

# 영문으로 반환한 경우
"category": "residential"         →  "category": "주거용"
"transaction_type": "lease"       →  "transaction_type": "전세"
```

---

## 4. Pydantic vs TypedDict — State 설계

### 핵심 규칙

**LangGraph State는 반드시 TypedDict로 선언한다.**

LangGraph는 내부적으로 state를 dict로 관리하기 때문에 Pydantic BaseModel은 호환되지 않는다.

```python
# ❌ 잘못된 방법
from pydantic import BaseModel
class AgentState(BaseModel):
    user_input: str
    error: str = ""
# → state.get("intent") 호출 시 AttributeError 발생

# ✅ 올바른 방법
from typing_extensions import TypedDict
class AgentState(TypedDict, total=False):
    user_input:  str
    intent:      Optional[PropertyIntent]
    error:       str
    retry_count: int
```

### Pydantic은 어디에 써야 하나

State가 아닌 **데이터 모델**에 사용한다. LLM 파싱 결과, API 응답, 감정평가 결과 등.

```python
class PropertyIntent(BaseModel):     # LLM 파싱 결과
    category: str = Field(default="주거용")

class ValuationResult(BaseModel):    # 감정평가 결과
    estimated_value: int = Field(default=0)
```

---

## 5. API 연동 핵심 정리

### 카카오 로컬 API

- **키 종류**: REST API 키만 사용 (JavaScript 키 아님)
- **인증 헤더**: `{"Authorization": f"KakaoAK {키}"}`
- **403 오류**: 개발자 콘솔 → 플랫폼 → Web → `http://localhost` 등록 필수
- **폴백 구조**: 주소 검색 실패 → 키워드 검색으로 자동 전환

### 국토부 실거래가 API

- **매매 전용** — 상업용·산업용·토지는 전월세 API 없음
- **지역코드**: 법정동코드 앞 5자리 (카카오 b_code에서 추출)
- **응답 형식**: XML → `xml.etree.ElementTree`로 파싱 (JSON 아님)
- **속도 느림** → SQLite 캐시 24시간 적용 필수

### 유형별 API 엔드포인트 (매매)

| 유형 | 서비스명 |
|------|----------|
| 아파트 | `RTMSDataSvcAptTradeDev` |
| 연립·다세대 | `RTMSDataSvcRHTrade` |
| 단독·다가구 | `RTMSDataSvcSHTrade` |
| 오피스텔 | `RTMSDataSvcOffiTrade` |
| 상업·업무용 | `RTMSDataSvcNrgTrade` |
| 공장·창고 | `RTMSDataSvcInduTrade` |
| 토지 | `RTMSDataSvcLandTrade` |

### 파일명 충돌 주의

`report.py`, `utils.py`, `test.py` 같은 일반적인 이름은 외부 패키지와 충돌한다.
→ `appraisal_report.py`처럼 프로젝트에 특화된 이름을 사용할 것.

---

## 6. 감정평가 모델 구조

### 4가지 핵심 출력물

| 출력물 | 산출 방식 |
|--------|----------|
| 추정 시장가치 | 인근 실거래 평균 ㎡당 단가 × 면적 (±10% 오차 범위) |
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

### 면적 변환

```
1평 = 3.3058㎡
20평대 → area_min: 66.1㎡, area_max: 99.2㎡
300평 이상 → area_min: 991.7㎡
```

---

## 7. 자주 발생한 오류와 해결법

| 오류 | 원인 | 해결법 |
|------|------|--------|
| `model 'llama3' not found` | 모델명 불일치 | `ollama list`로 확인 후 `.env` 수정 |
| `Field required` (ValidationError) | LLM이 JSON 필드 생략 | 모든 필드에 `default=""` 추가 |
| `AgentState has no attribute 'get'` | State를 Pydantic으로 선언 | TypedDict로 교체 |
| `ImportError from 'report'` | 파일명이 외부 패키지와 충돌 | `appraisal_report.py`로 이름 변경 |
| 카카오 `403 Forbidden` | 플랫폼 미등록 | 개발자 콘솔에서 Web 플랫폼 등록 |
| JSON이 중간에 잘림 | `num_predict` 기본값 낮음 | `num_predict=1024` 설정 |
| 결과 중복 출력 | validate_node 안에서 재귀 호출 | 노드 안 직접 재호출 금지, 엣지로 처리 |
| `category`가 영문으로 옴 | 소형 모델 한국어 응답 불안정 | `normalize_parsed_data()`로 한국어 변환 |

---

## 8. 실행 순서

### 최초 환경 준비

```bash
pip install -r requirements.txt
pip install typing_extensions

ollama pull exaone3.5:7.8b
ollama pull nomic-embed-text

cp .env.example .env
# .env 파일에서 API 키 입력

python cache_db.py   # SQLite 초기화 (최초 1회)
```

### 단계별 테스트 순서

```bash
python intent_agent.py      # 카테고리·위치·면적 한국어 출력 확인
python geocoding.py         # 위도/경도 반환 확인
python analysis_tools.py    # 실거래가 + 감정평가 계산 확인
python agents.py            # 5개 에이전트 출력 확인
python router.py            # 전체 파이프라인 end-to-end 실행
```

---

## 9. 파일 구조와 역할

```
프로젝트/
│
├── intent_agent.py       자연어 → 구조화 (카테고리/위치/면적/호가)
├── geocoding.py          지명 → 위도/경도 (카카오 API + Vworld)
├── router.py             파이프라인 연결 + LangGraph 그래프 정의
├── agents.py             5개 유형별 감정평가 계산 로직
├── analysis_tools.py     공통 도구 (실거래가 API, 계산 함수, LLM 의견서)
├── appraisal_report.py   마크다운 리포트 생성 노드
├── cache_db.py           SQLite 캐시 + 지역코드 37개 룩업
├── rag_pipeline.py       pgvector 벡터 검색 (선택적)
├── deep_analysis.py      API + RAG 통합 노드
│
├── .env                  API 키 (Git에 절대 올리지 말 것)
├── .env.example          키 템플릿
├── requirements.txt      패키지 목록
└── cache.db              SQLite 캐시 (자동 생성)
```

### 파일 간 의존 관계

```
router.py
  ├── intent_agent.py
  ├── geocoding.py
  ├── agents.py
  │     └── analysis_tools.py
  └── appraisal_report.py
```

---

## 기억해야 할 핵심 3가지

**① LangGraph State는 TypedDict**
Pydantic BaseModel로 만들면 `.get()` 오류가 발생한다.

**② 소형 LLM은 3중 방어**
`default` 설정 + 프롬프트 예시 + `normalize_parsed_data()` 정규화로 어떤 모델도 대응 가능하게 만든다.

**③ 파일명은 구체적으로**
`report.py`, `utils.py`처럼 흔한 이름은 외부 패키지와 충돌한다.