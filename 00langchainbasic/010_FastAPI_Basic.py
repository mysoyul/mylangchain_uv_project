# python 00langchainbasic\010_FastAPI_Basic.py
# 루트 경로에서 
# uvicorn 010_FastAPI_Basic:app --app-dir 00langchainbasic --reload

# uv add fastapi uvicorn langchain-openai python-dotenv
#
# 010_LangServe_Basic.py 와 같은 체인을 LangServe 없이 FastAPI 로 직접 서빙하는 예제
#   POST /chat         : 전체 답변을 JSON 으로 반환
#   POST /chat/stream  : 답변을 SSE(Server-Sent Events)로 토큰 단위 스트리밍
#   GET  /health       : 헬스체크
#   GET  /             : 스트리밍 테스트 페이지 (010_FastAPI_stream_test.html)
#
# 브라우저 테스트: 서버 실행 후 http://127.0.0.1:8000/ 접속 (한글도 UTF-8 로 전송되어 안전)
#
# ── 터미널에서 테스트하기 (서버를 먼저 실행한 상태에서 다른 터미널에 입력) ──
# * 호출할 때마다 Groq API 사용량이 발생합니다.
#
# [Git Bash / Linux / macOS] 작은따옴표로 JSON 을 감쌈
#   curl -X POST http://127.0.0.1:8000/chat -H "Content-Type: application/json" -d '{"question": "What is LangChain?"}'
#   curl -N -X POST http://127.0.0.1:8000/chat/stream -H "Content-Type: application/json" -d '{"question": "LangChain이 뭐야?"}'
#
# * 한글이 깨지면 PowerShell 에서 먼저 [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 실행
# * 브라우저에서 http://127.0.0.1:8000/docs (Swagger UI)로도 /chat 을 테스트할 수 있음
#   (/chat/stream 은 SSE 라 Swagger UI 에서 토큰 단위로 보이지 않으므로 curl -N 권장)

import json
import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# .env 파일 로드
load_dotenv()

# 설정 상수 (필요 시 환경 변수로 변경 가능)
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
MODEL_NAME = "openai/gpt-oss-120b"
HOST = "127.0.0.1"  # 로컬 전용. 외부 공개 시 인증 추가 후 변경
PORT = 8000
MAX_QUESTION_LENGTH = 2000  # 입력 길이 제한 (비용/남용 방지)
STREAM_TEST_HTML = Path(__file__).parent / "010_FastAPI_stream_test.html"  # 스트리밍 테스트 페이지

# 환경 변수에서 API 키 가져오기 (키 값은 로그에 출력하지 않음)
api_key = os.getenv("GROQ_API_KEY")
if not api_key:
    raise RuntimeError("GROQ_API_KEY 환경 변수가 설정되지 않았습니다. .env 파일을 확인하세요.")


class QuestionInput(BaseModel):
    """요청 본문 스키마. 형식이 맞지 않으면 FastAPI 가 자동으로 422 를 반환합니다."""
    question: str = Field(min_length=1, max_length=MAX_QUESTION_LENGTH)


class AnswerOutput(BaseModel):
    """응답 스키마."""
    answer: str


app = FastAPI(title="FastAPI Chat API")

# LLM / 프롬프트 / 체인 (LangServe 예제와 동일)
llm = ChatOpenAI(
    api_key=api_key,
    base_url=GROQ_BASE_URL,
    model=MODEL_NAME,
    temperature=0,
)
prompt = PromptTemplate.from_template("질문: {question}\n답변:")
chain = prompt | llm


@app.post("/chat", response_model=AnswerOutput)
async def chat(body: QuestionInput) -> AnswerOutput:
    """질문을 받아 전체 답변을 한 번에 반환합니다."""
    try:
        result = await chain.ainvoke({"question": body.question})
    except Exception as e:
        # TODO: 운영 시에는 예외 종류별로 상태 코드를 구분하고 상세 내용은 로그로만 남길 것
        raise HTTPException(status_code=502, detail=f"LLM 호출 실패: {type(e).__name__}") from e
    return AnswerOutput(answer=result.content)


@app.post("/chat/stream")
async def chat_stream(body: QuestionInput) -> StreamingResponse:
    """질문을 받아 답변을 SSE 로 스트리밍합니다. 각 이벤트: data: {"token": "..."}"""

    async def event_generator():
        try:
            async for chunk in chain.astream({"question": body.question}):
                if chunk.content:
                    # ensure_ascii=False: 한글을 이스케이프하지 않고 그대로 전송
                    yield f"data: {json.dumps({'token': chunk.content}, ensure_ascii=False)}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            # 스트리밍 시작 후에는 상태 코드를 바꿀 수 없으므로 에러 이벤트로 전달
            yield f"event: error\ndata: {json.dumps({'error': type(e).__name__})}\n\n"

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    """스트리밍 테스트 페이지를 반환합니다. (같은 출처로 서빙하므로 CORS 설정이 필요 없음)"""
    if not STREAM_TEST_HTML.exists():
        raise HTTPException(status_code=404, detail=f"{STREAM_TEST_HTML.name} 파일이 없습니다.")
    return FileResponse(STREAM_TEST_HTML)


@app.get("/health")
async def health_check():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host=HOST, port=PORT)
