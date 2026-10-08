# uv add gradio_pdf
"""PDF 질의응답(RAG) Gradio 앱: PDF 업로드 -> FAISS 벡터 저장소 -> Upstage Solar 답변.

전체 흐름
    1. PDF 업로드 + 질문 입력
    2. PDF를 청크(chunk)로 분할 -> 임베딩 -> FAISS 벡터 저장소 (PDF/분할 설정이 바뀔 때만 수행)
    3. 질문과 유사한 청크 k개 검색(retriever)
    4. 검색된 청크를 context로 프롬프트에 넣어 LLM이 답변 생성
    5. 답변 + 출처(파일명, 페이지)를 채팅창에 표시
"""
import os
from dataclasses import dataclass
from functools import lru_cache

import gradio as gr
from dotenv import load_dotenv

# langchain 패키지
from langchain_upstage import UpstageEmbeddings, ChatUpstage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnableLambda, RunnableParallel, RunnablePassthrough

# RAG Chain 구현을 위한 패키지
from langchain_community.document_loaders import PyPDFLoader            # PDF -> Document (페이지 단위)
from langchain_text_splitters import RecursiveCharacterTextSplitter     # 긴 텍스트를 청크로 분할
from langchain_community.vectorstores import FAISS                      # 메모리 기반 벡터 저장소

# gradio 인터페이스를 위한 패키지 (PDF 업로드/미리보기 컴포넌트)
from gradio_pdf import PDF

# ---------------------------------------------------------------------------
# 상수
# ---------------------------------------------------------------------------
API_KEY_ENV = "UPSTAGE_API_KEY"                 # .env 에서 읽을 환경 변수 이름
EMBEDDING_MODEL = "solar-embedding-1-large"     # 청크/질문을 벡터로 바꾸는 임베딩 모델
CHAT_MODEL = "solar-pro3"                       # 답변을 생성하는 LLM
UPSTAGE_BASE_URL = "https://api.upstage.ai/v1"
SEARCH_K = 6                                    # 질문마다 검색할 청크 개수 (많을수록 문맥↑, 토큰/비용↑)
SEPARATORS = ["\n\n", "\n", ".", " ", ""]       # 앞쪽 구분자부터 시도해 문단 > 줄 > 문장 > 단어 순으로 자연스럽게 분할

DEFAULT_CHUNK_SIZE = 1000                       # 청크 1개의 최대 글자 수
DEFAULT_CHUNK_OVERLAP = 200                     # 인접 청크가 겹치는 글자 수 (문맥 단절 방지)
DEFAULT_TEMPERATURE = 0.0                       # 0: 같은 질문에 일관된 답변 (RAG는 정확성 우선)
MIN_CHUNK_SIZE = 100                            # 너무 작은 청크는 의미가 없으므로 하한을 둔다

ERROR_PREFIX = "⚠️ "                            # 오류 메시지 접두어 (정상 답변과 구분)
SERVER_NAME = "127.0.0.1"                       # 로컬 접속만 허용
# server_port를 지정하지 않으면 Gradio가 7860부터 빈 포트를 자동으로 찾는다.

# 프롬프트: 문서 내용만 근거로 답하도록 제한해 환각(hallucination)을 줄인다.
# {context}에는 검색된 청크들이 들어간다.
SYSTEM_TEMPLATE = """다음 문맥을 바탕으로 질문에 정확하게 답변해주세요.
문맥에서 관련 정보를 찾을 수 없다면, "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답변해주세요.

<문맥>
{context}
</문맥>

답변 규칙:
1. 문서 내용만을 근거로 답변하세요
2. 단계별 설명이 필요하면 순서대로 작성하세요
3. 구체적인 메뉴명, 버튼명을 포함하세요
4. 문서에 없는 정보는 "문서에서 찾을 수 없습니다"라고 하세요"""

# 질문은 human 메시지로만 한 번 전달한다. (system에 중복해서 넣으면 토큰 낭비)
PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_TEMPLATE),
    ("human", "{question}"),
])


# ---------------------------------------------------------------------------
# 환경 설정 / 모델 생성
# ---------------------------------------------------------------------------
def require_api_key() -> str:
    """환경 변수에서 API 키를 읽어 검증한다. 키 값은 출력하지 않는다."""
    load_dotenv()  # .env 파일의 값을 환경 변수로 로드
    api_key = os.getenv(API_KEY_ENV)
    if not api_key:
        raise ValueError(f"{API_KEY_ENV}가 설정되지 않았습니다. .env 파일을 확인해주세요.")
    return api_key


@dataclass
class RagSession:
    """사용자 세션별 RAG 상태. 같은 (PDF, 분할 설정)이면 벡터 저장소를 재사용한다."""
    key: tuple          # (pdf 경로, chunk_size, chunk_overlap) - 이 값이 같으면 재사용
    retriever: object   # 벡터 저장소에서 만든 retriever (질문 -> 유사 청크 검색)


@lru_cache(maxsize=1)
def get_embeddings():
    """임베딩 모델을 한 번만 생성한다. (호출 때마다 만들 필요가 없으므로 캐시)"""
    return UpstageEmbeddings(model=EMBEDDING_MODEL)


@lru_cache(maxsize=8)
def get_llm(temperature: float):
    """temperature별로 ChatModel을 캐시해 재사용한다. (슬라이더 값이 바뀌어도 같은 값이면 재사용)"""
    return ChatUpstage(model=CHAT_MODEL, base_url=UPSTAGE_BASE_URL, temperature=temperature)


# ---------------------------------------------------------------------------
# 입력 검증 / 벡터 저장소 생성
# ---------------------------------------------------------------------------
def parse_split_options(chunk_size, chunk_overlap) -> tuple[int, int]:
    """청크 설정을 검증해 정수로 변환한다. 잘못된 값이면 ValueError."""
    # gr.Number는 입력을 지우면 None, 소수를 입력하면 float를 줄 수 있다.
    if chunk_size is None or chunk_overlap is None:
        raise ValueError("청크 크기와 청크 중복을 입력해주세요.")
    size, overlap = int(chunk_size), int(chunk_overlap)
    if size < MIN_CHUNK_SIZE:
        raise ValueError(f"청크 크기는 {MIN_CHUNK_SIZE} 이상이어야 합니다.")
    # overlap이 size 이상이면 분할기가 오류를 내거나 무한히 겹치게 된다.
    if overlap < 0 or overlap >= size:
        raise ValueError("청크 중복은 0 이상, 청크 크기보다 작아야 합니다.")
    return size, overlap


def load_pdf_to_retriever(pdf_file: str, chunk_size: int, chunk_overlap: int):
    """PDF를 읽어 청크로 분할하고 FAISS 벡터 저장소 기반 retriever를 반환한다."""
    print(f"PDF 파일 로딩 중: {pdf_file}")
    documents = PyPDFLoader(pdf_file).load()  # 페이지마다 Document 1개 (metadata: source, page)
    if not documents:
        raise ValueError("PDF 파일에서 텍스트를 추출할 수 없습니다.")
    print(f"총 {len(documents)}페이지 로드됨")

    # 페이지를 chunk_size 단위로 분할. metadata(source, page)는 청크에 그대로 복사되어 출처 표시에 쓰인다.
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size, chunk_overlap=chunk_overlap, separators=SEPARATORS
    )
    splits = splitter.split_documents(documents)
    print(f"총 {len(splits)}개 청크로 분할됨")

    # 청크를 임베딩해 FAISS에 저장한다. (Upstage 임베딩 API 호출 -> 비용 발생 구간)
    print("FAISS 벡터 저장소 생성 중...")
    vectorstore = FAISS.from_documents(documents=splits, embedding=get_embeddings())
    print("벡터 저장소 생성 완료!")

    # 질문 벡터와 가장 가까운(유사한) 청크 k개를 가져오는 검색기
    return vectorstore.as_retriever(search_type="similarity", search_kwargs={"k": SEARCH_K})


# ---------------------------------------------------------------------------
# 답변 생성 (RAG 체인)
# ---------------------------------------------------------------------------
def format_docs(docs) -> str:
    """검색된 문서를 프롬프트의 context 문자열로 합친다."""
    return "\n\n".join(doc.page_content for doc in docs)


def format_sources(docs) -> str:
    """검색된 문서의 출처(파일명, 페이지)를 중복 없이 번호 목록으로 만든다. (페이지는 1부터 표시)"""
    seen, lines = set(), []
    for doc in docs:
        # source는 업로드 임시 경로이므로 파일명만 표시한다.
        name = os.path.basename(str(doc.metadata.get("source", "Unknown")))
        page = doc.metadata.get("page")
        # PyPDFLoader의 page는 0부터 시작하므로 사용자에게는 +1 해서 보여준다.
        label = f"{name} (Page {page + 1})" if isinstance(page, int) else name
        # 같은 페이지에서 여러 청크가 검색될 수 있으므로 중복 제거
        if label not in seen:
            seen.add(label)
            lines.append(f"[{len(lines) + 1}] {label}")
    return "\n".join(lines)


def generate_answer(retriever, question: str, temperature: float) -> str:
    """검색 1번으로 얻은 문서를 근거로 답변을 만들고, 출처를 덧붙여 반환한다."""
    # 답변 체인: {"docs", "question"} -> context 문자열로 변환 -> 프롬프트 -> LLM -> 문자열
    answer_chain = (
        RunnableLambda(lambda x: {"context": format_docs(x["docs"]), "question": x["question"]})
        | PROMPT
        | get_llm(temperature)
        | StrOutputParser()
    )
    # 같은 질문을 retriever(문서 검색)와 RunnablePassthrough(원본 질문)에 동시에 전달해
    # {"docs", "question"}를 만들고, .assign으로 answer를 추가한다.
    # -> 검색은 1번만 수행하므로 답변과 출처 문서가 항상 일치하고 임베딩 API도 1번만 호출된다.
    chain = RunnableParallel(docs=retriever, question=RunnablePassthrough()).assign(answer=answer_chain)
    result = chain.invoke(question)  # {"docs": [...], "question": "...", "answer": "..."}
    return f"{result['answer']}\n\n{format_sources(result['docs'])}"


def answer_question(question, pdf_file, chunk_size, chunk_overlap, temperature, session):
    """입력을 검증하고 필요하면 벡터 저장소를 만든 뒤 답변한다. (답변 문자열, 갱신된 세션)을 반환."""
    if not pdf_file:
        raise ValueError("PDF 파일을 업로드해주세요.")
    size, overlap = parse_split_options(chunk_size, chunk_overlap)

    # PDF 또는 분할 설정이 바뀐 경우에만 벡터 저장소를 다시 만든다. (임베딩 비용/시간 절약)
    key = (pdf_file, size, overlap)
    if session is None or session.key != key:
        print("새로운 PDF/설정 처리 중...")
        session = RagSession(key=key, retriever=load_pdf_to_retriever(pdf_file, size, overlap))
    else:
        print("기존 벡터 저장소 사용")

    return generate_answer(session.retriever, question, float(temperature)), session


# ---------------------------------------------------------------------------
# Gradio 이벤트 핸들러 / UI
# ---------------------------------------------------------------------------
def respond(message, chat_history, pdf_file, chunk_size, chunk_overlap, temperature, session):
    """질문 처리 이벤트 핸들러. (채팅 기록, 입력창, 세션 상태)를 반환한다.

    인자는 UI의 inputs 리스트 순서와 같고, 반환값은 outputs 리스트 순서와 같다.
    """
    if not message or not message.strip():
        return chat_history, "", session  # 빈 질문은 무시
    try:
        bot_message, session = answer_question(
            message, pdf_file, chunk_size, chunk_overlap, temperature, session
        )
    except Exception as e:  # 검증/API/네트워크 오류를 채팅창에 표시
        print(f"오류: {e}")
        bot_message = f"{ERROR_PREFIX}{e}"

    # Gradio 채팅 기록 형식(dict의 리스트)에 맞춰 사용자/봇 메시지를 추가한다.
    # 입력받은 리스트를 직접 수정하지 않고 새 리스트를 만든다.
    chat_history = chat_history + [
        {"role": "user", "content": message},
        {"role": "assistant", "content": bot_message},
    ]
    return chat_history, "", session  # ""는 입력창 비우기


def create_interface():
    """Gradio 인터페이스를 생성한다."""
    with gr.Blocks(title="PDF 질의응답 시스템") as demo:
        gr.Markdown("# PDF 질의응답 시스템")
        gr.Markdown("PDF 파일을 업로드하고 질문하면 AI가 문서 내용을 바탕으로 답변해드립니다.")

        # 사용자(브라우저 세션)별 상태. 전역 변수와 달리 접속자마다 독립적이라
        # 다른 사용자의 PDF로 답변하는 문제가 없다. 화면에는 보이지 않는다.
        session = gr.State(None)

        with gr.Row():
            # 왼쪽: PDF 업로드 + 고급 설정
            with gr.Column(scale=1):
                pdf_input = PDF(label="PDF 파일 업로드")  # 값은 업로드된 파일의 경로(str)

                with gr.Accordion("고급 설정", open=False):
                    chunk_size = gr.Number(
                        label="청크 크기",
                        value=DEFAULT_CHUNK_SIZE,
                        info="텍스트를 나누는 단위 (500-2000 권장)",
                    )
                    chunk_overlap = gr.Number(
                        label="청크 중복",
                        value=DEFAULT_CHUNK_OVERLAP,
                        info="청크 간 중복되는 문자 수 (50-300 권장)",
                    )
                    temperature = gr.Slider(
                        label="창의성 수준",
                        minimum=0,
                        maximum=1,
                        step=0.1,
                        value=DEFAULT_TEMPERATURE,
                        info="0: 정확성 우선, 1: 창의성 우선",
                    )

            # 오른쪽: 대화창 + 질문 입력
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(label="💬 대화", height=500)
                msg = gr.Textbox(
                    label="질문 입력",
                    placeholder="PDF 내용에 대해 질문해주세요...",
                    lines=2,
                )

                with gr.Row():
                    submit_btn = gr.Button("📤 질문하기", variant="primary")
                    clear_btn = gr.Button("🗑️ 대화 초기화")

        # 예시 질문들
        gr.Markdown("### 질문 예시")
        example_questions = [
            "문서의 주요 내용을 요약해주세요.",
            "이 문서에서 가장 중요한 핵심 사항은 무엇인가요?",
            "문서에 포함된 주요 절차나 단계를 알려주세요.",
        ]
        with gr.Row():
            example_buttons = [gr.Button(q, size="sm") for q in example_questions]

        # 이벤트 연결: inputs의 현재 값이 respond 인자로 순서대로 전달되고,
        # respond의 반환값이 outputs 컴포넌트에 순서대로 들어간다.
        inputs = [msg, chatbot, pdf_input, chunk_size, chunk_overlap, temperature, session]
        outputs = [chatbot, msg, session]
        submit_btn.click(respond, inputs, outputs)  # 버튼 클릭
        msg.submit(respond, inputs, outputs)        # 입력창에서 Enter
        clear_btn.click(lambda: ([], ""), outputs=[chatbot, msg])  # 대화 기록/입력창 비우기

        # 예시 질문 버튼 클릭 시 입력창에 질문 채우기
        # lambda 기본 인자(q=question)로 현재 반복의 값을 고정해야 모든 버튼이 마지막 질문을 쓰는 문제가 없다.
        for question, btn in zip(example_questions, example_buttons):
            btn.click(lambda q=question: q, outputs=msg)

    return demo


# 인터페이스 실행
if __name__ == "__main__":
    require_api_key()  # 키가 없으면 UI를 띄우기 전에 바로 중단
    demo = create_interface()
    demo.launch(share=False, server_name=SERVER_NAME)  # share=False: 외부 공개 링크 생성 안 함
