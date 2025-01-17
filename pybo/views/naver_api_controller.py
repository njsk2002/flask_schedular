import torch
from flask import Flask, request, jsonify, Blueprint,render_template
from yt_dlp import YoutubeDL
from moviepy.audio.io.AudioFileClip import AudioFileClip
import os
from datetime import datetime
import whisper
import json
from ..service.authorization_key import Authorization
from ..service.youtube_trans import YoutubeAudio
from ..service.naver_api import NaverAPI
from ..repository.repositoty_youtube import RepositoryYoutube
from ..repository.repositoty_naverdata import RepositoryNaverData

bp = Blueprint('napi', __name__, url_prefix='/napi')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
TRANSCRIPT_DIR = os.path.join(BASE_DIR, "transcripts")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

# GPU 사용 가능 여부 확인 및 Whisper 모델 로드
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"  # GPU 사용 가능 시 'cuda', 아니면 'cpu'
model = whisper.load_model("base", device=DEVICE)  # 모델을 GPU/CPU에 로드

Authorization.auth()


@bp.route('/admin_pic', methods=['get', 'post'])
def admin_video():
    result = RepositoryYoutube.read_utube_url(star_name=None, type_video=None)
    print(result)
    return render_template("openai/admin_naver_list.html", data = result)



# YOUTUBE 영상 요약 및 정보 저장
@bp.route('/generate_image', methods=['get', 'post'])
def generate_image():
    type = request.json.get("request_type") # 검색할 종류 news,blog,image
    key_word = request.json.get('key_word') # 검색 키워드
    print(type, key_word)
    if not key_word:
        return jsonify({"error": "검색할 키워드를 제공해주세요."}), 400
    
    result = NaverAPI.requestNaverAPI(type, key_word)
    
      
    video_urls = RepositoryNaverData.read_naver_data(utube_video, sort_by=sort_by, max_videos=max_video)
    
    if video_urls is not None:
        result = YoutubeAudio.summarize_videos(video_urls)
    print(result)
    return jsonify(result)

# DB에 저장된 UTUBE 리스트 가져오기
@bp.route('/get_video', methods=['get', 'post'])
def get_video(): 
    result = RepositoryYoutube.read_utube_url(star_name=None, type_video=None)
    print(result)
    return jsonify(result)
    
    

@bp.route('/process', methods=['POST'])
def process_youtube():
    youtube_url = request.json.get("youtube_url")
    print(youtube_url)
    if not youtube_url:
        return jsonify({"error": "YouTube URL을 제공해주세요."}), 400

    try:
        # 현재 날짜와 시간 기반으로 파일명 생성
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_output_path = os.path.join(AUDIO_DIR, f"voice_{timestamp}.wav")
        json_output_path = os.path.join(TRANSCRIPT_DIR, f"transcript_{timestamp}.json")
        txt_output_path = os.path.join(TRANSCRIPT_DIR, f"transcript_{timestamp}.txt")

        # YouTube에서 오디오 다운로드
        download_youtube_audio(youtube_url, audio_output_path)

        # Whisper로 텍스트 추출 및 저장
        result = extract_transcript_and_save_whisper(audio_output_path, json_output_path, txt_output_path)

        return jsonify({
            "message": result.get("message", "Process completed"),
            "audio_file": audio_output_path,
            "transcript_json": json_output_path,
            "transcript_txt": txt_output_path
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def download_youtube_audio(youtube_url, output_path):
    """YouTube URL에서 오디오 다운로드 및 정확한 파일명 설정"""
    output_template = os.path.splitext(output_path)[0]
    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': f"{output_template}.%(ext)s",
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'wav',
            'preferredquality': '192',
        }],
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])

    final_file = f"{output_template}.wav"
    if not os.path.exists(final_file):
        raise FileNotFoundError(f"FFmpeg로 변환된 파일이 존재하지 않습니다: {final_file}")

    print(f"다운로드 및 변환된 파일 경로: {final_file}")
    return final_file


def extract_transcript_and_save_whisper(audio_file_path, json_output_path, txt_output_path):
    """Whisper를 사용하여 텍스트 추출 후 JSON과 TXT 파일로 저장"""
    try:
        # Whisper 모델을 사용하여 텍스트 추출
        result = model.transcribe(audio_file_path, fp16=torch.cuda.is_available())
        transcript = result["text"]

        # JSON 파일 저장
        transcript_json = {"transcript": transcript}
        with open(json_output_path, "w", encoding="utf-8") as json_file:
            json.dump(transcript_json, json_file, ensure_ascii=False, indent=4)

        # TXT 파일 저장
        with open(txt_output_path, "w", encoding="utf-8") as txt_file:
            txt_file.write(transcript)

        print(f"JSON 저장 경로: {json_output_path}")
        print(f"TXT 저장 경로: {txt_output_path}")

        return {"message": "Transcript saved successfully."}

    except Exception as e:
        error_message = f"Whisper 처리 중 오류 발생: {e}"

        # JSON과 TXT 파일에 오류 메시지 저장
        error_json = {"error": error_message}
        with open(json_output_path, "w", encoding="utf-8") as json_file:
            json.dump(error_json, json_file, ensure_ascii=False, indent=4)

        with open(txt_output_path, "w", encoding="utf-8") as txt_file:
            txt_file.write(error_message)

        print(f"오류 발생: {error_message} - JSON 및 TXT에 저장됨")
        return {"error": error_message}
