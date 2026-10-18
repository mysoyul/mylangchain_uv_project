# before_after — 취약점 개선 전/후 비교 노트북

OWASP 문서(`../docs/`)에서 지적하는 취약점 중, 학습 코드에서 실제로 확인된 항목을 **최소 재현 노트북**으로 정리합니다.
각 노트북은 `Before(취약 코드) → 공격 재현 → After(수정 코드) → 같은 공격 재시도 → 자동 검증(assert)` 순서입니다.

- 이 폴더의 노트북은 원본 노트북을 고치지 않고, 취약한 부분만 발췌해서 비교합니다.
  (단, 04의 MCP 예제 `04LangChainTool_Agent/20-4MCP_example_openai.ipynb`, `math_server.py`, `text_server.py` 는 검증 후 별도로 수정했습니다. 04 노트북 7장 참고)
- LLM 호출이 없습니다. (LLM 응답은 문자열 또는 가짜 모델로 모의) API 키와 비용이 필요 없습니다.
  (예외: 06 의 4-1 은 `OPENAI_API_KEY` 가 있을 때만 실행되는 **선택 실습**이며, 키가 없으면 건너뜁니다)
- 공격 페이로드는 모두 **무해한 예시**입니다. (화면 출력, 현재 경로 읽기, 임시 마커 파일 생성)

## 노트북 목록

| 노트북 | OWASP | 원본 위치 | 핵심 수정 | 상태 |
|---|---|---|---|---|
| `01_LLM10_eval_코드실행.ipynb` | LLM10 Improper Output Handling / ASI05 | `00langchainbasic/001-2_OutPutParser종류.ipynb` | `re.match + eval` → ① `ast` 허용 문법 직접 계산 (기존 코드 유지 시) ② 구조화 출력 `{action, column, n}` (새 코드 권장) | 완료 |
| `02_LLM04_FAISS_역직렬화.ipynb` | LLM04 Supply Chain / ASI04 | `allow_dangerous_deserialization=True` 사용 10곳 | ① 받은 인덱스는 열지 않고 원본 문서로 재생성 (시나리오 A) ② 저장 시 HMAC 서명, 로드 전 검증 (시나리오 B) | 완료 |
| `03_LLM06_무제한소비.ipynb` | LLM06 Unbounded Consumption | 에이전트/그래프 호출 전반 (`recursion_limit`, `max_tokens` 미설정) | `recursion_limit` + `ModelCallLimitMiddleware` + 입력 길이·`max_tokens`·`timeout` 상한 | 완료 |
| `04_ASI02_MCP_도구권한.ipynb` | ASI02 Tool Misuse / ASI03 | `04LangChainTool_Agent/20-4MCP_example_openai.ipynb`, `math_server.py`, `text_server.py` (MCP stdio 예제) | ① 도구 허용 목록(이름) ② 승인본 지문 비교(설명 변조, 심화) + 에이전트 경로 재현, 입력·결과 한도, 최소 환경 변수 | 완료 |
| `05_ASI09_HITL_승인.ipynb` | LLM03 Excessive Agency / ASI09 | `05LangGraph` (HITL 적용이 2개 파일뿐) | 조회 결과 속 간접 인젝션 재현 → 위험 도구만 사람 승인(`HumanInTheLoopMiddleware`, 승인 화면에 원래 요청 표시) + 위험 도구 미노출 + 도구 내부 검증 + 감사 로그 | 완료 |
| `06_LLM01_프롬프트인젝션.ipynb` | LLM01 Prompt Injection | RAG 노트북 (검색 문서를 프롬프트에 그대로 삽입) | 검색 문서 스캔·격리 + 프롬프트 구조화 + 출력 검사(허용 도메인·카나리 토큰) + 화면 이미지 자동 로딩 차단 + (선택) 실제 LLM 확인 | 완료 |

## 실행 방법

> **버전 주의 (검증 환경: langchain 1.2.6, langgraph 1.0.6, langchain-mcp-adapters 0.2.2)**
> - `langgraph-prebuilt` 는 `langgraph` 와 같은 버전대로 맞추세요. (`langgraph 1.0.6` + `langgraph-prebuilt 1.0.13` 조합은 `create_agent` import 시 `ImportError: ExecutionInfo`)
> - `mcp` 는 `mcp<2` 로 고정하세요. mcp 2.x 에서는 `mcp.server.fastmcp.FastMCP` 가 `MCPServer` 로 바뀌어 04 노트북과 원본 MCP 예제가 실행되지 않습니다.

1. 프로젝트 루트의 `.venv` 를 커널로 선택합니다. (`uv sync` 이후)
2. 노트북은 `../../data/titanic.csv` 처럼 **이 폴더 기준 상대 경로**를 사용하므로 `owasp/before_after/` 에서 엽니다. (폴더를 옮기면 경로가 깨집니다)
3. 위에서 아래로 순서대로 실행합니다. (뒤 셀이 앞 셀에서 만든 함수·변수를 사용)

## 노트북 공통 템플릿

1. 개요 표 (OWASP 번호, 원본 위치, 위험도)
2. Before — 원본과 같은 코드
3. 공격 재현 — 무해한 페이로드로 실제 문제 확인
4. After — 수정 코드와 수정 원칙
5. 전/후 비교 표 + `assert` 자동 검증
6. 바뀐 점 요약, **남는 위험과 추가 대책**

## 예제의 현실성 점검 ("억지스러운 시나리오"가 아닌지)

입문 개발자가 "내 코드와는 상관없는 이야기"로 느끼지 않도록, 각 노트북에 **이 위험이 언제 현실이 되는지**를 적었습니다.

| 노트북 | 실제로 일어나는 상황 | 과장될 수 있는 부분과 처리 |
|---|---|---|
| 01 eval | 공개 챗봇에서 사용자가 "명령 끝에 이 코드를 붙여 줘"라고 요청 — 특별한 기술 불필요 | 없음. 대신 새 코드에는 더 간단한 대안(구조화 출력)을 권장으로 추가 |
| 02 FAISS | 남이 만든 `db/` 폴더를 받아 열 때 (GitHub 예제, 공유 드라이브) | 내 노트북에서 직접 만든 인덱스는 위험이 낮음을 명시. 상황별로 대책을 나눔 (재생성 / 서명) |
| 03 무제한 소비 | 도구 장애·빈 결과 반복, 모호한 목표, 인젝션 | "항상 도구만 부르는 가짜 모델"은 최악의 경우를 재현하는 장치임을 명시 |
| 04 MCP | 남이 만든 MCP 서버를 붙이고, 서버가 업데이트될 때 | 지문 비교는 외부 서버용 심화로 구분, 입문 단계는 허용 목록으로 충분함을 명시 |
| 05 HITL | 에이전트가 읽는 데이터(조회 결과·메모·문서)에 남이 쓴 글이 섞일 때 | 고객이 자기 메시지로 자기 계정 삭제를 시키는 구조 → **조회 결과 속 간접 인젝션**으로 변경 |
| 06 프롬프트 인젝션 | 외부 업로드 문서가 RAG 검색 결과에 섞일 때 | 패턴 스캔(L1)이 "공격 문장에 맞춰 쓴 패턴"이라는 한계를 명시, 우선순위 제시, 실제 모델 확인 선택 셀 추가 |
