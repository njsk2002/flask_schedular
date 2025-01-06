import streamlit as st
import openai
from pytubefix import YouTube
#유튜브 영상편집

from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize.chain import load_summarize_chain # 패키지 변경
from langchain_openai import ChatOpenAI

#필요한 패키지
import re, os, shutil

from youtube_trans import YoutubeAudio

def main():
    st.set_page_config(page_title="YouTube Summarize", layout="wide")
    #session state 초기화
    utube = YoutubeAudio()
    if "summarize" not in st.session_state:
        st.session_state["summarize"] = ""
    
    #메인 공간
    st.header(" 📽️ YouTube Summarizer")
    st.image('C:/projects/flask_schedular/pybo/static/images/ai.png', width=200)
    youtube_video_url = st.text_input("Please write down the YouTube address. 🖋️",placeholder="https://www.youtube.com/watch?v=**********")
    print("url:" ,youtube_video_url)
    st.markdown('----')

    #url이 실제로 입력되었을 경우
    if len(youtube_video_url) > 2:
        #url이 잘못입력되었을 경우
        if not utube.youtube_url_check(youtube_video_url):
            st.error("YouTube URL을 확인하세요.")
        #URL을 제대로 입력했을 경우
        else:
            #동영상 재생 화면 불러오기
            width = 50
            side = width/2
            _, container, _ = st.columns([side, width, side])
            container.video(data=youtube_video_url)

            #영상 속 자막 추출하기.
            audio_file = utube.get_audio(youtube_video_url)
            transcript = utube.get_transcribe(audio_file)

            st.subheader("Summary Outcome (in English)")
            #언어모델
            llm = ChatOpenAI(
                model_name = "gpt-4o",
                openai_api_key = os.getenv("OPENAI_API_KEY")
            )
            #map prompt 설정 -- 1단계 요약
            prompt = PromptTemplate(
                template="""백틱으로 둘러싸인 전사본을 이용해 해당 유튜브 비디오를 요약해주세요\
                     ```{text}``` 단, 영어로 작성해주세요.
                     """, input_variables = ["text"]
            )

            # combile prompt 설정 -- 2단계 요약에서 사용
            combine_prompt = PromptTemplate(
                template="""백틱으로 둘러싸인 유튜브 스크립트를 모두 조합하여\
                    ```{text}```
                    10문장 내외의 간결한 요챡문을 제공해주세요. 단, 영어로 작성해주세요.
                    """, input_variables =["text"]
            )

            #Langchain을 활용하여 긴글 요약하기
            #긴문서를 문자열 크기 3000을 기준 길이로 하여 분할한다.
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size = 3000,
                chunk_overlap = 0
            )

            #분할된 문서들은 pages라는 문자열 리스트로 저장되어져 있다.
            #ex)
            # pages = ["텍스트1", "텍스트2", "텍스트3", "텍스트4"]
            pages = text_splitter.split_text(transcript)

            #pages를 load_summarize_chain이라는 Langchain 도구에서 처리가능한 형식으로 변환
            #변환 후에는 더이상 문자열이 아닌 Langchain에서  제공한느 타입의 리스트로 변환됨.
            #ex)
            # text = [Document(page_content="텍스트1"), Document(page_content="텍스트2"),
            #         Document(page_content="텍스트3"), Document(page_content="텍스트4")]
            # 이렇게 Langchain에서 원하는 다소 특이한 형태로 변환해주어야 아래에서 처리 가능!

            text = text_splitter.create_documents(pages)

            #위에서 준비한 map_prompt와 combine_prompt를 이용하여 두 단계 요약을 준비.
            chain = load_summarize_chain(
                llm,
                chain_type="map_reduce",
                verbose = False,
                map_prompt=prompt,
                combine_prompt = combine_prompt
            )

            # 두 단계 요약의 결과를 저장

            st.session_state['summarize'] = chain.run(text)
            st.success(st.session_state['summarize'])
            transe = utube.trans(st.session_state['summarize'])
            st.subheader("Final Analysis Result (Reply in Koean)")
            st.info(transe)

if __name__ == "__main__":
    main()
