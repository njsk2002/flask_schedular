# controllers/bulletin_controller.py 일부
import os, json, struct, tempfile, itertools, shutil
from datetime import datetime
from flask import Blueprint, request, send_file, jsonify, abort, Response, render_template,current_app
from io import BytesIO
import time, zlib
import numpy as np
from PIL import Image

from ..service.file_translation import FileTranslationWhiteBG, FileTranslationBlackBG
from ..service.image_to_bytes import ImageToBytes

bp = Blueprint("worksheet", __name__, url_prefix="/worksheet")
UPLOADS = {}
JOBS = {}
JOBSEQ = 1000
# 선택한 엔진을 구성 (화이트 배경 모드)
svc = FileTranslationBlackBG(uploads_store=UPLOADS, pdf_dpi=200)
UPLOAD_SEQ = itertools.count(1)

EINK_ASSET_ROOT = r"D:/bmp_files/"  # 디버깅용 BMP 저장 루트
os.makedirs(EINK_ASSET_ROOT, exist_ok=True)

def _safe_device_id(raw: str) -> str:
    return "".join(ch for ch in (raw or "") if ch.isalnum() or ch in "._-")[:64]

def _asset_basename(device_id, w, h, mode):
    return f"{_safe_device_id(device_id)}_{w}x{h}_{mode.upper()}"

def _asset_paths(device_id, w, h, mode):
    """
    디바이스/해상도/모드별 아티팩트 경로 생성
    - .bmp  : 디버깅용 이미지 (사람 눈 확인용)
    - .meta : 최소 메타 정보(JSON)
    - .h    : C 헤더 파일 (CRC 제외, 참고용)
    - .bin  : 최종 전송용 바이너리 (payload 전체, CRC 포함)
    """
    base = _asset_basename(device_id, w, h, mode)
    bmp  = os.path.join(EINK_ASSET_ROOT, base + ".bmp")        # 디버깅용
    meta = os.path.join(EINK_ASSET_ROOT, base + ".meta.json")  # 최소 메타
    hdr  = os.path.join(EINK_ASSET_ROOT, base + ".h")          # (옵션) 헤더
    bin  = os.path.join(EINK_ASSET_ROOT, base + ".bin")        # 전송용 payload
    return bmp, meta, hdr, bin


def _now(): return time.time()


@bp.route('/fileview', methods=['GET', 'POST'])
def file_view():

    return render_template('bulletinboard/e_work_sheet.html')


@bp.route("/preview_blob", methods=["POST"])
def preview_blob():
    """
    파일 포함(multipart) 또는 upload_id(JSON)로 요청 → 처리본/원본 PNG 반환.
    - multipart: file, width,height,mode,scale,percent,rotate,raw(0|1)
      → 헤더 X-Upload-Id 로 신규 upload_id 전달
    - json: {upload_id, width,height,mode,scale,percent,rotate,raw}
    """

    created_id = None

    # --- 1) 파일 새로 들어온 경우 (multipart/form-data) ---
    if request.mimetype and "multipart/form-data" in request.mimetype:
        f = request.files.get("file")
        if not f:
            abort(400, "file missing")

        suffix = os.path.splitext(f.filename or "")[1].lower() or ".bin"
        tmpdir = os.path.join(tempfile.gettempdir(), "eink_uploads")
        os.makedirs(tmpdir, exist_ok=True)
        upload_id = next(UPLOAD_SEQ)
        path = os.path.join(tmpdir, f"{upload_id}{suffix}")
        f.save(path)

        UPLOADS[upload_id] = {"path": path, "pages": 1, "name": f.filename or path}
        created_id = upload_id

        # 파라미터
      
        # width_client   = int(request.form.get("width", 800))
        # height_client  = int(request.form.get("height", 480))

        # if  width_client == 480 and height_client == 800:
        #     width   = height_client
        #     height  = width_client
        # else:
        #     width   = width_client
        #     height  = height_client    
        width   = int(request.form.get("width", 800))
        height  = int(request.form.get("height", 480))
        mode    = request.form.get("mode", "BW")
        scale   = request.form.get("scale", "fit")
        percent = int(request.form.get("percent", 100))
        rotate  = int(request.form.get("rotate", 0))
        raw     = int(request.form.get("raw", 0))

        current_app.logger.info(
            f"[PREVIEW] New upload: id={upload_id}, file={f.filename}, "
            f"saved={path}, size={width}x{height}, mode={mode}, rotate={rotate}, raw={raw}"
        )

    # --- 2) 기존 upload_id 로 재랜더(JSON) ---
    # --- 2) 기존 upload_id 로 재랜더(JSON) ---
    else:
        js = request.get_json(silent=True) or {}
        try:
            upload_id = int(js["upload_id"])
            width  = int(js.get("width", 800))
            height = int(js.get("height", 480))

            # e-ink가 800x480이므로, 480x800 들어오면 800x480으로 정규화
            # if width == 480 and height == 800:
            #     width, height = 800, 480  # ← 로컬 변수만 사용해서 스왑

            mode    = js.get("mode", "BW")
            scale   = js.get("scale", "fit")
            percent = int(js.get("percent", 100))
            rotate  = int(js.get("rotate", 0))   # 기본 0으로 통일 권장
            raw     = int(js.get("raw", 0))

            current_app.logger.info(
                f"[PREVIEW] Re-render: id={upload_id}, size={width}x{height}, "
                f"mode={mode}, rotate={rotate}, raw={raw}"
            )

        except Exception as e:
            abort(400, f"bad body: {e}")


    # --- 3) 미리보기 생성 ---
    if raw:
        im = svc.load_upload_image(upload_id, page=1)
        if rotate in (90, 180, 270):
            im = im.rotate(rotate, expand=True)
        im_preview = svc._place_into_canvas(im, width, height, mode=scale, percent=percent)
        current_app.logger.info(f"[PREVIEW] Raw mode preview generated for upload_id={upload_id}")
    else:
        im_preview = svc.build_preview_image(upload_id, page=1, width=width, height=height,
                                             mode=mode, scale=scale, percent=percent, rotate=rotate)
        current_app.logger.info(f"[PREVIEW] Processed preview generated for upload_id={upload_id}")

    # --- 4) PNG 응답 ---
    bio = BytesIO()
    im_preview.save(bio, format="PNG")
    bio.seek(0)

    resp = send_file(bio, mimetype="image/png")
    if created_id is not None:
        resp.headers["X-Upload-Id"] = str(created_id)

    # 캐시 방지 (브라우저가 이전 이미지 재사용하지 않도록)
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"

    return resp



@bp.route("/sendfile", methods=["POST"])
def send_file_route():
    """
    전송 준비:
    - 프리뷰에서 쓰던 파라미터 그대로 받아 타겟 해상도(W×H)로 배치/양자화
    - 디버깅용 BMP 저장 + 최소 메타(.meta.json) 저장 + (옵션).h 저장
    - (메타에 len/crc/ver/mode/size 저장 → /device/info가 그대로 사용)
    """
    js = request.get_json(silent=True) or {}
    try:
        upload_id = int(js["upload_id"])
        page      = int(js.get("page", 1))
        device_id = js["device_id"]
        mode      = js.get("mode", "BWRY")        # 'BW' | 'BWRY' | 'BWRYBG'  # 2025-09-11 CHANGED
        scale     = js.get("scale", "fit")
        percent   = int(js.get("percent", 100))
        rotate    = int(js.get("rotate", 270))
        width     = int(js.get("width", 800))
        height    = int(js.get("height", 480))

        # e-ink가 800x480이므로, 480x800 들어오면 800x480으로 정규화
        if width == 480 and height == 800:
            width, height = 800, 480  # ← 로컬 변수만 사용해서 스왑

    except Exception as e:
        abort(400, f"bad body: {e}")
    

    # 로그 출력
    current_app.logger.info(
        "[UPLOAD] upload_id=%s | page=%s | device_id=%s | mode=%s | scale=%s | "
        "percent=%s | rotate=%s | width=%s | height=%s",
        upload_id, page, device_id, mode, scale, percent, rotate, width, height
    )

    # (안전) 허용 해상도만 통과: 필요하면 화이트리스트로 제한
    ALLOWED = {(800,480),(480,800), (1600,1200),(1200,1600)}
    if (width, height) not in ALLOWED:
        abort(400, f"unsupported resolution {width}x{height}")

    # 1) 원본 로드 → 배치
    try:
        im_src = svc.load_upload_image(upload_id, page=page)
    except Exception as e:
        abort(404, f"upload not found or render fail: {e}")
    if rotate in (90,180,270):
        im_src = im_src.rotate(rotate, expand=True)
    im_canvas = svc._place_into_canvas(im_src, width, height, mode=scale, percent=percent)

    # 2) 팔레트/디더링 → 전송용 이미지
    mode_up = (mode or "BW").upper()
    if mode_up == "BWRY":
        im_proc = svc.quantize_to_BWRY(im_canvas)
        im_dbg  = im_proc.convert("RGB")
        fmt = "BWRY"
    elif mode_up in ("BWRYBG", "SPECTRA6", "COLOR6"):
        im_proc = svc.quantize_to_BWRYBG(im_canvas)
        im_dbg  = im_proc
        fmt = "BWRYBG"
    else:
        im_proc = svc.quantize_to_BW(im_canvas)
        fmt = "BW"



    print("im_proc.mode =", im_proc.mode)

    # 3) 파일 저장 경로
    bmp_path, meta_path, hdr_path, bin_path = _asset_paths(device_id, width, height, fmt)

    # 4) BMP 저장(디버깅 시각 확인용)
    try:
        im_proc.save(bmp_path, format="BMP")
    except Exception as e:
        abort(500, f"failed to save BMP: {e}")

    # 5) 페이로드(len/crc) 산출 (디바이스 수신 포맷)
    packing_map = {"BW":"1bpp", "BWRY":"2bpp", "BWRYBG":"3bpp"}     # 2025-09-11 NEW
    packing = packing_map.get(fmt, "1bpp")                          # 2025-09-11 CHANGED

    payload = ImageToBytes.image_to_payload(im_proc, fmt, size=(width, height))

    # 🔎 [DEBUG] 팔레트/인덱스 분포 + 첫 16바이트 확인
    if fmt.upper() == "BWRY":
        idx = np.array(im_proc, dtype=np.uint8)
        uniq, cnt = np.unique(idx, return_counts=True)
        # current_app.logger.info(f"first 16 bytes: {arr[:16]}")

    # 5-1) BIN 저장 (payload 전체: CRC 포함)
    try:
        with open(bin_path, "wb") as f:
            f.write(payload)
    except Exception as e:
        abort(500, f"failed to save BIN: {e}")

    raw = payload[:-4]
    arr = np.frombuffer(raw, dtype=np.uint8)
    # current_app.logger.info(f"first 16 bytes: {arr[:16]}")


    raw_len = len(payload) - 4
    crc32_le = struct.unpack("<I", payload[-4:])[0]
    ver = int(os.path.getmtime(bmp_path))  # 파일 mtime을 버전으로


    # 6) (옵션) .h 저장 (CRC 제외)
    try:
        pure = payload[:-4]
        with open(hdr_path, "w", encoding="utf-8") as f:
            f.write("// Auto-generated\n")
            f.write(f"// {datetime.now().isoformat()}\n")
            f.write(f"const unsigned char gImage_payload[{len(pure)}] = {{\n")
            for i in range(0, len(pure), 16):
                chunk = pure[i:i+16]
                f.write("    " + ",".join(f"0x{b:02X}" for b in chunk))
                if i+16 < len(pure): f.write(",")
                f.write("\n")
            f.write("};\n")
    except Exception:
        pass  # 헤더 저장 실패는 치명적이지 않음

    # 7) 최소 메타 저장 (디바이스 /device/info 응답 근거, .bin 추가)

    meta = {
        "device_id": device_id,
        "file": os.path.basename(bmp_path),   # 디버깅 BMP
        "bin":  os.path.basename(bin_path),   # 전송용 BIN
        "width": width, "height": height,
        "mode": fmt,
        "packing": packing,   # 2025-09-11 CHANGED
        "raw_len": raw_len,
        "total_len": raw_len + 4,
        "crc32": f"{crc32_le:08x}",
        "ver": ver,
        "updated_at": datetime.now().isoformat(timespec="seconds")
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # (선택) 최신본 비교/DB 기록은 여기서 처리
    # TODO: DB upsert by (device_id,width,height,mode) with (crc32,ver,total_len,file)

    # 8) 응답
    resp = jsonify({
        "status":"prepared",
        "job_id": int(time.time()*1000),
        "device_id": device_id,
        "file": os.path.basename(bmp_path),
        "meta": meta
    })

    # # 업로드 디렉토리 정리 (성공 시점)
    # upload_dir = UPLOADS.get(upload_id, {}).get("dir")
    # if upload_dir and os.path.isdir(upload_dir):
    #     try:
    #         shutil.rmtree(upload_dir)
    #         UPLOADS.pop(upload_id, None)
    #         current_app.logger.info(f"[CLEANUP] Deleted temp dir {upload_dir}")
    #     except Exception as e:
    #         current_app.logger.warning(f"[CLEANUP] Failed to delete {upload_dir}: {e}")

    # return resp


    # (수정) 업로드 정리: path 기준으로 안전하게 파일만 삭제
    info = UPLOADS.pop(upload_id, None)
    if info:
        path = info.get("path")
        try:
            if path and os.path.isfile(path):
                os.remove(path)
                current_app.logger.info(f"[CLEANUP] Deleted temp file {path}")
        except Exception as e:
            current_app.logger.warning(f"[CLEANUP] Failed to delete {path}: {e}")

    return resp




@bp.route("/calendar")
def calendar_page():
    return render_template("bulletinboard/calendar.html")




# ===== 디바이스용 최소 API =====

# @bp.route("/v1/ping", methods=["HEAD", "GET"])
# def v1_ping():
#     device_id = request.args.get("device_id", "").strip()
#     if not device_id:
#         abort(400)
#     job = JOBS.get(device_id)
#     if not job:
#         resp = Response(status=204)
#         resp.headers["X-Has-Job"] = "0"
#         return resp
#     resp = Response(status=200)
#     resp.headers["X-Has-Job"]   = "1"
#     resp.headers["X-Job-Id"]    = str(job["job_id"])
#     resp.headers["X-Job-Size"]  = str(len(job["payload"]))
#     resp.headers["X-Job-CRC32"] = hex(zlib.crc32(job["payload"]) & 0xFFFFFFFF)
#     return resp

# @bp.route("/v1/job", methods=["GET"])
# def v1_job():
#     device_id = request.args.get("device_id", "").strip()
#     job_id    = int(request.args.get("job_id", "0"))
#     job = JOBS.get(device_id)
#     if not job or job["job_id"] != job_id:
#         abort(404)
#     bio = BytesIO(job["payload"])
#     bio.seek(0)
#     return send_file(bio, mimetype="application/octet-stream")

# @bp.route("/v1/ack", methods=["POST"])
# def v1_ack():
#     js = request.get_json(silent=True) or {}
#     device_id = js.get("device_id", "").strip()
#     job_id    = js.get("job_id")
#     status    = js.get("status", "")
#     if device_id in JOBS and JOBS[device_id]["job_id"] == job_id and status == "ok":
#         JOBS.pop(device_id, None)
#     return jsonify({"ok": True})