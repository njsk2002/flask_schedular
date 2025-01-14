
import openai
from pytubefix import YouTube, Channel
#유튜브 영상편집

from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize.chain import load_summarize_chain # 패키지 변경
from langchain_openai import ChatOpenAI
from .authorization_key import Authorization

#필요한 패키지
import re, os, shutil, json



class YoutubeAudio:
        
    @staticmethod
    def get_audio(url):
        yt = YouTube(url)
        audio = yt.streams.filter(only_audio=True).first()
        audio_file = audio.download(output_path=".")
        base, ext = os.path.splitext(audio_file)
        new_audio_file = base + '.mp3'
        shutil.move(audio_file, new_audio_file)
        return new_audio_file

    # 음성 파일 위치를 전달받으면 스크립트를 추출
    @staticmethod
    def get_transcribe(file_path):
        client = Authorization.init_openai() # 호출
        with open(file_path, "rb") as audio_file:           
            transcript = client.audio.transcriptions.create(
                model="whisper-1",
                response_format="text",
                file=audio_file
            )
        return transcript

    # 영어 입력이 들어오면 한글로 번역 및 불렛포인트 요약을 수행
    @staticmethod
    def trans(text):
        client = Authorization.init_openai() # 호출
        response = client.chat.completions.create(
            model="gpt-4",
            messages=[
                {
                    "role": "system",
                    "content": "당신은 영한 번역가이자 요약가입니다. 들어오는 모든 입력을 한국어로 번역하고 불렛 포인트 요약을 사용하여 답변하시오. 반드시 불렛 포인트 요약이어야 합니다."
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )
        return response.choices[0].message.content

    # 유튜브 주소의 형식을 정규표현식(Regex)로 체크하는 함수
    @staticmethod
    def youtube_url_check(url):
        pattern = r'^https:\/\/www\.youtube\.com\/watch\?v=([a-zA-Z0-9_-]+)(\&ab_channel=[\w\d]+)?$'
        match = re.match(pattern, url)
        return match is not None

    ##### 확장 기능 #####

    # 유튜브 채널의 최신/인기 동영상 URL 리스트 가져오기
    @staticmethod
    def get_video_urls(channel_url, sort_by="date", max_videos=100):
        channel = Channel(channel_url)
        videos = channel.video_urls

        if sort_by == "popular":
            videos = sorted(videos, key=lambda url: YouTube(url).views, reverse=True)

        return videos[:max_videos]

    # URL의 동영상 내용을 요약하여 개별 JSON 파일로 저장
    @staticmethod
    def summarize_videos(video_urls):
        for url in video_urls:
            try:
                yt = YouTube(url)
                update_time = yt.publish_date.strftime("%Y%m%d%H%M%S") if yt.publish_date else "unknown"
                video_id = yt.video_id

                # Extract audio
                audio_file = YoutubeAudio.get_audio(url)

                # Transcribe audio
                transcript = YoutubeAudio.get_transcribe(audio_file)

                # Translate and summarize
                summary = YoutubeAudio.trans(transcript)

                # Prepare JSON data
                json_data = {
                    "url": url,
                    "summary": summary,
                    "updatedate": update_time
                }

                # Save to JSON file
                output_file = f"video_imhero_{video_id}_{update_time}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=4)

                print(f"Summary saved to {output_file}")

                # Clean up audio file
                os.remove(audio_file)
    
            except Exception as e:
                print(f"Error processing {url}: {e}")



        