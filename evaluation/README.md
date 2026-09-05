# 평가·검증 도구

매수 의사결정 상태, AVM 백테스트, 종합 컨시어지 의도 추출, 계산 결과, RAG 검색, 실제 챗봇 대화를 같은 명령과 보고서 형식으로 평가한다.
기존 `tests/` 회귀 테스트를 대체하지 않는다. 서비스의 공개 API에는 평가 추적 정보를 노출하지 않는다.

## 빠른 실행

저장소 루트에서 실행한다. 이 저장소에서는 아래 `python`을 WSL의 `./venv-wsl/bin/python`으로 바꾼다.

```bash
# DB·Redis·LLM 호출 없는 의사결정·가상 AVM·계산·시드 검색 평가
python -m evaluation run --suite all

# 주기능: 후보 검토 → 비교 → 선택 후 거래 준비 상태 재생
python -m evaluation run --suite decision

# 저장소 실거래 월을 시간순으로 나눠 평가 (LLM·국토부 API 호출 없음)
python -m evaluation run --suite avm --live

# 종합 컨시어지의 실제 자연어 조건·의도 추출 (법률 챗봇과 별도)
python -m evaluation run --suite intent --live --max-cases 1 --timeout 120

# 계산만 / 검색만
python -m evaluation run --suite calculator
python -m evaluation run --suite rag --k 4

# 설정된 DB 코퍼스·임베딩 검색 평가
python -m evaluation run --suite rag --live --timeout 120

# 실제 챗봇 1개 대화부터 확인 (각 사례는 여러 턴)
python -m evaluation run --suite chat --live --max-cases 1 --timeout 300

# 실제 대화 전체를 3회 반복
python -m evaluation run --suite chat --live --repeat 3 --timeout 300

# 사용자 평가 데이터셋
python -m evaluation validate evaluation/datasets/chat.json
python -m evaluation run --suite chat --dataset my_chat_cases.json --live
```

`--live`는 루트 `.env`를 읽고 기존 `model_factory`와 검색 저장소를 사용한다. 외부 모델·임베딩 호출 비용이 생길 수 있다.
`DATABASE_URL`은 PostgreSQL이어야 하며 서비스의 SQLite/메모리 DB 폴백을 추가하지 않는다.
시드 키워드 평가는 정적 시드 청크와 서비스의 키워드 점수를 사용하는 별도 평가 모드다. 운영 RAG나 임베딩 성능을 검증했다고 해석하면 안 된다.
실제 검색은 기존 서비스처럼 코퍼스가 비어 있으면 시드를 초기 적재한다. 기존 문서를 삭제하지 않는다.

`--max-cases`는 선택된 전체 사례 수의 상한(기본 100), `--repeat`는 반복 횟수다.
시간 제한은 턴당이 아니라 **사례 전체**에 적용한다. 시간 초과·의존성 오류는 `error`이며 성공률 분모에 포함한다.
대화 평가는 서비스 함수를 직접 호출하므로 HTTP 인증·레이트 리밋·브라우저 화면은 기존 API 테스트와 별도로 검증해야 한다.

## 평가 범위

| 영역 | 실행·측정 | 경계 |
|---|---|---|
| 의사결정 (`decision`) | 8개 시나리오·19개 상태의 분석 최신성, 후보별 위험·다음 행동, 비교 수치, 선택 유무에 따른 실행 작업·권장일·준비도 | 가상 입력으로 실제 서비스 규칙을 재생. API 저장·소유자 격리·브라우저·실제 매수 성과는 기존 테스트 및 별도 검증 대상 |
| 가격 (`avm`) | 과거 월로 이후 거래를 추정. MAPE·±10% 적중률·추정 커버리지·미추정 건수·매칭/표본수별 결과 | 기존 `backtest_avm`의 축약 추정기를 재사용. 전체 실서비스 AVM의 정확도와 동일하지 않음. 기본 모드는 가상 입력, `--live`만 저장소 실거래 |
| 종합 의도 (`intent`) | 5개 시나리오·6턴의 실제 의도·금액/면적·이전 조건 유지·변경, 도구 연결 여부 표시 | 의도 추출만 실행. 주소 확정·시장 조회·Redis 대화 저장까지의 종단간 평가는 아님 |
| 계산기 | 증여·상속·양도·보유세, DSR/LTV, 공시가격 추정의 고정 기대값·허용오차·합계·규칙 기준일 | 초기 16개 사례는 저장소 회귀값/수기 계산. 외부기관 계산 결과 대조 완료가 아님 |
| RAG | Precision@k, Recall@k, MRR@k, nDCG@k, 무관 질문의 결과 없음 | 초기 7개 사례는 법률 챗봇 코퍼스 대상. 실거래 매물 RAG 정확도 평가와 다름 |
| 대화 | 실제 응답으로 이어지는 8개 시나리오·18턴, 도구·파라미터·계산 출력·답변 숫자·관련 근거·금지 문구·폴백 | 자동 검사는 명시된 조건만 평가. 의미적 정확성·법령 최신성·가독성은 사람 검토 필요 |

검색 지표에서 중복 문서는 추가 적중으로 세지 않는다. Precision@k의 분모는 실제 반환 수가 아니라 k이며,
정답 문서가 없는 사례의 Recall/nDCG는 0점 대신 `null`이다. 이 경우 검색 결과 없음으로 따로 판정한다.
실제 검색 보고서에는 `keyword`/`embedding`/`mixed`와 임베딩 폴백 여부, 코퍼스 해시를 남긴다.

### 핵심 의사결정 평가의 해석

`decision`의 정답은 특정 매물을 사라는 지시가 아니라 **위험과 누락을 빠뜨리지 않는 기대 행동**이다.
예산 이내·낮은 희망가가 권리 위험을 상쇄하면 안 되고, 체크리스트 완료가 분석 만료를 감추면 안 된다.
각 상태의 기준 시각을 고정하므로 실행 날짜가 달라도 7·14·30일 경계와 기한 경과 결과가 바뀌지 않는다.
입력 상태의 최종 선택을 기준으로 템플릿·권장일·준비도를 계산하며, 실제 선택 저장 API가 호출됐다는 의미는 아니다.

`avm --live`는 아파트 계열의 기존 적재 데이터를 읽고 보정 파일 `data/avm_calibration.json`을 갱신하지 않는다.
대상 월 거래는 비교사례에서 제외하며, 해제 거래도 정답·비교사례에서 제외한다. 시점수정은 근사 월 변동률로 고정해
외부 지수 조회를 하지 않는다. 실제 당시 발표 정보와 신고 지연까지 복원하는 시점 기준 데이터셋은 아직 아니다.
기본 데이터셋은 서초구·최근 대상월 1개이며 평가 전 지역·기간·최소 표본·허용 MAPE·커버리지 기준을 정해야 한다.
가상 사례의 낮은 오차를 실거래 정확도로 발표하면 안 된다. 데이터 없음·미추정은 합격이 아니다.

종합 컨시어지 그래프에는 현재 지역 탐색만 활성화돼 있다. `intent`의 `unconnected_tools`가 이를 드러낸다.
의도 분류를 통과해도 미연결 기능을 실제 수행했다고 해석하면 안 된다.

## 보고서와 회귀 비교

실행마다 `evaluation-results/<실행ID>/`를 만들고 다음 파일을 저장한다. 기본 출력 폴더는 Git에서 제외된다.

- `results.json`: 자동 판정·기대/실제 값·영역별 지표·모델 설정·데이터셋/프롬프트/구현 해시.
- `report.html`: 브라우저에서 여는 독립 보고서. 상태 필터, 대화, 실패 검사, 상세 추적 정보를 제공한다.
- `human_review.json`: 실제 대화 결과의 사람 채점 양식. 최초에는 모두 `pending`이다.

실제 대화 추적에는 라우터 출력·계산 입력/출력·검색 청크·검색 방식·가드 적용 전 답변·삭제 항목·폴백이 포함된다.
시간 초과나 중간 오류가 발생해도 완료된 턴과 마지막 진행 단계(`routing`, `retrieval`, `generation`)를 남긴다.
인증키·DB 접속 문자열·환경변수 전체와 서비스 오류 로그 원문은 저장하지 않는다.
질문·답변 자체는 보고서에 남으므로 기본 데이터셋처럼 가상 사례를 사용한다.

```bash
python -m evaluation compare evaluation-results/<이전ID>/results.json evaluation-results/<현재ID>/results.json
python -m evaluation review evaluation-results/<현재ID>/results.json evaluation-results/<현재ID>/human_review.json
```

`compare`는 공통 사례·반복 번호의 통과→실패/오류, 검색 지표 변화, 추가·제거 사례를 보여준다.
데이터셋·모드·k·평가기 구현이 달라지면 동일 조건 비교가 아님을 표시한다. 모델·프롬프트는 보고서 설정을 함께 확인한다.

사람 검토 시 `status`를 `reviewed`로 바꾸고 `reviewer`, 네 점수(1~5), `critical_error`, `notes`를 기록한다.
점수는 질문 적합성(`relevance`), 근거 충실성(`groundedness`), 맥락 유지(`context_retention`), 명료성(`clarity`)이다.
1점은 핵심 실패, 3점은 주요 요구 충족이나 보완 필요, 5점은 근거·조건·설명이 충분한 답변으로 평가한다.
임의 세액·근거 없는 확정적 법률 판단 등은 `critical_error=true`로 남긴다.
각 항목 3점 이상·치명적 오류 없음이 초기 사람 검토 기준이며 자동 검사 결과와 별도로 집계한다.
미검토·대상 누락·중복·다른 실행의 검토 파일은 합격으로 처리하지 않는다.

종료 코드: `0` 선택된 자동 검사 통과, `1` 검사 실패/회귀/미검토, `2` 설정·실행 오류.
`run`의 0은 실제 법률·세무 검증 완료 또는 사람 검토 완료를 뜻하지 않는다.

## 데이터셋을 늘리는 방법

각 JSON은 `version`, `suite`, `cases`를 가진다. `evaluation/schema.py`가 오타·모르는 필드·중복 ID를 거부한다.

- 계산기: `inputs`, 실행 함수, 하드코딩한 `expected`, `tolerance`, `reference`를 작성한다.
  기대값을 평가 대상 함수로 자동 생성하지 않는다. 출처·기준일·산출 과정을 기록하고, 실제 외부 대조를 수행했을 때만 `independently_verified=true`로 표시한다.
- RAG: 질문과 정답 문서의 정확한 제목 목록 또는 `expect_no_results=true`를 지정한다.
- 대화: 턴별 질문, 예상 도구·파라미터, 선택적인 출력/숫자/근거 검사와 사람 검토 초점을 작성한다.
  후속 질문 정답을 모델에 주입하지 않는다. 실제 서비스와 동일하게 최근 6개 메시지를 전달한다.

## 기존 rag_eval 자료 가져오기

기존 Python 파일을 실행하거나 삭제하지 않고 질문 목록만 정적으로 추출한다.

```bash
# Python 정적 상수 목록 (목록 변수 이름과 원본 필드 이름을 명시)
python -m evaluation import-rag path/to/rag_eval.py evaluation/datasets/rag_legacy.json --variable EVAL_CASES --question-key question --titles-key expected_titles

# JSON / JSONL / CSV도 지원. CSV의 복수 정답 문서는 JSON 배열 문자열로 작성
python -m evaluation import-rag path/to/rag_eval.json evaluation/datasets/rag_legacy.json
python -m evaluation run --suite rag --dataset evaluation/datasets/rag_legacy.json --live
```

제목 외의 문서 ID를 사용하는 평가나 자체 검색기·채점 로직이 있는 원본은 해당 내용을 확인한 뒤 별도 어댑터로 옮겨야 한다.
정적 변환기는 기존 평가 함수나 RAGAS 등의 의미 평가 지표를 자동 이식하지 않는다.
기존 `rag_eval` 원본의 통합은 요청 정정으로 범위에서 제외됐다. 위 명령은 추후 자료를 가져오기 위한 선택 기능이다.

## 검증

```bash
python -m pytest tests/test_evaluation.py tests/test_rights_and_chat.py -q
python -m pytest tests/test_decision_evaluation.py -q
```

평가기 테스트는 잘못된 기대값·금액/불리언 혼동·후속 이력·계산과 답변 수치 불일치·중복 검색 결과·폴백·시간 초과·HTML 이스케이프를 확인한다.
기존 회귀 테스트는 유지한다. 평가에서 발견한 챗봇 품질 문제를 숨기기 위해 평가 기준을 낮추지 않는다.
