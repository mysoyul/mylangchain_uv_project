# uv add langserve langchain-community fastapi uvicorn sse_starlette

from fastapi import FastAPI
from langserve import add_routes
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableLambda
from dotenv import load_dotenv
import os
import uvicorn
from pydantic import BaseModel
from typing import Dict, Any

# .env 파일 로드
#load_dotenv(dotenv_path='../.env')
load_dotenv()

# 환경 변수에서 API 키 가져오기
api_key = os.getenv("GROQ_API_KEY")
print(api_key[:6])

# 입력 스키마 정의
class QuestionInput(BaseModel):
    question: str

# FastAPI 애플리케이션 생성
app = FastAPI(title="LangServe API with .env")

# LLM 모델 생성
llm = ChatOpenAI(
    api_key=api_key,
    base_url="https://api.groq.com/openai/v1",
    model="meta-llama/llama-4-scout-17b-16e-instruct",
    temperature=0
)

# 프롬프트 템플릿 설정
prompt = PromptTemplate.from_template("질문: {question}\n답변:")

# 체인 생성
chain = prompt | llm

# 방법 1: input_type을 딕셔너리로 설정
add_routes(
    app, 
    chain, 
    path="/chat",
    input_type=Dict[str, Any],  # 딕셔너리 타입으로 변경
    config_keys=["configurable"]
)

# 방법 2: 별도 엔드포인트로 문자열 입력 처리
def process_string_input(input_str: str) -> Dict[str, str]:
    return {"question": input_str}

string_chain = RunnableLambda(process_string_input) | chain

add_routes(
    app,
    string_chain,
    path="/chat_simple",
    input_type=str,  # 문자열 입력
    config_keys=["configurable"]
)

# 방법 3: Pydantic 모델 사용
def process_pydantic_input(input_data: QuestionInput) -> Dict[str, str]:
    return {"question": input_data.question}

pydantic_chain = RunnableLambda(process_pydantic_input) | chain

add_routes(
    app,
    pydantic_chain,
    path="/chat_pydantic",
    input_type=QuestionInput,  # Pydantic 모델 사용
    config_keys=["configurable"]
)

# 헬스체크 엔드포인트
@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# FastAPI 서버 실행
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)