import os
import json
import threading
from datetime import datetime

import torch
from flask import request, jsonify, Blueprint, render_template, current_app
from yt_dlp import YoutubeDL

from ..service.authorization_key import Authorization
from ..service.youtube_trans import YoutubeAudio
from ..repository.repositoty_youtube import RepositoryYoutube

bp = Blueprint('utube', __name__, url_prefix='/utube')

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
AUDIO_DIR = os.path.join(BASE_DIR, "audio")
TRANSCRIPT_DIR = os.path.join(BASE_DIR, "transcripts")
os.makedirs(AUDIO_DIR, exist_ok=True)
os.makedirs(TRANSCRIPT_DIR, exist_ok=True)

# ------------------------------------------------------------
# ✅ Lazy init (Whisper model / Authorization)
#   - import 시점에 무거운 작업(whisper.load_model, Authorization.auth) 금지
# ------------------------------------------------------------
_INIT_LOCK = threading.Lock()
_AUTH_READY = False

_MODEL_LOCK = threading.Lock()
_WHISPER_MODEL = None

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"


def ensure_auth_ready():
    """Authorization.auth()를 요청 시점에 1회만 실행"""
    global _AUTH_READY
    if _AUTH_READY:
        return

    with _INIT_LOCK:
        if _AUTH_READY:
            return
        Authorization.auth()
        _AUTH_READY = True
        try:
            current_app.logger.info("[UTUBE] Authorization initialized")
        except Exception:
            pass


def get_whisper_model():
    """
    Whisper 모델을 요청 시점에 1회만 로드
    - 개발 리로더/운영 재시작 시 import 단계 로딩 지연을 없앰
    """
    global _WHISPER_MODEL
    if _WHISPER_MODEL is not None:
        return _WHISPER_MODEL

    with _MODEL_LOCK:
        if _WHISPER_MODEL is not None:
            return _WHISPER_MODEL

        # ✅ 여기서만 whisper import + load_model (무거운 작업)
        import whisper

        # 환경/설정으로 모델명 바꾸고 싶으면 config로 빼도 됨
        model_name = current_app.config.get("WHISPER_MODEL_NAME", "base")
        _WHISPER_MODEL = whisper.load_model(model_name, device=DEVICE)

        try:
            current_app.logger.info(f"[UTUBE] Whisper model loaded: {model_name} on {DEVICE}")
        except Exception:
            pass

        return _WHISPER_MODEL


@bp.route('/admin_video', methods=['GET', 'POST'])
def admin_video():
    ensure_auth_ready()
    result = RepositoryYoutube.read_utube_url(star_name=None, type_video=None)
    return render_template("openai/admin_utube_list.html", data=result)


@bp.route('/generate_video', methods=['GET', 'POST'])
def generate_video():
    ensure_auth_ready()

    utube_video, utube_shorts = Authorization.utube_url()
    sort_by = "date"    # 또는 "popular"
    max_video = 5       # 검색 비디오수

    if not utube_video:
        return jsonify({"error": "YOUTUBE URL을 읽지 못함"}), 400

    video_urls = YoutubeAudio.get_video_urls(utube_video, sort_by=sort_by, max_videos=max_video)
    if video_urls is None:
        return jsonify({"error": "video url 목록을 가져오지 못함"}), 500

    result = YoutubeAudio.summarize_videos(video_urls)
    return jsonify(result)


@bp.route('/get_video', methods=['GET', 'POST'])
def get_video():
    ensure_auth_ready()
    result = RepositoryYoutube.read_utube_url(star_name=None, type_video=None)
    return jsonify(result)


@bp.route('/process', methods=['POST'])
def process_youtube():
    ensure_auth_ready()

    youtube_url = (request.json or {}).get("youtube_url")
    if not youtube_url:
        return jsonify({"error": "YouTube URL을 제공해주세요."}), 400

    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        audio_output_path = os.path.join(AUDIO_DIR, f"voice_{timestamp}.wav")
        json_output_path = os.path.join(TRANSCRIPT_DIR, f"transcript_{timestamp}.json")
        txt_output_path = os.path.join(TRANSCRIPT_DIR, f"transcript_{timestamp}.txt")

        # YouTube에서 오디오 다운로드
        final_audio = download_youtube_audio(youtube_url, audio_output_path)

        # Whisper로 텍스트 추출 및 저장
        result = extract_transcript_and_save_whisper(final_audio, json_output_path, txt_output_path)

        return jsonify({
            "message": result.get("message", "Process completed"),
            "audio_file": final_audio,
            "transcript_json": json_output_path,
            "transcript_txt": txt_output_path
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def download_youtube_audio(youtube_url, output_path):
    """YouTube URL에서 오디오 다운로드 및 wav 변환"""
    output_template = os.path.splitext(output_path)[0]
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": f"{output_template}.%(ext)s",
        "postprocessors": [{
            "key": "FFmpegExtractAudio",
            "preferredcodec": "wav",
            "preferredquality": "192",
        }],
        # 필요하면 여기서 quiet/logging 옵션도 조절 가능
    }

    with YoutubeDL(ydl_opts) as ydl:
        ydl.download([youtube_url])

    final_file = f"{output_template}.wav"
    if not os.path.exists(final_file):
        raise FileNotFoundError(f"FFmpeg로 변환된 파일이 존재하지 않습니다: {final_file}")

    try:
        current_app.logger.info(f"[UTUBE] Downloaded audio: {final_file}")
    except Exception:
        pass

    return final_file


def extract_transcript_and_save_whisper(audio_file_path, json_output_path, txt_output_path):
    """Whisper로 텍스트 추출 후 JSON/TXT 저장"""
    try:
        model = get_whisper_model()

        # fp16은 cuda일 때만 의미가 있음
        use_fp16 = (DEVICE == "cuda")
        result = model.transcribe(audio_file_path, fp16=use_fp16)
        transcript = (result or {}).get("text", "")

        transcript_json = {"transcript": transcript}
        with open(json_output_path, "w", encoding="utf-8") as json_file:
            json.dump(transcript_json, json_file, ensure_ascii=False, indent=4)

        with open(txt_output_path, "w", encoding="utf-8") as txt_file:
            txt_file.write(transcript)

        try:
            current_app.logger.info(f"[UTUBE] Transcript saved: {json_output_path}")
        except Exception:
            pass

        return {"message": "Transcript saved successfully."}

    except Exception as e:
        error_message = f"Whisper 처리 중 오류 발생: {e}"

        error_json = {"error": error_message}
        with open(json_output_path, "w", encoding="utf-8") as json_file:
            json.dump(error_json, json_file, ensure_ascii=False, indent=4)

        with open(txt_output_path, "w", encoding="utf-8") as txt_output:
            txt_output.write(error_message)

        try:
            current_app.logger.exception("[UTUBE] Whisper failed")
        except Exception:
            pass

        return {"error": error_message}
