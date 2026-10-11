# secure_modular — 공통 보안 모듈로 적용한 OWASP 보안판

`secure_examples/` 가 보안 코드를 **노트북 안에 내장**해서 학습용으로 보여준다면, 이 폴더는 보안 코드를 **공통 모듈(`owasp_secure`)로 분리**하고
노트북에서는 `import` 로 가져다 쓰는 **적용용** 방식입니다. 원본 노트북은 수정하지 않습니다.

| 폴더 | 보안 코드 위치 | 용도 |
|---|---|---|
| `secure_examples/` | 노트북 셀 안 | 코드를 끝까지 읽으며 이해 |
| `secure_modular/` (이 폴더) | `owasp_secure/` 모듈 | import 한 줄로 적용, 중복 없음, 단위 테스트 |

> 두 폴더에는 같은 개념의 코드가 있어 **의도된 중복**입니다. 한쪽을 고치면 다른 쪽도 맞춰 주세요.

## 구조

```
secure_modular/
├─ owasp_secure/            # 공통 모듈
│   ├─ faiss_integrity.py   # FAISS 서명 저장/검증 로드 (LLM04, ASI04)
│   ├─ safe_eval.py         # eval 없는 pandas 명령 실행 (LLM10, ASI05)
│   ├─ doc_guard.py         # 문서 스캔·격리, 프롬프트 구조화, 출력 검사 (LLM01)
│   ├─ limits.py            # 질문·날짜 검증, 모델·도구 호출 횟수 상한 (LLM06)
│   ├─ identity.py          # 호출자 신원(UserContext)·세션 분리 (ASI03, LLM03)
│   └─ security_log.py      # 보안 이벤트 기록
├─ tests/                   # 단위 테스트 (API 호출 없음)
└─ <원본 폴더>/<원본 이름>_secure.ipynb   # 원본 폴더 구조를 따라가는 보안판 노트북 (아래 목록)
```

## 보안판 노트북 (원본은 수정하지 않음)

| 보안판 | 원본 | 적용 내용 | OWASP |
|---|---|---|---|
| `00langchainbasic/001-2_OutPutParser종류_secure.ipynb` | `00langchainbasic/001-2_OutPutParser종류.ipynb` | `re.match + eval` → `safe_execute_pandas` (+ LLM 없이 실행되는 확인 셀) | LLM10 |
| `01RAG/01-0RAG_Data_Pipeline설명_secure.ipynb` | `01RAG/01-0RAG_Data_Pipeline설명.ipynb` | 서명 저장·검증 로드 (`index_name` 사용) | LLM04 |
| `01RAG/01-3RAG_Pipeline_PdfLoader_Upstage_secure.ipynb` | `01RAG/01-3RAG_Pipeline_PdfLoader_Upstage.ipynb` | 서명 저장 2곳, 검증 로드 | LLM04 |
| `01RAG/01-4RAG_DocxLoader_Faiss_Upstage_secure.ipynb` | `01RAG/01-4RAG_DocxLoader_Faiss_Upstage.ipynb` | 서명 저장 3곳 (원본의 로드는 주석 처리됨) | LLM04 |
| `01RAG/010_RAG_Pipeline_4Chroma_FAISS_secure.ipynb` | `01RAG/010_RAG_Pipeline_4Chroma_FAISS.ipynb` | 서명 저장·검증 로드. 저장 위치를 `db/` 로 이동 | LLM04 |
| `04LangChainTool_Agent/20-2LangChain_ToolCalling_secure.ipynb` | `04LangChainTool_Agent/20-2LangChain_ToolCalling.ipynb` | 서명 저장 2곳, 검증 로드 2곳 | LLM04 |
| `05LangGraph/01_LangGraph_StateGraph_secure.ipynb` | `05LangGraph/01_LangGraph_StateGraph.ipynb` | 서명 저장, 기존 저장소 최초 서명 셀, 검증 로드 | LLM04 |
| `05LangGraph/04_LangGraph_ReAct_Memory_secure.ipynb` | `05LangGraph/04_LangGraph_ReAct_Memory.ipynb` | 기존 저장소 최초 서명, 검증 로드 | LLM04 |
| `05LangGraph/06_LangGraph_Legal_pdf_qa_faiss_secure.ipynb` | `05LangGraph/06_LangGraph_Legal_pdf_qa_faiss.ipynb` | 서명 저장, 기존 저장소 3개 최초 서명 셀, 검증 로드 | LLM04 |
| `05LangGraph/LangGraph_MessageState_RAG_secure.ipynb` | `05LangGraph/LangGraph_MessageState_RAG.ipynb` | 기존 저장소 최초 서명, 검증 로드 | LLM04 |

`05_LangGraph_AgenticRAG`, `04-2LangChain_Agents` 의 보안판은 보안 코드를 노트북에 내장한 형태로 `../secure_examples/` 에 있습니다.

### 노트북을 쓸 때 알아 둘 점
* 노트북은 **`owasp/secure_modular/<폴더>/` 에서** 엽니다. 폴더가 한 단계 깊어져 데이터·DB 경로를 `../../../data`, `../../../db` 로 바꿨습니다.
* `.env` 에 `FAISS_INTEGRITY_KEY` 가 있어야 합니다. 없으면 임시 키를 만들지 않고 오류를 냅니다.
* **서명이 없는 기존 저장소**는 로드가 거부됩니다. 직접 만든 파일이 확실할 때만 최초 1회 서명하세요. (노트북의 `ensure_signed` 셀 또는 아래 명령)
  ```bash
  cd owasp/secure_modular
  python -m owasp_secure.faiss_integrity sign ../../db/menu_db
  python -m owasp_secure.faiss_integrity sign ../../db/faiss_index --index-name company_manual
  python -m owasp_secure.faiss_integrity verify ../../db/menu_db
  ```
* 같은 `db/` 폴더를 `secure_examples`, 원본 노트북과 **공유**합니다. 서명 파일(`*.sig`)이 추가될 뿐 기존 파일은 바꾸지 않으며, 원본 노트북은 서명 파일을 무시하고 그대로 동작합니다. 단, **원본 노트북이 인덱스를 다시 만들면 기존 서명이 맞지 않게 되어** 보안판의 로드가 거부됩니다. 이때는 서명 파일(`*.sig`)을 지우고 다시 서명하세요.
* LLM·임베딩 API 를 호출하는 셀은 실행해 검증하지 않았습니다. 저장→서명→로드 흐름은 가짜 임베딩으로 실행해 확인했습니다. (`01-3`, `01-4` 는 같은 패턴이며 코드 비교로만 확인)

## 테스트 실행

`pytest` 는 설치하지 않아도 되도록 표준 `unittest` 로 작성했습니다. (`pytest` 가 있으면 그대로 실행됩니다)

```bash
cd owasp/secure_modular
python -m unittest discover -s tests -t . -v
```

## 노트북에서 사용하기

노트북을 `owasp/secure_modular/` 아래(하위 폴더 포함)에서 열고, 첫 셀에서 모듈 위치를 경로에 추가합니다.

```python
import sys
from pathlib import Path

# 이 폴더(secure_modular) 를 찾을 때까지 위로 올라가 import 경로에 추가
root = next(p for p in [Path.cwd(), *Path.cwd().parents] if (p / "owasp_secure").is_dir())
sys.path.insert(0, str(root))

from owasp_secure import load_faiss_verified, scan_documents, guard_output, validate_question
```

## 모듈별 사용 예

```python
# LLM04: FAISS 서명 검증 로드 (FAISS_INTEGRITY_KEY 를 .env 에 설정)
from owasp_secure import sign_faiss_dir, load_faiss_verified
sign_faiss_dir("../db/menu_db")                          # 최초 1회: 지금 파일을 신뢰한다는 선언
db = load_faiss_verified("../db/menu_db", embeddings)    # 서명이 다르면 PermissionError

# LLM10: eval 대신 허용 문법만 계산
from owasp_secure import safe_execute_pandas
safe_execute_pandas(df, "df['Age'].mean()")

# LLM01: 검색 문서는 스캔 -> 구조화 -> 출력 검사
from owasp_secure import scan_documents, guard_output
from owasp_secure.doc_guard import build_context, hosts_of
clean, quarantined = scan_documents(docs)
context = build_context(clean)
answer, findings = guard_output(raw_answer, allowed_hosts=hosts_of(clean))

# LLM06: 입력 검증과 호출 상한
from owasp_secure import validate_question, agent_limits
question = validate_question(user_input)
agent = create_agent(model=llm, tools=tools, middleware=agent_limits())   # 모델·도구 호출 횟수 상한 (recursion_limit 은 불필요)
agent.invoke(inputs, config={"configurable": {"thread_id": tid}})

# ASI03: 신원은 서버가 정한다
from owasp_secure import UserContext, scoped_thread_id
ctx = UserContext("user", "홍길동", "E12345")            # 로그인 검증 결과로만 생성
tid = scoped_thread_id(ctx, "session-001")               # -> "E12345:session-001"
```

## 알려진 한계

* **시스템 프롬프트에는 API 키·비밀번호·접속 문자열·내부 정책 수치 같은 중요한 정보를 절대 넣지 마세요.** 프롬프트는 유출될 수 있다고 가정해야 합니다. `SECRET_PATTERNS` 의 카나리는 유출을 알아채는 보조 장치일 뿐, 요약·말바꿈 유출은 잡지 못합니다.
* 정규식 스캔은 알려진 표현만 잡습니다. 완곡한 표현은 통과하며(테스트 `test_paraphrase_evades_scanner`), 그래서 출력 검사를 함께 씁니다.
* `FAISS_INTEGRITY_KEY` 가 유출되면 서명을 위조할 수 있습니다. 최초 서명은 "지금 파일을 믿는다"는 선언일 뿐입니다.
* `UserContext` 는 서버 인증 결과로 만들어야 합니다. 사용자 입력으로 만들면 모든 권한 검사가 무의미합니다.
* 실제 LLM 이 인젝션에 얼마나 속는지는 측정하지 않았습니다. 이 모듈은 *속았을 때 코드가 막는가*를 다룹니다.
