# controllers/bulletin_controller.py
import os, json, struct, tempfile, itertools
from datetime import datetime
from flask import Blueprint, request, send_file, jsonify, abort, Response, render_template, current_app, url_for, g, session
from io import BytesIO
import time
from PIL import Image, ImageDraw, ImageFont  # ← 중복 import 정리

from ..service.file_translation import FileTranslationWhiteBG, FileTranslationBlackBG
from ..service.image_to_bytes import ImageToBytes

# Repository (옵셔널)
try:
    from ..repository.repository_eink import RepositoryEINK
except Exception:
    RepositoryEINK = None  # DB 미사용 환경 지원

bp = Blueprint("bulletin", __name__, url_prefix="/bulletin")

# ==== In-Memory Stores ====
UPLOADS = {}          # 업로드 파일 (id -> {path, pages, name})
LAYER_STORE = {}      # 레이어 이미지 토큰 저장 (token -> {path, name, mimetype})
JOBS = {}
JOBSEQ = 1000
UPLOAD_SEQ = itertools.count(1)

# 선택한 엔진
svc = FileTranslationBlackBG(uploads_store=UPLOADS, pdf_dpi=200)

# 저장 루트
EINK_ASSET_ROOT = r"D:/bmp_files/"
os.makedirs(EINK_ASSET_ROOT, exist_ok=True)
os.makedirs(os.path.join(EINK_ASSET_ROOT, "uploads"), exist_ok=True)   # 전결/비결재
os.makedirs(os.path.join(EINK_ASSET_ROOT, "proceed"), exist_ok=True)   # 검토 대기
os.makedirs(os.path.join(EINK_ASSET_ROOT, "checked"), exist_ok=True)   # 승인 대기(검토 완료)
os.makedirs(os.path.join(EINK_ASSET_ROOT, "updates"), exist_ok=True)   # 승인 완료

# 레이어 임시 저장 디렉토리
LAYER_TMP_DIR = os.path.join(tempfile.gettempdir(), "eink_layers")
os.makedirs(LAYER_TMP_DIR, exist_ok=True)

# ===== Debug Helpers =====
def _dump_json(obj, max_len=800):
    try:
        s = json.dumps(obj, ensure_ascii=False)
        return (s[:max_len] + "...") if len(s) > max_len else s
    except Exception:
        return str(obj)

def _dbg(tag: str, **kw):
    try:
        parts = [f"{k}={_dump_json(v)}" for k, v in kw.items()]
        current_app.logger.debug(f"[{tag}] " + " ".join(parts))
    except Exception:
        current_app.logger.debug(f"[{tag}] <log-failed>")

def _req_info():
    try:
        return {
            "path": request.path,
            "method": request.method,
            "mimetype": request.mimetype,
            "content_length": request.content_length,
            "args": request.args.to_dict(flat=True),
            "remote_addr": request.remote_addr,
            "user_agent": str(getattr(request, "user_agent", "")),
            "user_id": getattr(request, "user_id", None),
        }
    except Exception:
        return {}

# ===== Auth/Layer Helpers =====
def _current_user_id():
    """
    현재 로그인된 사용자 ID를 반환.
    우선순위:
      1. g.user.no (SQLAlchemy User 객체)
      2. session["userid"] → User.userid 매칭
      3. request.user_id (컨트롤러나 API에서 임시 지정)
    """
    # 1️⃣ g.user.no (Flask 로그인 시 로드됨)
    if getattr(g, "user", None) is not None and getattr(g.user, "no", None) is not None:
        return int(g.user.no)

    # 2️⃣ session["userid"] → User.userid (문자열일 수 있음)
    if "userid" in session:
        val = session.get("userid")
        if isinstance(val, (int, str)) and str(val).strip():
            return val if not str(val).isdigit() else int(val)

    # 3️⃣ request.user_id (e.g., API 인증 미들웨어에서 지정)
    if getattr(request, "user_id", None):
        try:
            return int(request.user_id)
        except Exception:
            return str(request.user_id)

    return None

def _bind_sign_layer_user(layers):
    """sign 레이어에 user_id가 비어 있으면 로그인 유저로 주입"""
    uid = _current_user_id()
    if not layers or not uid:
        return layers
    for L in layers:
        if (L.get("type") or "").lower() == "sign" and not L.get("user_id"):
            L["user_id"] = uid
    return layers

def _log_layers(layers, where):
    try:
        types = [(i, (L.get("type") or "").lower()) for i, L in enumerate(layers or [])]
        sample = []
        for i, L in list(enumerate(layers or []))[:2]:
            sample.append({
                "idx": i,
                "type": (L.get("type") or "").lower(),
                "has_token": bool(L.get("upload_token")),
                "user_id": L.get("user_id"),
                "parent": L.get("parent") if (L.get("type") or "").lower()=="signbox" else None,
                "slots": len(L.get("slots") or []) if (L.get("type") or "").lower()=="signbox" else None,
                "x": L.get("x"), "y": L.get("y"), "w": L.get("w"), "h": L.get("h"),
            })
        _dbg("apply_layers:summary", where=where, count=len(layers or []), types=types, sample=sample)
    except Exception as e:
        _dbg("apply_layers:summary", where=where, error=str(e))

# ===== Helpers =====
def _safe_device_id(raw: str) -> str:
    return "".join(ch for ch in (raw or "") if ch.isalnum() or ch in "._-")[:64]

def _asset_basename(device_id, w, h, mode):
    return f"{_safe_device_id(device_id)}_{w}x{h}_{mode.upper()}"

def _decide_target_dir(need_approval: bool, final_approval: bool) -> str:
    out = "uploads" if (final_approval or (not need_approval)) else "proceed"
    _dbg("decide_target_dir", need_approval=need_approval, final_approval=final_approval, decided=out)
    return out

def _asset_paths(device_id, w, h, mode, target_dir="uploads"):
    base = _asset_basename(device_id, w, h, mode)
    root = os.path.join(EINK_ASSET_ROOT, target_dir)
    bmp  = os.path.join(root, base + ".bmp")
    meta = os.path.join(root, base + ".meta.json")
    hdr  = os.path.join(root, base + ".h")
    binp = os.path.join(root, base + ".bin")
    _dbg("asset_paths", device_id=device_id, size=f"{w}x{h}", mode=mode, target_dir=target_dir, bmp=bmp, bin=binp, meta=meta, hdr=hdr)
    return bmp, meta, hdr, binp

def _parse_color(v, default=(0, 0, 0, 255)):
    if not v:
        return default
    if isinstance(v, (list, tuple)):
        if len(v) == 4: return tuple(v)
        if len(v) == 3: return (v[0], v[1], v[2], 255)
    if isinstance(v, str):
        s = v.strip().lstrip("#")
        if len(s) == 6:
            r,g,b = int(s[0:2],16), int(s[2:4],16), int(s[4:6],16)
            return (r,g,b,255)
        if len(s) == 8:
            r,g,b,a = int(s[0:2],16), int(s[2:4],16), int(s[4:6],16), int(s[6:8],16)
            return (r,g,b,a)
    return default

def _get_font(size_px: int) -> ImageFont.FreeTypeFont:
    _dbg("get_font:start", size_px=size_px)
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
                _dbg("get_font:try_path", path=p)
                return ImageFont.truetype(p, size_px)
        except Exception:
            current_app.logger.debug("[get_font] truetype failed", exc_info=True)
            continue
    _dbg("get_font:fallback_default")
    return ImageFont.load_default()

def _load_user_sign_rgba(user_id: int):
    _dbg("load_user_sign:start", user_id=user_id)
    if RepositoryEINK is None or not user_id:
        _dbg("load_user_sign:skip", reason="no_repo_or_userid")
        return None
    try:
        path = RepositoryEINK.get_user_sign_path(int(user_id))
        _dbg("load_user_sign:path", path=path)

        # ★ 상대경로 → 절대경로로 보정
        if path and not os.path.isabs(path):
            base = current_app.config.get("SIGN_BASE_DIR")
            if base:
                path = os.path.join(base, path)
                _dbg("load_user_sign:resolved", resolved_path=path)

        # 존재 확인 & 로드
        if path and os.path.isfile(path):
            img = Image.open(path).convert("RGBA")
            _dbg("load_user_sign:loaded", size=f"{img.width}x{img.height}")
            return img
        else:
            _dbg("load_user_sign:missing", checked_path=path)
    except Exception:
        current_app.logger.debug("[load_user_sign] failed", exc_info=True)
        return None
    return None


def _apply_layers_to_image(im, width, height, layers):
    _dbg("apply_layers:start", width=width, height=height, layers=len(layers or []))
    if not layers:
        return im
    BX, BY = 1200.0, 1600.0
    sx = float(width) / BX
    sy = float(height) / BY
    smin = max(0.5, min(sx, sy))
    base = im.convert("RGBA")
    draw = ImageDraw.Draw(base)

    for idx, L in enumerate(layers or []):
        ltype = (L.get("type") or "").lower()
        _dbg("apply_layers:item", idx=idx, type=ltype)

        if ltype == "signbox":
            parent = L.get("parent") or {}
            tpl = L.get("tpl") or {}
            border_color = _parse_color(tpl.get("border_color", "#198754"), (25,135,84,220))
            line_color   = _parse_color(tpl.get("line_color",   "#198754"), (25,135,84,220))
            font_color   = _parse_color(tpl.get("font_color",   "#14312d"), (20,49,45,255))
            font_size_px = int(round((tpl.get("font_size_px", 28)) * smin))
            line_thick   = max(1, int(round((tpl.get("line_thickness_px", 2)) * smin)))
            baselineY = float(tpl.get("line_pos_ratio", 0.72))
            hpad      = float(tpl.get("line_hpad_ratio", 0.08))
            _dbg("apply_layers:signbox_tpl", font_size_px=font_size_px, line_thick=line_thick, baselineY=baselineY, hpad=hpad)

            px = int(round(parent.get("x", 0) * sx))
            py = int(round(parent.get("y", 0) * sy))
            pw = int(round(parent.get("w", 0) * sx))
            ph = int(round(parent.get("h", 0) * sy))
            _dbg("apply_layers:signbox_parent", px=px, py=py, pw=pw, ph=ph)
            if pw > 0 and ph > 0:
                draw.rectangle([px, py, px + pw, py + ph], outline=border_color, width=max(1, int(round(2 * smin))))
            slots = L.get("slots") or []
            font = _get_font(font_size_px)
            pad  = max(2, int(round(6 * smin)))

            for sidx, S in enumerate(slots):
                sx_rel = float(S.get("x_rel", 0.0))
                sy_rel = float(S.get("y_rel", 0.0))
                sw_rel = float(S.get("w_rel", 0.0))
                sh_rel = float(S.get("h_rel", 0.0))
                label  = S.get("label") or S.get("role") or ""
                x0 = px + int(round(sx_rel * pw))
                y0 = py + int(round(sy_rel * ph))
                x1 = x0 + int(round(sw_rel * pw))
                y1 = y0 + int(round(sh_rel * ph))
                _dbg("apply_layers:slot", sidx=sidx, rect=[x0,y0,x1,y1], label=label)
                draw.rectangle([x0, y0, x1, y1], outline=border_color, width=max(1, int(round(1 * smin))))
                if label:
                    try:
                        draw.text((x0 + pad, y0 + pad), label, fill=font_color, font=font)
                    except Exception:
                        current_app.logger.debug("[apply_layers] draw.text fallback(no font)", exc_info=True)
                        draw.text((x0 + pad, y0 + pad), label, fill=font_color)
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
            ov = None
            if token and token in LAYER_STORE:
                path = LAYER_STORE[token]["path"]
                try:
                    ov = Image.open(path).convert("RGBA")
                    _dbg("apply_layers:overlay_loaded", token=token, size=f"{ov.width}x{ov.height}")
                except Exception:
                    current_app.logger.debug("[apply_layers] open overlay failed", exc_info=True)
                    ov = None
            if ov is None and ltype == "sign" and L.get("user_id"):
                ov = _load_user_sign_rgba(L.get("user_id"))

            if ov is None:
                _dbg("apply_layers:overlay_skip", reason="no_overlay")
                continue

            x = int(round((L.get("x", 0)) * sx))
            y = int(round((L.get("y", 0)) * sy))
            w = int(round((L.get("w", ov.width)) * sx))
            h = int(round((L.get("h", ov.height)) * sy))
            _dbg("apply_layers:overlay_place", x=x, y=y, w=w, h=h)
            if w > 0 and h > 0:
                ov = ov.resize((w, h), Image.LANCZOS)
            base.alpha_composite(ov, dest=(x, y))
            continue

    out = base.convert("RGB")
    _dbg("apply_layers:done", out_size=f"{out.width}x{out.height}")
    return out

# ----- 기본 주입 데이터 -----
def _default_devices():
    out = []
    for i in range(1, 7):
        num = f"{i:02d}"
        out.append({
            "device_no": num,
            "device_id": f"E{num}",
            "default_width": 480,
            "default_height": 800,
        })
    _dbg("default_devices", count=len(out))
    return out

def _default_routes():
    routes = [
        {
            "id": 1,
            "name": "기본 결재선",
            "steps": [
                {"role": "review", "assignee_userid": "reviewer01"},
                {"role": "approve", "assignee_userid": "approver01"},
            ],
        },
        {
            "id": 2,
            "name": "부서장 결재",
            "steps": [
                {"role": "review", "assignee_userid": "teamlead"},
                {"role": "approve", "assignee_userid": "head"},
            ],
        },
    ]
    _dbg("default_routes", count=len(routes))
    return routes

# ----- 스냅샷 → SignLayout 레코드 변환 -----
def _snapshot_to_signlayout_args(layout_snapshot: dict):
    _dbg("snapshot_to_signlayout:start", snapshot=_dump_json(layout_snapshot, 400))
    if not layout_snapshot:
        return None
    canvas = layout_snapshot.get("canvas") or {}
    layers = layout_snapshot.get("layers") or []
    signbox = next((L for L in layers if (L.get("type") or "").lower() == "signbox"), None)
    if not signbox:
        _dbg("snapshot_to_signlayout:skip", reason="no_signbox")
        return None
    parent = signbox.get("parent") or {}
    tpl = signbox.get("tpl") or {}
    slots = signbox.get("slots") or []
    out = {
        "canvas_w": int(canvas.get("w", 1200)),
        "canvas_h": int(canvas.get("h", 1600)),
        "parent_box": {
            "x": int(parent.get("x", 0)),
            "y": int(parent.get("y", 0)),
            "w": int(parent.get("w", 0)),
            "h": int(parent.get("h", 0)),
        },
        "tpl_json": tpl,
        "slots_json": slots,
        "layers_json": {"layers": layers},
    }
    _dbg("snapshot_to_signlayout:done", out=_dump_json(out, 400))
    return out

# ===== 파일/메타 이동 =====
def _move_bundle(src_dir: str, dst_dir: str, base_filename: str):
    _dbg("move_bundle:start", src_dir=src_dir, dst_dir=dst_dir, base_filename=base_filename)
    names = [
        base_filename,
        os.path.splitext(base_filename)[0] + ".bin",
        os.path.splitext(base_filename)[0] + ".meta.json",
        os.path.splitext(base_filename)[0] + ".h",
    ]
    os.makedirs(dst_dir, exist_ok=True)
    moved = []
    for name in names:
        s = os.path.join(src_dir, name)
        if os.path.isfile(s):
            d = os.path.join(dst_dir, os.path.basename(name))
            os.replace(s, d)
            moved.append({"from": s, "to": d})
            _dbg("move_bundle:file_moved", src=s, dst=d, bytes=os.path.getsize(d))
        else:
            _dbg("move_bundle:file_not_found", src=s)
    _dbg("move_bundle:done", moved_count=len(moved))
    return moved

# ===== Auth helper (userid/no 동시 확보) =====
from flask import g, session

def _current_user_ids():
    """
    returns: (user_no:int|None, userid:str|None)
    - g.user.no / g.user.userid 우선
    - 세션: session["no"], session["userid"] 지원
    - request.user_id는 숫자는 no로, 문자는 userid로 취급
    """
    uno = None
    uid = None
    try:
        if getattr(g, "user", None) is not None:
            if getattr(g.user, "no", None) is not None:
                uno = int(g.user.no)
            if getattr(g.user, "userid", None):
                uid = str(g.user.userid)
    except Exception:
        pass
    try:
        if "no" in session and uno is None:
            if str(session["no"]).isdigit():
                uno = int(session["no"])
        if "userid" in session and uid is None:
            if str(session["userid"]).strip():
                uid = str(session["userid"]).strip()
    except Exception:
        pass
    try:
        if getattr(request, "user_id", None) and uno is None and uid is None:
            # 숫자는 no로, 문자는 userid로
            v = request.user_id
            if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
                uno = int(v)
            else:
                uid = str(v)
    except Exception:
        pass
    return uno, uid


# ===== 업로드/결재 조회: 최신 1건 찾기 =====
def _find_latest_pending_for_user(userid: str):
    """
    사용자(userid)가 검토(review) 또는 승인(approve) 담당인 최신 건 하나를 반환.
    우선순위: proceed/in_review(검토자) → checked/checked(승인자)
    반환 예:
      {
        "id": 19, "device_id": "E01",
        "stored_path": "D:/bmp_files/proceed\\E01_1200x1600_BWRYBG.bmp",
        "target_dir": "proceed", "status": "in_review",
        "assignees": {"review":"njsk2006","approve":"njsk2003"},
        "meta_path": "D:/bmp_files/proceed\\E01_1200x1600_BWRYBG.meta.json",
        "width": 1200, "height": 1600, "mode": "BWRYBG"
      }
    """
    # 1) RepositoryEINK가 지원하면 그걸로 시도
    if RepositoryEINK is not None:
        try:
            row = RepositoryEINK.get_latest_pending_for_user(userid=userid)
            if row:
                # repo 구현체는 자유롭게, 여기선 필요한 키만 표준화
                return {
                    "id": row.get("id"),
                    "device_id": row.get("device_id"),
                    "stored_path": row.get("stored_path"),
                    "target_dir": row.get("target_dir"),
                    "status": row.get("status"),
                    "assignees": row.get("assignees") or {},
                    "meta_path": row.get("meta_path"),
                    "width": row.get("width", 1200),
                    "height": row.get("height", 1600),
                    "mode": row.get("mode", "BWRYBG"),
                    "created_at": row.get("created_at"),
                }
        except Exception:
            current_app.logger.debug("[_find_latest_pending_for_user] repo call failed", exc_info=True)

    # 2) fallback: 메타 디렉터리 스캔 (가장 최신 ver/mtime)
    import glob
    candidates = []

    def pick_from_dir(dir_name, expect_status):
        root = os.path.join(EINK_ASSET_ROOT, dir_name)
        for meta in glob.glob(os.path.join(root, "*.meta.json")):
            try:
                with open(meta, "r", encoding="utf-8") as f:
                    js = json.load(f)
                ass = js.get("assignees") or {}
                status = "in_review" if dir_name == "proceed" else ("checked" if dir_name == "checked" else js.get("status"))
                if status != expect_status:
                    continue
                # 검토자/승인자 일치
                need = (expect_status == "in_review" and ass.get("review") == userid) or \
                       (expect_status == "checked" and ass.get("approve") == userid)
                if not need:
                    continue
                bmp_base = js.get("file")
                bmp_path = os.path.join(root, bmp_base)
                if not os.path.isfile(bmp_path):
                    continue
                candidates.append({
                    "id": None,
                    "device_id": js.get("device_id"),
                    "stored_path": bmp_path,
                    "target_dir": dir_name,
                    "status": expect_status,
                    "assignees": ass,
                    "meta_path": meta,
                    "width": js.get("width", 1200),
                    "height": js.get("height", 1600),
                    "mode": js.get("mode", "BWRYBG"),
                    "created_at": js.get("updated_at"),
                    "_ver": js.get("ver", 0),
                    "_mtime": os.path.getmtime(meta),
                })
            except Exception:
                continue

    # 우선 검토(in_review) → 승인(checked) 순서
    pick_from_dir("proceed", "in_review")
    if not candidates:
        pick_from_dir("checked", "checked")

    if not candidates:
        return None
    # 최신 정렬: ver/mtime 기준
    candidates.sort(key=lambda x: (x.get("_ver", 0), x.get("_mtime", 0)), reverse=True)
    return candidates[0]


def _load_sign_image_for_user(user_no=None, userid=None):
    """
    현재 로그인 사용자의 photo_1 파일을 SIGN_BASE_DIR과 join하여 RGBA 반환
    RepositoryEINK.get_user_sign_path(user_no) 우선, 없으면 (SIGN_BASE_DIR / userid.png 등) 규칙 사용 가능.
    """
    base = current_app.config.get("SIGN_BASE_DIR") or ""
    # 1) DB에서 찾기
    if RepositoryEINK is not None:
        try:
            key = user_no if user_no is not None else userid
            if key is not None:
                path = RepositoryEINK.get_user_sign_path(int(user_no)) if user_no is not None else None
                if not path and userid:
                    path = RepositoryEINK.get_user_sign_path_by_userid(userid)  # 구현돼 있으면 사용
                if path:
                    # 절대경로가 아니라면 base와 합침
                    if not os.path.isabs(path):
                        path = os.path.join(base, path)
                    if os.path.isfile(path):
                        return Image.open(path).convert("RGBA")
        except Exception:
            current_app.logger.debug("[_load_sign_image_for_user] repo failed", exc_info=True)
    # 2) fallback: userid 파일명 추정 (원하면 규칙 보강)
    if userid:
        guess = os.path.join(base, f"{userid}.png")
        if os.path.isfile(guess):
            return Image.open(guess).convert("RGBA")
    # 실패
    return None


def _composite_sign_on_slot(im_canvas, width, height, layers, slot_role, sign_img_rgba):
    """
    signbox 레이어에서 slot_role(author/review/approve)을 찾아 해당 슬롯 박스에 sign_img_rgba를 맞춰 합성해서 반환
    (preview/전송 동일 좌표계 1200x1600 기준을 그대로 씀)
    """
    if not sign_img_rgba:
        return im_canvas
    # 베이스는 RGBA
    base = im_canvas.convert("RGBA")
    # 좌표 스케일
    BX, BY = 1200.0, 1600.0
    sx = float(width) / BX
    sy = float(height) / BY

    # signbox 찾기
    signbox = next((L for L in (layers or []) if (L.get("type") or "").lower() == "signbox"), None)
    if not signbox:
        return im_canvas

    parent = signbox.get("parent") or {}
    slots = signbox.get("slots") or []
    tgt = next((s for s in slots if (s.get("role") or "") == slot_role), None)
    if not tgt:
        return im_canvas

    px = int(round(parent.get("x", 0) * sx))
    py = int(round(parent.get("y", 0) * sy))
    pw = int(round(parent.get("w", 0) * sx))
    ph = int(round(parent.get("h", 0) * sy))

    # 슬롯 절대 박스
    x0 = px + int(round(tgt.get("x_rel", 0) * pw))
    y0 = py + int(round(tgt.get("y_rel", 0) * ph))
    x1 = x0 + int(round(tgt.get("w_rel", 0) * pw))
    y1 = y0 + int(round(tgt.get("h_rel", 0) * ph))

    w = max(1, x1 - x0)
    h = max(1, y1 - y0)

    ov = sign_img_rgba.resize((w, h), Image.LANCZOS)
    base.alpha_composite(ov, dest=(x0, y0))
    return base.convert("RGB")


# ===== 결재 알림: pending 조회 =====
@bp.route("/approval/pending", methods=["GET"])
def approval_pending():
    _dbg("approval_pending:req", **_req_info())
    user_no, userid = _current_user_ids()
    if not userid:
        return jsonify({"has": False})

    item = _find_latest_pending_for_user(userid)
    if not item:
        return jsonify({"has": False})

    # 클라이언트 안내용 요약
    return jsonify({
        "has": True,
        "status": item["status"],
        "target_dir": item["target_dir"],
        "device_id": item.get("device_id"),
        "bmp_path": item.get("stored_path"),
        "meta_path": item.get("meta_path"),
        "width": item.get("width", 1200),
        "height": item.get("height", 1600),
        "mode": item.get("mode", "BWRYBG"),
        # 승인 페이지 이동에 필요한 쿼리
        "goto": url_for("bulletin.approval_page",
                        device_id=item.get("device_id"),
                        meta=item.get("meta_path"),
                        status=item.get("status"))
    })


# ===== 결재 페이지 =====
@bp.route("/approval/page", methods=["GET"])
def approval_page():
    _dbg("approval_page:req", **_req_info())
    device_id = request.args.get("device_id")
    meta_path = request.args.get("meta")
    status = request.args.get("status")  # in_review | checked
    if not (device_id and meta_path and os.path.isfile(meta_path)):
        abort(404, "meta missing")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # 결재 단계별 버튼 활성화
    stage = "review" if status == "in_review" else ("approve" if status == "checked" else "unknown")

    # 결재 화면에서는 딱 한 장(1200x1600)만 보여주면 되므로 라우트 인자 그대로 템플릿에 전달
    # (이미 BMP가 만들어져 있으므로 <img src="/bulletin/approval/preview?..."> 같은 라우트로 서빙해도 되고,
    #  여기서는 meta로부터 bmp 경로 역산하여 프리뷰 라우트 제공)
    bmp_dir = os.path.dirname(meta_path)
    bmp_file = meta.get("file")
    bmp_path = os.path.join(bmp_dir, bmp_file)
    if not os.path.isfile(bmp_path):
        abort(404, "bmp not found")

    # 프리뷰 서빙용 핸들(간단히 meta 경로를 키로)
    preview_url = url_for("bulletin.layer_img", token=os.path.basename(bmp_path))  # 임시 재사용 × → 별도 라우트가 낫다
    # 더 안전하게: 전용 서빙
    preview_url = url_for("bulletin.approval_preview", meta=meta_path)

    # 화면 렌더
    return render_template("bulletinboard/e_file_approval.html",
                           device_id=device_id,
                           meta_path=meta_path,
                           preview_url=preview_url,
                           status=status,
                           stage=stage,
                           width=meta.get("width", 1200),
                           height=meta.get("height", 1600),
                           mode=meta.get("mode", "BWRYBG"),
                           assignees=meta.get("assignees") or {})


# BMP 프리뷰 서빙(보안: meta 경로 검증)
@bp.route("/approval/preview", methods=["GET"])
def approval_preview():
    meta_path = request.args.get("meta") or ""
    if not (meta_path and os.path.isfile(meta_path)):
        abort(404)
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        bmp_dir = os.path.dirname(meta_path)
        bmp_file = meta.get("file")
        bmp_path = os.path.join(bmp_dir, bmp_file)
        if not os.path.isfile(bmp_path):
            abort(404)
        return send_file(bmp_path, mimetype="image/bmp")
    except Exception:
        abort(404)


# ===== 결재 액션(검토/승인/반려) =====
@bp.route("/approval/act", methods=["POST"])
def approval_act():
    js = request.get_json(silent=True) or {}
    _dbg("approval_act:req", **_req_info(), body=_dump_json(js, 400))

    def _fail(http_code:int, msg:str):
        # ADD: 에러 사유를 로그로 남기고 abort
        _dbg("approval_act:fail", code=http_code, reason=msg)
        abort(http_code, msg)

    # --- 입력값 정리 ---
    meta_path_raw = js.get("meta_path")
    action = (js.get("action") or "").lower()

    if action not in ("review", "approve", "reject"):
        _fail(400, "action invalid")

    # ADD: 경로 정규화 + 존재 확인
    meta_path = os.path.normpath(meta_path_raw) if meta_path_raw else None
    if not (meta_path and os.path.isfile(meta_path)):
        _fail(404, f"meta not found: {meta_path_raw}")

    _dbg("approval_act:meta_path", raw=meta_path_raw, norm=meta_path)

    # --- 메타 로드 ---
    try:
        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        _fail(400, f"meta parse error: {e}")

    device_id = meta.get("device_id")
    width  = int(meta.get("width", 1200))
    height = int(meta.get("height", 1600))
    fmt    = meta.get("mode", "BWRYBG")
    target_dir_meta = (meta.get("dir") or "").strip()              # proceed | checked | uploads/updates...
    status_meta     = (meta.get("status") or "").strip()           # in_review | checked | approved | rejected ...
    assignees       = meta.get("assignees") or {}

    # --- 파일 경로 계산 ---
    bmp_dir  = os.path.dirname(meta_path)
    bmp_file = meta.get("file")
    if not bmp_file:
        _fail(400, "meta.file missing")
    bmp_path = os.path.join(bmp_dir, bmp_file)
    bin_path = os.path.join(bmp_dir, os.path.splitext(bmp_file)[0] + ".bin")

    if not os.path.isfile(bmp_path):
        _fail(404, f"bmp missing: {bmp_path}")

    # ADD: 실제 부모 폴더명으로 target_dir 보정 (meta가 잘못됐을 수 있음)
    actual_dir = os.path.basename(os.path.dirname(bmp_path))  # proceed / checked / uploads / updates
    target_dir = target_dir_meta or actual_dir

    # ADD: meta.status가 비어있거나 틀리면 디렉터리 기준으로 추론
    # proceed -> in_review, checked -> checked, uploads/updates -> approved(참고)
    if not status_meta:
        inferred = {"proceed": "in_review", "checked": "checked", "uploads": "approved", "updates": "approved"}
        status_meta = inferred.get(actual_dir, "in_review")

    _dbg("approval_act:stage_context",
         action=action,
         device_id=device_id,
         meta_dir=target_dir_meta,
         actual_dir=actual_dir,
         target_dir_used=target_dir,
         status_meta=status_meta,
         width=width, height=height, fmt=fmt,
         assignees=assignees)

    # --- 레이어 스냅샷 로드(있으면 서명 합성) ---
    layers = []
    if RepositoryEINK is not None:
        try:
            snap = RepositoryEINK.get_layout_snapshot_by_meta(meta_path)
            if isinstance(snap, dict):
                layers = (snap.get("layers") or []) if "layers" in snap else (snap.get("layout", {}).get("layers") or [])
            _dbg("approval_act:layers_loaded", has=bool(layers), count=len(layers or []))
        except Exception as e:
            _dbg("approval_act:layers_error", error=str(e))

    # 현재 로그인 사용자 서명 이미지
    user_no, userid = _current_user_ids()
    sign_img = _load_user_sign_rgba(user_no) if user_no else _load_user_sign_rgba(None)
    _dbg("approval_act:sign_info", user_no=user_no, userid=userid, has_sign=bool(sign_img))

    # --- 검토/승인일 때 서명 합성 ---
    if action in ("review", "approve") and sign_img is not None and layers:
        role = "review" if action == "review" else "approve"
        try:
            im = Image.open(bmp_path).convert("RGB")
            im = _composite_sign_on_slot(im, width, height, layers, role, sign_img)
            im.save(bmp_path, format="BMP")
            payload = ImageToBytes.image_to_payload(im, fmt, size=(width, height))
            with open(bin_path, "wb") as f:
                f.write(payload)
            raw_len   = len(payload) - 4
            crc32_le  = int.from_bytes(payload[-4:], "little", signed=False)
            meta["raw_len"]   = raw_len
            meta["total_len"] = raw_len + 4
            meta["crc32"]     = f"{crc32_le:08x}"
            meta["ver"]       = int(os.path.getmtime(bmp_path))
            meta["updated_at"]= datetime.now().isoformat(timespec="seconds")
            _dbg("approval_act:sign_applied", role=role, raw_len=raw_len, crc32=meta["crc32"], ver=meta["ver"])
        except Exception as e:
            _fail(500, f"sign composite failed: {e}")

    # --- 번들 이동 & 단계 검증 ---
    moved = []
    new_status = meta.get("status") or status_meta
    new_dir    = target_dir

    if action == "review":
        # proceed -> checked
        if target_dir not in ("proceed",) and actual_dir not in ("proceed",):
            _fail(400, f"not in review stage (dir={target_dir}, actual={actual_dir}, status={status_meta})")
        src_dir = os.path.join(EINK_ASSET_ROOT, "proceed")
        dst_dir = os.path.join(EINK_ASSET_ROOT, "checked")
        moved = _move_bundle(src_dir, dst_dir, bmp_file)
        new_status = "checked"
        new_dir = "checked"

    elif action == "approve":
        # checked -> updates
        if target_dir not in ("checked",) and actual_dir not in ("checked",):
            _fail(400, f"not in approve stage (dir={target_dir}, actual={actual_dir}, status={status_meta})")
        src_dir = os.path.join(EINK_ASSET_ROOT, "checked")
        dst_dir = os.path.join(EINK_ASSET_ROOT, "updates")
        moved = _move_bundle(src_dir, dst_dir, bmp_file)
        new_status = "approved"
        new_dir = "updates"

    elif action == "reject":
        # 이동 없음
        new_status = "rejected"
        new_dir = target_dir

    _dbg("approval_act:moved", count=len(moved), new_status=new_status, new_dir=new_dir)

    # --- 메타 파일 갱신(위치/상태) ---
    new_meta_path = os.path.join(EINK_ASSET_ROOT, new_dir, os.path.basename(meta_path))
    meta["dir"] = new_dir
    meta["need_approval"] = meta.get("need_approval", True) if action != "approve" else False
    meta["final_approval"] = (action == "approve")
    meta["status"] = new_status

    try:
        with open(new_meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
        _dbg("approval_act:meta_rewrote", path=new_meta_path)
    except Exception as e:
        _dbg("approval_act:meta_rewrite_failed", error=str(e))

    # --- DB 갱신 ---
    if RepositoryEINK is not None:
        try:
            ok = RepositoryEINK.update_upload_status_by_meta(
                old_meta_path=new_meta_path, # meta_path에서 new_meta_path로 수정
                new_dir=new_dir,
                new_status=new_status,
                note=js.get("note")
            )
            _dbg("approval_act:db_update", ok=ok, new_status=new_status, new_dir=new_dir)
        except Exception as e:
            current_app.logger.debug("[approval_act] DB update failed", exc_info=True)

    return jsonify({"ok": True, "moved": moved, "new_status": new_status, "new_dir": new_dir, "meta_path": new_meta_path})


# ===== Routes =====
#팝업 1번만
@bp.route("/approval/mark_checked", methods=["POST"])
def approval_mark_checked():
    try:
        session['approval_checked'] = True
        return jsonify({"ok": True})
    except Exception:
        current_app.logger.debug("[approval_mark_checked] failed", exc_info=True)
        return jsonify({"ok": False}), 500


@bp.route('/fileview', methods=['GET', 'POST'])
def file_view():
    t0 = time.time()
    _dbg("file_view:req", **_req_info())

    devices = _default_devices()
    try:
        if RepositoryEINK is not None:
            devices = RepositoryEINK.get_devices_for_dashboard() or devices
            approval_routes = RepositoryEINK.get_approval_routes() or _default_routes()
        else:
            approval_routes = _default_routes()
    except Exception as e:
        current_app.logger.debug("[file_view] Repository fetch failed", exc_info=True)
        approval_routes = _default_routes()

    uid = _current_user_id()
    current_user = {
        "no": uid,
        "name": getattr(getattr(g, "user", None), "username", None) or "Guest",
    }

    _dbg("file_view:context",
         devices=len(devices),
         routes=len(approval_routes),
         current_user=_dump_json(current_user))

    resp = render_template(
        'bulletinboard/e_file_select.html',
        devices=devices,
        current_user=current_user,
        approval_routes=approval_routes
    )
    _dbg("file_view:done", ms=int((time.time()-t0)*1000))
    return resp

@bp.route("/routes/list", methods=["GET"])
def routes_list():
    _dbg("routes_list:req", **_req_info())
    try:
        if RepositoryEINK is not None:
            routes = RepositoryEINK.get_approval_routes() or _default_routes()
        else:
            routes = _default_routes()
    except Exception:
        current_app.logger.debug("[routes_list] Repository error", exc_info=True)
        routes = _default_routes()
    _dbg("routes_list:resp", count=len(routes))
    return jsonify({"routes": routes})

# ====== 추가: 부서/사용자 셀렉트 ======
@bp.route("/departments", methods=["GET"])
def list_departments():
    _dbg("departments:req", **_req_info())
    try:
        if RepositoryEINK is None:
            _dbg("departments:resp", departments=0, reason="no_repo")
            return jsonify({"departments": []})
        depts = RepositoryEINK.list_departments() or []
        _dbg("departments:resp", departments=len(depts))
        return jsonify({"departments": depts})
    except Exception:
        current_app.logger.debug("[departments] failed", exc_info=True)
        return jsonify({"departments": []})

@bp.route("/users", methods=["GET"])
def list_users_by_department():
    dept = request.args.get("department")
    _dbg("users:req", **_req_info(), department=dept)
    try:
        if RepositoryEINK is None:
            _dbg("users:resp", users=0, reason="no_repo")
            return jsonify({"users": []})
        users = RepositoryEINK.list_users_by_department(dept) or []
        _dbg("users:resp", users=len(users))
        return jsonify({"users": users})
    except Exception:
        current_app.logger.debug("[users] failed", exc_info=True)
        return jsonify({"users": []})

@bp.route("/preview_blob", methods=["POST"])
def preview_blob():
    t0 = time.time()
    created_id = None
    layers = []
    _dbg("preview_blob:req", **_req_info())

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

        _dbg("preview_blob:multipart_saved",
             upload_id=upload_id, path=path, bytes=os.path.getsize(path),
             width=width, height=height, mode=mode, scale=scale, percent=percent, rotate=rotate, raw=raw)

    else:
        js = request.get_json(silent=True) or {}
        _dbg("preview_blob:json_body", body=_dump_json(js))
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
        except Exception as e:
            current_app.logger.debug("[preview_blob] bad body", exc_info=True)
            abort(400, f"bad body: {e}")

    # 로그인 유저 자동 바인딩 + 요약 로그
    layers = _bind_sign_layer_user(layers)
    _log_layers(layers, where="preview_blob")

    _dbg("preview_blob:params",
         upload_id=created_id or upload_id, size=f"{width}x{height}",
         mode=mode, scale=scale, percent=percent, rotate=rotate, raw=raw, layers=len(layers))

    if raw:
        im = svc.load_upload_image(upload_id, page=1)
        _dbg("preview_blob:raw_loaded", src_size=f"{im.width}x{im.height}")
        if rotate in (90, 180, 270):
            im = im.rotate(rotate, expand=True)
            _dbg("preview_blob:raw_rotated", rotate=rotate, new_size=f"{im.width}x{im.height}")
        im_preview = svc._place_into_canvas(im, width, height, mode=scale, percent=percent)
        im_preview = _apply_layers_to_image(im_preview, width, height, layers)
    else:
        im_preview = svc.build_preview_image(upload_id, page=1, width=width, height=height,
                                             mode=mode, scale=scale, percent=percent, rotate=rotate)
        _dbg("preview_blob:preview_built", size=f"{im_preview.width}x{im_preview.height}")
        im_preview = _apply_layers_to_image(im_preview, width, height, layers)

    bio = BytesIO()
    im_preview.save(bio, format="PNG")
    bio.seek(0)
    resp = send_file(bio, mimetype="image/png")
    if created_id is not None:
        resp.headers["X-Upload-Id"] = str(created_id)
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    _dbg("preview_blob:done", ms=int((time.time()-t0)*1000))
    return resp

@bp.route("/sendfile", methods=["POST"])
def send_file_route():
    t0 = time.time()
    js = request.get_json(silent=True) or {}
    _dbg("sendfile:req", **_req_info(), body=_dump_json(js))

    try:
        upload_id = int(js["upload_id"])
        page      = int(js.get("page", 1))
        device_id = js["device_id"]
        mode      = js.get("mode", "BWRY")
        scale     = js.get("scale", "fit")
        percent   = int(js.get("percent", 100))
        rotate    = int(js.get("rotate", 270))
        width     = int(js.get("width", 800))
        height    = int(js.get("height", 480))
        layers    = js.get("layers") or []

        need_approval  = bool(js.get("need_approval", True))
        final_approval = bool(js.get("final_approval", False))
        route_id       = js.get("route_id")
        assignees      = js.get("assignees") or {}
        layout_snapshot= js.get("layout_snapshot") or {}
    except Exception as e:
        current_app.logger.debug("[sendfile] bad body", exc_info=True)
        abort(400, f"bad body: {e}")

    if (width, height) == (480, 800):
        width, height = 800, 480
        _dbg("sendfile:swap_wh_for_portrait", new_size=f"{width}x{height}")

    try:
        im_src = svc.load_upload_image(upload_id, page=page)
        _dbg("sendfile:src_loaded", src_size=f"{im_src.width}x{im_src.height}", page=page)
    except Exception as e:
        current_app.logger.debug("[sendfile] upload not found or render fail", exc_info=True)
        abort(404, f"upload not found or render fail: {e}")

    if rotate in (90, 180, 270):
        im_src = im_src.rotate(rotate, expand=True)
        _dbg("sendfile:src_rotated", rotate=rotate, new_size=f"{im_src.width}x{im_src.height}")

    # 로그인 유저 자동 바인딩 + 요약 로그
    layers = _bind_sign_layer_user(layers)
    _log_layers(layers, where="send_file")

    im_canvas = svc._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
    _dbg("sendfile:placed_canvas", canvas_size=f"{im_canvas.width}x{im_canvas.height}", scale=scale, percent=percent)
    im_canvas = _apply_layers_to_image(im_canvas, width, height, layers)

    mode_up = (mode or "BW").upper()
    if mode_up == "BWRY":
        im_proc = svc.quantize_to_BWRY(im_canvas); fmt = "BWRY"
    elif mode_up in ("BWRYBG","SPECTRA6","COLOR6"):
        im_proc = svc.quantize_to_BWRYBG(im_canvas); fmt = "BWRYBG"
    else:
        im_proc = svc.quantize_to_BW(im_canvas); fmt = "BW"
    _dbg("sendfile:quantized", fmt=fmt)

    target_dir = _decide_target_dir(need_approval, final_approval)

    bmp_path, meta_path, hdr_path, bin_path = _asset_paths(device_id, width, height, fmt, target_dir=target_dir)
    try:
        im_proc.save(bmp_path, format="BMP")
        _dbg("sendfile:bmp_saved", path=bmp_path, bytes=os.path.getsize(bmp_path))
    except Exception as e:
        current_app.logger.debug("[sendfile] failed to save BMP", exc_info=True)
        abort(500, f"failed to save BMP: {e}")

    payload = ImageToBytes.image_to_payload(im_proc, fmt, size=(width, height))
    try:
        with open(bin_path, "wb") as f:
            f.write(payload)
        _dbg("sendfile:bin_saved", path=bin_path, bytes=os.path.getsize(bin_path))
    except Exception as e:
        current_app.logger.debug("[sendfile] failed to save BIN", exc_info=True)
        abort(500, f"failed to save BIN: {e}")

    raw_len = len(payload) - 4
    crc32_le = int.from_bytes(payload[-4:], "little", signed=False)
    ver = int(os.path.getmtime(bmp_path))

    meta = {
        "device_id": device_id,
        "dir": target_dir,
        "file": os.path.basename(bmp_path),
        "bin":  os.path.basename(bin_path),
        "width": width, "height": height,
        "mode": fmt,
        "packing": {"BW":"1bpp", "BWRY":"2bpp", "BWRYBG":"3bpp"}[fmt],
        "raw_len": raw_len,
        "total_len": raw_len + 4,
        "crc32": f"{crc32_le:08x}",
        "ver": ver,
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "need_approval": need_approval,
        "final_approval": final_approval,
        "route_id": route_id,
        "assignees": assignees,
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    _dbg("sendfile:meta_saved", path=meta_path, meta=_dump_json(meta, 600))

    info = UPLOADS.pop(upload_id, None)
    if info:
        path = info.get("path")
        try:
            if path and os.path.isfile(path):
                os.remove(path)
                _dbg("sendfile:cleanup_tmp", path=path)
        except Exception:
            current_app.logger.debug("[CLEANUP] Failed to delete temp file", exc_info=True)

    current_app.logger.info(
        f"[send_file] device={device_id} size={width}x{height} fmt={fmt} dir={target_dir} "
        f"need_approval={need_approval} final_approval={final_approval} route_id={route_id} "
        f"assignees={assignees} layout_layers={len(layout_snapshot.get('layers', [])) if layout_snapshot else 0}"
    )

    # ===== (옵션) DB 저장 =====
    upload_row_id = None
    sign_layout_id = None
    if RepositoryEINK is not None:
        try:
            db_status = "approved" if target_dir == "uploads" else "in_review"
            orig_filename = info.get("name") if info else os.path.basename(bmp_path)
            upload_row_id = RepositoryEINK.create_upload_record(
                user_id=_current_user_id(),  # ← 로그인 유저 통일
                device_id=device_id,
                orig_filename=orig_filename,
                stored_path=bmp_path,
                target_dir=target_dir,
                need_approval=need_approval,
                status=db_status,
                pages=1,
                width=width, height=height, mode=fmt,
                scale=scale, percent=percent, rotate=rotate,
                route_id=route_id,
                sign_layout_id=None,
                route_snapshot={"route_id": route_id, "assignees": assignees} if route_id else None,
                layout_snapshot=layout_snapshot if layout_snapshot else None,
                metadata={"assignees": assignees} if assignees else None,
            )
            _dbg("sendfile:db_created_upload", upload_row_id=upload_row_id, status=db_status)

            if layout_snapshot:
                args = _snapshot_to_signlayout_args(layout_snapshot)
                if args:
                    sign_layout_id = RepositoryEINK.insert_sign_layout(
                        name=f"Device {device_id} Snapshot",
                        owner_user_id=_current_user_id(),  # ← 로그인 유저 통일
                        canvas_w=args["canvas_w"],
                        canvas_h=args["canvas_h"],
                        parent_box=args["parent_box"],
                        tpl_json=args["tpl_json"],
                        slots_json=args["slots_json"],
                        layers_json=args["layers_json"],
                        version=1,
                    )
                    _dbg("sendfile:db_sign_layout_created", sign_layout_id=sign_layout_id)
        except Exception:
            current_app.logger.debug("[DB] save skipped", exc_info=True)

    _dbg("sendfile:done", ms=int((time.time()-t0)*1000))
    return jsonify({
        "status": "prepared",
        "job_id": int(time.time()*1000),
        "device_id": device_id,
        "dir": target_dir,
        "file": os.path.basename(bmp_path),
        "meta": meta,
        "upload_row_id": upload_row_id,
        "sign_layout_id": sign_layout_id
    })

@bp.route("/layer_upload", methods=["POST"])
def layer_upload():
    _dbg("layer_upload:req", **_req_info())
    if not (request.mimetype and "multipart/form-data" in request.mimetype):
        abort(400, "multipart/form-data required")
    f = request.files.get("file")
    if not f:
        abort(400, "file missing")
    ext = (os.path.splitext(f.filename or "")[1] or ".png").lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        abort(400, "only .png/.jpg supported")
    token = f"{int(time.time()*1000)}_{os.path.basename(f.filename or 'layer')}"
    safe_token = "".join(ch for ch in token if ch.isalnum() or ch in "._-")[:128]
    out_path = os.path.join(LAYER_TMP_DIR, safe_token)
    f.save(out_path)
    LAYER_STORE[safe_token] = {
        "path": out_path,
        "name": f.filename or safe_token,
        "mimetype": "image/png" if ext == ".png" else "image/jpeg"
    }
    preview_url = url_for("bulletin.layer_img", token=safe_token)
    _dbg("layer_upload:done", token=safe_token, path=out_path, bytes=os.path.getsize(out_path), preview_url=preview_url)
    return jsonify({"upload_token": safe_token, "preview_url": preview_url})

@bp.route("/layer_img/<path:token>", methods=["GET"])
def layer_img(token):
    _dbg("layer_img:req", token=token, **_req_info())
    info = LAYER_STORE.get(token)
    if not info or not os.path.isfile(info["path"]):
        _dbg("layer_img:not_found", token=token)
        abort(404)
    _dbg("layer_img:serve", path=info["path"], mimetype=info.get("mimetype", "image/png"))
    return send_file(info["path"], mimetype=info.get("mimetype", "image/png"))

@bp.route("/sign_layout/save_batch", methods=["POST"])
def save_layout_batch():
    _dbg("save_layout_batch:req", **_req_info())
    js = request.get_json(silent=True) or {}
    _dbg("save_layout_batch:body", body=_dump_json(js, 800))
    items = js.get("items") or []
    current_app.logger.info(f"[save_layout_batch] items={len(items)}")
    results = []
    for it in items:
        device_id = _safe_device_id(it.get("device_id", "UNKNOWN"))
        layout = it.get("layout") or {}
        path = os.path.join(EINK_ASSET_ROOT, f"layout_{device_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(layout, f, ensure_ascii=False, indent=2)
            results.append({"device_id": device_id, "saved": True, "path": path})
            _dbg("save_layout_batch:file_saved", device_id=device_id, path=path)

            if RepositoryEINK is not None:
                try:
                    args = _snapshot_to_signlayout_args(layout)
                    if args:
                        RepositoryEINK.insert_sign_layout(
                            name=f"Device {device_id} Snapshot",
                            owner_user_id=_current_user_id(),  # ← 로그인 유저 통일
                            canvas_w=args["canvas_w"],
                            canvas_h=args["canvas_h"],
                            parent_box=args["parent_box"],
                            tpl_json=args["tpl_json"],
                            slots_json=args["slots_json"],
                            layers_json=args["layers_json"],
                            version=1,
                        )
                        _dbg("save_layout_batch:db_inserted", device_id=device_id)
                except Exception:
                    current_app.logger.debug("[DB] sign_layout skip", exc_info=True)

        except Exception as e:
            _dbg("save_layout_batch:error", device_id=device_id, error=str(e))
            results.append({"device_id": device_id, "saved": False, "error": str(e)})
    _dbg("save_layout_batch:done", saved_count=len([r for r in results if r.get("saved")]))
    return jsonify({"ok": True, "saved": results})

@bp.route("/calendar")
def calendar_page():
    _dbg("calendar:req", **_req_info())
    return render_template("bulletinboard/calendar.html")

# ====== 결재 진행: 검토 → 승인 → 완료 ======
@bp.route("/approval/advance", methods=["POST"])
def approval_advance():
    """
    body:
      {
        "stage": "review" | "approve",
        "file": "<bmp 파일명 또는 meta 파일명>",
        "device_id": "E01" (선택, 검증용)
      }

    - stage=="review": proceed → checked
    - stage=="approve": checked → updates
    """
    js = request.get_json(silent=True) or {}
    _dbg("approval_advance:req", **_req_info(), body=_dump_json(js))

    stage = (js.get("stage") or "").lower()
    file_param = js.get("file") or ""
    device_id = js.get("device_id")

    if stage not in ("review", "approve"):
        abort(400, "stage must be 'review' or 'approve'")

    # 파일명 정규화: .meta.json 이 들어와도 .bmp 베이스로 환산
    base = file_param
    if base.endswith(".meta.json"):
        base = base[:-10] + ".bmp"
    elif not base.endswith(".bmp"):
        abort(400, "file must be a .bmp or .meta.json")
    _dbg("approval_advance:normalized", base=base, device_id=device_id)

    src_dir = os.path.join(EINK_ASSET_ROOT, "proceed" if stage == "review" else "checked")
    dst_dir = os.path.join(EINK_ASSET_ROOT, "checked" if stage == "review" else "updates")
    _dbg("approval_advance:dirs", src_dir=src_dir, dst_dir=dst_dir)

    moved = _move_bundle(src_dir, dst_dir, base)
    if not moved:
        _dbg("approval_advance:moved_none", base=base)
        abort(404, f"no files moved (src={src_dir}, file={base})")

    _dbg("approval_advance:done", stage=stage, moved_count=len(moved))
    return jsonify({"ok": True, "stage": stage, "moved": moved})
