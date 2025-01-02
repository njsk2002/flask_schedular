import os
import urllib.request
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_community.embeddings import OpenAIEmbeddings
from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Weaviate
from langchain_community.vectorstores import Milvus
from langchain_community.vectorstores import Chroma
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 환경 변수 가져오기
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

os.environ['OPENAI_API_KEY'] = OPENAI_API_KEY

#urllib.request.urlretrieve("https://github.com/chatgpt-kr/openai-api-tutorial/raw/main/ch06/2023_%EB%B6%81%ED%95%9C%EC%9D%B8%EA%B6%8C%EB%B3%B4%EA%B3%A0%EC%84%9C.pdf", filename="2023_북한인권보고서.pdf")

loader = PyPDFLoader('./2023_북한인권보고서.pdf')
pages = loader.load_and_split() # 페이지 수 대로 분리
#print('청크의 수: ', len(pages))
#print(pages[1].page_content)

text_split = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=0)
split_docs = text_split.split_documents(pages)
print('분할된 청크의 수: ', len(split_docs))

chunks = [split_doc.page_content for split_doc in split_docs]
print('청크의 최대 길이: ', max(len(chunk) for chunk in chunks))
print('청크의 최소 길이: ', min(len(chunk) for chunk in chunks))

#db = Chroma.from_documents(split_docs, OpenAIEmbeddings()) #메모리에만 저장 
# print('문서의 수: ', db._collection.count())

# print(type(db))

# question = '북한의 교육과정'
# docs = db.similarity_search(question)
# print('문서의 수: ', len(docs))

# for doc in docs:
#     print (doc)
#     print("-----" * 10)

db_to_file = Chroma.from_documents(split_docs, OpenAIEmbeddings(), persist_directory= './chroma_test.db')
print('문서의 수:', db_to_file._collection.count())



db_from_file = Chroma(persist_directory = "./chroma_test.db", embedding_function=OpenAIEmbeddings())
#embedding_function=OpenAIEmbeddings()는 query를 ventor화

question = "북한의 소득 수준"
docs = db_from_file.similarity_search(question)
print(len(docs))

for doc in docs:
    print(doc)
    print('-----------'*10)