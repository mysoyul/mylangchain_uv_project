# secure_examples — 원본 예제에 OWASP 보안 지침을 적용한 노트북

`before_after/` 가 취약점 **하나만 발췌**해 전/후를 비교한다면, 이 폴더는 **원본 노트북의 흐름을 유지한 채** 필요한 지점만 고친 완성본입니다.
바뀐 셀에는 `# [OWASP …]` 주석이 붙어 있어 원본과 나란히 열어 비교할 수 있습니다. 원본은 수정하지 않습니다.

| 노트북 | 원본 | 적용한 OWASP 항목 | 상태 |
|---|---|---|---|
| `05_LangGraph_AgenticRAG_secure.ipynb` | `05LangGraph/05_LangGraph_AgenticRAG.ipynb` | LLM04 FAISS 서명 검증, LLM01 검색 문서 격리·출력 검사, LLM06 입력·문맥·스텝 상한, LLM03 승인 화면 | 완료 |
| `04-2LangChain_Agents_secure.ipynb` | `04LangChainTool_Agent/04-2LangChain_Agents.ipynb` | ASI03/LLM03 도구 권한(사번을 인증 컨텍스트에서 읽음), LLM01 웹 검색 결과 격리, ASI03 메모리 분리, LLM06 날짜 검증·호출 횟수 제한 | 완료 |

## 실행 방법

1. `.env` 에 `FAISS_INTEGRITY_KEY` 를 추가합니다. 
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
2. `owasp/secure_examples/` 에서 노트북을 엽니다. (`../../db`, `../../data` 상대 경로 사용)
3. 노트북 마지막의 **보안 검증 장은 API 호출 없이** 실행됩니다. 앞부분의 API 호출 셀은 `needs-api` 태그가 붙어 있습니다.

## 검증 범위

* 실행해서 확인함: 보안 함수 단위 동작, 모의 모델·모의 검색으로 재현한 공격 4종의 전/후, FAISS 변조 거부, 상한 동작, HITL 재검사
* 실행하지 않음: Upstage·Tavily 를 호출하는 셀(비용), 실제 LLM 이 인젝션에 얼마나 속는지
