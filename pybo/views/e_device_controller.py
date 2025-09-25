import os, functools, time, base64,vobject, urllib, io, struct, threading, zlib
from uuid import uuid4
from datetime import datetime, timedelta
from flask import Blueprint, url_for, render_template, flash, request, session, g , jsonify, current_app, send_from_directory,Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect, secure_filename
from sqlalchemy.exc import SQLAlchemyError
from PIL import Image  # ✅ WEBP 변환을 위해 추가
from pybo import db
from pybo.forms import UserCreateForm, UserLoginForm
from pybo.models import User, NameCard, FileUpload, ShareCard, QRCode, WelcomeData
from ..views.auth_views import login_required
from ..service.image_manageent import ImageManagement
from ..service.bmp_trans import BMPTrans
from ..service.e_mail_sender import EMailSender
from ..service.bmp_to_bytes import BMPToBytes  # 이전에 만든 2bit 패커
from flask import Flask, request, jsonify, send_from_directory
import smtplib

import mimetypes
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email.header import Header
from email import encoders

bp =Blueprint('edevice',__name__,url_prefix='/edevice')


SMTP_SERVER = EMailSender.SMTP_SERVER
SMTP_PORT = EMailSender.SMTP_PORT
EMAIL_SENDER = EMailSender.EMAIL_SENDER
EMAIL_PASSWORD = EMailSender.EMAIL_PASSWORD
# 업로드된 파일을 정적 경로로 서빙


# 업로드 폴더(현재 경로 유지)
# UPLOAD_FOLDER = r"C:/DavidProject/flask_project/bmp_files/아이유/col4_397"
UPLOAD_FOLDER = r"D:/bmp_files"
bp.upload_folder = UPLOAD_FOLDER

@bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(bp.upload_folder, filename)

# ---------------- 캐시 ----------------
_payload_cache = {}
_cache_lock = threading.Lock()

DEFAULT_BMP_FILENAME = "E01_800x480_BWRY.bmp"
PACKED_LEN = 96000 + 4  # 2bit packed(96k) + CRC32(4)


def _safe_device_id(raw: str) -> str:
    """간단 화이트리스트: 영문/숫자/._- 만 허용."""
    if not raw:
        return ""
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in "._-")
    return safe[:64]

def select_bmp_path(device_id: str) -> str:
    """디바이스 전용 파일이 있으면 사용, 없으면 기본 파일."""
    safe_id = _safe_device_id(device_id or "")
    if safe_id:
        cand = os.path.join(bp.upload_folder, f"{safe_id}.bmp")
        cand = os.path.normpath(cand)
        # 업로드 루트 밖으로 나가는 것 방지
        if cand.startswith(os.path.normpath(bp.upload_folder)) and os.path.exists(cand):
            return cand
    return os.path.join(bp.upload_folder, DEFAULT_BMP_FILENAME)

def save_payload_as_header(payload: bytes, out_path: str, array_name: str = "gImage_29"):
    """
    payload (packed 2bit + CRC32) → C header(.h) 파일로 저장
    CRC32(마지막 4바이트)는 제외
    """
    # CRC 제외
    pure = payload[:-4]
    length = len(pure)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write("// Auto-generated from server BMPToBytes\n")
        f.write(f"// Date: {datetime.now().isoformat()}\n\n")
        f.write(f"const unsigned char {array_name}[{length}] = {{\n")

        # 16바이트씩 끊어서 출력
        for i in range(0, length, 16):
            chunk = pure[i:i+16]
            hexes = ",".join(f"0x{b:02X}" for b in chunk)
            f.write("    " + hexes)
            if i + 16 < length:
                f.write(",")
            f.write("\n")

        f.write("};\n")

    current_app.logger.info(f"[BMP] header file saved: {out_path} ({length} bytes, no CRC)")
    return out_path



def _get_payload_cached(filepath: str):
    if not os.path.exists(filepath):
        current_app.logger.warning(f"[BMP] not found: {filepath}")
        return None

    mtime = os.path.getmtime(filepath)
    key = (filepath, int(mtime))

    with _cache_lock:
        hit = _payload_cache.get(key)
        if hit:
            return hit

    # (re)build payload
    payload = BMPToBytes.image_file_to_payload(filepath)
    if not payload:
        current_app.logger.error("[BMP] empty payload")
        return None

    length = len(payload)
    if length != PACKED_LEN:
        current_app.logger.error(f"[BMP] bad payload size {length} (expect {PACKED_LEN})")
        return None

    crc32_le = struct.unpack("<I", payload[-4:])[0]
    version = int(mtime)

    # === NEW: .h 파일로 저장 ===
    header_name = os.path.splitext(os.path.basename(filepath))[0] + ".h"
    header_path = os.path.join(bp.upload_folder, header_name)
    save_payload_as_header(payload, header_path, array_name="gImage_29")

    meta = {
        "payload": payload,
        "length": length,
        "crc32": crc32_le,
        "version": version,
        "filename": os.path.basename(filepath),
        "mtime": int(mtime),
        "header_file": header_path
    }

    with _cache_lock:
        for k in list(_payload_cache.keys()):
            if k[0] == filepath:
                _payload_cache.pop(k)
        _payload_cache[key] = meta

    current_app.logger.info(
        f"[BMP] cache built: {meta['filename']} len={length} crc=0x{crc32_le:08x} ver={version}, header={header_path}"
    )
    return meta

# ---------------- /info ----------------
@bp.route("/info", methods=["GET"])
def device_info():
    device_id = request.args.get("device_id")
    cap       = request.args.get("cap")
    fw        = request.args.get("fw")

    client_ip = request.remote_addr or "unknown"
    ua = request.headers.get("User-Agent", "")

    if not all([device_id, cap, fw]):
        current_app.logger.warning(f"[BAD] {client_ip} missing params id={device_id} cap={cap} fw={fw}")
        return jsonify({"status":"error", "reason":"missing params", "from":client_ip}), 400

    current_app.logger.info(f"[OK] {client_ip} id={device_id} cap={cap} fw={fw} ua='{ua}'")

    bmp_path = select_bmp_path(device_id)
    meta = _get_payload_cached(bmp_path)
    if not meta:
        return jsonify({"status":"error", "reason":"no bmp file"}), 404

    bmp_url = url_for("edevice.send_bmp",
                      device_id=_safe_device_id(device_id),
                      v=meta["version"],
                      _external=True)

    return jsonify({
        "status": "ok",
        "allow_update": True,
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "echo": {"device_id": device_id, "cap": cap, "fw": fw},
        "bmp": {
            "url": bmp_url,                    # 절대 URL(포트 포함)
            "len": meta["length"],             # 96004
            "crc32": f"{meta['crc32']:08x}",  # 참조용
            "ver": meta["version"],           # 파일 mtime 기반
            "file": meta["filename"],
        },
        "from": client_ip
    }), 200

# ---------------- /bmp ----------------
@bp.route("/bmp", methods=["GET"])
def send_bmp():
    device_id = request.args.get("device_id", "")
    _ = request.args.get("v")  # 클라이언트 캐시 힌트(서버에서는 직접 사용 X)

    bmp_path = select_bmp_path(device_id)
    meta = _get_payload_cached(bmp_path)
    if not meta:
        return jsonify({"status":"error", "reason":"no bmp file"}), 404

    # 안전검사(사이즈/CRC)
    if meta["length"] != PACKED_LEN:
        current_app.logger.error(f"[BMP] inconsistent length {meta['length']}")
        return jsonify({"status":"error", "reason":"bad payload len"}), 500

    # 바이너리 응답
    resp = Response(meta["payload"], mimetype="application/octet-stream")
    resp.headers["Content-Length"] = str(meta["length"])
    resp.headers["X-CRC32"] = f"{meta['crc32']:08x}"
    resp.headers["X-Payload-Version"] = str(meta["version"])
    resp.headers["X-Colors"] = "BWR-2bit"
    resp.headers["ETag"] = f'W/"{meta["version"]}-{meta["crc32"]:08x}-{meta["length"]}"'
    resp.headers["Last-Modified"] = datetime.utcfromtimestamp(meta["mtime"]).strftime("%a, %d %b %Y %H:%M:%S GMT")
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Content-Disposition"] = f'attachment; filename="{_safe_device_id(device_id) or "image"}.bin"'

    current_app.logger.info(f"[BMP] send {meta['filename']} → {request.remote_addr} (len={meta['length']})")
    return resp

# def _get_payload_cached(filepath: str):
#     if not os.path.exists(filepath):
#         current_app.logger.warning(f"[BMP] not found: {filepath}")
#         return None

#     mtime = os.path.getmtime(filepath)
#     key = (filepath, int(mtime))

#     with _cache_lock:
#         hit = _payload_cache.get(key)
#         if hit:
#             return hit

#     # (re)build payload
#     payload = BMPToBytes.image_file_to_payload(filepath)  # bytes/bytearray
#     if not payload:
#         current_app.logger.error("[BMP] empty payload")
#         return None

#     length = len(payload)
#     if length != PACKED_LEN:
#         current_app.logger.error(f"[BMP] bad payload size {length} (expect {PACKED_LEN})")
#         return None

#     crc32_le = struct.unpack("<I", payload[-4:])[0]
#     version = int(mtime)  # 파일 갱신 시 자동 변경

#     meta = {
#         "payload": payload,
#         "length": length,
#         "crc32": crc32_le,
#         "version": version,
#         "filename": os.path.basename(filepath),
#         "mtime": int(mtime),
#     }

#     with _cache_lock:
#         # 동일 파일의 이전 캐시 제거
#         for k in list(_payload_cache.keys()):
#             if k[0] == filepath:
#                 _payload_cache.pop(k)
#         _payload_cache[key] = meta

#     current_app.logger.info(f"[BMP] cache built: {meta['filename']} len={length} crc=0x{crc32_le:08x} ver={version}")
#     return meta




# #=== 로그인 되었는지 먼저 확인하는 함수 @login_required 어노테이션으로 사용 가능 ====
# def login_required(view):
#     @functools.wraps(view)
#     def wrapped_view(**kwargs):
#         if g.user is None:
#             return redirect(url_for('auth.login'))
#         return view(**kwargs)
    
#     return wrapped_view

# #=== 로그인 되었을때 session data를 g.user 데이터로 이동/ 다른 class에서 g.user로 login 유무 확인가능 ====
# @bp.before_app_request
# def load_logged_in_user():
#     user_id = session.get('user_id')
#     if user_id is None:
#         g.user = None
#     else:
#         g.user = db.session.query(User).filter_by(userid=user_id).first()
#         print(f"조회된 사용자: {g.user}")  # user 값이 None인지 확인
        
#         if g.user is None:
#             session.pop('user_id', None)  # 세션에 유효하지 않은 ID 제거


########## DEVICE-ESP32  ###################

# @bp.route("/info", methods=["GET"])
# def device_info():
#     device_id = request.args.get("device_id")
#     cap       = request.args.get("cap")
#     fw        = request.args.get("fw")

#     # 실제 요청 보낸 클라이언트 IP (프록시 없다는 가정)
#     client_ip = request.remote_addr or "unknown"
#     ua = request.headers.get("User-Agent", "")

#     # 파라미터 검증
#     if not all([device_id, cap, fw]):
#         current_app.logger.warning(f"[BAD] {client_ip} missing params id={device_id} cap={cap} fw={fw}")
#         return jsonify({"status":"error", "reason":"missing params", "from":client_ip}), 400

#     # 접속 로그 (ESP32 구분: User-Agent)
#     current_app.logger.info(f"[OK] {client_ip} id={device_id} cap={cap} fw={fw} ua='{ua}'")

#     # ESP32 쪽에서 "status":"ok" 확인 후 EPD 업데이트
#     return jsonify({
#         "status": "ok",
#         "allow_update": True,                 # 클라이언트가 검사할 추가 플래그(원하면 사용)
#         "server_time": datetime.now().isoformat(timespec="seconds"),
#         "echo": {"device_id": device_id, "cap": cap, "fw": fw},
#         "from": client_ip
#     }), 200

# # 선택: 헬스체크 엔드포인트
# @bp.route("/health", methods=["GET"])
# def health():
#     return "ok", 200

# # BMP 파일 변환
# @bp.route("/bmp", methods=["GET"])
# def send_bmp():
#     device_id = request.args.get("device_id")
#     if not device_id:
#         return jsonify({"status": "error", "reason": "missing device_id"}), 400

#     # 샘플 파일 경로 (upload된 BMP/PNG 파일 사용)
#     bmp_path = os.path.join(bp.upload_folder, "sample.bmp")

#     if not os.path.exists(bmp_path):
#         return jsonify({"status": "error", "reason": "no bmp file"}), 404

#     payload = BMPTrans.image_file_to_payload(bmp_path)

#     return Response(payload, mimetype="application/octet-stream")