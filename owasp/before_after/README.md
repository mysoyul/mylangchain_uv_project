# before_after — 취약점 개선 전/후 비교 노트북

OWASP 문서(`../docs/`)에서 지적하는 취약점 중, 학습 코드에서 실제로 확인된 항목을 **최소 재현 노트북**으로 정리합니다.
각 노트북은 `Before(취약 코드) → 공격 재현 → After(수정 코드) → 같은 공격 재시도 → 자동 검증(assert)` 순서입니다.

- 이 폴더의 노트북은 원본 노트북을 고치지 않고, 취약한 부분만 발췌해서 비교합니다.
  (단, 04의 MCP 예제 `04LangChainTool_Agent/20-4MCP_example_openai.ipynb`, `math_server.py`, `text_server.py` 는 검증 후 별도로 수정했습니다. 04 노트북 7장 참고)
- LLM 호출이 없습니다. (LLM 응답은 문자열로 모의) API 키와 비용이 필요 없습니다.
- 공격 페이로드는 모두 **무해한 예시**입니다. (화면 출력, 현재 경로 읽기, 임시 마커 파일 생성)

## 노트북 목록

| 노트북 | OWASP | 원본 위치 | 핵심 수정 | 상태 |
|---|---|---|---|---|
| `01_LLM10_eval_코드실행.ipynb` | LLM10 Improper Output Handling / ASI05 | `00langchainbasic/001-2_OutPutParser종류.ipynb` | `re.match + eval` → `ast` 허용 문법 직접 계산 | 완료 |
| `02_LLM04_FAISS_역직렬화.ipynb` | LLM04 Supply Chain / ASI04 | `allow_dangerous_deserialization=True` 사용 10곳 | 저장 시 HMAC 서명, 로드 전 검증 | 완료 |
| `03_LLM06_무제한소비.ipynb` | LLM06 Unbounded Consumption | 에이전트/그래프 호출 전반 (`recursion_limit`, `max_tokens` 미설정) | `recursion_limit` + `ModelCallLimitMiddleware` + 입력 길이·`max_tokens`·`timeout` 상한 | 완료 |
| `04_ASI02_MCP_도구권한.ipynb` | ASI02 Tool Misuse / ASI03 | `04LangChainTool_Agent/20-4MCP_example_openai.ipynb`, `math_server.py`, `text_server.py` (MCP stdio 예제) | 도구 allowlist + 승인본 지문 비교, 입력·결과 한도, 최소 환경 변수 | 완료 |
| `05_ASI09_HITL_승인.ipynb` | LLM03 Excessive Agency / ASI09 | `05LangGraph` (HITL 적용이 2개 파일뿐) | 위험 도구만 사람 승인(`HumanInTheLoopMiddleware`) + 위험 도구 미노출 + 도구 내부 검증 + 감사 로그 | 완료 |
| `06_LLM01_프롬프트인젝션.ipynb` | LLM01 Prompt Injection | RAG 노트북 (검색 문서를 프롬프트에 그대로 삽입) | 검색 문서 스캔·격리 + 프롬프트 구조화 + 출력 검사(허용 도메인·카나리 토큰) | 완료 |

## 실행 방법

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
