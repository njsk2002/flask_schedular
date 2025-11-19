# controllers/device_controller.py
# ─────────────────────────────────────────────────────────────────────────────
# 목적
#  - ESP32 등 디바이스가 /device/info, /device/bmp 를 호출할 때
#  - "로그인 세션이 없더라도" 안전하게 userid를 식별하여
#    D:/bmp_files/{userid}/uploads 에서 자산(meta/bin/bmp)을 제공.
#
# 보안/정책 (권장 우선순위)
#  1) device_id → DB(eink_device) 매핑으로 소유자 userid를 조회  ← ★1순위(장치에는 쿠키가 없음)
#  2) 세션에 userid가 있다면, ①의 사용자와 동일해야 함 (다르면 403)
#  3) 쿼리(userid, ts, sig)가 있고 sig(HMAC)가 유효하면 최후 수단으로 허용
#     - 운영환경에서는 반드시 sig 검증 사용할 것. (sig 없으면 무시)
#
# 로깅
#  - 어떤 경로로 userid가 결정되었는지 모두 DEBUG 로그로 남김
# ─────────────────────────────────────────────────────────────────────────────

import os, glob, json, time, threading, hmac, hashlib
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, url_for, current_app

from ..service.image_to_bytes import ImageToBytes  # 가변 해상도/모드 지원 버전
from ..service.file_management import current_userid_str
try:
    from ..service.file_management import get_global_asset_root  # 예: D:/bmp_files
except Exception:
    get_global_asset_root = None

# ★ DB 모델 import (프로젝트 경로에 맞게 조정)
from ..models import db, EInkDevice, User

bp = Blueprint('device', __name__, url_prefix='/device')

# ─────────────────────────────────────────────────────────────
# 설정/상수
# ─────────────────────────────────────────────────────────────
# 공유 비밀키(운영에서는 환경변수로 주입)
DEVICE_LINK_SECRET = os.environ.get("DEVICE_LINK_SECRET", "change-me")

# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────
def _safe_userid(v: str) -> str:
    """userid를 파일 경로용으로 안전하게 정규화"""
    return "".join(ch for ch in str(v or "") if ch.isalnum() or ch in "._-")[:64] or "guest"

def _safe_device_id(raw: str) -> str:
    """device_id도 파일명/패턴용으로 정규화"""
    if not raw:
        return ""
    return "".join(ch for ch in raw if ch.isalnum() or ch in "._-")[:64]

def _global_asset_root() -> str:
    """글로벌 루트 (설정값 우선, 없으면 D:/bmp_files)"""
    base = None
    if callable(get_global_asset_root):
        try:
            base = get_global_asset_root()
        except Exception:
            base = None
    if not base:
        base = os.path.join("D:/", "bmp_files")
    return base

def _asset_root_uploads_for(userid: str) -> str:
    """해당 userid의 업로드 루트: <글로벌루트>/<userid>/uploads"""
    root = os.path.join(_global_asset_root(), _safe_userid(userid), "uploads")
    os.makedirs(root, exist_ok=True)
    return root

def _session_userid() -> str | None:
    """세션에 userid가 있으면 안전 문자열로 반환, 없으면 None"""
    try:
        uid = (current_userid_str() or "").strip()
        if uid and uid.lower() != "guest":
            return _safe_userid(uid)
    except Exception:
        pass
    return None

def _query_userid_with_hmac() -> str | None:
    """
    쿼리에서 userid, ts, sig를 받아 HMAC 검증 후 유효하면 userid 반환.
    - 운영 보안: sig가 없으면 무조건 None (허용하지 않음).
    """
    uid = (request.args.get("userid", "") or "").strip()
    ts  = (request.args.get("ts", "") or "").strip()
    sig = (request.args.get("sig", "") or "").strip()
    if not (uid and ts and sig):
        return None
    msg = f"{uid}|{ts}".encode("utf-8")
    good = hmac.new(DEVICE_LINK_SECRET.encode("utf-8"), msg, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(good, sig):
        current_app.logger.debug(f"[device] QUERY userid HMAC invalid: uid={uid}")
        return None
    current_app.logger.debug(f"[device] QUERY userid accepted via HMAC: uid={uid}, ts={ts}")
    return _safe_userid(uid)

def _device_owner_userid(device_id: str) -> str | None:
    """
    DB에서 device_id의 소유자 userid를 조회.
    - EInkDevice.user_no → User.no 조인하여 User.userid를 얻음.
    - 충돌/중복은 가장 최신(updated_at) 1건 채택.
    """
    if not device_id:
        return None
    try:
        q = (
            db.session.query(User.userid)
            .join(EInkDevice, EInkDevice.user_no == User.no)
            .filter(EInkDevice.device_id == _safe_device_id(device_id))
            .order_by(EInkDevice.updated_at.desc(), EInkDevice.id.desc())
        )
        owner_uid = q.first()
        if owner_uid and owner_uid[0]:
            uid = _safe_userid(owner_uid[0])
            current_app.logger.debug(f"[device] userid via DB mapping: dev={device_id} -> uid={uid}")
            return uid
    except Exception as e:
        current_app.logger.error(f"[device] DB lookup failed for dev={device_id}: {e}")
    return None

def _resolve_userid(device_id: str) -> tuple[str | None, str]:
    """
    ★ 권장 정책에 따른 userid 결정 로직
    반환: (userid or None, how)
      - how: 'db', 'session', 'query+hmac', 'mismatch', 'missing'
    우선순위:
      1) DB 매핑(device_id → userid)
         - 세션 userid가 들어왔다면 동일해야 함. 다르면 ('mismatch')
      2) DB가 없고, 쿼리(userid, ts, sig)가 유효하면 채택('query+hmac')
      3) 그래도 없으면, 세션 userid가 있으면 사용('session')  ← 장치 요청에는 거의 없음
      4) 실패('missing')
    """
    # 1) DB 매핑
    uid_db = _device_owner_userid(device_id)
    uid_sess = _session_userid()
    if uid_db:
        if uid_sess and uid_sess != uid_db:
            current_app.logger.debug(f"[device] userid mismatch: session={uid_sess}, db={uid_db} (dev={device_id})")
            return None, "mismatch"
        return uid_db, "db"

    # 2) 쿼리(userid+HMAC)
    uid_q = _query_userid_with_hmac()
    if uid_q:
        return uid_q, "query+hmac"

    # 3) 세션 (보조)
    if uid_sess:
        current_app.logger.debug(f"[device] userid via SESSION (no db mapping): uid={uid_sess}, dev={device_id}")
        return uid_sess, "session"

    # 4) 실패
    return None, "missing"

def _pick_meta(device_id: str, res: str | None, mode: str | None, userid: str | None):
    """
    device_id, (옵션)res='1600x1200', (옵션)mode='BW'|'BWRY'
    → 해당 userid의 uploads 디렉터리에서 가장 적합한 meta.json 경로와 dict 반환
    파일명 패턴: <device>_<WxH>_<MODE>.meta.json
    """
    if not userid:
        return None, None
    asset_root = _asset_root_uploads_for(userid)
    pattern = f"{_safe_device_id(device_id)}_*_*.meta.json"
    current_app.logger.debug(f"[device] pick_meta uid={userid}, root={asset_root}, pattern={pattern}")

    cand = glob.glob(os.path.join(asset_root, pattern))
    metas = []
    for p in cand:
        try:
            with open(p, "r", encoding="utf-8") as f:
                m = json.load(f)
            metas.append((p, m))
        except Exception:
            continue
    if not metas:
        return None, None

    def score(item):
        _p, m = item
        sc = 0
        if res:
            if f"{m.get('width','')}x{m.get('height','')}" == res:
                sc += 10
        if mode:
            if m.get("mode", "").upper() == (mode or "").upper():
                sc += 5
        # 최신 우선 (보통 ver=mtime 기반)
        try:
            sc += int(m.get("ver", 0)) // 1000
        except Exception:
            pass
        return sc

    metas.sort(key=score, reverse=True)
    return metas[0]  # (meta_path, meta_dict)

# ─────────────────────────────────────────────────────────────
# 간단 바이너리 캐시 (파일 경로/mtime 기준)
#   ※ 이제 .bin을 우선 사용하므로 캐시 키도 bin_path 기준으로 바꿈
# ─────────────────────────────────────────────────────────────
_bin_cache = {}  # key: (path, mtime_int) -> {"payload":bytes, "len":int, "crc32":str}
_cache_lock = threading.Lock()

# ─────────────────────────────────────────────────────────────
# 라우트
# ─────────────────────────────────────────────────────────────
@bp.route("/info", methods=["GET"])
def device_info():
    """
    ESP32가 상태 확인 및 다운로드 정보 요청:
    GET /device/info?device_id=E01&cap=BWR&fw=1.0.0[&res=1600x1200][&userid=...&ts=...&sig=...]
    - userid는 기본적으로 DB 매핑(device_id)으로 결정
    - 세션이 들어오면 DB 매핑과 불일치 시 403
    - 쿼리(userid)는 HMAC(sig) 유효 시에만 최후 수단으로 허용
    """
    device_id = request.args.get("device_id", "").strip()
    cap       = request.args.get("cap", "").strip()
    fw        = request.args.get("fw", "").strip()
    res       = request.args.get("res", "").strip()

    if not device_id or not cap or not fw:
        current_app.logger.debug(f"[device/info] 400 missing params dev={device_id}, cap={cap}, fw={fw}")
        return jsonify({"status": "error", "reason": "missing params"}), 400

    userid, how = _resolve_userid(device_id)
    if how == "mismatch":
        # 세션 사용자와 장치 소유자가 다름 → 보안 차단
        return jsonify({"status": "error", "reason": "forbidden (session vs device owner mismatch)"}), 403
    if not userid:
        current_app.logger.debug(f"[device/info] 401 userid missing (how={how}, dev={device_id})")
        return jsonify({"status": "error", "reason": "no userid"}), 401

    # cap 힌트로 모드 유추 (BWR* → BWRY, 아니면 BW)
    mode_hint = "BWRY" if cap.upper().startswith("BWR") else "BW"

    meta_path, meta = _pick_meta(device_id, res or None, mode_hint, userid)
    if not meta:
        root = _asset_root_uploads_for(userid)
        current_app.logger.debug(f"[device/info] 404 no asset uid={userid}, root={root}, dev={device_id}, res={res}, mode={mode_hint}")
        return jsonify({"status": "error", "reason": "no prepared asset"}), 404

    # 세션이 없을 수 있으므로 /bmp에도 userid를 전달 (단, 보안상 HMAC 사용 권장)
    bmp_url = url_for(
        "device.send_bmp",
        device_id=_safe_device_id(device_id),
        res=f"{meta['width']}x{meta['height']}",
        mode=meta["mode"],
        cap=cap,
        v=meta["ver"],
        userid=userid,  # 동일 사용자 폴더 접근 보장 (HMAC 붙이는 것을 권장)
        _external=True,
    )

    current_app.logger.debug(f"[device/info] 200 ok uid={userid} (via {how}) meta_ver={meta['ver']}")

    return jsonify({
        "status": "ok",
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "echo": {"device_id": device_id, "cap": cap, "fw": fw, "userid": userid, "resolved_via": how},
        "bmp": {
            "url": bmp_url,
            "len": meta["total_len"],       # CRC 포함 길이
            "crc32": meta["crc32"],         # 8-hex string (소문자)
            "ver": meta["ver"],             # 보통 mtime(int)
            "mode": meta["mode"],           # 'BW' | 'BWRY' | 'BWRYBG'
            "size": f"{meta['width']}x{meta['height']}",
            "file": meta["file"],           # 디버깅 BMP 파일명
        },
    }), 200

@bp.route("/bmp", methods=["GET"])
def send_bmp():
    """
    ESP32가 실제 바이너리 다운로드:
    GET /device/bmp?device_id=E01&res=1600x1200&mode=BWRY&v=1755842843[&userid=...&ts=...&sig=...]
    - 자산은 해당 userid의 uploads에서 조회
    - .bin(EJOB payload, CRC 포함)을 우선적으로 스트리밍, 없으면 BMP→payload 폴백
    """
    device_id = request.args.get("device_id", "").strip()
    res       = request.args.get("res", "").strip()
    mode_q    = request.args.get("mode", "").strip()
    _cap_q    = request.args.get("cap", "BWR").strip()
    _         = request.args.get("v", "").strip()

    if not device_id:
        current_app.logger.debug("[device/bmp] 400 missing device_id")
        return jsonify({"status": "error", "reason": "missing device_id"}), 400

    userid, how = _resolve_userid(device_id)
    if how == "mismatch":
        return jsonify({"status": "error", "reason": "forbidden (session vs device owner mismatch)"}), 403
    if not userid:
        current_app.logger.debug(f"[device/bmp] 401 userid missing (how={how}, dev={device_id})")
        return jsonify({"status": "error", "reason": "no userid"}), 401

    meta_path, meta = _pick_meta(device_id, res or None, mode_q or None, userid)
    if not (meta and meta_path):
        root = _asset_root_uploads_for(userid)
        current_app.logger.debug(f"[device/bmp] 404 no asset uid={userid}, root={root}, dev={device_id}, res={res}, mode={mode_q}")
        return jsonify({"status": "error", "reason": "no asset"}), 404

    asset_root = os.path.dirname(meta_path)  # 해당 userid/uploads
    bin_name = meta.get("bin")
    bin_path = os.path.join(asset_root, bin_name) if bin_name else None
    bmp_path = os.path.join(asset_root, meta["file"])
    use_bin = bin_path and os.path.exists(bin_path)

    current_app.logger.debug(
        f"[device/bmp] 200 prepare uid={userid} (via {how}), root={asset_root}, "
        f"dev={_safe_device_id(device_id)}, use_bin={bool(use_bin)}, bin={bin_name}, bmp={meta.get('file')}"
    )

    # mtime/경로 기준 캐시 키
    path_for_cache = bin_path if use_bin else bmp_path
    if not os.path.exists(path_for_cache):
        return jsonify({"status": "error", "reason": "file missing"}), 404

    mtime = int(os.path.getmtime(path_for_cache))
    cache_key = (path_for_cache, mtime)
    with _cache_lock:
        cached = _bin_cache.get(cache_key)

    if cached:
        payload   = cached["payload"]
        crc_hex   = cached["crc32"]
        total_len = cached["len"]
    else:
        if use_bin:
            # 표준: .bin 그대로 스트리밍
            try:
                with open(bin_path, "rb") as f:
                    payload = f.read()
            except Exception as e:
                current_app.logger.error(f"[BIN] read fail: {e}")
                return jsonify({"status": "error", "reason": "bin read fail"}), 500
            total_len = len(payload)
            try:
                import struct
                crc_le = struct.unpack("<I", payload[-4:])[0]
                crc_hex = f"{crc_le:08x}"
            except Exception:
                crc_hex = meta.get("crc32", "00000000")
        else:
            # 폴백: BMP → payload
            payload = ImageToBytes.image_file_to_payload(bmp_path, meta["mode"])
            total_len = len(payload)
            try:
                import struct
                crc_le = struct.unpack("<I", payload[-4:])[0]
                crc_hex = f"{crc_le:08x}"
            except Exception:
                crc_hex = meta.get("crc32", "00000000")

        # 캐시 저장
        with _cache_lock:
            _bin_cache[cache_key] = {"payload": payload, "crc32": crc_hex, "len": total_len}

    # 응답 헤더/바디
    resp = Response(payload, mimetype="application/octet-stream")
    resp.headers["Content-Length"] = str(total_len)
    resp.headers["X-CRC32"] = crc_hex
    resp.headers["X-Payload-Version"] = str(meta["ver"])
    resp.headers["X-Colors"] = "BWR-2bit" if meta["mode"].upper() == "BWRY" else "BW-1bit"
    resp.headers["ETag"] = f'W/"{meta["ver"]}-{crc_hex}-{total_len}"'
    resp.headers["Last-Modified"] = datetime.utcfromtimestamp(mtime).strftime("%a, %d %b %Y %H:%M:%S GMT")
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Content-Disposition"] = f'attachment; filename="{_safe_device_id(device_id) or "image"}.bin"'

    src_tag = "BIN" if use_bin else "BMP→PAYLOAD"
    current_app.logger.info(
        f"[BMP] send ({src_tag}) dev={_safe_device_id(device_id)} uid={userid} "
        f"(len={total_len}, crc=0x{crc_hex}, ver={meta['ver']}) → {request.remote_addr}"
    )
    return resp
