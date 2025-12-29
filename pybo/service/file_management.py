# service/file_management.py
import os
import json
import time
import tempfile
import itertools
import shutil
from datetime import datetime
from io import BytesIO

from flask import current_app, request, g, session
from PIL import Image, ImageDraw, ImageFont


from pathlib import Path


try:
    import qrcode
except ImportError:
    qrcode = None

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
_UPLOADS: dict = {}
_LAYER_STORE: dict = {}
_UPLOAD_SEQ = itertools.count(1)

UPLOADS_BASE_DIR = r"D:\bmp_files"   # Per-user storage root on Windows


def get_upload_store():
    return _UPLOADS


def get_layer_store():
    return _LAYER_STORE


def next_upload_id():
    return next(_UPLOAD_SEQ)


_translator = None


def get_translation_service():
    """
    PDF/이미지 → 내부 upload_store 기반 변환 엔진.
    실제 디바이스 팔레트 적용은 place_into_canvas_and_quantize() 쪽에서 처리.
    """
    global _translator
    if _translator is None:
        _translator = FileTranslationBlackBG(uploads_store=_UPLOADS, pdf_dpi=200)
    return _translator

# ──────────────────────────────────────────────────────────
# 공용 폰트 로더
# ──────────────────────────────────────────────────────────

# def get_font(size: int, bold: bool = False):
#     """
#     Windows 기준 한글용 폰트 우선.
#     bold=True 이면 굵은 폰트 먼저 시도.
#     """
#     font_paths = []

#     # Windows 기본 폰트 경로
#     win_fonts = os.path.join("C:\\", "Windows", "Fonts")

#     # 맑은 고딕 계열
#     if bold:
#         font_paths.append(os.path.join(win_fonts, "malgunbd.ttf"))  # 맑은 고딕 Bold
#     font_paths.append(os.path.join(win_fonts, "malgun.ttf"))

#     # 나눔고딕 계열 (설치돼 있으면 사용)
#     if bold:
#         font_paths.append(os.path.join(win_fonts, "NanumGothicBold.ttf"))
#     font_paths.append(os.path.join(win_fonts, "NanumGothic.ttf"))

#     # 위 경로들을 순차적으로 시도
#     for path in font_paths:
#         try:
#             if os.path.isfile(path):
#                 return ImageFont.truetype(path, size)
#         except Exception:
#             continue

#     # 그래도 실패하면 Arial → 기본 폰트 순
#     try:
#         return ImageFont.truetype("arial.ttf", size)
#     except Exception:
#         return ImageFont.load_default()



# ──────────────────────────────────────────────────────────
# auto_font용 임시 캔버스 (공용)
# ──────────────────────────────────────────────────────────
_AUTO_FONT_IMG = Image.new("RGBA", (1, 1))
_AUTO_FONT_DRAW = ImageDraw.Draw(_AUTO_FONT_IMG)


def auto_font(
    text: str,
    box_w: int,
    box_h: int,
    max_px: int,
    min_px: int = 8,
    margin_ratio: float = 0.1,
    height_ratio: float = 0.65,
    bold: bool = False,
):
    """
    칸 크기에 맞게 폰트 크기를 자동 조정.
    - height_ratio: box_h 대비 시작 폰트 높이 비율 (0.65 ~ 0.95 정도)
    - margin_ratio: 좌우 여백 비율 (작을수록 글자가 더 커짐)
    """
    if not text:
        return get_font(min_px, bold=bold)

    # 텍스트 주변 여백
    inner_w = max(1, int(box_w * (1.0 - margin_ratio)))
    inner_h = max(1, int(box_h * (1.0 - margin_ratio) * 0.9))

    # 시작 폰트 크기 (박스 높이 비율 기준)
    size = max(min_px, min(max_px, int(box_h * float(height_ratio))))

    while size >= min_px:
        f = get_font(size, bold=bold)
        try:
            bbox = _AUTO_FONT_DRAW.textbbox((0, 0), text, font=f)
            tw = bbox[2] - bbox[0]
            th = bbox[3] - bbox[1]
        except Exception:
            tw, th = inner_w, inner_h

        if tw <= inner_w and th <= inner_h:
            return f

        size -= 1

    return get_font(min_px, bold=bold)


def center_top_bias(box_y0: int, box_h: int, text_h: int, bias: float = 0.5) -> int:
    """
    중앙 정렬 대신 살짝 위/아래로 치우치게 하고 싶을 때 사용.
    - bias=0.5 → 정확한 중앙
    - bias<0.5 → 위로 이동, bias>0.5 → 아래로 이동
    """
    return box_y0 + max(0, int((box_h - text_h) * float(bias)))


def draw_bold_text(draw: ImageDraw.ImageDraw, x: int, y: int,
                   text: str, font, fill, strength: int = 1):
    """
    간이 Bold 효과: 주변 픽셀에 여러 번 찍어서 두껍게 보이게.
    strength=1이면 1픽셀 정도 번짐.
    """
    if not text:
        return

    if strength <= 0:
        draw.text((x, y), text, fill=fill, font=font)
        return

    offsets = [(0, 0)]
    for dx in (-strength, 0, strength):
        for dy in (-strength, 0, strength):
            if dx == 0 and dy == 0:
                continue
            offsets.append((dx, dy))

    for dx, dy in offsets:
        draw.text((x + dx, y + dy), text, fill=fill, font=font)

def auto_font_vertical(
    text: str,
    box_w: int,
    box_h: int,
    max_px: int,
    min_px: int = 8,
    margin_ratio: float = 0.10,
    gap_ratio: float = 0.25,
):
    """
    세로쓰기 전용 폰트 자동 조정.

    - text: "작성부서" 같이 세로로 쓸 문자열
    - box_w, box_h: dept 컬럼 전체 박스 크기 (px)
    - max_px: 시작 폰트 크기 상한
    - min_px: 최소 폰트 크기
    - margin_ratio: 상하/좌우 여백 비율
    - gap_ratio: 글자 사이 간격 비율 (폰트 size 기준)
    """
    if not text:
        return get_font(min_px)

    # 박스 내부 usable 영역
    inner_w = max(1, int(box_w * (1.0 - margin_ratio)))
    inner_h = max(1, int(box_h * (1.0 - margin_ratio)))

    # 세로쓰기니까, 폭은 box_w 기준, 높이는 box_h 기준으로 제한
    size = max(min_px, min(max_px, int(min(box_w * 0.9, box_h * 0.35))))

    chars = list(text)

    while size >= min_px:
        f = get_font(size)

        max_char_w = 0
        total_h = 0

        # 글자 사이 간격 (폰트 크기 비율)
        gap = int(size * gap_ratio)

        for ch in chars:
            try:
                bbox = _AUTO_FONT_DRAW.textbbox((0, 0), ch, font=f)
                cw = bbox[2] - bbox[0]
                ch_h = bbox[3] - bbox[1]
            except Exception:
                cw, ch_h = size, size

            max_char_w = max(max_char_w, cw)
            total_h += ch_h

        # 위·아래 여백용 gap 하나씩 + 중간 gap들
        total_h += gap * (len(chars) + 1)

        # 폭/높이 둘 다 만족하면 OK
        if max_char_w <= inner_w and total_h <= inner_h:
            return f

        size -= 1

    return get_font(min_px)



# ──────────────────────────────────────────────────────────
# Sign path / 이미지 오픈 유틸
# ──────────────────────────────────────────────────────────
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
# def current_user_id():
#     """
#     숫자 PK(no) 또는 세션 기반 userid를 best-effort로 반환.
#     - 우선순위: g.user.no → session['no'] → request.user_id
#     """
#     if getattr(g, "user", None) is not None and getattr(g.user, "no", None) is not None:
#         return int(g.user.no)
#     if "userid" in session:
#         val = session.get("userid")
#         if isinstance(val, (int, str)) and str(val).strip():
#             return val if not str(val).isdigit() else int(val)
#     if getattr(request, "user_id", None):
#         try:
#             return int(request.user_id)
#         except Exception:
#             return str(request.user_id)
#     return None

def current_user_id():
    if getattr(g, "user", None) is not None and getattr(g.user, "no", None) is not None:
        return int(g.user.no)
    if "no" in session and str(session["no"]).isdigit():
        return int(session["no"])
    return None


def current_user_ids():
    """
    (user_no, userid 문자열) 쌍을 반환.
    가능한 한 둘 다 채우려고 시도.
    """
    uno, uid = None, None
    try:
        if getattr(g, "user", None) is not None:
            if getattr(g.user, "no", None) is not None:
                uno = int(g.user.no)
            if getattr(g.user, "userid", None):
                uid = str(g.user.userid)
    except Exception:
        pass
    try:
        if "no" in session and uno is None and str(session["no"]).isdigit():
            uno = int(session["no"])
        if "userid" in session and uid is None and str(session["userid"]).strip():
            uid = str(session["userid"]).strip()
    except Exception:
        pass
    try:
        if getattr(request, "user_id", None) and uno is None and uid is None:
            v = request.user_id
            if isinstance(v, int) or (isinstance(v, str) and v.isdigit()):
                uno = int(v)
            else:
                uid = str(v)
    except Exception:
        pass
    return uno, uid


def _safe_fragment(s) -> str:
    """
    파일/디렉토리명으로 사용할 수 있는 안전한 fragment 생성.
    - s 가 int/None 이 와도 안전하게 처리
    - 허용 문자: [0-9a-zA-Z], '.', '_', '-'
    - 결과가 비면 'guest' 리턴
    """
    # 1) 어떤 타입이 와도 문자열로 변환
    if s is None:
        raw = ""
    else:
        raw = str(s)

    # 2) 허용된 문자만 필터링
    cleaned = "".join(ch for ch in raw if ch.isalnum() or ch in "._-")

    # 3) 최대 길이 제한 + fallback
    return cleaned[:64] or "guest"




def current_userid_str():
    """
    경로 구성용 userid 문자열.
    - 우선순위: g.user.userid → session['userid'] → str(current_user_id()) → "guest"
    """
    if getattr(getattr(g, "user", None), "userid", None):
        return str(g.user.userid)
    if "userid" in session and str(session["userid"]).strip():
        return str(session["userid"]).strip()
    uid = current_user_id()
    return str(uid) if uid is not None else "guest"


# ──────────────────────────────────────────────────────────
# Paths & dirs
# 1) 문서 마스터 저장소 (approval_process / bulletin_files)
# 2) 디바이스 에셋 저장소 (BMP/BIN/meta)
# ──────────────────────────────────────────────────────────
def get_global_docs_root() -> str:
    """
    문서 마스터 저장소 루트.
    - EINK_DOC_ROOT 설정 우선
    - 없으면 D:/eink_docs
    """
    try:
        base = current_app.config.get("EINK_DOC_ROOT")
        if base:
            return base
    except Exception:
        pass
    return os.path.join("D:/", "eink_docs")


def get_global_asset_root() -> str:
    """
    디바이스용 에셋 저장 루트.
    - EINK_ASSET_ROOT 또는 과거 구성 호환을 위해 EINK_ROOT 사용
    - 설정 없으면 D:/bmp_files
    """
    try:
        base = current_app.config.get("EINK_ASSET_ROOT") or current_app.config.get("EINK_ROOT")
        if base:
            return base
    except Exception:
        pass
    return os.path.join("D:/", "bmp_files")


def get_doc_root_for_user(userid: str | None = None) -> str:
    uid = _safe_fragment(userid or current_userid_str())
    return os.path.join(get_global_docs_root(), uid)


# def get_doc_dir(userid: str, document_info_id: int) -> str:
#     """
#     {DOC_ROOT}/{userid}/approval_process/{doc_id}/
#     """
#     return os.path.join(get_doc_root_for_user(userid), "approval_process", str(document_info_id))


def get_doc_paths(userid: str, document_info_id: int, source_ext: str) -> dict:
    """
    DocumentInfo 1건에 대응되는 기본 파일 경로 세트.
    - original.{ext}
    - normalized.pdf
    - layout_snapshot.json
    - metadata.json
    """
    doc_dir = get_doc_dir(userid, document_info_id)
    os.makedirs(doc_dir, exist_ok=True)
    source_ext = (source_ext or "").lstrip(".") or "pdf"
    original = os.path.join(doc_dir, f"original.{source_ext}")
    pdf = os.path.join(doc_dir, "normalized.pdf")
    layout_json = os.path.join(doc_dir, "layout_snapshot.json")
    meta_json = os.path.join(doc_dir, "metadata.json")
    return {
        "doc_dir": doc_dir,
        "original": original,
        "normalized_pdf": pdf,
        "layout_snapshot_json": layout_json,
        "metadata_json": meta_json,
    }


def make_doc_relpath(userid: str, *parts: str) -> str:
    """
    DocumentInfo.stored_path / final_doc_relpath 에 저장할 상대경로 생성.
    예) make_doc_relpath("njsk2006", "approval_process", "123", "original.pptx")
        → "njsk2006/approval_process/123/original.pptx"
    """
    uid = _safe_fragment(userid)
    return "/".join([uid] + [p.strip("/\\") for p in parts if p])


def get_asset_root_for_user(userid: str | None = None) -> str:
    uid = _safe_fragment(userid or current_userid_str())
    return os.path.join(get_global_asset_root(), uid)


def get_asset_dirs(userid: str | None = None) -> dict:
    """
    디바이스 에셋용 경로.
    - uploads       : 최종 디바이스로 나가는 BIN/BMP
    - in_review     : (옵션) 에셋 레벨에서 상태를 나누고 싶을 때
    - checked       : "
    - approved      : "
    - bulletin_files: 결재 없이 바로 게시되는 PNG/BIN 저장소(필요 시)
    실제 워크플로 상태는 DB(DocumentInfo/EInkAsset)가 책임지고,
    이 디렉터리들은 단순 저장소 의미만 갖는다.
    """
    root = get_asset_root_for_user(userid)
    return {
        "root": root,
        "uploads": os.path.join(root, "uploads"),
        "in_review": os.path.join(root, "in_review"),
        "checked": os.path.join(root, "checked"),
        "approved": os.path.join(root, "approved"),
        "bulletin_files": os.path.join(root, "bulletin_files"),
    }


LAYER_TMP_DIR = os.path.join(tempfile.gettempdir(), "eink_layers")


def ensure_asset_dirs(userid: str | None = None):
    d = get_asset_dirs(userid)
    for _, p in d.items():
        os.makedirs(p, exist_ok=True)
    os.makedirs(LAYER_TMP_DIR, exist_ok=True)


# ──────────────────────────────────────────────────────────
# Logging helpers
# ──────────────────────────────────────────────────────────
def dump_json(obj, max_len=800):
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
        return (s[:max_len] + "...") if len(s) > max_len else s
    except Exception:
        return str(obj)


def dbg(tag: str, **kw):
    try:
        parts = [f"{k}={dump_json(v)}" for k, v in kw.items()]
        current_app.logger.debug(f"[FileMgmt:{tag}] " + " ".join(parts))
    except Exception:
        try:
            current_app.logger.debug(f"[FileMgmt:{tag}] <log-failed>")
        except Exception:
            pass


def req_info():
    try:
        return {
            "path": request.path,
            "method": request.method,
            "mimetype": request.mimetype,
            "content_length": request.content_length,
            "args": request.args.to_dict(flat=True),
            "remote_addr": request.remote_addr,
            "user_agent": str(getattr(request, "user_agent", "")),
        }
    except Exception:
        return {}


# ──────────────────────────────────────────────────────────
# Routing / assets (에셋 파일명/경로)
# ──────────────────────────────────────────────────────────
def safe_device_id(raw: str) -> str:
    return "".join(ch for ch in (raw or "") if ch.isalnum() or ch in "._-")[:64]


def asset_basename(device_id, w, h, mode):
    return f"{safe_device_id(device_id)}_{w}x{h}_{(mode or '').upper()}"


def decide_target_dir(need_approval: bool, final_approval: bool) -> str:
    """
    DocumentInfo.target_dir / 에셋 target_dir 추천 값.
    - 결재 필요 X 또는 최종 승인 완료 → 'uploads'
    - 그 외는 'in_review'부터 시작
    실제 status/target_dir 반영은 Service/Repository에서 수행.
    """
    out = "uploads" if (final_approval or (not need_approval)) else "in_review"
    dbg("decide_target_dir", need_approval=need_approval, final_approval=final_approval, decided=out)
    return out


def asset_paths(device_id, w, h, mode, target_dir="uploads", userid: str | None = None):
    """
    디바이스 에셋(BMP/BIN/meta/h) 경로 묶음 반환.
    - target_dir: 'uploads' | 'in_review' | 'checked' | 'approved' | 'bulletin_files'
    - userid: 명시하면 그 사용자 기준, 아니면 current_user 기준
    """
    base = asset_basename(device_id, w, h, mode)
    dirs = get_asset_dirs(userid)
    root = dirs[target_dir]
    bmp = os.path.join(root, base + ".bmp")
    meta = os.path.join(root, base + ".meta.json")
    hdr = os.path.join(root, base + ".h")
    binp = os.path.join(root, base + ".bin")
    dbg(
        "asset_paths",
        device_id=device_id,
        size=f"{w}x{h}",
        mode=mode,
        target_dir=target_dir,
        bmp=bmp,
        bin=binp,
        meta=meta,
        hdr=hdr,
    )
    return bmp, meta, hdr, binp


# ──────────────────────────────────────────────────────────
# Color/Fonts/Layers (내부 렌더링용)
# ──────────────────────────────────────────────────────────
def parse_color(v, default=(0, 0, 0, 255)):
    if not v:
        return default
    if isinstance(v, (list, tuple)):
        if len(v) == 4:
            return tuple(v)
        if len(v) == 3:
            return (v[0], v[1], v[2], 255)
    if isinstance(v, str):
        s = v.strip().lstrip("#")
        if len(s) == 6:
            r, g, b = int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
            return (r, g, b, 255)
        if len(s) == 8:
            r, g, b, a = (
                int(s[0:2], 16),
                int(s[2:4], 16),
                int(s[4:6], 16),
                int(s[6:8], 16),
            )
            return (r, g, b, a)
    return default


def get_font(size: int, bold: bool = False):
    """
    공용 폰트 로더.
    - EINK_FONT_PATH (config/env) 우선
    - 그 다음 Windows/리눅스/맥 기본 한글 폰트
    - bold=True면 가능한 Bold 계열 먼저 시도
    """
    paths: list[str] = []

    # 1) 설정/환경 변수 우선
    try:
        cfg = current_app.config.get("EINK_FONT_PATH")
    except Exception:
        cfg = None
    env = os.environ.get("EINK_FONT_PATH")

    for p in (cfg, env):
        if p and os.path.isfile(p):
            paths.append(p)

    # 2) Windows 기본 폰트 경로
    win_fonts = os.path.join("C:\\", "Windows", "Fonts")

    if bold:
        paths.append(os.path.join(win_fonts, "malgunbd.ttf"))          # 맑은 고딕 Bold
        paths.append(os.path.join(win_fonts, "NanumGothicBold.ttf"))   # 나눔고딕 Bold (있다면)
    paths.append(os.path.join(win_fonts, "malgun.ttf"))
    paths.append(os.path.join(win_fonts, "NanumGothic.ttf"))

    # 3) 리눅스/맥 공통 경로도 백업으로 추가
    paths += [
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/AppleGothic.ttf",
        "/Library/Fonts/Arial.ttf",
        "C:/Windows/Fonts/arial.ttf",
    ]

    # 실제 로딩
    for p in paths:
        try:
            if os.path.isfile(p):
                return ImageFont.truetype(p, size)
        except Exception:
            continue

    return ImageFont.load_default()



def bind_sign_layer_user(layers, user_id):
    """
    내부 layers 중 type=='sign'인데 user_id가 비어 있으면 기본 user_id 주입.
    """
    if not layers or not user_id:
        return layers
    for L in layers:
        if (L.get("type") or "").lower() == "sign" and not L.get("user_id"):
            L["user_id"] = user_id
    return layers


def log_layers_summary(layers, where):
    try:
        types = [(i, (L.get("type") or "").lower()) for i, L in enumerate(layers or [])]
        sample = []
        for i, L in list(enumerate(layers or []))[:2]:
            sample.append(
                {
                    "idx": i,
                    "type": (L.get("type") or "").lower(),
                    "has_token": bool(L.get("upload_token")),
                    "user_id": L.get("user_id"),
                    "parent": L.get("parent")
                    if (L.get("type") or "").lower() == "signbox"
                    else None,
                    "slots": len(L.get("slots") or [])
                    if (L.get("type") or "").lower() == "signbox"
                    else None,
                    "x": L.get("x"),
                    "y": L.get("y"),
                    "w": L.get("w"),
                    "h": L.get("h"),
                }
            )
        dbg("layers:summary", where=where, count=len(layers or []), types=types, sample=sample)
    except Exception as e:
        dbg("layers:summary", where=where, error=str(e))


def _overlay_from_store(token):
    info = _LAYER_STORE.get(token)
    if not info:
        return None
    try:
        return Image.open(info["path"]).convert("RGBA")
    except Exception:
        return None


# ──────────────────────────────────────────────────────────
# 서명 이미지 로딩 (DB photo_1 우선)
# ──────────────────────────────────────────────────────────
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
            db_path = RepositoryEINK.get_user_sign_path(user_id)
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

def load_stamp_rgba(stamp_id: int):
    """
    stamp_id → DB 조회 → stored_path 로 이미지 오픈(RGBA)
    """
    if not stamp_id or RepositoryEINK is None:
        return None

    try:
        stored_path = RepositoryEINK.get_stamp_stored_path(int(stamp_id), active_only=True)
        if not stored_path:
            return None

        # ✅ 상대경로 대응 (SIGN 로직 재사용)
        return _open_rgba(_resolve_sign_path(stored_path))
    except Exception:
        return None


def load_sign_image_for_current():
    """
    현재 로그인 사용자를 user_no(정수 PK) → userid(문자 ID) 순으로 확인하여
    DB(User.photo_1) 경로를 우선 사용하고,
    그래도 없으면 SIGN_BASE_DIR/{uno or uid}.png 로 폴백한다.
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


# ──────────────────────────────────────────────────────────
# editor_layers → 내부 렌더링 layers 변환
# ──────────────────────────────────────────────────────────
def convert_editor_layers_to_render_layers(editor_layers: list[dict]) -> list[dict]:
    """
    프론트에서 온 editor_layers(approval_box/period_box/message_box/stamp_box/qr_box 등)를
    내부 렌더링용 layers 구조로 변환한다.

    내부 레이어 타입:
      - signbox : 결재란 전체 박스 + 슬롯 정보
      - period  : 유효기간 텍스트 박스
      - message : 자유 텍스트 박스
      - stamp   : 직인/도장 이미지 박스
      - qr      : QR 코드 박스
      - 그 외   : line/rect 등은 그대로 통과
    """
    out: list[dict] = []
    if not editor_layers:
        return out

    for L in editor_layers:
        ltype = (L.get("type") or "").lower()

        # 1) approval_box → signbox
        if ltype == "approval_box":
            parent = {
                "x": int(L.get("x", 0)),
                "y": int(L.get("y", 0)),
                "w": int(L.get("w", 0)),
                "h": int(L.get("h", 0)),
            }
            cols = L.get("columns") or []
            col_count = max(1, len(cols))

            tpl = L.get("tpl") or {}
            # sign_box 템플릿 기본값 세팅
            tpl.setdefault("border_color", "#198754")
            tpl.setdefault("line_color", "#198754")
            tpl.setdefault("font_color", "#14312d")
            tpl.setdefault("font_size_px", 28)
            tpl.setdefault("line_thickness_px", 2)
            tpl.setdefault("line_pos_ratio", 0.72)
            tpl.setdefault("line_hpad_ratio", 0.08)

            slots = []
            for idx, c in enumerate(cols, start=1):
                # 균등 분할 (0~1) 기준
                x_rel = float(idx - 1) / col_count
                w_rel = 1.0 / col_count
                y_rel = 0.0
                h_rel = 1.0

                dept = c.get("dept") or ""
                role = c.get("role") or ""
                raw_name = c.get("user_name")
                raw_id = c.get("user_id")
                username = str(raw_name if raw_name not in (None, "") else (raw_id if raw_id is not None else ""))

                label = dept or role or username

                rt = c.get("runtime") or {}
                slot_status = rt.get("status")
                if slot_status is None:
                    slot_status = c.get("status")

                slot_stamp_text = rt.get("stamp_text")
                if slot_stamp_text is None:
                    slot_stamp_text = c.get("stamp_text")

                slot = {
                    "status": c.get("status") or (c.get("runtime") or {}).get("status"),
                    "stamp_text": c.get("stamp_text") or (c.get("runtime") or {}).get("stamp_text"),
                    "id": c.get("id"),
                    "col_index": idx,
                    "group": c.get("group"),  # draft / check 등
                    "dept": dept,
                    "role": role,
                    "user_id": c.get("user_id"),
                    "user_name": username,
                    "user_photo_1": c.get("user_photo_1"),
                    "x_rel": x_rel,
                    "y_rel": y_rel,
                    "w_rel": w_rel,
                    "h_rel": h_rel,
                    "label": label,
                }
                slots.append(slot)

            out.append(
                {
                    "type": "signbox",
                    "id": L.get("id"),
                    "parent": parent,
                    "tpl": tpl,
                    "slots": slots,
                }
            )
            continue

        # 2) period_box → period layer (텍스트 박스)
        if ltype == "period_box":
            # 1순위: editor가 만들어준 text
            text = L.get("text") or ""

            # 2순위: start/end가 있으면 거기서 생성 (호환용)
            if not text:
                start = L.get("start") or ""
                end = L.get("end") or ""
                if start or end:
                    text = f"{start} ~ {end}"

            out.append(
                {
                    "type": "period",
                    "id": L.get("id"),
                    "x": L.get("x", 0),
                    "y": L.get("y", 0),
                    "w": L.get("w", 300),
                    "h": L.get("h", 80),
                    "text": text,
                    "fontSize": L.get("fontSize", 24),
                    "color": L.get("color", "#000000"),
                    "align": L.get("align", "left"),
                }
            )
            continue

        # 3) message_box → message layer (텍스트 박스)
        if ltype == "message_box":
            out.append(
                {
                    "type": "message",
                    "id": L.get("id"),
                    "x": L.get("x", 0),
                    "y": L.get("y", 0),
                    "w": L.get("w", 600),
                    "h": L.get("h", 80),
                    "text": L.get("text", ""),
                    "fontSize": L.get("fontSize", 24),
                    "color": L.get("color", "#000000"),
                    "align": L.get("align", "left"),
                }
            )
            continue

        # 4) stamp_box → stamp layer (직인/도장)
        if ltype == "stamp_box":
            stamp = L.get("stamp") or {}
            out.append(
                {
                    "type": "stamp",
                    "id": L.get("id"),
                    "x": L.get("x", 0),
                    "y": L.get("y", 0),
                    "w": L.get("w", 150),
                    "h": L.get("h", 150),
                    "upload_token": L.get("upload_token"),

                    # ✅ 핵심: DB lookup용 키 유지
                    "stamp_id": stamp.get("id"),
                    "stamp_url": stamp.get("url"),
                    "stamp_size": stamp.get("size") or L.get("size"),
                    "stamp_type": stamp.get("type"),   # company/user 등
                    "stamp_name": stamp.get("name"),
                }
            )
            continue


        # 5) qr_box → qr layer (QR 코드)
        if ltype == "qr_box":
            out.append(
                {
                    "type": "qr",
                    "id": L.get("id"),
                    "x": L.get("x", 0),
                    "y": L.get("y", 0),
                    "w": L.get("w", 100),   # 기본 100
                    "h": L.get("h", 100),
                    "text": L.get("text", ""),      # QR 데이터
                    "qr_size": L.get("qr_size"),    # 옵션: 강제 크기 지정 시
                }
            )
            continue

        # 6) 이미 내부 타입(signbox/text/line/rect/sign/stamp/qr 등)이면 그대로 유지
        out.append(L)

    log_layers_summary(out, where="convert_editor_layers_to_render_layers")
    return out

def _normalize_layout_snapshot(layout_snapshot) -> dict:
    """
    layout_snapshot_json이 dict로 오기도 하고, JSON 문자열(TEXT)로 오기도 하므로 통일.
    """
    if layout_snapshot is None:
        return {}
    if isinstance(layout_snapshot, dict):
        return layout_snapshot
    if isinstance(layout_snapshot, str):
        s = layout_snapshot.strip()
        if not s:
            return {}
        try:
            obj = json.loads(s)
            return obj if isinstance(obj, dict) else {}
        except Exception:
            return {}
    return {}

def apply_editor_layout_to_image(im, width: int, height: int, layout_snapshot: dict):
    ls = layout_snapshot or {}

    # 1) 구 구조 우선
    editor_layers = ls.get("editor_layers") or ls.get("layers") or []

    # 2) 신 구조(또는 혼합) 호환: layers_json 지원
    if (not editor_layers) and ("layers_json" in ls):
        raw = ls.get("layers_json")
        if isinstance(raw, dict) and "layers" in raw:
            editor_layers = raw.get("layers") or []
        elif isinstance(raw, list):
            editor_layers = raw

    layers = convert_editor_layers_to_render_layers(editor_layers)

    # 🔥 디버깅 로그(필수)
    try:
        current_app.logger.debug(
            "[apply_editor_layout_to_image] keys=%s editor_layers=%d internal_layers=%d",
            list(ls.keys()),
            len(editor_layers or []),
            len(layers or []),
        )
    except Exception:
        pass

    return apply_layers_to_image(im, width, height, layers)


#-----------------------------------------------------------
#            QR 생성 
#------------------------------------------------------------


def generate_qr_rgba(text: str, size: int = 100) -> Image.Image:
    """
    텍스트로부터 RGBA QR 이미지를 생성.
    - qrcode 라이브러리가 있으면 실제 QR 생성
    - 없으면 단순 placeholder 박스를 생성
    """
    size = max(20, int(size or 100))

    # 1) qrcode 라이브러리를 사용할 수 있는 경우
    if qrcode is not None and text:
        qr = qrcode.QRCode(
            version=None,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(text)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGBA")
        qr_img = qr_img.resize((size, size), Image.LANCZOS)
        return qr_img

    # 2) fallback: 단순 사각형 + "QR" 텍스트
    img = Image.new("RGBA", (size, size), (255, 255, 255, 0))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, size - 1, size - 1], outline=(0, 0, 0, 255), width=3)
    d.text((size // 3, size // 2 - 8), "QR", fill=(0, 0, 0, 255))
    return img

def _safe_photo_abs(photo_filename: str) -> str | None:
    if not photo_filename:
        return None
    base = os.path.basename(photo_filename)
    if base != photo_filename or any(x in base for x in ("..", "/", "\\")):
        return None
    pload_folder = current_app.config.get("SIGN_BASE_DIR")  # ✅ 여기서 전역 설정 읽기
    p = os.path.join(pload_folder, base)
    return p if os.path.isfile(p) else None

def _paste_fit(im_bg: Image.Image, im_fg: Image.Image, box: tuple[int, int, int, int]) -> None:
    # box=(x,y,w,h)
    x, y, w, h = box
    if w <= 2 or h <= 2:
        return
    fg = im_fg.convert("RGBA")
    bw, bh = fg.size
    scale = min(w / bw, h / bh)
    nw, nh = max(1, int(bw * scale)), max(1, int(bh * scale))
    fg = fg.resize((nw, nh))
    px = x + (w - nw) // 2
    py = y + (h - nh) // 2
    im_bg.paste(fg, (px, py), fg)


# ──────────────────────────────────────────────────────────
# 실제 레이어 합성 엔진
# ──────────────────────────────────────────────────────────
def apply_layers_to_image(im, width, height, layers):
    """
    내부 layers(이미 convert_editor_layers_to_render_layers 통과한 구조)를
    E-INK 캔버스 위에 합성.
    """
    if not layers:
        return im

    # BASE 좌표계(에디터 기준)
    BX, BY = 1200.0, 1600.0
    sx = float(width) / BX
    sy = float(height) / BY
    smin = max(0.5, min(sx, sy))

    base = im.convert("RGBA")
    draw = ImageDraw.Draw(base)

    SIGNBOX_TYPES   = {"signbox", "approval_box", "approval_signbox"}
    STAMP_TYPES     = {"stamp", "stamp_box", "seal", "dojang"}
    QR_TYPES        = {"qr", "qrcode", "qrcode_box", "qr_box"}
    VALIDITY_TYPES  = {"validity"}
    SIGN_IMG_TYPES  = {"sign", "signature", "user_sign"}
    TEXT_TYPES      = {"text", "message", "message_box", "text_box", "period"}
    LINE_TYPES      = {"line", "line_box"}
    RECT_TYPES      = {"rect", "rect_box", "box"}

    current_app.logger.debug(f"LAYER : {layers}")

    for L in (layers or []):
        ltype = (L.get("type") or "").lower()

        # ─────────────────────
        # 1) 결재란 전체 박스 (프론트와 동일한 3행 구조)
        # ─────────────────────
        if ltype in SIGNBOX_TYPES:
            parent = L.get("parent") or {}
            tpl = L.get("tpl") or {}

            # 모든 선/텍스트는 검정
            border_color = parse_color("#000000", (0, 0, 0, 255))
            line_color   = parse_color("#000000", (0, 0, 0, 255))
            font_color   = parse_color("#000000", (0, 0, 0, 255))

            # 3행 비율 [header, stamp, name]
            row_ratio = tpl.get("row_ratio") or [1, 3, 1]
            if not isinstance(row_ratio, (list, tuple)) or len(row_ratio) != 3:
                row_ratio = [1, 3, 1]
            r0, r1, r2 = row_ratio
            rsum = float(r0 + r1 + r2) or 1.0
            hdr_ratio   = r0 / rsum
            stamp_ratio = r1 / rsum
            name_ratio  = r2 / rsum

            # 직인 row 내에서 사용할 영역 비율
            stamp_scale = float(tpl.get("stamp_scale", 0.8))
            stamp_scale = max(0.1, min(stamp_scale, 1.0))

            # 사이드 안에서 dept 컬럼 폭 비율 (작성부서/확인부서)
            dept_col_ratio = float(tpl.get("dept_col_ratio", 0.18))
            dept_col_ratio = max(0.05, min(dept_col_ratio, 0.4))

            px = int(round(parent.get("x", 0) * sx))
            py = int(round(parent.get("y", 0) * sy))
            pw = int(round(parent.get("w", 0) * sx))
            ph = int(round(parent.get("h", 0) * sy))

            if pw <= 0 or ph <= 0:
                continue

            border_width = max(1, int(round(2 * smin)))

            # 바깥 박스: ✅ 배경을 흰색(불투명)으로 채워서 아래 레이어가 안 비치게
            bg_white = parse_color("#ffffff", (255, 255, 255, 255))

            # 바깥 박스
            draw.rectangle(
                [px, py, px + pw, py + ph],
                fill=bg_white,              # ✅ 핵심
                outline=border_color,
                width=border_width,
            )

            # 3행 높이 계산
            hdr_h   = int(round(ph * hdr_ratio))
            stamp_h = int(round(ph * stamp_ratio))
            name_h  = ph - hdr_h - stamp_h

            hdr_y0 = py
            hdr_y1 = hdr_y0 + hdr_h
            stamp_y0 = hdr_y1
            stamp_y1 = stamp_y0 + stamp_h
            name_y0 = stamp_y1
            name_y1 = py + ph

            # 행 구분선 (가로)
            draw.line([(px, hdr_y1), (px + pw, hdr_y1)], fill=border_color, width=border_width)
            draw.line([(px, stamp_y1), (px + pw, stamp_y1)], fill=border_color, width=border_width)

            slots = L.get("slots") or []

            # 좌/우 그룹 분리 및 col_index 순 정렬
            draft_slots = sorted(
                [s for s in slots if s.get("group") == "draft"],
                key=lambda s: int(s.get("col_index") or 0),
            )
            check_slots = sorted(
                [s for s in slots if s.get("group") == "check"],
                key=lambda s: int(s.get("col_index") or 0),
            )

            nd = len(draft_slots)
            nc = len(check_slots)
            if nd + nc == 0:
                continue

            # 🔹 weight 계산 방식 수정
            if nd > 0 and nc > 0:
                weight_d = nd
                weight_c = nc
            elif nd > 0 and nc == 0:
                weight_d = 1
                weight_c = 0
            elif nd == 0 and nc > 0:
                weight_d = 0
                weight_c = 1
            else:
                continue

            total_w = float(weight_d + weight_c) or 1.0

            if weight_d > 0:
                draft_w = int(round(pw * weight_d / total_w))
            else:
                draft_w = 0
            check_w = pw - draft_w

            # 공통 dept 폭 계산
            if draft_w > 0 and check_w > 0:
                base_side = min(draft_w, check_w)
            else:
                base_side = max(draft_w, check_w)

            dept_w_px = int(round(base_side * dept_col_ratio))
            dept_w_px = max(int(20 * smin), min(dept_w_px, base_side // 2))

            def side_geometry(side_x0, side_w, n_cols, dept_w):
                if n_cols <= 0 or side_w <= 0:
                    return None
                cols_w_total = side_w - dept_w
                col_w = int(round(cols_w_total / n_cols))
                return {
                    "x0": side_x0,
                    "x1": side_x0 + side_w,
                    "dept_w": dept_w,
                    "col_w": col_w,
                }

            # 왼쪽: draft
            draft_geo = side_geometry(px, draft_w, nd, dept_w_px if draft_w > 0 else 0)
            # 오른쪽: check
            check_geo = side_geometry(px + draft_w, check_w, nc, dept_w_px if check_w > 0 else 0)

            # dept 컬럼 배경 그레이
            dept_bg = parse_color("#e9ecef", (233, 236, 239, 255))

            def draw_side(side_slots, geo, dept_label):
                if not side_slots or not geo:
                    return

                x0 = geo["x0"]
                dept_w = geo["dept_w"]
                col_w = geo["col_w"]

                # dept 컬럼 영역
                dept_x0 = x0
                dept_x1 = x0 + dept_w
                draw.rectangle(
                    [dept_x0, py, dept_x1, py + ph],
                    fill=dept_bg,
                    outline=border_color,
                    width=border_width,
                )

                # dept 세로 텍스트
                chars = list(dept_label)
                dept_font = auto_font_vertical(
                    dept_label,
                    box_w=dept_w,
                    box_h=ph,
                    max_px=int(ph * 0.20),
                    min_px=int(9 * smin),
                )

                total_h = 0
                char_sizes = []
                for ch in chars:
                    try:
                        bbox = _AUTO_FONT_DRAW.textbbox((0, 0), ch, font=dept_font)
                        cw = bbox[2] - bbox[0]
                        ch_h = bbox[3] - bbox[1]
                    except Exception:
                        cw, ch_h = dept_w, int(ph / max(1, len(chars)))
                    char_sizes.append((cw, ch_h))
                    total_h += ch_h

                gap = int(max(2 * smin, (ph - total_h) / max(1, len(chars) + 1)))
                cur_y = py + gap

                for i, ch in enumerate(chars):
                    cw, ch_h = char_sizes[i]
                    tx = dept_x0 + max(0, (dept_w - cw) // 2)
                    ty = cur_y
                    try:
                        draw.text((tx, ty), ch, fill=font_color, font=dept_font)
                    except Exception:
                        draw.text((tx, ty), ch, fill=font_color, font=dept_font)
                    cur_y += ch_h + gap

                # dept 오른쪽 세로 구분선
                draw.line([(dept_x1, py), (dept_x1, py + ph)], fill=border_color, width=border_width)

                # 컬럼별 세로선 + 내부 텍스트/도장
                for idx, S in enumerate(side_slots):
                    col_x0 = dept_x1 + idx * col_w
                    col_x1 = col_x0 + col_w

                    # 마지막 컬럼 오른쪽 경계
                    draw.line([(col_x1, py), (col_x1, py + ph)], fill=border_color, width=border_width)

                    # Header 텍스트 (role)
                    role_label = (S.get("role") or "").strip()
                    if role_label:
                        header_font = auto_font(
                            role_label,
                            box_w=col_w,
                            box_h=hdr_h,
                            max_px=int(hdr_h * 0.8),
                            min_px=int(10 * smin),
                            height_ratio=0.6,
                            bold=False,
                        )
                        try:
                            bbox = _AUTO_FONT_DRAW.textbbox((0, 0), role_label, font=header_font)
                            tw = bbox[2] - bbox[0]
                            th = bbox[3] - bbox[1]
                        except Exception:
                            tw, th = col_w, hdr_h

                        tx = col_x0 + max(0, (col_w - tw) // 2)
                        ty = center_top_bias(hdr_y0, hdr_h, th, bias=0.35)
                        draw.text((tx, ty), role_label, fill=font_color, font=header_font)

                    # Stamp row 영역 (도장 이미지 위치)
                    stamp_row_h = stamp_h
                    stamp_box_size = int(round(min(col_w, stamp_row_h) * stamp_scale))
                    stamp_cx = col_x0 + col_w // 2
                    stamp_cy = stamp_y0 + stamp_row_h // 2

                    stamp_box_x0 = stamp_cx - stamp_box_size // 2
                    stamp_box_y0 = stamp_cy - stamp_box_size // 2
                    stamp_box_x1 = stamp_box_x0 + stamp_box_size
                    stamp_box_y1 = stamp_box_y0 + stamp_box_size

                    # ✅ [ADD] 작성(role=="작성")이면 user_photo_1을 stamp 영역에 합성, 없으면 "완료"
                    # ✅ [FIX] col_index + status 기반으로 도장/완료/반려 표시
                    try:
                        role = (S.get("role") or "").strip()
                        col_index = int(S.get("col_index") or 0)

                        # status는 스냅샷이면 None일 수 있음 → 기본값 ''
                        status = (S.get("status") or "").strip().lower()

                        # 사용자 서명 토큰(있으면 우선)
                        photo_fn = (S.get("user_photo_1") or "").strip()
                        photo_path = _safe_photo_abs(photo_fn) if photo_fn else None
                        exists = bool(photo_path and os.path.isfile(photo_path))

                        current_app.logger.debug(
                            "[signbox:slot] group=%s col_index=%s role=%r status=%r user_id=%r "
                            "photo_fn=%r photo_path=%r exists=%s stamp_box=(%d,%d,%d,%d)",
                            S.get("group"), col_index, role, status, S.get("user_id"),
                            photo_fn, photo_path, exists,
                            stamp_box_x0, stamp_box_y0, stamp_box_x1, stamp_box_y1
                        )

                        pad = max(2, int(stamp_box_size * 0.05))
                        sign_x = stamp_box_x0 + pad
                        sign_y = stamp_box_y0 + pad
                        sign_w = max(1, stamp_box_size - 2 * pad)
                        sign_h = max(1, stamp_box_size - 2 * pad)

                        # ---------------------------------------------------------
                        # ✅ 표시 규칙(추천)
                        #  - status가 done/approved면: 서명(있으면) 또는 "완료"
                        #  - status가 reject/rejected면: "반려"
                        #  - status가 없으면(스냅샷) : col_index==1(작성)만 기본 표시(기존과 동일)
                        # ---------------------------------------------------------
                        is_done = status in ("done", "approved", "approve", "signed")
                        is_reject = status in ("reject", "rejected", "deny", "returned")

                        should_draw = False
                        draw_mode = None  # "sig" | "done" | "reject"

                        if is_reject:
                            should_draw = True
                            draw_mode = "reject"
                        elif is_done:
                            should_draw = True
                            draw_mode = "sig" if exists else "done"
                        else:
                            # status가 비어있으면(현재 너 로그처럼 None) → 작성칸(col_index=1)만 기본 표시
                            if col_index == 1:
                                should_draw = True
                                draw_mode = "sig" if exists else "done"

                        current_app.logger.debug(
                            "[signbox:decision] col_index=%s role=%r status=%r should_draw=%s draw_mode=%s",
                            col_index, role, status, should_draw, draw_mode
                        )

                        if should_draw:
                            if draw_mode == "sig":
                                try:
                                    with Image.open(photo_path) as sig:
                                        _paste_fit(base, sig, (sign_x, sign_y, sign_w, sign_h))
                                    current_app.logger.debug("[signbox:render] pasted signature col_index=%s", col_index)
                                except Exception:
                                    current_app.logger.debug(
                                        "[signbox:render] signature open/paste failed col_index=%s photo_path=%r",
                                        col_index, photo_path, exc_info=True
                                    )
                                    # 실패하면 텍스트로 fallback
                                    draw_mode = "done"

                            if draw_mode == "done":
                                done_txt = "완료"
                                done_font = auto_font(
                                    done_txt,
                                    box_w=sign_w,
                                    box_h=sign_h,
                                    max_px=int(sign_h * 0.7),
                                    min_px=int(10 * smin),
                                    height_ratio=0.6,
                                    bold=False,
                                )
                                bbox = _AUTO_FONT_DRAW.textbbox((0, 0), done_txt, font=done_font)
                                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                                tx = sign_x + max(0, (sign_w - tw) // 2)
                                ty = sign_y + max(0, (sign_h - th) // 2)
                                draw.text((tx, ty), done_txt, fill=font_color, font=done_font)
                                current_app.logger.debug("[signbox:render] drew DONE text col_index=%s", col_index)

                            if draw_mode == "reject":
                                rej_txt = "반려"
                                rej_font = auto_font(
                                    rej_txt,
                                    box_w=sign_w,
                                    box_h=sign_h,
                                    max_px=int(sign_h * 0.7),
                                    min_px=int(10 * smin),
                                    height_ratio=0.6,
                                    bold=False,
                                )
                                bbox = _AUTO_FONT_DRAW.textbbox((0, 0), rej_txt, font=rej_font)
                                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                                tx = sign_x + max(0, (sign_w - tw) // 2)
                                ty = sign_y + max(0, (sign_h - th) // 2)
                                draw.text((tx, ty), rej_txt, fill=font_color, font=rej_font)
                                current_app.logger.debug("[signbox:render] drew REJECT text col_index=%s", col_index)

                    except Exception:
                        current_app.logger.debug("[signbox] stamp render block failed", exc_info=True)

                    except Exception:
                        current_app.logger.debug("[signbox] user_photo_1 paste failed", exc_info=True)

                    # Name row 텍스트 (user_name)
                    name_label = (S.get("user_name") or "").strip()
                    if name_label:
                        name_font = auto_font(
                            name_label,
                            box_w=col_w,
                            box_h=name_h,
                            max_px=int(name_h * 0.8),
                            min_px=int(9 * smin),
                            height_ratio=0.55,
                            bold=False,
                        )
                        try:
                            bbox = _AUTO_FONT_DRAW.textbbox((0, 0), name_label, font=name_font)
                            tw = bbox[2] - bbox[0]
                            th = bbox[3] - bbox[1]
                        except Exception:
                            tw, th = col_w, name_h

                        tx = col_x0 + max(0, (col_w - tw) // 2)
                        ty = center_top_bias(name_y0, name_h, th, bias=0.40)
                        draw.text((tx, ty), name_label, fill=font_color, font=name_font)


            # 왼쪽 draft: "작성부서"
            if draft_geo:
                draw_side(draft_slots, draft_geo, "작성부서")

            # 오른쪽 check: "확인부서"
            if check_geo:
                draw_side(check_slots, check_geo, "확인부서")

            continue

        # ─────────────────────
        # 2) 도장/QR/서명 이미지 오버레이
        # ─────────────────────
        if (
            ltype in STAMP_TYPES
            or ltype in QR_TYPES
            or ltype in VALIDITY_TYPES
            or ltype in SIGN_IMG_TYPES
        ):
            ov = None
            token = L.get("upload_token")

            bx = float(L.get("x", 0))
            by = float(L.get("y", 0))
            bw_base = float(L.get("w", 0) or 0)
            bh_base = float(L.get("h", 0) or 0)

            if token:
                ov = _overlay_from_store(token)

            if ov is None and ltype in STAMP_TYPES:
                sid = L.get("stamp_id")
                if sid:
                    ov = load_stamp_rgba(int(sid))

            if ov is None and ltype in QR_TYPES:
                text = L.get("text") or ""
                size_hint = max(
                    100,
                    int(bw_base) if bw_base > 0 else 0,
                    int(bh_base) if bh_base > 0 else 0,
                    int(L.get("qr_size") or 0),
                )
                ov = generate_qr_rgba(text, size=size_hint)

            if ov is None and ltype in SIGN_IMG_TYPES and L.get("user_id"):
                ov = load_user_sign_rgba(L.get("user_id"))

            if ov is None:
                continue

            x = int(round(bx * sx))
            y = int(round(by * sy))

            if bw_base <= 0 or bh_base <= 0:
                bw_base = ov.width
                bh_base = ov.height

            w = int(round(bw_base * sx))
            h = int(round(bh_base * sy))
            if w <= 0 or h <= 0:
                w = ov.width
                h = ov.height

            ov = ov.resize((w, h), Image.LANCZOS)
            base.alpha_composite(ov, dest=(x, y))
            continue

        # ─────────────────────
        # 3) 텍스트 박스
        # ─────────────────────
        if ltype in TEXT_TYPES:
            text = L.get("text") or ""
            font_size = int(L.get("fontSize", 28))
            color = parse_color(L.get("color", "#000000"))
            align = (L.get("align", "left") or "left")

            bx = int(round(L.get("x", 0) * sx))
            by = int(round(L.get("y", 0) * sy))
            bw = int(round(L.get("w", 300) * sx))
            bh = int(round(L.get("h", 80) * sy))

            font = get_font(int(round(font_size * min(sx, sy))))
            pad = 4

            tmp_img = Image.new("RGBA", (1, 1))
            tmp_draw = ImageDraw.Draw(tmp_img)
            bbox = tmp_draw.textbbox((0, 0), text, font=font)
            w_text = bbox[2] - bbox[0]
            h_text = bbox[3] - bbox[1]

            if align == "center":
                tx = bx + max(0, (bw - w_text) // 2)
            elif align == "right":
                tx = bx + max(0, (bw - w_text))
            else:
                tx = bx + pad

            ty = by + max(0, (bh - h_text) // 2)

            draw.text((tx, ty), text, fill=color, font=font)
            continue

        # ─────────────────────
        # 4) 라인
        # ─────────────────────
        if ltype in LINE_TYPES:
            color = parse_color(L.get("color", "#000000"))
            bx = int(round(L.get("x", 0) * sx))
            by = int(round(L.get("y", 0) * sy))
            bw = int(round(L.get("w", 300) * sx))
            bh = max(1, int(round(L.get("h", 2) * sy)))
            draw.rectangle([bx, by, bx + bw, by + bh], fill=color)
            continue

        # ─────────────────────
        # 5) 직사각형 박스
        # ─────────────────────
        if ltype in RECT_TYPES:
            stroke = parse_color(L.get("stroke", "#000000"))
            fill = parse_color(
                L.get("fill", "rgba(13,110,253,0.0)"),
                (0, 0, 0, 0),
            )
            bx = int(round(L.get("x", 0) * sx))
            by = int(round(L.get("y", 0) * sy))
            bw = int(round(L.get("w", 300) * sx))
            bh = int(round(L.get("h", 200) * sy))
            draw.rectangle([bx, by, bx + bw, by + bh], outline=stroke, fill=fill, width=1)
            continue

    return base.convert("RGB")


def composite_sign_on_slot(im_canvas, width, height, layers, slot_role, sign_img_rgba):
    """
    기존 signbox + slots 구조에서, 특정 role에 해당하는 칸에 sign_img_rgba를 합성하고 싶을 때 사용.
    (필요 시 사용할 헬퍼. 현재는 process_runtime 기반 서명 완료 시점에 쓸 수 있음)
    """
    if not sign_img_rgba:
        return im_canvas
    base = im_canvas.convert("RGBA")
    BX, BY = 1200.0, 1600.0
    sx = float(width) / BX
    sy = float(height) / BY
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
    x0 = px + int(round(tgt.get("x_rel", 0) * pw))
    y0 = py + int(round(tgt.get("y_rel", 0) * ph))
    x1 = x0 + int(round(tgt.get("w_rel", 0) * pw))
    y1 = y0 + int(round(tgt.get("h_rel", 0) * ph))
    w = max(1, x1 - x0)
    h = max(1, y1 - y0)
    ov = sign_img_rgba.resize((w, h), Image.LANCZOS)
    base.alpha_composite(ov, dest=(x0, y0))
    return base.convert("RGB")


# ──────────────────────────────────────────────────────────
# Preview & save helpers
# ──────────────────────────────────────────────────────────
def render_preview_png(
    svc,
    upload_id,
    width,
    height,
    mode,
    scale,
    percent,
    rotate,
    raw,
    layers,
    page: int = 1,
):
    """
    PNG 프리뷰 이미지 생성.
    - raw=True  : svc.load_upload_image → _place_into_canvas → apply_layers_to_image
    - raw=False : svc.build_preview_image → apply_layers_to_image
    layers는 이미 내부 렌더링용 구조(signbox/text/rect...)라고 가정한다.
    (editor_layers를 받으려면 convert_editor_layers_to_render_layers() 후 넘겨야 한다)
    """
    if raw:
        im = svc.load_upload_image(upload_id, page=1)
        if rotate in (90, 180, 270):
            im = im.rotate(rotate, expand=True)
        im_preview = svc._place_into_canvas(im, width, height, mode=scale, percent=percent)
        im_preview = apply_layers_to_image(im_preview, width, height, layers)
    else:
        im_preview = svc.build_preview_image(
            upload_id,
            page=1,
            width=width,
            height=height,
            mode=mode,
            scale=scale,
            percent=percent,
            rotate=rotate,
        )
        im_preview = apply_layers_to_image(im_preview, width, height, layers)
    bio = BytesIO()
    im_preview.save(bio, format="PNG")
    bio.seek(0)
    return bio


def place_into_canvas_and_quantize(
    svc,
    upload_id,
    page,
    width,
    height,
    scale,
    percent,
    rotate,
    mode,
    layers,
):
    """
    PDF/이미지를 디바이스 캔버스에 배치하고,
    editor_layers(또는 내부 layers)를 합성한 뒤,
    디바이스 팔레트(BW/BWRY/BWRYBG)에 맞게 양자화.
    """
    im_src = svc.load_upload_image(upload_id, page=page)
    if rotate in (90, 180, 270):
        im_src = im_src.rotate(rotate, expand=True)
    im_canvas = svc._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
    im_canvas = apply_layers_to_image(im_canvas, width, height, layers)
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
    return im_proc, fmt


def image_to_payload(im, fmt, size):
    return ImageToBytes.image_to_payload(im, fmt, size=size)


def save_meta_bundle(
    im,
    fmt,
    size,
    bmp_path,
    bin_path,
    meta_path,
    device_id,
    target_dir,
    need_approval,
    final_approval,
    route_id,
    assignees,
    doc_id=None,
    upload_row_id=None,
):
    """
    BMP + BIN + meta.json 번들을 에셋 경로에 저장.
    여기서의 status/dir은 “에셋 기준 상태”로,
    문서 전체 워크플로 상태는 DocumentInfo/EInkAsset가 관리한다.
    """
    os.makedirs(os.path.dirname(bmp_path), exist_ok=True)

    # BMP
    im.save(bmp_path, format="BMP")

    # BIN payload
    payload = image_to_payload(im, fmt, size=size)
    with open(bin_path, "wb") as f:
        f.write(payload)
    raw_len = len(payload) - 4
    crc32_le = int.from_bytes(payload[-4:], "little", signed=False)

    meta = {
        "device_id": device_id,
        "dir": target_dir,
        "file": os.path.basename(bmp_path),
        "bin": os.path.basename(bin_path),
        "width": size[0],
        "height": size[1],
        "mode": fmt,
        "packing": {"BW": "1bpp", "BWRY": "2bpp", "BWRYBG": "3bpp"}[fmt],
        "raw_len": raw_len,
        "total_len": raw_len + 4,
        "crc32": f"{crc32_le:08x}",
        "ver": int(os.path.getmtime(bmp_path)),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "need_approval": bool(need_approval),
        "final_approval": bool(final_approval),
        "route_id": route_id,
        "assignees": assignees or {},
        "doc_id": doc_id, # 혹시 사용 대비 (햔재 미사용 )
        "upload_row_id": upload_row_id, # 혹시 사용 대비 (햔재 미사용 )
        # 에셋 레벨 status (문서 status와는 분리)
        "status": (
            "uploads"
            if target_dir == "uploads"
            else "approved"
            if target_dir == "approved"
            else "checked"
            if target_dir == "checked"
            else "in_review"
        ),
    }
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    return payload, meta


def render_flat_image(
    svc,
    upload_id,
    width,
    height,
    scale,
    percent,
    rotate,
    layers,
):
    """
    (흑백/팔레트 변환 없이) 레이어만 합성한 평면 PNG 생성.
    주로 “원본 탭” 프리뷰에 필요하다면 활용.
    """
    im_src = svc.load_upload_image(upload_id, page=1)
    if rotate in (90, 180, 270):
        im_src = im_src.rotate(rotate, expand=True)
    im_canvas = svc._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
    im_canvas = apply_layers_to_image(im_canvas, width, height, layers)
    bio = BytesIO()
    im_canvas.save(bio, format="PNG")
    bio.seek(0)
    return bio


# ──────────────────────────────────────────────────────────
# Defaults / move / bulletin direct helper
# ──────────────────────────────────────────────────────────
def default_devices():
    """
    프런트 테스트용 기본 디바이스 목록.
    실제 디바이스 테이블이 생기면 해당 테이블 조회로 대체.
    """
    out = []
    for i in range(1, 7):
        num = f"{i:02d}"
        out.append({"device_no": num, "device_id": f"E{num}", "default_width": 480, "default_height": 800})
    return out


def default_routes():
    """
    프런트 테스트용 기본 결재선.
    실제 ApprovalRoute/ApprovalRouteStep 쪽과는 별개로 단순 데모용.
    """
    return [
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



def snapshot_to_signlayout_args(layout_snapshot: dict):
    """
    layout_snapshot_json → SignLayout INSERT용 args 변환.

    지원하는 형태:
    1) 새 구조:
       {
         "canvas_w": 1200,
         "canvas_h": 1600,
         "parent_box": {...},
         "tpl_json": {...},
         "slots_json": {...},
         "layers_json": [... 또는 {"layers":[...]}]
       }

    2) 구 구조:
       {
         "canvas": {"w":1200,"h":1600},
         "editor_layers": [approval_box/message_box/... (또는 signbox 구조)],
         ...
       }
       → editor_layers를 convert_editor_layers_to_render_layers()로 변환해서 signbox 추출
    """
    if not layout_snapshot:
        return None

    # 1) 새 구조 우선 처리
    if "canvas_w" in layout_snapshot and "canvas_h" in layout_snapshot:
        canvas_w = int(layout_snapshot.get("canvas_w", 1200))
        canvas_h = int(layout_snapshot.get("canvas_h", 1600))
        parent_box = layout_snapshot.get("parent_box") or {}
        tpl_json = layout_snapshot.get("tpl_json") or {}
        slots_json = layout_snapshot.get("slots_json") or {}
        layers_raw = layout_snapshot.get("layers_json") or []
        # layers_json이 {"layers":[...]} 형태일 수도 있으니 풀어줌
        if isinstance(layers_raw, dict) and "layers" in layers_raw:
            layers = layers_raw["layers"]
        else:
            layers = layers_raw

        return {
            "canvas_w": canvas_w,
            "canvas_h": canvas_h,
            "parent_box": {
                "x": int(parent_box.get("x", 0)),
                "y": int(parent_box.get("y", 0)),
                "w": int(parent_box.get("w", 0)),
                "h": int(parent_box.get("h", 0)),
            },
            "tpl_json": tpl_json,
            "slots_json": slots_json,
            "layers_json": layers,
        }

    # 2) 구 구조 (canvas + editor_layers 기반)
    canvas = layout_snapshot.get("canvas") or {}
    editor_layers = (
        layout_snapshot.get("editor_layers")
        or layout_snapshot.get("layers")
        or []
    )

    # editor_layers가 approval_box 등 프론트 타입일 수 있으므로 내부 signbox로 변환
    internal_layers = convert_editor_layers_to_render_layers(editor_layers)
    signbox = next(
        (L for L in internal_layers if (L.get("type") or "").lower() == "signbox"),
        None,
    )
    if not signbox:
        return None

    parent = signbox.get("parent") or {}
    tpl = signbox.get("tpl") or {}
    slots = signbox.get("slots") or []

    return {
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
        "layers_json": internal_layers,
    }


def move_bundle(src_dir: str, dst_dir: str, base_filename: str):
    """
    src_dir/ 에 있는 base_filename(.bmp/.bin/.meta.json/.h)을 dst_dir/ 로 한 번에 이동.
    BIN/BMP/h/meta 번들을 통째로 디렉터리 간 이동할 때 사용.
    """
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
    return moved


def save_draft_bundle(
    svc,
    upload_id,
    width,
    height,
    mode,
    scale,
    percent,
    rotate,
    layers,
    user_id,
    device_id="",
    memo="",
    filename="",
):
    """
    결재 미사용 즉시 저장: bulletin_files/ 에 PNG+JSON 저장.
    - DocumentInfo를 거치지 않고 단발성 안내/테스트용으로 사용할 때 의미가 있음.
    - 정식 결재/게시 워크플로는 DocumentInfo + approval_process/{doc_id}/ 구조 사용.
    """
    im_src = svc.load_upload_image(upload_id, page=1)
    if rotate in (90, 180, 270):
        im_src = im_src.rotate(rotate, expand=True)
    im_canvas = svc._place_into_canvas(im_src, width, height, mode=scale, percent=percent)
    im_canvas = apply_layers_to_image(im_canvas, width, height, layers)

    base = asset_basename(device_id or "BF", width, height, mode or "BW")
    stamp = int(time.time())
    dirs = get_asset_dirs()
    out_png = os.path.join(dirs["bulletin_files"], f"{base}_{stamp}.png")
    out_meta = os.path.join(dirs["bulletin_files"], f"{base}_{stamp}.json")

    os.makedirs(os.path.dirname(out_png), exist_ok=True)
    im_canvas.save(out_png, format="PNG")
    meta = {
        "type": "bulletin_direct",
        "device_id": device_id,
        "file": os.path.basename(out_png),
        "width": width,
        "height": height,
        "mode": (mode or "BW").upper(),
        "user_id": user_id,
        "filename": filename,
        "memo": memo,
        "layers": layers,
        "saved_at": datetime.now().isoformat(timespec="seconds"),
    }
    with open(out_meta, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    return {"png": out_png, "meta": out_meta}


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
# Docs master store (eink_docs) - approval_process / bulletin_files
# ──────────────────────────────────────────────────────────
def safe_doc_bucket(raw: str | None) -> str:
    v = (raw or "").strip().lower()
    if v in ("approval_process", "bulletin_files"):
        return v
    return "approval_process"


def decide_doc_bucket(need_approval: bool) -> str:
    """
    - need_approval=True  -> approval_process
    - need_approval=False -> bulletin_files
    """
    return "approval_process" if bool(need_approval) else "bulletin_files"


def get_doc_dir(userid: str, document_info_id: int, bucket: str = "approval_process") -> str:
    """
    {ROOT}/eink_docs/{user_id}/{bucket}/{doc_id}/
    """
    bucket = safe_doc_bucket(bucket)
    return os.path.join(get_doc_root_for_user(userid), bucket, str(document_info_id))


def get_doc_bundle_paths(userid: str, document_info_id: int, bucket: str, source_ext: str) -> dict:
    """
    DocumentInfo 1건의 마스터 파일 경로 세트.
    """
    bucket = safe_doc_bucket(bucket)
    doc_dir = get_doc_dir(userid, document_info_id, bucket=bucket)
    os.makedirs(doc_dir, exist_ok=True)

    source_ext = (source_ext or "").lstrip(".") or "pdf"

    return {
            "doc_dir": doc_dir,
            "bucket": bucket,
            "original": os.path.join(doc_dir, f"original.{source_ext}"),
            "normalized_pdf": os.path.join(doc_dir, "normalized.pdf"),
            "layout_snapshot_json": os.path.join(doc_dir, "layout_snapshot.json"),
            "metadata_json": os.path.join(doc_dir, "metadata.json"),

            # ✅ 추가
            "preview_base_png": os.path.join(doc_dir, "preview_base.png"),
            "preview_merged_png": os.path.join(doc_dir, "preview_merged.png"),

            "onelayer_bmp": os.path.join(doc_dir, "onelayer.bmp"),
            "onelayer_bin": os.path.join(doc_dir, "onelayer.bin"),
            "onelayer_meta_json": os.path.join(doc_dir, "onelayer_meta.json"),
        }


def _guess_normalized_pdf_from_upload(upload_path: str) -> str | None:
    """
    LibreOffice 변환 로직(_convert_doc_to_image) 기준:
    원본이 {base}/{name}.pptx면 {base}/{name}.pdf가 생성되는 케이스가 많음.
    """
    try:
        if not upload_path:
            return None
        base_dir = os.path.dirname(upload_path)
        base_name = os.path.splitext(os.path.basename(upload_path))[0]
        guess = os.path.join(base_dir, base_name + ".pdf")
        return guess if os.path.isfile(guess) else None
    except Exception:
        return None


def save_doc_master_bundle(
    userid: str,
    doc_id: int,
    bucket: str,
    im,
    fmt: str,
    size: tuple[int, int],
    device_id: str,
    upload_temp_path: str | None,
    orig_filename: str,
    normalized_pdf_path: str | None,
    layout_snapshot: dict | None,
    metadata: dict | None,
    need_approval: bool,
    final_approval: bool,
    route_id=None,
    assignees=None,

    preview_base_im=None,     # ✅ 추가
    preview_merged_im=None,   # ✅ 추가 (여기에 merged_rgb가 들어와야 함)
):
    """
    {ROOT}/eink_docs/{userid}/{bucket}/{doc_id}/ 아래에:
      - original.xxx (가능하면 copy)
      - normalized.pdf (가능하면 copy)
      - layout_snapshot.json (옵션 dump)
      - metadata.json (옵션 dump)
      - preview_base.png / preview_merged.png
      - onelayer.bmp / onelayer.bin / onelayer_meta.json 저장

    반환: (payload_bytes, onelayer_meta_dict, paths_dict)
    """
    bucket = safe_doc_bucket(bucket)

    # 1) 원본 확장자 결정
    source_ext = "pdf"
    try:
        if orig_filename and "." in orig_filename:
            source_ext = orig_filename.rsplit(".", 1)[-1].lower()
        elif upload_temp_path and "." in upload_temp_path:
            source_ext = upload_temp_path.rsplit(".", 1)[-1].lower()
    except Exception:
        source_ext = "pdf"

    paths = get_doc_bundle_paths(userid, doc_id, bucket=bucket, source_ext=source_ext)

    # ✅ preview 저장용: BW('1') / P(BWRY)면 PNG 저장 전에 RGB로 변환
    def _to_rgb_for_preview(img):
        if img is None:
            return None
        if getattr(img, "mode", None) in ("1", "P"):
            return img.convert("RGB")
        # RGBA도 안전하게 RGB로
        if getattr(img, "mode", None) == "RGBA":
            return img.convert("RGB")
        return img

    # 2) original.xxx 복사 (있으면)
    try:
        if upload_temp_path and os.path.isfile(upload_temp_path):
            shutil.copy2(upload_temp_path, paths["original"])
    except Exception:
        current_app.logger.debug("[DocMaster] original copy failed", exc_info=True)

    # 3) normalized.pdf 복사 (있으면)
    try:
        norm = normalized_pdf_path or (upload_temp_path and _guess_normalized_pdf_from_upload(upload_temp_path))
        if norm and os.path.isfile(norm):
            shutil.copy2(norm, paths["normalized_pdf"])
    except Exception:
        current_app.logger.debug("[DocMaster] normalized.pdf copy failed", exc_info=True)

    # 4) snapshot dump (옵션)
    try:
        if layout_snapshot is not None:
            with open(paths["layout_snapshot_json"], "w", encoding="utf-8") as f:
                json.dump(layout_snapshot, f, ensure_ascii=False, indent=2)
    except Exception:
        current_app.logger.debug("[DocMaster] layout_snapshot dump failed", exc_info=True)

    try:
        if metadata is not None:
            with open(paths["metadata_json"], "w", encoding="utf-8") as f:
                json.dump(metadata, f, ensure_ascii=False, indent=2)
    except Exception:
        current_app.logger.debug("[DocMaster] metadata dump failed", exc_info=True)

    # ✅ 4-1) preview_base.png 저장 (레이어 없음: base_canvas)
    try:
        if preview_base_im is not None:
            pb = _to_rgb_for_preview(preview_base_im)
            if pb is not None:
                pb.save(paths["preview_base_png"], format="PNG")
    except Exception:
        current_app.logger.debug("[DocMaster] preview_base.png save failed", exc_info=True)

    # ✅ 4-2) preview_merged.png 저장 (프론트와 동일: merged_rgb)
    #     - 양자화 금지
    #     - im(final_im)으로 fallback 금지 (형 요구사항)
    try:
        if preview_merged_im is not None:
            pm = _to_rgb_for_preview(preview_merged_im)  # merged_rgb는 보통 RGB
            if pm is not None:
                pm.save(paths["preview_merged_png"], format="PNG")
    except Exception:
        current_app.logger.debug("[DocMaster] preview_merged.png save failed", exc_info=True)

    # 5) ✅ onelayer.bmp 저장 (도트 = final_im)
    if im is not None:
        im.save(paths["onelayer_bmp"], format="BMP")

    # 6) onelayer.bin 저장 (payload는 도트 기준)
    payload = image_to_payload(im, fmt, size=size)
    with open(paths["onelayer_bin"], "wb") as f:
        f.write(payload)

    raw_len = len(payload) - 4
    crc32_le = int.from_bytes(payload[-4:], "little", signed=False)

    # 7) onelayer_meta.json 저장
    onelayer_meta = {
        "doc_id": int(doc_id),
        "bucket": bucket,
        "device_id": device_id,
        "original_name": orig_filename,
        "files": {
            "original": os.path.basename(paths["original"]),
            "normalized_pdf": os.path.basename(paths["normalized_pdf"]),
            "layout_snapshot_json": os.path.basename(paths["layout_snapshot_json"]),
            "metadata_json": os.path.basename(paths["metadata_json"]),

            # ✅ preview는 "있을 수도, 없을 수도" 있으니 파일명은 유지
            "preview_base_png": os.path.basename(paths["preview_base_png"]),
            "preview_merged_png": os.path.basename(paths["preview_merged_png"]),

            "bmp": os.path.basename(paths["onelayer_bmp"]),
            "bin": os.path.basename(paths["onelayer_bin"]),
        },
        "width": size[0],
        "height": size[1],
        "mode": fmt,
        "packing": {"BW": "1bpp", "BWRY": "2bpp", "BWRYBG": "3bpp"}.get(fmt, ""),
        "raw_len": raw_len,
        "total_len": raw_len + 4,
        "crc32": f"{crc32_le:08x}",
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "need_approval": bool(need_approval),
        "final_approval": bool(final_approval),
        "route_id": route_id,
        "assignees": assignees or {},
    }

    with open(paths["onelayer_meta_json"], "w", encoding="utf-8") as f:
        json.dump(onelayer_meta, f, ensure_ascii=False, indent=2)

    return payload, onelayer_meta, paths



def get_device_upload_dir(userid: str | None = None) -> str:
    """
    {ROOT}/eink_docs/{userid}/upload/
    """
    uid = _safe_fragment(userid or current_userid_str())
    d = os.path.join(get_global_docs_root(), uid, "upload")
    os.makedirs(d, exist_ok=True)
    return d


def save_device_upload_bundle(
    *,
    userid: str,
    base_name: str,          # ex) "E03_10_202512120901_202512150900"
    payload: bytes,          # BIN bytes
    meta_json: dict,         # JSON dict
):
    """
    {ROOT}/eink_docs/{userid}/upload/{base_name}.bin / .json 저장
    """
    base_name = _safe_fragment(base_name)
    out_dir = get_device_upload_dir(userid)

    bin_path = os.path.join(out_dir, base_name + ".bin")
    json_path = os.path.join(out_dir, base_name + ".json")

    with open(bin_path, "wb") as f:
        f.write(payload)

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(meta_json, f, ensure_ascii=False, indent=2)

    return {"bin": bin_path, "json": json_path}


def inject_approval_runtime_into_snapshot(layout_snapshot: dict, runtime_map: dict[int, dict]) -> int:
    """
    layout_snapshot 안의 approval_box.columns(여러 위치)에
    runtime/status를 주입해서 렌더러가 slot.status를 채울 수 있게 만든다.
    """
    if not layout_snapshot or not runtime_map:
        return 0

    def _apply_to_columns(cols: list) -> int:
        changed = 0
        if not isinstance(cols, list):
            return 0
        for c in cols:
            if not isinstance(c, dict):
                continue
            try:
                col = int(c.get("col_index") or 0)
            except Exception:
                col = 0
            if col <= 0:
                continue

            rt = runtime_map.get(col)
            if not rt:
                continue

            # ✅ 호환을 위해 runtime + status 둘 다 세팅
            c["status"] = rt.get("status", c.get("status"))
            if rt.get("stamp_text") is not None:
                c["stamp_text"] = rt.get("stamp_text")

            runtime = c.get("runtime") or {}
            runtime["status"] = rt.get("status")
            if rt.get("stamp_text") is not None:
                runtime["stamp_text"] = rt.get("stamp_text")
            c["runtime"] = runtime

            changed += 1
        return changed

    changed_total = 0

    # 1) tpl_json.approval_box.columns
    try:
        cols = (((layout_snapshot.get("tpl_json") or {}).get("approval_box") or {}).get("columns")) or []
        changed_total += _apply_to_columns(cols)
    except Exception:
        pass

    # 2) slots_json.approval.columns
    try:
        cols = (((layout_snapshot.get("slots_json") or {}).get("approval") or {}).get("columns")) or []
        changed_total += _apply_to_columns(cols)
    except Exception:
        pass

    # 3) layers_json 내 approval_box.columns
    try:
        layers = layout_snapshot.get("layers_json") or []
        if isinstance(layers, list):
            for L in layers:
                if not isinstance(L, dict):
                    continue
                if (L.get("type") or "").lower() != "approval_box":
                    continue
                cols = L.get("columns") or []
                changed_total += _apply_to_columns(cols)
    except Exception:
        pass

    try:
        current_app.logger.debug(
            "[inject_runtime] changed=%s keys=%s",
            changed_total, sorted(runtime_map.keys())
        )
    except Exception:
        pass

    return changed_total



def inject_user_photo1_into_snapshot(layout_snapshot: dict) -> int:
    if not layout_snapshot:
        return 0

    try:
        from pybo.models import User
    except Exception:
        return 0

    def _fill(cols: list) -> int:
        changed = 0
        if not isinstance(cols, list):
            return 0

        for c in cols:
            if not isinstance(c, dict):
                continue

            uid = c.get("user_id")
            if not uid:
                continue

            # 이미 프론트/기존값이 있으면 그대로 두고 싶으면 여기서 skip
            # if (c.get("user_photo_1") or "").strip():
            #     continue

            u = None
            try:
                if isinstance(uid, int) or (isinstance(uid, str) and uid.isdigit()):
                    u = User.query.filter(User.id == int(uid)).first()
                else:
                    u = User.query.filter(User.userid == str(uid)).first()
            except Exception:
                u = None

            new_photo = (getattr(u, "photo_1", "") or "").strip() if u else ""
            old_photo = (c.get("user_photo_1", "") or "").strip()

            if new_photo != old_photo:
                c["user_photo_1"] = new_photo
                changed += 1

        return changed

    changed_total = 0

    # tpl_json.approval_box.columns
    cols = (((layout_snapshot.get("tpl_json") or {}).get("approval_box") or {}).get("columns")) or []
    changed_total += _fill(cols)

    # slots_json.approval.columns
    cols = (((layout_snapshot.get("slots_json") or {}).get("approval") or {}).get("columns")) or []
    changed_total += _fill(cols)

    # layers_json approval_box.columns
    layers = layout_snapshot.get("layers_json") or []
    if isinstance(layers, list):
        for L in layers:
            if isinstance(L, dict) and (L.get("type") or "").lower() == "approval_box":
                changed_total += _fill(L.get("columns") or [])

    return changed_total






# =============================================================================
# Safe filesystem helpers
# =============================================================================
def _is_path_inside_root(target: str, root: str) -> bool:
    """
    Return True only if 'target' resolves to a path that is inside 'root'.
    This prevents accidental deletion outside the intended storage tree.
    """
    root_p = Path(root).resolve()
    target_p = Path(target).resolve()
    return (root_p == target_p) or (root_p in target_p.parents)


def _safe_remove_any(path: str, *, root: str, retries: int = 5, sleep_sec: float = 0.15) -> None:
    """
    Remove a file or directory safely.
    - Only allow deletion inside 'root'.
    - Retry for Windows file-lock conditions.
    """
    if not path:
        return

    if not _is_path_inside_root(path, root):
        raise RuntimeError(f"Refuse to delete outside root: target={path}, root={root}")

    p = Path(path)
    if not p.exists():
        return

    last_err = None
    for _ in range(max(1, int(retries))):
        try:
            if p.is_dir():
                shutil.rmtree(str(p))
            else:
                p.unlink(missing_ok=True)
            return
        except Exception as e:
            last_err = e
            time.sleep(float(sleep_sec))

    raise last_err


def _ensure_empty_dir(dir_path: str, *, root: str) -> str:
    """
    Ensure the directory exists and is empty (delete all children).
    The directory itself is preserved, only its contents are removed.
    """
    if not dir_path:
        raise RuntimeError("dir_path is empty")

    # Create directory first (safe to call repeatedly).
    os.makedirs(dir_path, exist_ok=True)

    # Enforce deletion scope under 'root'.
    if not _is_path_inside_root(dir_path, root):
        raise RuntimeError(f"Refuse to clean outside root: dir={dir_path}, root={root}")

    # Remove all children (files and directories).
    for name in os.listdir(dir_path):
        child = os.path.join(dir_path, name)
        _safe_remove_any(child, root=root)

    return dir_path