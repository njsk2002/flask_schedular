# controllers/bulletin_controller.py
import os, json, struct, tempfile, itertools, shutil
from datetime import datetime
from flask import Blueprint, request, send_file, jsonify, abort, Response, render_template, current_app, url_for
from io import BytesIO
import time, zlib
import numpy as np
from PIL import Image, ImageDraw, ImageFont  # ← ImageFont 추가

from ..service.file_translation import FileTranslationWhiteBG, FileTranslationBlackBG
from ..service.image_to_bytes import ImageToBytes

bp = Blueprint("bulletin", __name__, url_prefix="/bulletin")

# ==== In-Memory Stores ====
UPLOADS = {}          # 업로드 파일 (id -> {path, pages, name})
LAYER_STORE = {}      # 레이어 이미지 토큰 저장 (token -> {path, name, mimetype})
JOBS = {}             # (옵션) 디바이스 잡
JOBSEQ = 1000
UPLOAD_SEQ = itertools.count(1)

# 선택한 엔진 (화이트/블랙 배경 모드 중 택1)
svc = FileTranslationBlackBG(uploads_store=UPLOADS, pdf_dpi=200)

# 디버깅용 출력 루트
EINK_ASSET_ROOT = r"D:/bmp_files/"
os.makedirs(EINK_ASSET_ROOT, exist_ok=True)

# 레이어 임시 저장 디렉토리
LAYER_TMP_DIR = os.path.join(tempfile.gettempdir(), "eink_layers")
os.makedirs(LAYER_TMP_DIR, exist_ok=True)

# ===== Helpers =====
def _safe_device_id(raw: str) -> str:
    return "".join(ch for ch in (raw or "") if ch.isalnum() or ch in "._-")[:64]

def _asset_basename(device_id, w, h, mode):
    return f"{_safe_device_id(device_id)}_{w}x{h}_{mode.upper()}"

def _asset_paths(device_id, w, h, mode):
    base = _asset_basename(device_id, w, h, mode)
    bmp  = os.path.join(EINK_ASSET_ROOT, base + ".bmp")        # 디버깅용 BMP
    meta = os.path.join(EINK_ASSET_ROOT, base + ".meta.json")  # 메타
    hdr  = os.path.join(EINK_ASSET_ROOT, base + ".h")          # (옵션) C 헤더
    binp = os.path.join(EINK_ASSET_ROOT, base + ".bin")        # 전송 BIN
    return bmp, meta, hdr, binp

def _now(): return time.time()

def _parse_color(v, default=(0, 0, 0, 255)):
    """'#RRGGBB' 또는 (r,g,b[,a]) 형태를 RGBA 튜플로 변환."""
    if not v:
        return default
    if isinstance(v, (list, tuple)):
        if len(v) == 4: return tuple(v)
        if len(v) == 3: return (v[0], v[1], v[2], 255)
    if isinstance(v, str):
        s = v.strip()
        if s.startswith("#"):
            s = s.lstrip("#")
            if len(s) == 6:
                r = int(s[0:2], 16)
                g = int(s[2:4], 16)
                b = int(s[4:6], 16)
                return (r, g, b, 255)
            if len(s) == 8:
                r = int(s[0:2], 16)
                g = int(s[2:4], 16)
                b = int(s[4:6], 16)
                a = int(s[6:8], 16)
                return (r, g, b, a)
    return default

def _get_font(size_px: int) -> ImageFont.FreeTypeFont:
    """
    한글 지원 폰트를 우선적으로 시도.
    우선순위:
      1) current_app.config['EINK_FONT_PATH'] 또는 ENV 'EINK_FONT_PATH'
      2) OS별 흔한 경로(NotoSansCJK/Nanum/Malgun/Apple SD Gothic/DejaVu)
      3) PIL 기본 폰트
    """
    paths = []
    cfg_path = None
    try:
        cfg_path = current_app.config.get("EINK_FONT_PATH")
    except Exception:
        pass
    env_path = os.environ.get("EINK_FONT_PATH")

    for p in (cfg_path, env_path):
        if p and os.path.isfile(p):
            paths.append(p)

    # Linux
    paths += [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    # Windows
    paths += [
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunsl.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]
    # macOS
    paths += [
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/AppleGothic.ttf",
        "/Library/Fonts/Arial.ttf",
    ]

    for p in paths:
        try:
            if os.path.isfile(p):
                return ImageFont.truetype(p, size_px)
        except Exception:
            continue
    # 마지막 수단(영문 위주)
    return ImageFont.load_default()

def _alpha_composite(base_rgb_or_p, overlay_rgba, xy):
    """base를 RGBA로 변환해 overlay를 합성 후 다시 RGB로."""
    base = base_rgb_or_p.convert("RGBA")
    base.alpha_composite(overlay_rgba, dest=xy)
    return base.convert("RGB")

def _apply_layers_to_image(im, width, height, layers):
    """
    프론트가 1200×1600 절대좌표(BASE) 기준으로 준 레이어를
    현재 타깃 캔버스(width×height)에 스케일링해 합성.

    - signbox: 부모/슬롯 테두리, 라벨 텍스트, 서명선 렌더링
      (프론트에서 넘겨준 L['tpl']의 스타일 파라미터 사용)
      * 라벨/서명선 위치/길이 조정은 L['tpl']의 line_* 비율로 제어
      * 두께/폰트 크기는 해상도 스케일에 맞춰 보정
    - stamp/validity/sign: 업로드된 PNG/JPG를 알파 합성
    """
    if not layers:
        return im

    # BASE 좌표계
    BX, BY = 1200.0, 1600.0
    sx = float(width) / BX
    sy = float(height) / BY
    smin = max(0.5, min(sx, sy))  # 너무 얇아지지 않도록 하한

    base = im.convert("RGBA")
    draw = ImageDraw.Draw(base)

    for L in layers:
        ltype = (L.get("type") or "").lower()

        if ltype == "signbox":
            parent = L.get("parent") or {}
            tpl = L.get("tpl") or {}

            # 스타일(색/두께/폰트)
            border_color = _parse_color(tpl.get("border_color", "#198754"), (25, 135, 84, 220))
            line_color   = _parse_color(tpl.get("line_color",   "#198754"), (25, 135, 84, 220))
            font_color   = _parse_color(tpl.get("font_color",   "#14312d"), (20, 49, 45, 255))
            font_size_px = int(round((tpl.get("font_size_px", 28)) * smin))
            line_thick   = max(1, int(round((tpl.get("line_thickness_px", 2)) * smin)))

            # 서명선 위치/길이(비율)
            baselineY = float(tpl.get("line_pos_ratio", 0.72))      # 슬롯 높이 대비
            hpad      = float(tpl.get("line_hpad_ratio", 0.08))     # 좌우 여백(슬롯 폭 대비)

            # 부모 박스 좌표 (BASE → 타깃)
            px = int(round(parent.get("x", 0) * sx))
            py = int(round(parent.get("y", 0) * sy))
            pw = int(round(parent.get("w", 0) * sx))
            ph = int(round(parent.get("h", 0) * sy))

            # 부모 박스 테두리
            if pw > 0 and ph > 0:
                draw.rectangle([px, py, px + pw, py + ph], outline=border_color, width=max(1, int(round(2 * smin))))

            # 슬롯 그리기
            slots = L.get("slots") or []
            font = _get_font(font_size_px)
            pad  = max(2, int(round(6 * smin)))  # 라벨 패딩

            for S in slots:
                sx_rel = float(S.get("x_rel", 0.0))
                sy_rel = float(S.get("y_rel", 0.0))
                sw_rel = float(S.get("w_rel", 0.0))
                sh_rel = float(S.get("h_rel", 0.0))
                label  = S.get("label") or S.get("role") or ""

                x0 = px + int(round(sx_rel * pw))
                y0 = py + int(round(sy_rel * ph))
                x1 = x0 + int(round(sw_rel * pw))
                y1 = y0 + int(round(sh_rel * ph))

                # 슬롯 테두리
                draw.rectangle([x0, y0, x1, y1], outline=border_color, width=max(1, int(round(1 * smin))))

                # 라벨(슬롯 좌상단)
                if label:
                    try:
                        draw.text((x0 + pad, y0 + pad), label, fill=font_color, font=font)
                    except Exception:
                        # 폰트 문제 시 기본 폰트로 재시도
                        draw.text((x0 + pad, y0 + pad), label, fill=font_color)

                # 서명선 (슬롯 내부 비율 기준)
                sw = x1 - x0
                sh = y1 - y0
                line_y    = y0 + int(round(sh * baselineY))
                line_left = x0 + int(round(sw * hpad))
                line_right= x0 + int(round(sw * (1.0 - hpad)))
                if line_right > line_left:
                    draw.line([(line_left, line_y), (line_right, line_y)], fill=line_color, width=line_thick)

            continue

        if ltype in ("stamp", "validity", "sign"):
            token = L.get("upload_token")
            if not token or token not in LAYER_STORE:
                continue
            path = LAYER_STORE[token]["path"]
            try:
                ov = Image.open(path).convert("RGBA")
            except Exception:
                continue

            x = int(round((L.get("x", 0)) * sx))
            y = int(round((L.get("y", 0)) * sy))
            w = int(round((L.get("w", ov.width)) * sx))
            h = int(round((L.get("h", ov.height)) * sy))
            if w > 0 and h > 0:
                ov = ov.resize((w, h), Image.LANCZOS)
            base.alpha_composite(ov, dest=(x, y))
            continue

        # 기타 타입은 무시

    return base.convert("RGB")

# ===== Routes =====

@bp.route('/fileview', methods=['GET', 'POST'])
def file_view():
    # 템플릿 이름은 프로젝트 구조에 맞게 조정
    return render_template('bulletinboard/e_file_select.html')


@bp.route("/preview_blob", methods=["POST"])
def preview_blob():
    """
    파일 포함(multipart) 또는 upload_id(JSON)로 요청 → 처리본/원본 PNG 반환.
    - multipart: file, width,height,mode,scale,percent,rotate,raw(0|1)
      → 헤더 X-Upload-Id 로 신규 upload_id 전달
    - json: {upload_id, width,height,mode,scale,percent,rotate,raw, layers}
    """
    created_id = None
    layers = []

    # --- 1) 파일 업로드 (최초) ---
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

    # --- 2) 기존 upload_id 재랜더(JSON) ---
    else:
        js = request.get_json(silent=True) or {}
        try:
            upload_id = int(js["upload_id"])
            width  = int(js.get("width", 800))
            height = int(js.get("height", 480))
            mode    = js.get("mode", "BW")
            scale   = js.get("scale", "fit")
            percent = int(js.get("percent", 100))
            rotate  = int(js.get("rotate", 0))
            raw     = int(js.get("raw", 0))
            layers  = js.get("layers") or []

            current_app.logger.info(
                f"[PREVIEW] Re-render: id={upload_id}, size={width}x{height}, "
                f"mode={mode}, rotate={rotate}, raw={raw}, layers={len(layers)}"
            )

        except Exception as e:
            abort(400, f"bad body: {e}")

    # --- 3) 미리보기 생성 ---
    if raw:
        # 원본(placed into canvas) + 레이어 합성
        im = svc.load_upload_image(upload_id, page=1)
        if rotate in (90, 180, 270):
            im = im.rotate(rotate, expand=True)
        im_preview = svc._place_into_canvas(im, width, height, mode=scale, percent=percent)
        im_preview = _apply_layers_to_image(im_preview, width, height, layers)
        current_app.logger.info(f"[PREVIEW] Raw mode preview generated for upload_id={upload_id}")
    else:
        # 처리본 + 레이어 합성
        im_preview = svc.build_preview_image(upload_id, page=1, width=width, height=height,
                                             mode=mode, scale=scale, percent=percent, rotate=rotate)
        im_preview = _apply_layers_to_image(im_preview, width, height, layers)
        current_app.logger.info(f"[PREVIEW] Processed preview generated for upload_id={upload_id}")

    # --- 4) PNG 응답 ---
    bio = BytesIO()
    im_preview.save(bio, format="PNG")
    bio.seek(0)

    resp = send_file(bio, mimetype="image/png")
    if created_id is not None:
        resp.headers["X-Upload-Id"] = str(created_id)

    # 캐시 방지
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@bp.route("/sendfile", methods=["POST"])
def send_file_route():
    """
    전송 준비:
    - 프리뷰에서 쓰던 파라미터 그대로 받아 타깃 해상도(W×H)로 배치/양자화
    - 레이어(layers) 합성 → 디버깅용 BMP/메타/헤더/BIN 저장
    """
    js = request.get_json(silent=True) or {}
    try:
        upload_id = int(js["upload_id"])
        page      = int(js.get("page", 1))
        device_id = js["device_id"]
        mode      = js.get("mode", "BWRY")        # 'BW' | 'BWRY' | 'BWRYBG'
        scale     = js.get("scale", "fit")
        percent   = int(js.get("percent", 100))
        rotate    = int(js.get("rotate", 270))
        width     = int(js.get("width", 800))
        height    = int(js.get("height", 480))
        layers    = js.get("layers") or []

        # 일부 장비 스왑 규칙 유지(필요 시)
        if (width, height) == (480, 800):
            width, height = 800, 480

    except Exception as e:
        abort(400, f"bad body: {e}")

    current_app.logger.info(
        "[UPLOAD] upload_id=%s | page=%s | device_id=%s | mode=%s | scale=%s | "
        "percent=%s | rotate=%s | width=%s | height=%s | layers=%s",
        upload_id, page, device_id, mode, scale, percent, rotate, width, height, len(layers)
    )

    # 허용 해상도 체크
    ALLOWED = {(800,480),(480,800),(1600,1200),(1200,1600)}
    if (width, height) not in ALLOWED:
        abort(400, f"unsupported resolution {width}x{height}")

    # 1) 원본 로드 → 배치
    try:
        im_src = svc.load_upload_image(upload_id, page=page)
    except Exception as e:
        abort(404, f"upload not found or render fail: {e}")

    if rotate in (90, 180, 270):
        im_src = im_src.rotate(rotate, expand=True)

    im_canvas = svc._place_into_canvas(im_src, width, height, mode=scale, percent=percent)

    # 1-1) 레이어 합성
    im_canvas = _apply_layers_to_image(im_canvas, width, height, layers)

    # 2) 팔레트/디더링
    mode_up = (mode or "BW").upper()
    if mode_up == "BWRY":
        im_proc = svc.quantize_to_BWRY(im_canvas)
        fmt = "BWRY"
    elif mode_up in ("BWRYBG", "SPECTRA6", "COLOR6"):
        im_proc = svc.quantize_to_BWRYBG(im_canvas)
        fmt = "BWRYBG"
    else:
        im_proc = svc.quantize_to_BW(im_canvas)
        fmt = "BW"

    # 3) 파일 저장 경로
    bmp_path, meta_path, hdr_path, bin_path = _asset_paths(device_id, width, height, fmt)

    # 4) BMP 저장(디버깅)
    try:
        im_proc.save(bmp_path, format="BMP")
    except Exception as e:
        abort(500, f"failed to save BMP: {e}")

    # 5) 페이로드(BIN)
    packing_map = {"BW":"1bpp", "BWRY":"2bpp", "BWRYBG":"3bpp"}
    packing = packing_map.get(fmt, "1bpp")
    payload = ImageToBytes.image_to_payload(im_proc, fmt, size=(width, height))

    try:
        with open(bin_path, "wb") as f:
            f.write(payload)
    except Exception as e:
        abort(500, f"failed to save BIN: {e}")

    raw_len = len(payload) - 4
    crc32_le = struct.unpack("<I", payload[-4:])[0]
    ver = int(os.path.getmtime(bmp_path))

    # 6) .h (옵션)
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
        pass

    # 7) 메타 저장
    meta = {
        "device_id": device_id,
        "file": os.path.basename(bmp_path),
        "bin":  os.path.basename(bin_path),
        "width": width, "height": height,
        "mode": fmt,
        "packing": packing,
        "raw_len": raw_len,
        "total_len": raw_len + 4,
        "crc32": f"{crc32_le:08x}",
        "ver": ver,
        "updated_at": datetime.now().isoformat(timespec="seconds")
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    # 업로드 파일 정리(파일 단위 제거)
    info = UPLOADS.pop(upload_id, None)
    if info:
        path = info.get("path")
        try:
            if path and os.path.isfile(path):
                os.remove(path)
                current_app.logger.info(f"[CLEANUP] Deleted temp file {path}")
        except Exception as e:
            current_app.logger.warning(f"[CLEANUP] Failed to delete {path}: {e}")

    return jsonify({
        "status": "prepared",
        "job_id": int(time.time()*1000),
        "device_id": device_id,
        "file": os.path.basename(bmp_path),
        "meta": meta
    })


@bp.route("/layer_upload", methods=["POST"])
def layer_upload():
    """
    모달/카드에서 PNG/JPG 업로드 → 토큰 발급 + 미리보기 URL 반환
    응답: { upload_token, preview_url }
    """
    if not (request.mimetype and "multipart/form-data" in request.mimetype):
        abort(400, "multipart/form-data required")

    f = request.files.get("file")
    if not f:
        abort(400, "file missing")

    ext = (os.path.splitext(f.filename or "")[1] or ".png").lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        abort(400, "only .png/.jpg supported")

    token = f"{int(time.time()*1000)}_{os.path.basename(f.filename or 'layer')}"
    # 토큰을 파일명에 쓰므로 경로 안전하게
    safe_token = "".join(ch for ch in token if ch.isalnum() or ch in "._-")[:128]
    out_path = os.path.join(LAYER_TMP_DIR, safe_token)
    f.save(out_path)

    LAYER_STORE[safe_token] = {
        "path": out_path,
        "name": f.filename or safe_token,
        "mimetype": "image/png" if ext == ".png" else "image/jpeg"
    }

    preview_url = url_for("bulletin.layer_img", token=safe_token)
    return jsonify({"upload_token": safe_token, "preview_url": preview_url})


@bp.route("/layer_img/<path:token>", methods=["GET"])
def layer_img(token):
    """업로드된 레이어 이미지를 브라우저 미리보기용으로 제공."""
    info = LAYER_STORE.get(token)
    if not info or not os.path.isfile(info["path"]):
        abort(404)
    return send_file(info["path"], mimetype=info.get("mimetype", "image/png"))


@bp.route("/sign_layout/save_batch", methods=["POST"])
def save_layout_batch():
    """
    카드별 레이아웃(좌표/슬롯 등) 배치 저장.
    body: {"items":[{"device_id":"E01","upload_id":...,"layout":{"canvas":{"w":1200,"h":1600},"layers":[...]}}]}
    파일: D:/bmp_files/layout_<device_id>.json 로 저장
    """
    js = request.get_json(silent=True) or {}
    items = js.get("items") or []
    results = []
    for it in items:
        device_id = _safe_device_id(it.get("device_id", "UNKNOWN"))
        layout = it.get("layout") or {}
        path = os.path.join(EINK_ASSET_ROOT, f"layout_{device_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(layout, f, ensure_ascii=False, indent=2)
            results.append({"device_id": device_id, "saved": True, "path": path})
        except Exception as e:
            results.append({"device_id": device_id, "saved": False, "error": str(e)})

    return jsonify({"ok": True, "saved": results})


@bp.route("/calendar")
def calendar_page():
    return render_template("bulletinboard/calendar.html")


# ===== (옵션) 디바이스용 최소 API 샘플 =====
# 필요시 주석 해제해 사용
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
