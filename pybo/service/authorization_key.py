import openai
from pytubefix import YouTube
import re, os



class Authorization:
    # API 키 로드 (환경 변수로 설정)   
    @staticmethod
    def auth():
        with open("C:/DavidProject/api_keys/api_keys.txt") as f:
            file = f.read()
        api_key = re.search(r"OPENAI_API_KEY\s*=\s*'(.*?)'", file)
        utube_video = re.search(r"YOUTUBE_VIDEOS\s*=\s*'(.*?)'", file)
        utube_shorts = re.search(r"YOUTUBE_SHORTS\s*=\s*'(.*?)'", file)
        print(api_key ,utube_video ,utube_shorts)
        if api_key and utube_video and utube_shorts:
            os.environ['OPENAI_API_KEY'] = api_key.group(1)
            os.environ['YOUTUBE_VIDEOS'] = utube_video.group(1)
            os.environ['YOUTUBE_SHORTS'] = utube_shorts.group(1)
            print("Key Loaded.")

    # Whisper 및 OpenAI 클라이언트 초기화 함수
    @staticmethod
    def init_openai():      
        api_key = os.getenv("OPENAI_API_KEY")  # 환경 변수에서 API 키 읽기
        if not api_key:
            raise ValueError("OPENAI_API_KEY가 설정되지 않았습니다.")
        return openai.OpenAI(api_key=api_key)
    
    @staticmethod
    def utube_url():
        utube_video = os.getenv("YOUTUBE_VIDEOS")  # 환경 변수에서 API 키 읽기
        utube_shorts = os.getenv("YOUTUBE_SHORTS")  # 환경 변수에서 API 키 읽기
        if not utube_video and utube_shorts:
            raise ValueError("URL 주소가 정상적으로 설정되지 않았습니다.")
        return utube_video,utube_shorts




