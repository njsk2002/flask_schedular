import openai
from pytubefix import YouTube, Channel
#유튜브 영상편집

from langchain.prompts import PromptTemplate
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains.summarize.chain import load_summarize_chain # 패키지 변경
from langchain_openai import ChatOpenAI
from .authorization_key import Authorization
from ..repository.repositoty_youtube import RepositoryYoutube

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
            messages = [
                {
                    "role": "system",
                    "content": (
                        "당신은 유튜브 요약가이자, 어른에게 예의있게 말하는 사람입니다. "
                        "들어오는 유튜브 내용을 임영웅이 직접 말하는 것처럼 재미있고 친근한 말투로 요약하세요. "
                        "요약은 최대 100자 이내로 작성하며, #을 써서 해시태크 처럼 불렛 포인트 형식으로 정리해주세요."
                    )
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


    # 유튜브 채널의 최신/인기 동영상 URL 리스트 가져오기
    @staticmethod
    def get_video_urls(channel_url, sort_by="date", max_videos=100):
        # 채널 객체 생성
        channel = Channel(channel_url)
        videos = channel.videos  # YouTube 객체 리스트 가져오기

        # 인기 동영상 정렬 (조회수 기준)
        if sort_by == "popular":
            videos = sorted(videos, key=lambda yt: yt.views, reverse=True)

        # YouTube 객체에서 URL 문자열 생성
        video_urls = []
        for video in videos[:max_videos]:
            try:
                # 기존과 동일한 URL은 제외
                url = f"https://www.youtube.com/watch?v={video.video_id}"
                

                result = RepositoryYoutube.check_duplication_url(url, update_date = None)
                print(f"중복유무 {url} :", result)
                
                if result == True:  # 중복 안될 경우
                    video_urls.append(f"https://www.youtube.com/watch?v={video.video_id}")

            except AttributeError:
                print(f"Error: video object {video} does not have 'video_id'. Skipping...")

        return video_urls


    # URL의 동영상 내용을 요약하여 개별 JSON 파일로 저장
    @staticmethod
    def summarize_videos(video_urls,star_name = 'imhero', type_video = 'video'):
        for url in video_urls:
            try:
                yt = YouTube(url)
                update_time = yt.publish_date.strftime("%Y%m%d%H%M%S") if yt.publish_date else "unknown"
                video_id = yt.video_id
                video_title = yt.title

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
                    "updatedate": update_time,
                    "videotitle" : video_title
                }

                # Save to JSON file
                output_file = f"video_imhero_{video_id}_{update_time}.json"
                with open(output_file, "w", encoding="utf-8") as f:
                    json.dump(json_data, f, ensure_ascii=False, indent=4)
                
                # db에 정보 저장
                RepositoryYoutube.insert_utube_url(star_name, type_video, output_file, json_data)
                 

                print(f"Summary saved to {output_file}")

                # Clean up audio file
                os.remove(audio_file)
    
            except Exception as e:
                print(f"Error processing {url}: {e}")
        #정보 호출
        result = RepositoryYoutube.read_utube_url(star_name, type_video)
       
        return result
    




        