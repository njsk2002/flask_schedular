import os, re
import gradio as gr
from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate

#from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
#from langchain_openai import OpenAIEmbeddings
from langchain_community.vectorstores import Weaviate
from langchain_community.vectorstores import Milvus
from langchain_chroma import Chroma
from langchain_community.vectorstores import FAISS



from pdf_chatbot import EconomyBot

#API키 설정
EconomyBot.set_api_key()

with gr.Blocks() as demo:
    with gr.Row():  # Row를 사용해 버튼을 분리하여 배치
        data_learn = gr.Button("데이터 학습")  # 학습 버튼
        clear = gr.Button("대화 초기화")  # 초기화 버튼

    chatbot = gr.Chatbot(label="한국 경제 전망 챗봇", type="messages")
    msg = gr.Textbox(label="질문해주세요!", placeholder="질문을 입력하세요...")


    #EconomyBot.row_data()

    # def respond(message, chat_history):
    #     chat_history.append({"role": "user", "content": message})

    #     bot_message = EconomyBot.get_chat_response(message)
    #     # 채팅 기록에 사용자의 메시지와 봇의 응답을 추가.
    #     #chat_history.append((message, bot_message)) 
    #     chat_history.append({"role": "assistant", "content": bot_message})
    #     return "", chat_history

    def respond(message, chat_history):
        chat_history.append({"role": "user", "content": message})
        print("질문: ", message)
        response = EconomyBot.get_chat_response_free_gpu(message)
        result_summary = response["result"]
        source_details = response["details"]

        # 응답 포맷 구성
        bot_message = f"요약:\n{result_summary}\n\n세부 정보:\n"
        for detail in source_details:
            bot_message += f"출처: {detail['source']} (p.{detail['page']})\n내용: {detail['content']}\n\n"

        # 채팅 기록에 추가
        chat_history.append({"role": "assistant", "content": bot_message})
        return "", chat_history

    def clear_chat():
        return [], ""

    #data_learn.click(EconomyBot.row_data())# 데이터 학습 버튼 ==> 초기화시 row_data()함께 호춝됨
    data_learn.click(lambda: EconomyBot.row_data())  # 함수 참조를 전달

    # 사용자의 입력을 제출(submit)하면 respond 함수가 호출.
    msg.submit(respond, [msg, chatbot], [msg,chatbot])


    #초기화 버튼을 클릭하면 채팅창 초기화
    clear.click(lambda: None, None, chatbot, queue=False )
    #clear.click(clear_chat, outputs=[chatbot])

    

# 인터페이스 실행
demo.launch(debug=True)  

    # #챗봇의 답변을 처리하는 함수
    # def respond(message, chat_histroy):
    #     bot_message = get_chatbot_response(message)