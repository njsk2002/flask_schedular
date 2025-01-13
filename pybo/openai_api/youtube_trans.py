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

# API 키 로드 (환경 변수로 설정)
def load_api_key(filepath):
    with open(filepath) as f:
        file = f.read()
    match = re.search(r"OPENAI_API_KEY = '(.*?)'", file)
    if match:
        api_key = match.group(1)
        os.environ["OPENAI_API_KEY"] = api_key  # 환경 변수에 설정
        # os.environ["OPENAI_API_KEY"]에 API 키를 저장하면 모든 클래스와 함수에서 os.getenv("OPENAI_API_KEY")로 접근할 수 있습니다.
        # 환경 변수는 코드에 직접 API 키를 노출하지 않아 보안이 강화됩니다.
        return api_key
    else:
        raise ValueError("API 키를 찾을 수 없습니다.")

# Whisper 및 OpenAI 클라이언트 초기화 함수
def init_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")  # 환경 변수에서 API 키 읽기
    if not api_key:
        raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
    return openai.OpenAI(api_key=api_key)

# API 키 로드 및 초기화
load_api_key("C:/projects/api_keys/api_keys.txt")
client = init_openai_client()



class YoutubeAudio:
        
    ##### 기본 구현 함수 ######
    # 주소 입력시 유튜브 동영상의 음성(mp3)를 추출하는 함수
    @staticmethod
    def get_audio(url):
        yt = YouTube(url)
        audio = yt.streams.filter(only_audio=True).first()
        audio_file = audio.download(output_path=".")
        base, ext = os.path.splitext(audio_file)
        new_audio_file = base + '.mp3'
        print(f'오리진파일은 {audio_file}이고, base는 {base}이고, ext는 {ext}이고,/n new_audio_file은{new_audio_file}이야')
        shutil.move(audio_file, new_audio_file)
        return new_audio_file

    #음성 파일 위치를 전달받으면 스크립트를 추출
    @staticmethod
    def get_transcribe(file_path):
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
                model = "whisper-1",
                response_format = "text", # response_format을 text로 하면 자막이 아닌 텍스트로 변환
                file = audio_file
            )
        
        return transcript
    
    #영어 입력이 들어오면 한글로 변역 및 불렛포인트 요약을 수행.
    @staticmethod
    def trans(text):
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role" : "system",
                    "content" : "당신은 영한 번역가이자 요약가입니다. 들어오는 모든 입력을 한국어로 번역하고 불렛 포인트 요약을 사용하여 답변하시오. 반드시 불렛 포인트 요약이어야 합니다."
                    },
                {
                    "role" : "user",
                    "content" : text
                }

            ]
        )
        print('response: ', response)
        return response.choices[0].message.content

    #유튜브 주소의 형탤르 정규표현식(Regex)로 체크하는 함수.(선택적 사용)
    @staticmethod
    def youtube_url_check(url):
        pattern = r'^https:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)(\&ab_channel=[\w\d]+)?$'
        match = re.match(pattern, url)
        return match is not None


        