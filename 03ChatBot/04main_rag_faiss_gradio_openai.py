# poetry add gradio_pdf
# 환경 변수에서 API 키 가져오기
import os
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
print(OPENAI_API_KEY[:5])

# API 키 검증
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다. .env 파일을 확인해주세요.")

# langchain 패키지
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
import gradio as gr

# RAG Chain 구현을 위한 패키지
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS

from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_classic.chains import create_retrieval_chain
#from langchain.chains.combine_documents import create_stuff_documents_chain
#from langchain.chains import create_retrieval_chain

# gradio 인터페이스를 위한 패키지
from gradio_pdf import PDF

# 전역 변수로 벡터 저장소 관리 (성능 향상을 위해)
current_vectorstore = None
current_pdf_path = None

# pdf 파일을 읽어서 벡터 저장소에 저장
def load_pdf_to_vector_store(pdf_file, chunk_size=1000, chunk_overlap=100):
    try:
        print(f"PDF 파일 로딩 중: {pdf_file}")
        
        # PDF 파일 로딩
        loader = PyPDFLoader(pdf_file)
        documents = loader.load()
        
        if not documents:
            raise ValueError("PDF 파일에서 텍스트를 추출할 수 없습니다.")
        
        print(f"총 {len(documents)}페이지 로드됨")

        # 텍스트 분할
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=int(chunk_size), 
            chunk_overlap=int(chunk_overlap),
            separators=["\n\n", "\n", ".", " ", ""]  # 더 자연스러운 분할을 위해
        )
        splits = text_splitter.split_documents(documents)
        print(f"총 {len(splits)}개 청크로 분할됨")

        # 임베딩 모델 생성
        embeddings = OpenAIEmbeddings(api_key=OPENAI_API_KEY, model="text-embedding-3-small")
        
        # FAISS 벡터 저장소 생성 (배치 처리 불필요)
        print("FAISS 벡터 저장소 생성 중...")
        vectorstore = FAISS.from_documents(
            documents=splits, 
            embedding=embeddings
        )
        
        print("벡터 저장소 생성 완료!")
        return vectorstore
        
    except Exception as e:
        print(f"PDF 로딩 중 오류 발생: {str(e)}")
        raise e


# 벡터 저장소에서 문서를 검색하고 답변을 생성
def retrieve_and_generate_answers(vectorstore, message, temperature=0.5):
    try:
        # 검색 성능 향상을 위한 retriever 설정
        retriever = vectorstore.as_retriever(
            search_type="similarity",
            search_kwargs={"k": 6}  # 더 많은 문서 검색
        )

        # 한국어에 최적화된 프롬프트
        system_template = '''다음 문맥을 바탕으로 질문에 정확하게 답변해주세요. 
        문맥에서 관련 정보를 찾을 수 없다면, "제공된 문서에서 해당 정보를 찾을 수 없습니다"라고 답변해주세요.

        <문맥>
        {context}
        </문맥>

        질문: {input}

        답변 규칙:
        1. 문서 내용만을 근거로 답변하세요
        2. 단계별 설명이 필요하면 순서대로 작성하세요  
        3. 구체적인 메뉴명, 버튼명을 포함하세요
        4. 문서에 없는 정보는 "문서에서 찾을 수 없습니다"라고 하세요

        답변:'''

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_template),
            ("human", "{input}")
        ])

        # ChatModel 인스턴스 생성
        model = ChatOpenAI(
            model='gpt-4o-mini', 
            #model='gpt-3.5-turbo', 
            temperature=float(temperature),
            api_key=OPENAI_API_KEY
        )
        print(model.model_name)

        # Prompt와 ChatModel을 Chain으로 연결
        document_chain = create_stuff_documents_chain(model, prompt)

        # Retriever를 Chain에 연결
        rag_chain = create_retrieval_chain(retriever, document_chain)

        # 검색 결과를 바탕으로 답변 생성
        response = rag_chain.invoke({'input': message})
        print(response)

        return response['answer']
        
    except Exception as e:
        return f"답변 생성 중 오류가 발생했습니다: {str(e)}"


# Gradio 인터페이스에서 사용할 함수
def process_pdf_and_answer(message, history, pdf_file, chunk_size, chunk_overlap, temperature):
    global current_vectorstore, current_pdf_path
    
    # 입력 검증
    if not pdf_file:
        return "PDF 파일을 업로드해주세요."
    
    if not message.strip():
        return "질문을 입력해주세요."
    
    try:
        # PDF 파일이 변경되었거나 처음 로드하는 경우에만 벡터 저장소 재생성
        if current_vectorstore is None or current_pdf_path != pdf_file:
            print("새로운 PDF 파일 처리 중...")
            current_vectorstore = load_pdf_to_vector_store(
                pdf_file, chunk_size, chunk_overlap
            )
            current_pdf_path = pdf_file
            print("PDF 처리 완료!")
        else:
            print("기존 벡터 저장소 사용")

        # 답변 생성
        answer = retrieve_and_generate_answers(current_vectorstore, message, temperature)
        
        return answer
        
    except Exception as e:
        error_msg = f"처리 중 오류가 발생했습니다: {str(e)}"
        print(error_msg)
        return error_msg


# Gradio 인터페이스 생성
def create_interface():
    with gr.Blocks(title="PDF 질의응답 시스템") as demo:
        gr.Markdown("# PDF 질의응답 시스템")
        gr.Markdown("PDF 파일을 업로드하고 질문하면 AI가 문서 내용을 바탕으로 답변해드립니다.")
        
        with gr.Row():
            with gr.Column(scale=1):
                pdf_input = PDF(label="PDF 파일 업로드")
                
                with gr.Accordion("고급 설정", open=False):
                    chunk_size = gr.Number(
                        label="청크 크기", 
                        value=1000, 
                        info="텍스트를 나누는 단위 (500-2000 권장)"
                    )
                    chunk_overlap = gr.Number(
                        label="청크 중복", 
                        value=200, 
                        info="청크 간 중복되는 문자 수 (50-300 권장)"
                    )
                    temperature = gr.Slider(
                        label="창의성 수준", 
                        minimum=0, 
                        maximum=1, 
                        step=0.1, 
                        value=0.0,
                        info="0: 정확성 우선, 1: 창의성 우선"
                    )
            
            with gr.Column(scale=2):
                chatbot = gr.Chatbot(label="💬 대화", height=500)
                msg = gr.Textbox(
                    label="질문 입력", 
                    placeholder="PDF 내용에 대해 질문해주세요...",
                    lines=2
                )
                
                with gr.Row():
                    submit_btn = gr.Button("📤 질문하기", variant="primary")
                    clear_btn = gr.Button("🗑️ 대화 초기화")
        
        # 예시 질문들
        gr.Markdown("### 질문 예시")
        example_questions = [
            "문서의 주요 내용을 요약해주세요.",
            "이 문서에서 가장 중요한 핵심 사항은 무엇인가요?",
            "문서에 포함된 주요 절차나 단계를 알려주세요."
        ]
        
        example_buttons = []
        with gr.Row():
            for question in example_questions:
                btn = gr.Button(question, size="sm")
                example_buttons.append(btn)
        
        # 이벤트 처리
        def respond(message, chat_history, pdf_file, chunk_size, chunk_overlap, temperature):
            if not message.strip():
                return chat_history, ""
            
            # 답변 생성
            bot_message = process_pdf_and_answer(
                message, chat_history, pdf_file, chunk_size, chunk_overlap, temperature
            )
            
            # 채팅 히스토리에 추가
            chat_history.append({"role": "user", "content": message})  # 사용자 메시지 추가
            chat_history.append({"role": "assistant", "content": bot_message})  # 봇 응답 추가

            return chat_history, ""
        
        # 버튼 이벤트 연결
        submit_btn.click(
            respond, 
            [msg, chatbot, pdf_input, chunk_size, chunk_overlap, temperature], 
            [chatbot, msg]
        )
        
        msg.submit(
            respond, 
            [msg, chatbot, pdf_input, chunk_size, chunk_overlap, temperature], 
            [chatbot, msg]
        )
        
        clear_btn.click(lambda: ([], ""), outputs=[chatbot, msg])
        
        # 예시 질문 버튼들
        for i, btn in enumerate(example_buttons):
            btn.click(
                lambda q=example_questions[i]: q,
                outputs=msg
            )
    
    return demo

# 인터페이스 실행
if __name__ == "__main__":
    demo = create_interface()
    demo.launch(
        share=False,  # 로컬에서만 실행
        debug=True,   # 디버그 모드
        server_name="127.0.0.1",  # 로컬 접속만 허용
        server_port=7860
    )