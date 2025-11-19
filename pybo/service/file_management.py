# service/file_management.py
import os, json, time, tempfile, itertools
from datetime import datetime
from io import BytesIO
from flask import current_app, request, g, session
from PIL import Image, ImageDraw, ImageFont

from .file_translation import FileTranslationBlackBG
from .image_to_bytes import ImageToBytes

# DB의 photo_1 경로를 활용하기 위해 RepositoryEINK 임포트
try:
    from ..repository.repository_eink import RepositoryEINK
except Exception:
    RepositoryEINK = None


# ──────────────────────────────────────────────────────────
# In-memory stores / engine
# ──────────────────────────────────────────────────────────
_UPLOADS = {}
_LAYER_STORE = {}
_UPLOAD_SEQ = itertools.count(1)

def get_upload_store(): return _UPLOADS
def get_layer_store():  return _LAYER_STORE
def next_upload_id():   return next(_UPLOAD_SEQ)

_translator = None
def get_translation_service():
    global _translator
    if _translator is None:
        _translator = FileTranslationBlackBG(uploads_store=_UPLOADS, pdf_dpi=200)
    return _translator


# (추가) photo_1이 절대/상대경로, 파일명만인 경우 모두 안전하게 처리하기 위한 유틸
def _resolve_sign_path(p: str) -> str:
    """
    DB(User.photo_1)에 저장된 경로 문자열을 안전하게 실제 경로로 해석한다.
    - 절대경로면 그대로 사용
    - 상대경로나 파일명만 있으면 SIGN_BASE_DIR(설정) 기준으로 합친다
    """
    if not p:
        return ""
    try:
        if os.path.isabs(p):
            return p
        base = (current_app.config.get("SIGN_BASE_DIR") or "").strip()
        return os.path.join(base, p) if base else p
    except Exception:
        return p

def _open_rgba(path: str):
    """이미지 파일을 RGBA로 안전하게 오픈."""
    try:
        if path and os.path.isfile(path):
            return Image.open(path).convert("RGBA")
    except Exception:
        pass
    return None


# ──────────────────────────────────────────────────────────
# User / IDs
# ──────────────────────────────────────────────────────────
def current_user_id():
    if getattr(g, "user", None) is not None and getattr(g.user, "no", None) is not None:
        return int(g.user.no)
    if "userid" in session:
        val = session.get("userid")
        if isinstance(val, (int, str)) and str(val).strip():
            return val if not str(val).isdigit() else int(val)
    if getattr(request, "user_id", None):
        try: return int(request.user_id)
        except Exception: return str(request.user_id)
    return None

def current_user_ids():
    uno, uid = None, None
    try:
        if getattr(g, "user", None) is not None:
            if getattr(g.user, "no", None) is not None: uno = int(g.user.no)
            if getattr(g.user, "userid", None): uid = str(g.user.userid)
    except Exception: pass
    try:
        if "no" in session and uno is None and str(session["no"]).isdigit():
            uno = int(session["no"])
        if "userid" in session and uid is None and str(session["userid"]).strip():
            uid = str(session["userid"]).strip()
    except Exception: pass
    try:
        if getattr(request, "user_id", None) and uno is None and uid is None:
            v = request.user_id
            if isinstance(v, int) or (isinstance(v, str) and v.isdigit()): uno = int(v)
            else: uid = str(v)
    except Exception: pass
    return uno, uid

def _safe_fragment(s: str) -> str:
    return "".join(ch for ch in (s or "") if ch.isalnum() or ch in "._-")[:64] or "guest"

def current_userid_str():
    # 우선순위: g.user.userid → session['userid'] → str(current_user_id())
    if getattr(getattr(g, "user", None), "userid", None):
        return str(g.user.userid)
    if "userid" in session and str(session["userid"]).strip():
        return str(session["userid"]).strip()
    uid = current_user_id()
    return str(uid) if uid is not None else "guest"

# ──────────────────────────────────────────────────────────
# Paths & dirs  (★ 사용자별 루트)
# ──────────────────────────────────────────────────────────
def get_global_asset_root() -> str:
    """공용 루트: 설정 EINK_ROOT 없으면 D:/bmp_files"""
    try:
        base = current_app.config.get("EINK_ROOT")
        if base:
            return base
    except Exception:
        pass
    return os.path.join("D:/", "bmp_files")

def get_asset_root() -> str:
    uid = _safe_fragment(current_userid_str())
    return os.path.join(get_global_asset_root(), uid)

def get_asset_dirs() -> dict:
    root = get_asset_root()
    return {
        "root": root,
        "uploads": os.path.join(root, "uploads"),
        "in_review": os.path.join(root, "in_review"),
        "checked": os.path.join(root, "checked"),
        "approved": os.path.join(root, "approved"),
        "bulletin_files": os.path.join(root, "bulletin_files"),
    }

LAYER_TMP_DIR = os.path.join(tempfile.gettempdir(), "eink_layers")

def ensure_asset_dirs():
    d = get_asset_dirs()
    for _, p in d.items():
        os.makedirs(p, exist_ok=True)
    os.makedirs(LAYER_TMP_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────
# Logging helpers
# ──────────────────────────────────────────────────────────
def dump_json(obj, max_len=800):
    try:
        s = json.dumps(obj, ensure_ascii=False)
        return (s[:max_len] + "...") if len(s) > max_len else s
    except Exception:
        return str(obj)

def dbg(tag: str, **kw):
    try:
        parts = [f"{k}={dump_json(v)}" for k, v in kw.items()]
        current_app.logger.debug(f"[{tag}] " + " ".join(parts))
    except Exception:
        try: current_app.logger.debug(f"[{tag}] <log-failed>")
        except Exception: pass

def req_info():
    try:
        return {
            "path": request.path, "method": request.method,
            "mimetype": request.mimetype, "content_length": request.content_length,
            "args": request.args.to_dict(flat=True), "remote_addr": request.remote_addr,
            "user_agent": str(getattr(request, "user_agent", "")),
        }
    except Exception:
        return {}

# ──────────────────────────────────────────────────────────
# Routing / assets
# ──────────────────────────────────────────────────────────
def safe_device_id(raw: str) -> str:
    return "".join(ch for ch in (raw or "") if ch.isalnum() or ch in "._-")[:64]

def asset_basename(device_id, w, h, mode):
    return f"{safe_device_id(device_id)}_{w}x{h}_{(mode or '').upper()}"

def decide_target_dir(need_approval: bool, final_approval: bool) -> str:
    # 최종 승인 또는 결재 미사용 → uploads, 아니면 in_review
    out = "uploads" if (final_approval or (not need_approval)) else "in_review"
    dbg("decide_target_dir", need_approval=need_approval, final_approval=final_approval, decided=out)
    return out

def asset_paths(device_id, w, h, mode, target_dir="uploads"):
    base = asset_basename(device_id, w, h, mode)
    dirs = get_asset_dirs()
    root = dirs[target_dir]
    bmp  = os.path.join(root, base + ".bmp")
    meta = os.path.join(root, base + ".meta.json")
    hdr  = os.path.join(root, base + ".h")
    binp = os.path.join(root, base + ".bin")
    dbg("asset_paths", device_id=device_id, size=f"{w}x{h}", mode=mode, target_dir=target_dir, bmp=bmp, bin=binp, meta=meta, hdr=hdr)
    return bmp, meta, hdr, binp

# ──────────────────────────────────────────────────────────
# Color/Fonts/Layers
# ──────────────────────────────────────────────────────────
def parse_color(v, default=(0,0,0,255)):
    if not v: return default
    if isinstance(v, (list, tuple)):
        if len(v)==4: return tuple(v)
        if len(v)==3: return (v[0],v[1],v[2],255)
    if isinstance(v, str):
        s=v.strip().lstrip("#")
        if len(s)==6:
            r,g,b=int(s[0:2],16),int(s[2:4],16),int(s[4:6],16); return (r,g,b,255)
        if len(s)==8:
            r,g,b,a=int(s[0:2],16),int(s[2:4],16),int(s[4:6],16),int(s[6:8],16); return (r,g,b,a)
    return default

def get_font(size_px: int) -> ImageFont.FreeTypeFont:
    paths=[]
    cfg = None
    try: cfg=current_app.config.get("EINK_FONT_PATH")
    except Exception: pass
    env = os.environ.get("EINK_FONT_PATH")
    for p in (cfg, env):
        if p and os.path.isfile(p): paths.append(p)
    paths += [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "C:/Windows/Fonts/malgun.ttf","C:/Windows/Fonts/malgunsl.ttf","C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc","/Library/Fonts/AppleGothic.ttf","/Library/Fonts/Arial.ttf",
    ]
    for p in paths:
        try:
            if os.path.isfile(p): return ImageFont.truetype(p, size_px)
        except Exception:
            continue
    return ImageFont.load_default()

def bind_sign_layer_user(layers, user_id):
    if not layers or not user_id: return layers
    for L in layers:
        if (L.get("type") or "").lower() == "sign" and not L.get("user_id"):
            L["user_id"] = user_id
    return layers

def log_layers_summary(layers, where):
    try:
        types = [(i, (L.get("type") or "").lower()) for i, L in enumerate(layers or [])]
        sample=[]
        for i, L in list(enumerate(layers or []))[:2]:
            sample.append({
                "idx": i, "type": (L.get("type") or "").lower(),
                "has_token": bool(L.get("upload_token")),
                "user_id": L.get("user_id"),
                "parent": L.get("parent") if (L.get("type") or "").lower()=="signbox" else None,
                "slots": len(L.get("slots") or []) if (L.get("type") or "").lower()=="signbox" else None,
                "x": L.get("x"), "y": L.get("y"), "w": L.get("w"), "h": L.get("h")
            })
        dbg("apply_layers:summary", where=where, count=len(layers or []), types=types, sample=sample)
    except Exception as e:
        dbg("apply_layers:summary", where=where, error=str(e))

def _overlay_from_store(token):
    info = _LAYER_STORE.get(token)
    if not info: return None
    try: return Image.open(info["path"]).convert("RGBA")
    except Exception: return None

# DB(User.photo_1) 우선으로 서명 이미지를 찾고, 없으면 기존 {user_id}.png로 폴백
def load_user_sign_rgba(user_id: int):
    """
    서명 이미지 로드 순서:
    1) RepositoryEINK.get_user_sign_path(user_id) → photo_1 경로 사용 (DB 우선)
       - 절대/상대/파일명만 모두 허용 (_resolve_sign_path로 정규화)
    2) 폴백: SIGN_BASE_DIR/{user_id}.png
    """
    if not user_id:
        return None

    # 1) DB photo_1 우선
    if RepositoryEINK is not None:
        try:
            db_path = RepositoryEINK.get_user_sign_path(user_id)  # e.g. 'signs/njsk2006.png' or 'D:/.../sign.png'
            img = _open_rgba(_resolve_sign_path(db_path))
            if img is not None:
                return img
        except Exception:
            pass

    # 2) 폴백: SIGN_BASE_DIR/{user_id}.png
    base = ""
    try:
        base = current_app.config.get("SIGN_BASE_DIR") or ""
    except Exception:
        pass
    guess = os.path.join(base, f"{user_id}.png") if base else f"{user_id}.png"
    return _open_rgba(guess)

# (교체) 현재 로그인 사용자의 서명 이미지도 DB photo_1을 우선 사용
def load_sign_image_for_current():
    """
    현재 로그인 사용자를 user_no(정수 PK) → userid(문자 ID) 순으로 확인하여
    DB(User.photo_1) 경로를 우선 사용하고, 그래도 없으면 SIGN_BASE_DIR/{uno or uid}.png 로 폴백한다.
    """
    uno, uid = current_user_ids()

    # 1) user_no → DB photo_1
    if RepositoryEINK is not None and uno:
        try:
            p = RepositoryEINK.get_user_sign_path(uno)
            img = _open_rgba(_resolve_sign_path(p))
            if img is not None:
                return img
        except Exception:
            pass

    # 2) userid → DB photo_1
    if RepositoryEINK is not None and uid:
        try:
            p = RepositoryEINK.get_user_sign_path_by_userid(uid)
            img = _open_rgba(_resolve_sign_path(p))
            if img is not None:
                return img
        except Exception:
            pass

    # 3) 폴백: SIGN_BASE_DIR/{uno or uid}.png
    base = ""
    try:
        base = current_app.config.get("SIGN_BASE_DIR") or ""
    except Exception:
        pass

    if uno:
        img = _open_rgba(os.path.join(base, f"{uno}.png") if base else f"{uno}.png")
        if img is not None:
            return img
    if uid:
        img = _open_rgba(os.path.join(base, f"{uid}.png") if base else f"{uid}.png")
        if img is not None:
            return img

    return None


def apply_layers_to_image(im, width, height, layers):
    if not layers: return im
    BX, BY = 1200.0, 1600.0
    sx = float(width) / BX
    sy = float(height) / BY
    smin = max(0.5, min(sx, sy))
    base = im.convert("RGBA")
    draw = ImageDraw.Draw(base)

    for L in (layers or []):
        ltype = (L.get("type") or "").lower()

        if ltype == "signbox":
            parent = L.get("parent") or {}
            tpl = L.get("tpl") or {}
            border_color = parse_color(tpl.get("border_color", "#198754"), (25,135,84,220))
            line_color   = parse_color(tpl.get("line_color",   "#198754"), (25,135,84,220))
            font_color   = parse_color(tpl.get("font_color",   "#14312d"), (20,49,45,255))
            font_size_px = int(round((tpl.get("font_size_px", 28)) * smin))
            line_thick   = max(1, int(round((tpl.get("line_thickness_px", 2)) * smin)))
            baselineY = float(tpl.get("line_pos_ratio", 0.72))
            hpad      = float(tpl.get("line_hpad_ratio", 0.08))

            px = int(round(parent.get("x", 0) * sx))
            py = int(round(parent.get("y", 0) * sy))
            pw = int(round(parent.get("w", 0) * sx))
            ph = int(round(parent.get("h", 0) * sy))

            if pw > 0 and ph > 0:
                draw.rectangle([px, py, px + pw, py + ph], outline=border_color, width=max(1, int(round(2 * smin))))
            slots = L.get("slots") or []
            font = get_font(font_size_px)
            pad  = max(2, int(round(6 * smin)))
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
                draw.rectangle([x0, y0, x1, y1], outline=border_color, width=max(1, int(round(1 * smin))))
                if label:
                    try: draw.text((x0 + pad, y0 + pad), label, fill=font_color, font=font)
                    except Exception: draw.text((x0 + pad, y0 + pad), label, fill=font_color)
                sw = x1 - x0; sh = y1 - y0
                line_y    = y0 + int(round(sh * baselineY))
                line_left = x0 + int(round(sw * hpad))
                line_right= x0 + int(round(sw * (1.0 - hpad)))
                if line_right > line_left:
                    draw.line([(line_left, line_y), (line_right, line_y)], fill=line_color, width=line_thick)
            continue

        if ltype in ("stamp", "validity", "sign"):
            ov = None
            token = L.get("upload_token")
            if token: ov = _overlay_from_store(token)
            if ov is None and ltype == "sign" and L.get("user_id"):
                ov = load_user_sign_rgba(L.get("user_id"))
            if ov is None: continue
            x = int(round((L.get("x", 0)) * sx))
            y = int(round((L.get("y", 0)) * sy))
            w = int(round((L.get("w", ov.width)) * sx))
            h = int(round((L.get("h", ov.height)) * sy))
            if w > 0 and h > 0:
                ov = ov.resize((w, h), Image.LANCZOS)
            base.alpha_composite(ov, dest=(x, y))
            continue

        if ltype == "text":
            text = L.get("text") or ""
            font_size   = int(L.get("fontSize", 28))
            color       = parse_color(L.get("color", "#000000"))
            align       = (L.get("align","left") or "left")
            bx = int(round(L.get("x",0) * sx))
            by = int(round(L.get("y",0) * sy))
            bw = int(round(L.get("w",300) * sx))
            bh = int(round(L.get("h",80) * sy))
            font = get_font(int(round(font_size * min(sx, sy))))
            pad = 4
            w_text, h_text = ImageDraw.Draw(Image.new("RGBA",(1,1))).textbbox((0,0), text, font=font)[2:]
            if align == "center": tx = bx + max(0, (bw - w_text)//2)
            elif align == "right": tx = bx + max(0, (bw - w_text))
            else: tx = bx + pad
            ty = by + max(0, (bh - h_text)//2)
            draw.text((tx, ty), text, fill=color, font=font)

        if ltype == "line":
            color = parse_color(L.get("color","#000000"))
            bx = int(round(L.get("x",0)*sx)); by = int(round(L.get("y",0)*sy))
            bw = int(round(L.get("w",300)*sx)); bh = max(1, int(round(L.get("h",2)*sy)))
            draw.rectangle([bx, by, bx+bw, by+bh], fill=color)

        if ltype == "rect":
            stroke = parse_color(L.get("stroke","#0d6efd"))
            fill   = parse_color(L.get("fill","rgba(13,110,253,0.04)"), (13,110,253,28))
            bx = int(round(L.get("x",0)*sx)); by = int(round(L.get("y",0)*sy))
            bw = int(round(L.get("w",300)*sx)); bh = int(round(L.get("h",200)*sy))
            draw.rectangle([bx,by,bx+bw,by+bh], outline=stroke, fill=fill, width=1)

    return base.convert("RGB")

def composite_sign_on_slot(im_canvas, width, height, layers, slot_role, sign_img_rgba):
    if not sign_img_rgba: return im_canvas
    base = im_canvas.convert("RGBA")
    BX, BY = 1200.0, 1600.0
    sx = float(width) / BX; sy = float(height) / BY
    signbox = next((L for L in (layers or []) if (L.get("type") or "").lower() == "signbox"), None)
    if not signbox: return im_canvas
    parent = signbox.get("parent") or {}; slots = signbox.get("slots") or []
    tgt = next((s for s in slots if (s.get("role") or "") == slot_role), None)
    if not tgt: return im_canvas
    px = int(round(parent.get("x", 0) * sx)); py = int(round(parent.get("y", 0) * sy))
    pw = int(round(parent.get("w", 0) * sx)); ph = int(round(parent.get("h", 0) * sy))
    x0 = px + int(round(tgt.get("x_rel", 0) * pw)); y0 = py + int(round(tgt.get("y_rel", 0) * ph))
    x1 = x0 + int(round(tgt.get("w_rel", 0) * pw)); y1 = y0 + int(round(tgt.get("h_rel", 0) * ph))
    w = max(1, x1 - x0); h = max(1, y1 - y0)
    ov = sign_img_rgba.resize((w, h), Image.LANCZOS)
    base.alpha_composite(ov, dest=(x0, y0))
    return base.convert("RGB")

# ──────────────────────────────────────────────────────────
# Preview & save helpers
# ──────────────────────────────────────────────────────────
def render_preview_png(svc, upload_id, width, height, mode, scale, percent, rotate, raw, layers):
    if raw:
        im = svc.load_upload_image(upload_id, page=1)
        if rotate in (90,180,270): im = im.rotate(rotate, expand=True)
        im_preview = svc._place_into_canvas(im, width, height, mode=scale, percent=percent)
        im_preview = apply_layers_to_image(im_preview, width, height, layers)
    else:
        im_preview = svc.build_preview_image(upload_id, page=1, width=width, height=height,
                                             mode=mode, scale=scale, percent=percent, rotate=rotate)
        im_preview = apply_layers_to_image(im_preview, width, height, layers)
    bio = BytesIO(); im_preview.save(bio, format="PNG"); bio.seek(0)
    return bio

def place_into_canvas_and_quantize(svc, upload_id, page, width, height, scale, percent, rotate, mode, layers):
    im_src = svc.load_upload_image(upload_id, page=page)
    if rotate in (90,180,270): im_src = im_src.rotate(rotate, expand=True)
    im_canvas = svc._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
    im_canvas = apply_layers_to_image(im_canvas, width, height, layers)
    mode_up = (mode or "BW").upper()
    if mode_up == "BWRY":
        im_proc = svc.quantize_to_BWRY(im_canvas); fmt = "BWRY"
    elif mode_up in ("BWRYBG","SPECTRA6","COLOR6"):
        im_proc = svc.quantize_to_BWRYBG(im_canvas); fmt = "BWRYBG"
    else:
        im_proc = svc.quantize_to_BW(im_canvas); fmt = "BW"
    return im_proc, fmt

def image_to_payload(im, fmt, size):
    return ImageToBytes.image_to_payload(im, fmt, size=size)

def save_meta_bundle(im, fmt, size, bmp_path, bin_path, meta_path,
                     device_id, target_dir, need_approval, final_approval, route_id, assignees):
    im.save(bmp_path, format="BMP")
    payload = image_to_payload(im, fmt, size=size)
    with open(bin_path, "wb") as f: f.write(payload)
    raw_len = len(payload) - 4
    crc32_le = int.from_bytes(payload[-4:], "little", signed=False)
    meta = {
        "device_id": device_id,
        "dir": target_dir,
        "file": os.path.basename(bmp_path),
        "bin":  os.path.basename(bin_path),
        "width": size[0], "height": size[1],
        "mode": fmt,
        "packing": {"BW":"1bpp", "BWRY":"2bpp", "BWRYBG":"3bpp"}[fmt],
        "raw_len": raw_len, "total_len": raw_len + 4,
        "crc32": f"{crc32_le:08x}",
        "ver": int(os.path.getmtime(bmp_path)),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "need_approval": need_approval,
        "final_approval": final_approval,
        "route_id": route_id,
        "assignees": assignees or {},
        "status": ("uploads" if target_dir == "uploads" else
                "approved" if target_dir == "approved" else
                "checked" if target_dir == "checked" else
                "in_review"),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return payload, meta

def render_flat_image(svc, upload_id, width, height, scale, percent, rotate, layers):
    im_src = svc.load_upload_image(upload_id, page=1)
    if rotate in (90,180,270): im_src = im_src.rotate(rotate, expand=True)
    im_canvas = svc._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
    im_canvas = apply_layers_to_image(im_canvas, width, height, layers)
    bio = BytesIO(); im_canvas.save(bio, format="PNG"); bio.seek(0)
    return bio

# ──────────────────────────────────────────────────────────
# Defaults / move / snapshots / approval helper
# ──────────────────────────────────────────────────────────
def default_devices():
    out=[]
    for i in range(1,7):
        num=f"{i:02d}"
        out.append({"device_no":num,"device_id":f"E{num}","default_width":480,"default_height":800})
    return out

def default_routes():
    return [
        {"id":1,"name":"기본 결재선","steps":[{"role":"review","assignee_userid":"reviewer01"},{"role":"approve","assignee_userid":"approver01"}]},
        {"id":2,"name":"부서장 결재","steps":[{"role":"review","assignee_userid":"teamlead"},{"role":"approve","assignee_userid":"head"}]},
    ]

def snapshot_to_signlayout_args(layout_snapshot: dict):
    if not layout_snapshot: return None
    canvas = layout_snapshot.get("canvas") or {}
    layers = layout_snapshot.get("layers") or []
    signbox = next((L for L in layers if (L.get("type") or "").lower() == "signbox"), None)
    if not signbox: return None
    parent = signbox.get("parent") or {}
    tpl = signbox.get("tpl") or {}
    slots = signbox.get("slots") or []
    return {
        "canvas_w": int(canvas.get("w", 1200)),
        "canvas_h": int(canvas.get("h", 1600)),
        "parent_box": {"x": int(parent.get("x",0)),"y": int(parent.get("y",0)),"w": int(parent.get("w",0)),"h": int(parent.get("h",0))},
        "tpl_json": tpl, "slots_json": slots, "layers_json": {"layers": layers},
    }

def move_bundle(src_dir: str, dst_dir: str, base_filename: str):
    names = [
        base_filename,
        os.path.splitext(base_filename)[0] + ".bin",
        os.path.splitext(base_filename)[0] + ".meta.json",
        os.path.splitext(base_filename)[0] + ".h",
    ]
    os.makedirs(dst_dir, exist_ok=True)
    moved=[]
    for name in names:
        s = os.path.join(src_dir, name)
        if os.path.isfile(s):
            d = os.path.join(dst_dir, os.path.basename(name))
            os.replace(s, d)
            moved.append({"from": s, "to": d})
    return moved

def find_latest_pending_for_user(userid: str):
    """
    공용 루트(D:/bmp_files) 하위의 모든 사용자별 디렉터리를 훑어
    결재 담당자(userid)가 'in_review' 또는 'checked'인 최신 1건을 찾는다.
    """
    import glob

    GLOBAL = get_global_asset_root()

    def _dirs_under(user_root: str) -> dict:
        return {
            "root": user_root,
            "uploads": os.path.join(user_root, "uploads"),
            "in_review": os.path.join(user_root, "in_review"),
            "checked": os.path.join(user_root, "checked"),
            "approved": os.path.join(user_root, "approved"),
            "bulletin_files": os.path.join(user_root, "bulletin_files"),
        }

    candidates = []

    try:
        for name in os.listdir(GLOBAL):
            user_root = os.path.join(GLOBAL, name)
            if not os.path.isdir(user_root):
                continue

            dirs = _dirs_under(user_root)

            def pick(dir_key, expect_status):
                root = dirs[dir_key]
                for meta in glob.glob(os.path.join(root, "*.meta.json")):
                    try:
                        with open(meta, "r", encoding="utf-8") as f:
                            js = json.load(f)
                        ass = js.get("assignees") or {}
                        status = js.get("status") or expect_status
                        if status != expect_status:
                            continue

                        need = (
                            (expect_status == "in_review" and ass.get("review") == userid) or
                            (expect_status == "checked"   and ass.get("approve") == userid)
                        )
                        if not need:
                            continue

                        bmp_base = js.get("file")
                        bmp_path = os.path.join(root, bmp_base) if bmp_base else ""
                        if not (bmp_base and os.path.isfile(bmp_path)):
                            continue

                        candidates.append({
                            "device_id": js.get("device_id"),
                            "stored_path": bmp_path,
                            "target_dir": dir_key,
                            "status": expect_status,
                            "assignees": ass,
                            "meta_path": meta,
                            "width": js.get("width", 1200),
                            "height": js.get("height", 1600),
                            "mode": js.get("mode", "BWRYBG"),
                            "_ver": js.get("ver", 0),
                            "_mtime": os.path.getmtime(meta),
                        })
                    except Exception:
                        continue

            pick("in_review", "in_review")
            pick("checked", "checked")

    except Exception:
        pass

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x.get("_ver", 0), x.get("_mtime", 0)), reverse=True)
    return candidates[0]

# ──────────────────────────────────────────────────────────
# Draft/direct saving helpers
# ──────────────────────────────────────────────────────────
def save_draft_bundle(svc, upload_id, width, height, mode, scale, percent, rotate, layers,
                      user_id, device_id="", memo="", filename=""):
    """
    결재 미사용 즉시 저장: bulletin_files/ 에 PNG+JSON 저장
    """
    im_src = svc.load_upload_image(upload_id, page=1)
    if rotate in (90,180,270): im_src = im_src.rotate(rotate, expand=True)
    im_canvas = svc._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
    im_canvas = apply_layers_to_image(im_canvas, width, height, layers)

    base = asset_basename(device_id or "BF", width, height, mode or "BW")
    stamp = int(time.time())
    dirs = get_asset_dirs()
    out_png = os.path.join(dirs["bulletin_files"], f"{base}_{stamp}.png")
    out_meta= os.path.join(dirs["bulletin_files"], f"{base}_{stamp}.json")

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    im_canvas.save(out_png, format="PNG")
    meta = {
        "type": "bulletin_direct",
        "device_id": device_id,
        "file": os.path.basename(out_png),
        "width": width, "height": height,
        "mode": (mode or "BW").upper(),
        "user_id": user_id,
        "filename": filename,
        "memo": memo,
        "layers": layers,
        "saved_at": datetime.now().isoformat(timespec="seconds")
    }
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"png": out_png, "meta": out_meta}
