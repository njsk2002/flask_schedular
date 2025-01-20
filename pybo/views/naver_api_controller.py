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

bp = Blueprint('naverapi', __name__, url_prefix='/naverapi')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
TRANSCRIPT_DIR = os.path.join(BASE_DIR, "transcripts")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

# GPU 사용 가능 여부 확인 및 Whisper 모델 로드
DEVICE = "cuda" if torch.cuda.is_available() else "cpu"  # GPU 사용 가능 시 'cuda', 아니면 'cpu'
model = whisper.load_model("base", device=DEVICE)  # 모델을 GPU/CPU에 로드

Authorization.auth()


@bp.route('/admin_image', methods=['get', 'post'])
def admin_image():
    result = RepositoryNaverData.read_image_data(star_name=None, type_video=None)
    print("결과는: ", result)
    return render_template("openai/admin_naver_list.html", data = result)



# NAVER 이미지 가져오기 및 정보 저장
@bp.route('/generate_image', methods=['get', 'post'])
def generate_image():
    type = request.json.get("request_type") # 검색할 종류 news,blog,image
    key_word = request.json.get('key_word') # 검색 키워드
    print(type, key_word)
    if not key_word:
        return jsonify({"error": "검색할 키워드를 제공해주세요."}), 400
    
    result = NaverAPI.requestNaverAPI(type, key_word)
    
      
    #video_urls = RepositoryNaverData.read_image_data(utube_video, sort_by=sort_by, max_videos=max_video)
    
    # if video_urls is not None:
    #     result = YoutubeAudio.summarize_videos(video_urls)
    print(result)
    return jsonify(result)

# DB에 저장된 UTUBE 리스트 가져오기
@bp.route('/get_video', methods=['get', 'post'])
def get_video(): 
    result = RepositoryYoutube.read_utube_url(star_name=None, type_video=None)
    print(result)
    return jsonify(result)
    
    
