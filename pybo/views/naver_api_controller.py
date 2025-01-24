#import torch
from flask import Flask, request, jsonify, Blueprint,render_template, redirect, url_for, send_file, send_from_directory, Response
from yt_dlp import YoutubeDL
from moviepy.audio.io.AudioFileClip import AudioFileClip
import os, base64
from datetime import datetime
from PIL import Image
import whisper
import json
from ..service.authorization_key import Authorization
from ..service.youtube_trans import YoutubeAudio
from ..service.naver_api import NaverAPI
from ..repository.repositoty_youtube import RepositoryYoutube
from ..repository.repositoty_naverdata import RepositoryNaverData

#bp = Blueprint('naverapi', __name__, url_prefix='/naverapi')
bp = Blueprint(
    'naverapi',
    __name__,
    url_prefix='/naverapi',
    static_folder='../../../bmp_files/iu/',  # 정적 파일 디렉토리
    static_url_path='/naverapi/bmp_files'  # 정적 파일 URL 경로
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
TRANSCRIPT_DIR = os.path.join(BASE_DIR, "transcripts")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

# # GPU 사용 가능 여부 확인 및 Whisper 모델 로드
# DEVICE = "cuda" if torch.cuda.is_available() else "cpu"  # GPU 사용 가능 시 'cuda', 아니면 'cpu'
# model = whisper.load_model("base", device=DEVICE)  # 모델을 GPU/CPU에 로드

Authorization.auth()
# 정적 파일 경로 추가
# BMP 파일 디렉토리 설정
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..','..'))
bmp_dir = os.path.join(BASE_DIR, 'bmp_files/iu')
os.makedirs(bmp_dir, exist_ok=True)  # BMP 파일 디렉토리가 없으면 생성
# bp.add_url_rule('/bmp_files/<path:filename>', endpoint='bmp_files', view_func=bp.send_static_file, defaults={'filename': ''})



@bp.route('/admin_image', methods=['GET', 'POST'])
def admin_image():
    try:
        # 클라이언트에서 요청한 페이지와 항목 수 가져오기
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        
        print(page, per_page)

        # 데이터베이스에서 값 읽기
        result = RepositoryNaverData.read_image_data(
            star_name=None, type_image=None, page=page, per_page=per_page
        )
        data = result.get("data", [])
        total_count = result.get("total_count", 0)

        # 데이터가 없을 경우 처리
        if not data and page == 1:
            return render_template(
                "openai/admin_image_list.html", data=[], message="데이터가 없습니다."
            )
        
        print("data는? :", data, "\n")
        print("페이지는? :", page)
        # 처음 요청은 HTML 템플릿 반환
        if page == 1:
            return render_template(
                "openai/admin_image_list.html", data=data, total_count=total_count
            )
     
        # 이후 요청은 JSON 반환
        return jsonify({
            "data": data,
            "total_count": total_count,
            "page": page,
            "per_page": per_page,
            "has_next": (page * per_page) < total_count,
        })

    except Exception as e:
        print("오류 발생:", e)
        return jsonify({
            "data": [],
            "message": "데이터를 불러오는 중 오류가 발생했습니다.",
            "has_more": False,
        })





# NAVER 이미지 가져오기 및 정보 저장
@bp.route('/generate_image', methods=['GET', 'POST'])
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
    if result is not None: 
       return redirect(url_for('naverapi.admin_image'))

# DB에 저장된 bmp 파일 호출
@bp.route('/get_bmp', methods=['GET', 'POST'])
def get_bmp():
    # 클라이언트에서 요청받은 BMP 파일 이름
    bmp_file = request.json.get("bmp_file")  # 클라이언트에서 파일명 전달
    file_path = f"C:/DavidProject/flask_project/bmp_files/iu/{bmp_file}"  # 서버에서 BMP 파일 경로
    print(bmp_file)

    try:
        # 파일 경로 디버깅용 출력
        print(f"Requested BMP file path: {file_path}")

        # 파일 반환
        return send_file(file_path, mimetype='image/bmp', as_attachment=True)
    except FileNotFoundError:
        # 파일이 없을 경우 에러 반환
        print("BMP 파일을 찾을 수 없습니다.")
        return jsonify({"error": "BMP 파일을 찾을 수 없습니다."}), 404
    except Exception as e:
        # 기타 에러 처리
        print(f"Error: {e}")
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500

@bp.route('/get_namecard', methods=['GET', 'POST'])
def get_namecard():
    # 클라이언트에서 요청받은 BMP 파일 이름
    bmp_file = request.json.get("bmp_file")  # 클라이언트에서 파일명 전달
    file_path = f"C:/DavidProject/flask_project/bmp_files/iu/{bmp_file}"  # 서버에서 BMP 파일 경로
    print(bmp_file)

    try:
        # 파일 경로 디버깅용 출력
        print(f"Requested BMP file path: {file_path}")

        # 파일 반환
        return send_file(file_path, mimetype='image/bmp', as_attachment=True)
    except FileNotFoundError:
        # 파일이 없을 경우 에러 반환
        print("BMP 파일을 찾을 수 없습니다.")
        return jsonify({"error": "BMP 파일을 찾을 수 없습니다."}), 404
    except Exception as e:
        # 기타 에러 처리
        print(f"Error: {e}")
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500


# 정적 파일 경로 추가
@bp.route('/bmp_files/<path:filename>')
def serve_bmp_file(filename):
    # 디버깅용 출력
    file_path = os.path.join(bmp_dir, filename)
    print(f"Requested BMP file: {filename}")
    print(f"Full path to BMP file: {file_path}")

    # 파일 존재 여부 확인
    if not os.path.exists(file_path):
        print("BMP file does not exist.")
        return jsonify({"error": "BMP file not found"}), 404

    try:
        # 파일 반환
        return send_from_directory(bmp_dir, filename, mimetype='image/bmp')
    except Exception as e:
        print(f"Error serving BMP file: {e}")
        return jsonify({"error": "Error serving BMP file"}), 500

# DB에 저장된 UTUBE 리스트 가져오기
@bp.route('/get_video', methods=['get', 'post'])
def get_video(): 
    result = RepositoryYoutube.read_utube_url(star_name=None, type_video=None)
    print(result)
    return jsonify(result)


@bp.route('/generate_vcard')
def generate_vcard():
    photo_base64 = encode_photo_to_base64("C:/DavidProject/flask_project/bmp_files/iu/202411111646288523_t.jpg")
    vcard_data = f"""BEGIN:VCARD
VERSION:3.0
FN:아이유
EMAIL:iu2@icetech.co.kr
TEL:+1234567890
NOTE:안녕하세요! 아이유에요! 만나 뵙게 되어 영광입니다. 2025-01-24일 아이스기술 본사
PHOTO;ENCODING=b;TYPE=JPEG:{photo_base64}
END:VCARD
"""
    return Response(vcard_data, mimetype='text/vcard', headers={"Content-Disposition": "attachment;filename=contact.vcf"})

   #PHOTO;ENCODING=b;TYPE=JPEG:{photo_base64}
    
def encode_photo_to_base64(photo_path):
    with open(photo_path, "rb") as photo_file:
        encoded_photo = base64.b64encode(photo_file.read()).decode("utf-8")
    return encoded_photo

def resize_image(image_path, output_path, size=(300, 300)):
    with Image.open(image_path) as img:
        img.thumbnail(size)
        img.save(output_path, "JPEG")
    

# # 호출 예제
# resize_image("C:/DavidProject/flask_project/bmp_files/iu/202411111646288523_t.jpg", 
#              "C:/DavidProject/flask_project/bmp_files/iu/resized_t.jpg")