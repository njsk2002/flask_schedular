import os, re, csv
import gradio as gr
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate


from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Weaviate
from langchain_community.vectorstores import Milvus
from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS
from langchain.chains.retrieval_qa.base import RetrievalQA
from sentence_transformers import SentenceTransformer, util
from transformers import pipeline
import torch


class EconomyBot:
    @staticmethod
    def set_api_key():

        with open("C:/projects/api_keys/api_keys.txt") as f:
            file = f.read()
        match = re.search(r"OPENAI_API_KEY = '(.*?)'", file)
        if match:
            os.environ['OPENAI_API_KEY'] = match.group(1)
            print("API Key Loaded.")
    
    @staticmethod   
    def row_data():
        print("data 학습 시작 !!")
    #urllib.request.urlretrieve("https://github.com/chatgpt-kr/openai-api-tutorial/raw/main/ch07/2020_%EA%B2%BD%EC%A0%9C%EA%B8%88%EC%9C%B5%EC%9A%A9%EC%96%B4%20700%EC%84%A0_%EA%B2%8C%EC%8B%9C.pdf", filename="2020_경제금융용어 700선_게시.pdf")

        # file_path = "C:/projects/api_keys/economy_rowdata/대외경제정책연구원(KIEP).pdf"
        file_paths = [
            "C:/projects/api_keys/economy_rowdata/대외경제정책연구원(KIEP).pdf",
            "C:/projects/api_keys/economy_rowdata/산업연구원.pdf",
            "C:/projects/api_keys/economy_rowdata/삼일회계법인.pdf",
            "C:/projects/api_keys/economy_rowdata/하나금융연구소.pdf",
            "C:/projects/api_keys/economy_rowdata/한국산업연구원(KIET).pdf",
            "C:/projects/api_keys/economy_rowdata/한화투자증권.pdf",
            "C:/projects/api_keys/economy_rowdata/현대금융연구소.pdf"
        ]

        #PDF 로더로 모든 파일 불러오기
        all_document =[]
        for file_path in file_paths:
            loader = PyPDFLoader(file_path)
            documents = loader.load_and_split()
            #documents = loader.load() # 아래  text_splitter 사용 안함에 따라, 주석처리
            all_document.extend(documents)
        print(len(all_document))
        
        #EconomyBot.save_documents(all_document)
        

        # 텍스트 분할 설정
        # text_splitter = RecursiveCharacterTextSplitter(
        #     chunk_size=1000,  # 조각 크기
        #     chunk_overlap=100  # 조각 간의 겹침
        # )

        
        embedding = OpenAIEmbeddings()

        vectordb = Chroma.from_documents(
            documents = all_document,
            embedding = embedding,
            persist_directory= './economy_2025.db'
        )

        #print("Database saved with ", vectordb._collection.count(), 'documents.')
        print(f"Database saved at: {vectordb._persist_directory}")
        print(f"Number of documents: {len(all_document)}")
        print("===== 학습완료 ======")



    @staticmethod
    def get_chat_response_free(input_text):
        # DB 로드
        db_from_file = Chroma(persist_directory="./economy_2025.db", embedding_function=OpenAIEmbeddings())
        retrievers = db_from_file.as_retriever(search_kwargs={"k": 4})

        # Sentence Transformer 로드 (무료)
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2")

        # Hugging Face 기반 텍스트 생성 모델 로드 (무료)
        text_generator = pipeline("text-generation", model="EleutherAI/gpt-neo-1.3B", device=-1)  # -1: CPU, 0: GPU

        # 검색된 문서 가져오기
        relevant_docs = retrievers.invoke(input_text)
        if not relevant_docs:
            return {"result": "관련된 문서를 찾을 수 없습니다.", "details": []}

        # 컨텍스트 생성 (문서당 최대 300자, 총 1500자 제한)
        max_context_length = 1500
        context = "\n".join([doc.page_content[:300] for doc in relevant_docs])
        context = context[:max_context_length]  # 전체 컨텍스트 길이 제한

        # 프롬프트 생성
        prompt = f"""당신은 2025년 경제를 전망하는 애널리스트입니다.
        질문: {input_text}
        검색 결과:
        {context}

        답변:
        """

        # 텍스트 생성
        try:
            generated_response = text_generator(
                prompt,
                max_new_tokens=300,  # 출력 길이 제한
                truncation=True,  # 입력 자르기 활성화
                num_return_sequences=1
            )[0]["generated_text"]
        except Exception as e:
            print("Text Generation Error:", str(e))
            generated_response = "텍스트 생성 중 오류가 발생했습니다."

        # 요약 및 세부 정보 구성
        source_details = [
            {
                "source": doc.metadata.get("source", "알 수 없음"),
                "page": doc.metadata.get("page", "N/A"),
                "content": doc.page_content[:300]
            } for doc in relevant_docs
        ]

        print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        print("요약내용 : ", generated_response.strip())
        print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        print("세부내용 : ", source_details)
        print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

        # 반환 값 구성
        return {
            "result": generated_response.strip(),
            "details": source_details
        }

    @staticmethod
    def get_chat_response_free_gpu(input_text):
        # Check GPU availability
        device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
        print(f"Device set to use: {device}")

        # Load Sentence Transformer for embedding
        embedding_model = SentenceTransformer("all-MiniLM-L6-v2", device=device)

        # Wrap SentenceTransformer to provide required methods
        embedding_function = CustomEmbeddingFunction(embedding_model)

        # Load database with the correct embedding function
        db_from_file = Chroma(
            persist_directory="./economy_2025.db",
            embedding_function=embedding_function
        )
        retrievers = db_from_file.as_retriever(search_kwargs={"k": 4})

        # Load Hugging Face Model for text generation
        text_generator = pipeline("text-generation", model="EleutherAI/gpt-neo-125M", device=0)

        # Retrieve documents
        relevant_docs = retrievers.get_relevant_documents(input_text)
        if not relevant_docs:
            return {"result": "관련된 문서를 찾을 수 없습니다.", "details": []}

        # Create context (limit 300 chars per document, total 1500 chars)
        max_context_length = 1500
        context = "\n".join([doc.page_content[:300] for doc in relevant_docs])
        context = context[:max_context_length]

        # Create prompt
        prompt = f"""당신은 2025년 경제를 전망하는 애널리스트입니다.
        질문: {input_text}
        검색 결과:
        {context}

        답변:
        """

        # Generate response
        try:
            generated_response = text_generator(
                prompt,
                max_new_tokens=150,
                truncation=True,
                num_return_sequences=1
            )[0]["generated_text"]
        except Exception as e:
            print("Text Generation Error:", str(e))
            generated_response = "텍스트 생성 중 오류가 발생했습니다."

        # Prepare source details
        source_details = [
            {
                "source": doc.metadata.get("source", "알 수 없음"),
                "page": doc.metadata.get("page", "N/A"),
                "content": doc.page_content[:300]
            } for doc in relevant_docs
        ]

        print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        print("요약내용 : ", generated_response.strip())
        print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        print("세부내용 : ", source_details)
        print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

        # Return result
        return {
            "result": generated_response.strip(),
            "details": source_details
        }



    @staticmethod
    def get_chat_response(input_text):
        db_from_file = Chroma(persist_directory = "./economy_2025.db", embedding_function=OpenAIEmbeddings())
        
        # 유사도가 높은 문서 10개만 추출. k = 10
        retrievers = db_from_file.as_retriever(search_kwargs={"k":4})

        # Create Prompt
        template = """당신은 2025년 경제를 전망하는 애널리스트입니다..
        정현수 개발자가 만들었습니다. 주어진 검색 결과를 바탕으로 답변하세요.
        검색을 자세히 해서 관련내용은 친근한 말투로 답변해줘.
        {context}

        Question: {question}
        Answer:
        """

        prompt = PromptTemplate.from_template(template)

        #모델
        llm = ChatOpenAI(
            model_name = "gpt-4",
            temperature= 0
        )

         # 검색 결과 가져오기
        # relevant_docs = retrievers.invoke(input_text)
        # context = "\n".join([doc.page_content[:500] for doc in relevant_docs])  # 각 문서를 500자까지만 포함

        #체인 구성
        qa_chain = RetrievalQA.from_chain_type(
            llm = llm,
            chain_type_kwargs={"prompt" : prompt},
            retriever = retrievers,
            return_source_documents=True
        )

        # 입력값 전달
        try:
            response = qa_chain.invoke({"query": input_text})
        except Exception as e:
            print("Invoke Error:", str(e))
            raise

 
         # 요약 결과
        result_summary = response.get("result", "결과를 찾을 수 없습니다.").strip()

        # 세부 정보
        sources = response.get("source_documents", [])
        source_details = []
        for doc in sources:
            metadata = doc.metadata
            source_info = {
                "source": metadata.get("source", "알 수 없음"),
                "page": metadata.get("page", "N/A"),
                "content": doc.page_content[:500]  # 첫 500자만 포함
            }
            source_details.append(source_info)

        print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")      
        print("요약내용 : ",result_summary)
        print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        print("세부내용 : ",source_details)
        print("++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
        # return response['result'].strip()
        #return response


        # 반환 값 구성
        return {
            "result": result_summary,
            "details": source_details
        }

    

    @staticmethod
    def save_documents(all_document, text_file_path="C:/projects/api_keys/economy_rowdata/documents.txt", csv_file_path="C:/projects/api_keys/economy_rowdata/documents.csv"):
        # 텍스트 파일로 저장
        with open(text_file_path, "w", encoding="utf-8") as txt_file:
            for i, doc in enumerate(all_document):
                txt_file.write(f"Document {i+1}:\n")
                txt_file.write(doc.page_content + "\n")
                txt_file.write("="*80 + "\n")  # 문서 구분을 위한 구분선 추가

        # CSV 파일로 저장
        with open(csv_file_path, "w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(["Document_ID", "Content"])  # 헤더 작성
            for i, doc in enumerate(all_document):
                writer.writerow([f"Document {i+1}", doc.page_content])

        print(f"Documents saved as:\n - Text file: {text_file_path}\n - CSV file: {csv_file_path}")


class CustomEmbeddingFunction:
    def __init__(self, model):
        self.model = model

    def embed_query(self, query):
        # Query embedding using SentenceTransformer
        return self.model.encode(query, convert_to_tensor=True)

    def embed_documents(self, docs):
        # Document embedding using SentenceTransformer
        return [self.model.encode(doc, convert_to_tensor=True) for doc in docs]

