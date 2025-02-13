from flask import Flask, request, jsonify, render_template, Blueprint, session, json, send_file
from openai import OpenAI
import uuid
from ..gpt_dalle.gen_story import GenerateStory
import base64
from io import BytesIO
import os 
from gtts import gTTS


bp = Blueprint('openai',__name__,url_prefix='/openai')

# 데이터 저장 경로
DATA_DIR = './story_data'
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# TTS 디렉토리 생성
TTS_DIR = 'C:/DavidProject/flask_project/flask_schedular/tts'
if not os.path.exists(TTS_DIR):
    os.makedirs(TTS_DIR)


@bp.route("/generate_story", methods=["POST"])
def generate_story():
    # 요청 데이터 처리
    data = request.json
    print("data:", data)
    genre = data.get("genre", "")
    user_choice = data.get("user_choice", "")

    # OpenAI 클라이언트 초기화 및 인증
    GenerateStory.auth()
    client = OpenAI()
      # 새로운 UUID 생성
    oid = str(uuid.uuid4())

    # GenerateStory로부터 결과 가져오기
    result = GenerateStory.get_story_and_image(genre, user_choice, client,oid)

    # PIL 이미지 객체를 Base64로 변환
    if "dalle_img" in result:
        dalle_img = result["dalle_img"]
        buffered = BytesIO()
        dalle_img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode('utf-8')
        result["dalle_img"] = f"data:image/png;base64,{img_base64}"  # Base64로 변환된 이미지 데이터

  
    session.setdefault('oid_list', []).append(oid)
    session.modified = True

    # 데이터를 파일로 저장
    with open(os.path.join(DATA_DIR, f"{oid}.json"), 'w') as file:
        json.dump({
            'oid': oid,
            'story_en': result.get('story_en', ''),
            'story_kr': result.get('story_kr', ''),
            'decisionQuestion_kr': result.get('decisionQuestion_kr', ''),
            'decisionQuestion_en': result.get('decisionQuestion_en', ''),
            'choices_en': result.get('choices_en', []),
            'choices_kr': result.get('choices_kr', []),
            'dalle_img': result.get('dalle_img', '')
        }, file)
    print("oid: ", oid)
    # 응답에 UUID 추가

    return jsonify({'oid': oid, **result})


@bp.route("/get_stories", methods=["GET"])
def get_stories():
    # 세션에서 UUID 목록 가져오기
    oid_list = session.get('oid_list', [])

    stories = []
    for oid in oid_list:
        file_path = os.path.join(DATA_DIR, f"{oid}.json")
        if os.path.exists(file_path):
            with open(file_path, 'r') as file:
                stories.append(json.load(file))

    return jsonify({'stories': stories})

@bp.route("/delete_story/<oid>", methods=["DELETE"])
def delete_story(oid):
    """JSON 파일 삭제"""
    file_path = os.path.join('./story_data', f"{oid}.json")
    if os.path.exists(file_path):
        os.remove(file_path)  # 파일 삭제
        return jsonify({"status": "success", "message": f"{oid}.json 파일이 삭제되었습니다."}), 200
    else:
        return jsonify({"status": "error", "message": "파일이 존재하지 않습니다."}), 404


@bp.route('/story_tts/<oid>', methods=['GET'])
def story_tts(oid):
    try:
        # JSON 파일에서 oid에 해당하는 story_en 읽기
        story_file = os.path.join("./story_data", f"{oid}.json")
        if not os.path.exists(story_file):
            return jsonify({"error": "Story not found"}), 404

        with open(story_file, "r") as file:
            story_data = json.load(file)
            story_en = story_data.get("story_en", "No story available")

        # gTTS로 TTS 파일 생성
        tts = gTTS(text=story_en, lang="en")
        tts_path = os.path.join(TTS_DIR, f"{oid}.mp3")
        tts.save(tts_path)

        # 생성된 TTS 파일 URL 반환
        return jsonify({"audio_url": f"openai/tts/{oid}.mp3"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# Static 파일 제공
@bp.route('/tts/<filename>')
def serve_tts(filename):
    print('TTS:', filename)
    try:
        filepath = os.path.join(TTS_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({"error": "File not found"}), 404
        return send_file(filepath, as_attachment=False)
    except Exception as e:
        return jsonify({"error": str(e)}), 500



@bp.route("/save", methods=["POST"])
def save_file():
    data = request.json
    file_type = data.get("type")
    content = data.get("content")
    file_name = f"{uuid.uuid4()}.{file_type}"
    file_path = f"./saved_files/{file_name}"
    with open(file_path, "w") as file:
        file.write(content)
    return jsonify({"message": "File saved", "path": file_path})


