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

bp = Blueprint('naverapi', __name__, url_prefix='/naverapi')
# bp = Blueprint(
#     'naverapi',
#     __name__,
#     url_prefix='/naverapi',
#     static_folder='../../../bmp_files/iu/',  # 정적 파일 디렉토리
#     static_url_path='/naverapi/bmp_files'  # 정적 파일 URL 경로
# )

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
        # 요청 정보 출력 (디버깅용)
        print("=== [DEBUG] 클라이언트 요청 정보 ===")
        print("Headers:", request.headers)
        print("Accept Mimetypes:", request.accept_mimetypes)
        print("Request Method:", request.method)
        print("Request Args:", request.args)

        # 클라이언트에서 요청한 페이지와 항목 수 가져오기
        page = int(request.args.get('page', 1))
        per_page = int(request.args.get('per_page', 10))
        key_word = request.args.get('key_word', None)

        print(f"[INFO] 요청 받은 페이지: {page}, 페이지당 항목 수: {per_page}, key_word: {key_word}")

        # 데이터베이스에서 값 읽기
        result = RepositoryNaverData.read_image_data(
           key_word=key_word, type_image=None, page=page, per_page=per_page
        )
        data = result.get("data", [])
        total_count = result.get("total_count", 0)
        unique_key = result.get("unique_key", [])

        # 데이터가 없는 경우 처리
        if not data and page == 1:
            print("[WARN] 데이터 없음: 첫 페이지 요청")
            if request.accept_mimetypes['application/json'] >= request.accept_mimetypes['text/html']:
                return jsonify({"data": [], "message": "데이터가 없습니다.", "has_more": False})
            else:
                return render_template("openai/e_image.html", data=[], message="데이터가 없습니다.")

        print(f"[INFO] 불러온 데이터 개수: {len(data)}")
        print(f"[INFO] 총 데이터 개수: {total_count}")
        print(f"[INFO] 현재 페이지: {page}")
        print("uniquedata: ", unique_key)

        # Accept 헤더의 우선순위를 비교하여 JSON 응답을 우선하도록 처리
        if request.accept_mimetypes['application/json'] >= request.accept_mimetypes['text/html']:
            return jsonify({
                "data": data,
                "total_count": total_count,
                "unique_key": unique_key,
                "page": page,
                "per_page": per_page,
                "has_next": (page * per_page) < total_count,
            })
        else:
            return render_template("openai/e_image.html", data=data, total_count=total_count, unique_key=unique_key)

    except Exception as e:
        print("[ERROR] 오류 발생:", e)
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



@bp.route('/get_bmp', methods=['GET', 'POST'])
def get_bmp():
    # 요청 데이터 처리 (POST와 GET을 통합)
    if request.method == 'POST':
        data = request.get_json()
    else:
        data = request.args

    bmp_file_param = data.get("bmp_file", "").strip()
    key_word = data.get("key_word", "").strip()

    print(f"DEBUG: 요청 메서드={request.method}, key_word={key_word}, bmp_file_param={bmp_file_param}")

    # 쿼리 스트링 제거 (예: "file.bmp?t=123456")
    bmp_file = bmp_file_param.split('?')[0] if '?' in bmp_file_param else bmp_file_param

    print("DEBUG: bmp_file =", bmp_file)
    print("DEBUG: key_word =", key_word)

    # 필수 파라미터 확인
    if not bmp_file or not key_word:
        print("ERROR: bmp_file 또는 key_word 파라미터가 누락되었습니다.")
        return jsonify({"error": "bmp_file 및 key_word 파라미터가 필요합니다."}), 400

    # 파일명을 기반으로 폴더 이름 추출
    parts = bmp_file.split('_')
    if len(parts) < 2:
        print("ERROR: bmp_file 형식이 올바르지 않습니다.")
        return jsonify({"error": "유효한 bmp_file 이름이 아닙니다."}), 400

    folder_name = '_'.join(parts[:2])
    print(f"DEBUG: 추출된 폴더 이름: {folder_name}")

    # 최종 BMP 파일 경로 생성
    base_path = os.path.join("C:/DavidProject/flask_project/bmp_files", key_word, folder_name)
    file_path = os.path.join(base_path, bmp_file)

    print(f"DEBUG: 최종 BMP 파일 경로: {file_path}")

    # 파일 존재 여부 확인 후 처리
    if not os.path.exists(file_path):
        print("ERROR: BMP 파일을 찾을 수 없습니다.")
        return jsonify({"error": "BMP 파일을 찾을 수 없습니다."}), 404

    try:
        response = send_file(file_path, mimetype='image/bmp', as_attachment=(request.method == 'GET'))
        
        # 캐싱 방지 헤더 추가
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        return response

    except Exception as e:
        print(f"ERROR: Exception occurred: {e}")
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
    photo_base64 = encode_photo_to_base64("C:/DavidProject/flask_project/flask_schedular/uploads/2_6114c7ee.png")
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