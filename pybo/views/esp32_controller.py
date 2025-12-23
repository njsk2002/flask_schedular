# controllers/device_controller.py
# ─────────────────────────────────────────────────────────────────────────────
# 목적 (수정 후)
#  - ESP32 디바이스가 /device/info, /device/bmp 를 호출할 때
#  - "uploads 폴더 스캔"이 아니라,
#    DB의 현재 Posting(active/scheduled) -> Asset 기준으로 meta/bin을 제공한다.
#
# 보안/정책(유지)
#  1) device_id → DB(eink_device) 매핑으로 소유자 userid를 조회  ← ★1순위(장치에는 쿠키가 없음)
#  2) 세션에 userid가 있다면, ①의 사용자와 동일해야 함 (다르면 403)
#  3) 쿼리(userid, ts, sig)가 있고 sig(HMAC)가 유효하면 최후 수단으로 허용
#
# NOTE
#  - 이 파일은 이제 uploads 디렉터리(glob) 기반 _pick_meta 를 쓰지 않는다.
#  - meta는 EInkAsset.meta_relpath(또는 meta_json)를 사용한다.
# ─────────────────────────────────────────────────────────────────────────────

import os, json, time, threading, hmac, hashlib, struct
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, url_for, current_app, send_file

# (폴백 변환이 필요할 때만 사용)
from ..service.image_to_bytes import ImageToBytes
from ..service.file_management import current_userid_str

# ★ DB 모델
from ..models import db, EInkDevice, User

# ★ DB Posting/Asset 기반 선택 로직
from ..repository.repository_edevice import RepositoryEDevice as R

bp = Blueprint('device', __name__, url_prefix='/device')

# ─────────────────────────────────────────────────────────────
# 설정/상수
# ─────────────────────────────────────────────────────────────
DEVICE_LINK_SECRET = os.environ.get("DEVICE_LINK_SECRET", "change-me")


# ─────────────────────────────────────────────────────────────
# 유틸
# ─────────────────────────────────────────────────────────────
def _safe_userid(v: str) -> str:
    """userid를 안전하게 정규화"""
    return "".join(ch for ch in str(v or "") if ch.isalnum() or ch in "._-")[:64] or "guest"


def _safe_device_id(raw: str) -> str:
    """device_id도 파일명/패턴용으로 정규화"""
    if not raw:
        return ""
    return "".join(ch for ch in raw if ch.isalnum() or ch in "._-")[:64]


def _session_userid() -> str | None:
    """세션에 userid가 있으면 반환, 없으면 None"""
    try:
        uid = (current_userid_str() or "").strip()
        if uid and uid.lower() != "guest":
            return _safe_userid(uid)
    except Exception:
        pass
    return None


def _query_userid_with_hmac() -> str | None:
    """
    쿼리(userid, ts, sig) HMAC 검증 후 유효하면 userid 반환.
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
    DB에서 device_id 소유자 userid 조회 (EInkDevice.user_no -> User.no -> User.userid)
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
    userid 결정: (userid, how)
      - how: 'db', 'session', 'query+hmac', 'mismatch', 'missing'
    """
    uid_db = _device_owner_userid(device_id)
    uid_sess = _session_userid()

    if uid_db:
        if uid_sess and uid_sess != uid_db:
            current_app.logger.debug(f"[device] userid mismatch: session={uid_sess}, db={uid_db} (dev={device_id})")
            return None, "mismatch"
        return uid_db, "db"

    uid_q = _query_userid_with_hmac()
    if uid_q:
        return uid_q, "query+hmac"

    if uid_sess:
        current_app.logger.debug(f"[device] userid via SESSION (no db mapping): uid={uid_sess}, dev={device_id}")
        return uid_sess, "session"

    return None, "missing"


def _get_user_by_userid(userid: str) -> User | None:
    if not userid:
        return None
    return User.query.filter(User.userid == userid).first()


def _load_meta_for_asset(user: User, asset) -> dict:
    """
    meta 우선순위:
      1) asset.meta_relpath 파일이 있으면 그걸 읽는다.
      2) 없으면 asset.meta_json을 사용한다.
    """
    meta = {}
    meta_abs = None

    try:
        if getattr(asset, "meta_relpath", None):
            meta_abs = R.abs_path_from_rel(user, asset.meta_relpath)
            if meta_abs and os.path.isfile(meta_abs):
                with open(meta_abs, "r", encoding="utf-8") as f:
                    meta = json.load(f) or {}
    except Exception as e:
        current_app.logger.debug(f"[device] meta_relpath read fail: {e}")

    if not meta:
        try:
            meta = getattr(asset, "meta_json", None) or {}
        except Exception:
            meta = {}

    # 보정값들(필드가 없을 때 asset 기반)
    meta.setdefault("width", getattr(asset, "width", 0) or 0)
    meta.setdefault("height", getattr(asset, "height", 0) or 0)
    meta.setdefault("mode", getattr(asset, "mode", None) or "BWRYBG")
    meta.setdefault("total_len", int(getattr(asset, "total_len", 0) or 0))
    meta.setdefault("raw_len", int(getattr(asset, "raw_len", 0) or 0))
    meta.setdefault("crc32", (getattr(asset, "crc32_le", "") or "").lower())
    meta.setdefault("ver", int(getattr(asset, "ver", int(time.time())) or int(time.time())))

    # 디버깅용 파일명들(있으면)
    if "file" not in meta:
        files = meta.get("files") if isinstance(meta.get("files"), dict) else {}
        meta["file"] = files.get("bmp") or meta.get("bmp") or "onelayer.bmp"
    if "bin" not in meta:
        files = meta.get("files") if isinstance(meta.get("files"), dict) else {}
        meta["bin"] = files.get("bin") or meta.get("bin") or "onelayer.bin"

    return meta


def _no_cache_headers(resp):
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


# (선택) BMP->payload 폴백 캐시 (거의 안 탐)
_payload_cache = {}
_cache_lock = threading.Lock()


# ─────────────────────────────────────────────────────────────
# 라우트: /device/info
# ─────────────────────────────────────────────────────────────
@bp.route("/info", methods=["GET"])
def device_info():
    """
    ESP32가 상태 확인 및 다운로드 정보 요청:
      GET /device/info?device_id=E01&cap=BWR&fw=1.0.0[&res=1200x1600][&userid=...&ts=...&sig=...]
    - userid는 기본적으로 DB 매핑(device_id)으로 결정
    - 세션 userid가 들어오면 DB 매핑과 불일치 시 403
    - 쿼리(userid)는 HMAC(sig) 유효 시에만 최후 수단으로 허용
    - 자산 선택은 uploads 스캔이 아니라 "DB posting -> asset" 기반
    """
    t0 = time.perf_counter()

    device_id = request.args.get("device_id", "").strip()
    cap       = request.args.get("cap", "").strip()
    fw        = request.args.get("fw", "").strip()
    res       = request.args.get("res", "").strip()

    if not device_id or not cap or not fw:
        current_app.logger.debug(f"[device/info] 400 missing params dev={device_id}, cap={cap}, fw={fw}")
        return _no_cache_headers(jsonify({"status": "error", "reason": "missing params"})), 400

    userid, how = _resolve_userid(device_id)
    if how == "mismatch":
        return _no_cache_headers(jsonify({"status": "error", "reason": "forbidden (session vs device owner mismatch)"})), 403
    if not userid:
        current_app.logger.debug(f"[device/info] 401 userid missing (how={how}, dev={device_id})")
        return _no_cache_headers(jsonify({"status": "error", "reason": "no userid"})), 401

    user = _get_user_by_userid(userid)
    if not user:
        return _no_cache_headers(jsonify({"status": "error", "reason": "user_not_found"})), 404

    now = R.kst_now_naive()

    # ✅ DB에서 현재 posting/asset 결정
    cur, nxt = R.pick_current_and_next_posting(user.no, _safe_device_id(device_id), now)
    if not cur or not getattr(cur, "asset", None):
        elapsed = int((time.perf_counter() - t0) * 1000)
        current_app.logger.debug(f"[device/info] 200 no_posting uid={userid} dev={device_id} elapsed_ms={elapsed}")
        return _no_cache_headers(jsonify({
            "status": "ok",
            "allow_update": False,
            "reason": "no_posting",
            "server_time": datetime.now().isoformat(timespec="seconds"),
            "echo": {"device_id": device_id, "cap": cap, "fw": fw, "res": res, "userid": userid, "resolved_via": how},
        })), 200

    asset = cur.asset
    meta = _load_meta_for_asset(user, asset)

    # /device/bmp URL (userid를 쿼리에 싣지 않음: device_id→DB 매핑으로만 접근)
    bmp_url = url_for(
        "device.send_bmp",
        device_id=_safe_device_id(device_id),
        cap=cap,
        v=str(meta.get("ver") or getattr(asset, "ver", "")),
        _external=True,
    )

    elapsed = int((time.perf_counter() - t0) * 1000)
    current_app.logger.debug(
        f"[device/info] 200 ok uid={userid} (via {how}) "
        f"dev={_safe_device_id(device_id)} asset_id={getattr(asset,'id',None)} ver={meta.get('ver')} elapsed_ms={elapsed}"
    )

    resp = jsonify({
        "status": "ok",
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "echo": {"device_id": device_id, "cap": cap, "fw": fw, "res": res, "userid": userid, "resolved_via": how},
        "bmp": {
            "url": bmp_url,
            "len": int(meta.get("total_len") or 0),     # CRC 포함 길이
            "crc32": (meta.get("crc32") or "").lower(), # 8-hex string
            "ver": int(meta.get("ver") or 0),
            "mode": str(meta.get("mode") or "BWRYBG"),
            "size": f"{int(meta.get('width') or 0)}x{int(meta.get('height') or 0)}",
            "file": meta.get("file") or "onelayer.bmp", # 디버깅 표시용
        },
    })

    return _no_cache_headers(resp), 200


# ─────────────────────────────────────────────────────────────
# 라우트: /device/bmp
# ─────────────────────────────────────────────────────────────
@bp.route("/bmp", methods=["GET"])
def send_bmp():
    """
    ESP32가 실제 바이너리 다운로드:
      GET /device/bmp?device_id=E01&cap=BWR&v=...
    - uploads 스캔이 아니라 DB posting->asset의 bin_relpath를 전송
    - bin 없으면 (선택) bmp->payload 폴백 가능
    """
    t0 = time.perf_counter()

    device_id = request.args.get("device_id", "").strip()
    _cap_q    = request.args.get("cap", "BWR").strip()
    _         = request.args.get("v", "").strip()  # 버전 힌트(선택)

    if not device_id:
        current_app.logger.debug("[device/bmp] 400 missing device_id")
        return _no_cache_headers(jsonify({"status": "error", "reason": "missing device_id"})), 400

    userid, how = _resolve_userid(device_id)
    if how == "mismatch":
        return _no_cache_headers(jsonify({"status": "error", "reason": "forbidden (session vs device owner mismatch)"})), 403
    if not userid:
        current_app.logger.debug(f"[device/bmp] 401 userid missing (how={how}, dev={device_id})")
        return _no_cache_headers(jsonify({"status": "error", "reason": "no userid"})), 401

    user = _get_user_by_userid(userid)
    if not user:
        return _no_cache_headers(jsonify({"status": "error", "reason": "user_not_found"})), 404

    now = R.kst_now_naive()

    cur, _nxt = R.pick_current_and_next_posting(user.no, _safe_device_id(device_id), now)
    if not cur or not getattr(cur, "asset", None):
        elapsed = int((time.perf_counter() - t0) * 1000)
        current_app.logger.debug(f"[device/bmp] 404 no_posting uid={userid} dev={device_id} elapsed_ms={elapsed}")
        return _no_cache_headers(jsonify({"status": "error", "reason": "no_posting"})), 404

    asset = cur.asset
    meta = _load_meta_for_asset(user, asset)

    # 1) 표준: bin_relpath 전송
    bin_path = None
    if getattr(asset, "bin_relpath", None):
        try:
            bin_path = R.abs_path_from_rel(user, asset.bin_relpath)
        except Exception as e:
            current_app.logger.debug(f"[device/bmp] abs_path_from_rel fail: {e}")
            bin_path = None

    if bin_path and os.path.isfile(bin_path):
        st = os.stat(bin_path)
        total_len = int(st.st_size)

        # total_len 검증(있으면)
        if getattr(asset, "total_len", None) and int(asset.total_len) != total_len:
            msg = f"size_mismatch {total_len}!={int(asset.total_len)}"
            current_app.logger.error(f"[device/bmp] 500 {msg} dev={device_id} uid={userid}")
            return _no_cache_headers(jsonify({"status": "error", "reason": msg})), 500

        # crc32: 파일 끝 4바이트(LE)
        crc_hex = (meta.get("crc32") or "").lower() or "00000000"
        try:
            with open(bin_path, "rb") as f:
                f.seek(-4, os.SEEK_END)
                crc_le = struct.unpack("<I", f.read(4))[0]
            crc_hex = f"{crc_le:08x}"
        except Exception:
            pass

        ver = int(meta.get("ver") or getattr(asset, "ver", int(time.time())) or int(time.time()))
        mtime = int(os.path.getmtime(bin_path))

        elapsed = int((time.perf_counter() - t0) * 1000)
        current_app.logger.info(
            f"[BMP] send (BIN) dev={_safe_device_id(device_id)} uid={userid} "
            f"(len={total_len}, crc=0x{crc_hex}, ver={ver}) elapsed_ms={elapsed} → {request.remote_addr}"
        )

        resp = send_file(
            bin_path,
            mimetype="application/octet-stream",
            as_attachment=False,
            conditional=True,
            max_age=0,
        )
        resp.headers["Content-Length"] = str(total_len)
        resp.headers["X-CRC32"] = crc_hex
        resp.headers["X-Payload-Version"] = str(ver)
        resp.headers["ETag"] = f'W/"{ver}-{crc_hex}-{total_len}"'
        resp.headers["Last-Modified"] = datetime.utcfromtimestamp(mtime).strftime("%a, %d %b %Y %H:%M:%S GMT")
        resp.headers["Content-Disposition"] = f'attachment; filename="{_safe_device_id(device_id) or "image"}.bin"'
        return _no_cache_headers(resp)

    # 2) 폴백(선택): bmp->payload
    #    bin이 없거나 경로가 깨졌을 때 최소한 화면을 보내고 싶다면 사용.
    bmp_rel = None
    try:
        bmp_rel = getattr(asset, "preview_relpath", None)
    except Exception:
        bmp_rel = None

    if bmp_rel:
        bmp_path = R.abs_path_from_rel(user, bmp_rel)
        if os.path.isfile(bmp_path):
            cache_key = (bmp_path, int(os.path.getmtime(bmp_path)), str(meta.get("mode") or "BWRYBG"))
            with _cache_lock:
                cached = _payload_cache.get(cache_key)

            if cached:
                payload = cached["payload"]
                crc_hex = cached["crc32"]
                total_len = cached["len"]
            else:
                payload = ImageToBytes.image_file_to_payload(bmp_path, str(meta.get("mode") or "BWRYBG"))
                total_len = len(payload)
                try:
                    crc_le = struct.unpack("<I", payload[-4:])[0]
                    crc_hex = f"{crc_le:08x}"
                except Exception:
                    crc_hex = "00000000"
                with _cache_lock:
                    _payload_cache[cache_key] = {"payload": payload, "crc32": crc_hex, "len": total_len}

            ver = int(meta.get("ver") or getattr(asset, "ver", int(time.time())) or int(time.time()))
            mtime = int(os.path.getmtime(bmp_path))

            resp = Response(payload, mimetype="application/octet-stream")
            resp.headers["Content-Length"] = str(total_len)
            resp.headers["X-CRC32"] = crc_hex
            resp.headers["X-Payload-Version"] = str(ver)
            resp.headers["ETag"] = f'W/"{ver}-{crc_hex}-{total_len}"'
            resp.headers["Last-Modified"] = datetime.utcfromtimestamp(mtime).strftime("%a, %d %b %Y %H:%M:%S GMT")
            resp.headers["Content-Disposition"] = f'attachment; filename="{_safe_device_id(device_id) or "image"}.bin"'
            return _no_cache_headers(resp)

    return _no_cache_headers(jsonify({"status": "error", "reason": "payload_missing"})), 404
