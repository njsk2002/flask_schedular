import os, re
import gradio as gr
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Weaviate
from langchain_community.vectorstores import Milvus
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores import FAISS
#from langchain.chains import RetrievalQA
from langchain.chains.retrieval_qa.base import RetrievalQA



with open("C:/projects/api_keys/api_keys.txt") as f:
    file = f.read()

match = re.search(r"OPENAI_API_KEY = '(.*?)'", file)


if match:
    os.environ['OPENAI_API_KEY'] = match.group(1)

#urllib.request.urlretrieve("https://github.com/chatgpt-kr/openai-api-tutorial/raw/main/ch07/2020_%EA%B2%BD%EC%A0%9C%EA%B8%88%EC%9C%B5%EC%9A%A9%EC%96%B4%20700%EC%84%A0_%EA%B2%8C%EC%8B%9C.pdf", filename="2020_경제금융용어 700선_게시.pdf")

file_path = "./2020_경제금융용어 700선_게시.pdf"
loader = PyPDFLoader(file_path)
texts = loader.load_and_split()

# print('문서의 수', len(texts))

# #0번 문서의 머리말
# print(texts[0].page_content)

# print(texts[5].page_content)

texts = texts[13:] # 목차제거
# print("줄어든 texts의 길이 : ", len(texts))
# print('첫번째문서 출력 : ', texts[0])

texts = texts[:-1]
# print("마지막 데이터 제거 후 texts의 길이: ", len(texts))

# print(texts[-1])


embedding = OpenAIEmbeddings()

vectordb = Chroma.from_documents(
    documents = texts,
    embedding = embedding
)

# 백터 db 개수 확인
print(vectordb._collection.count())

for key in vectordb._collection.get():
    print(key)

#embedding  호출 시도
# result = vectordb._collection.get()['embeddings']
# print(result)  #결과값은 none

embeddings = vectordb._collection.get(include=['embeddings'])['embeddings']
# print('임베딩 백터의 갯수', len(embeddings))

print('첫번째 문서의 임베딩 값 출력: ',embeddings[0])
print('첫번째 문서의 임베딩 값의 길이: ',len(embeddings[0]))

metadatas = vectordb._collection.get()['metadatas']
print('metadatas의 갯수는? ', len(metadatas))
print('첫번째 문서의 출처: ', metadatas[0])

# 유사도가 높은 문서 2개만 추출. k = 2
retrivers = vectordb.as_retriever(search_kwargs={"k":2})
#입력 쿼리에 대해 유사도 기반 검색을 수행할 수 있는 retriever 객체를 반환
#예를 들어, k=2는 입력 쿼리에 대해 유사도가 높은 2개의 문서를 반환

docs = retrivers.get_relevant_documents("비트코인이 궁금해")
# print('유사 문서 개수: ', len(docs))
# print("----"*20)
# print('첫번째 유사 문서: ', docs[0])
# print('두번째 유사 문서:', docs[1])

#  Create Prompt
template = """당신은 한국은행에서 만든 금융 용어를 설명해주는 금융쟁이입니다.
안상준 개발자가 만들었습니다. 주어진 검색 결과를 바탕으로 답변하세요.
검색 결과에 없는 내용이라면 답변할 수 없다고 하세요. 반말로 친근하게 답변하세요.
{context}

Question : {question}
Answer:

"""
prompt = PromptTemplate.from_template(template)

#모델
llm = ChatOpenAI(
    model_name = "gpt-4o",
    temperature= 0
)

#체인 구성
qa_chain = RetrievalQA.from_chain_type(
    llm = llm,
    chain_type_kwargs={"prompt" : prompt},
    retriever = retrivers,
    return_source_documents=True
)

input_text = "디커플링이란 무엇인가?"
chatbot_response = qa_chain.invoke(input_text)
print(chatbot_response)