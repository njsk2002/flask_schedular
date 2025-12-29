# pybo/views/esp32_controller.py
# - /device/info : Provide server time, offset guidance, next wake plan, and active posting metadata.
# - /device/bmp  : Provide binary payload. If no posting is active, return default.bin (no 404 backoff trap).
# - /device/ack  : Confirm "Display Done!!" completion to finalize update success tracking.
#
# Design Intent:
#   1) The server time is the source of truth.
#   2) The device may lose CRC across power cycles; therefore, missing CRC (when the "crc" parameter is present)
#      must be treated as "unknown state" and may trigger a download path on the next wake.
#   3) All critical decisions shall be observable in DEBUG logs.

import os
import time
import json
import struct
import hmac
import hashlib
import threading
from datetime import datetime

from flask import Blueprint, request, jsonify, Response, url_for, current_app, send_file

# Optional: payload conversion fallback (only used when present in the project).
try:
    from ..service.image_to_bytes import ImageToBytes
except Exception:
    ImageToBytes = None

from ..service.file_management import current_userid_str
from ..models import db, EInkDevice, User
from ..repository.repository_edevice import RepositoryEDevice as R


bp = Blueprint("device", __name__, url_prefix="/device")

# ─────────────────────────────────────────────────────────────
# Configuration / Constants
# ─────────────────────────────────────────────────────────────
DEVICE_LINK_SECRET = os.environ.get("DEVICE_LINK_SECRET", "change-me")

MAX_POLL_SEC_DEFAULT = 60 * 60 * 4   # 4 hours (upper bound for liveness check)
MIN_WAKE_SEC_DEFAULT = 60            # minimum wake interval (seconds)
GUARD_SEC_DEFAULT    = 20            # safety margin for Wi-Fi association / network latency

DEFAULT_MODE = "BWRYBG"
DEFAULT_MAX_NO_POSTING_SEC = 60 * 60          # 1 hour (no_posting 전용)
DEFAULT_MAX_NO_CHANGE_SEC  = 60 * 60 * 4      # 4 hours (그 외 fallback)

# default.bin selection rules (resolution-aware):
#   1) If DEFAULT_EINK_BIN_REL contains "{res}", use it as a template.
#   2) Otherwise, try "default_{res}.bin" in the same directory as DEFAULT_EINK_BIN_REL.
#   3) Otherwise, fall back to DEFAULT_EINK_BIN_REL itself.
DEFAULT_BIN_REL = os.environ.get("DEFAULT_EINK_BIN_REL", "static/eink/default.bin")

_DEFAULT_META_CACHE = {}  # key=(abs_path, mtime) -> meta
_cache_lock = threading.Lock()
_payload_cache = {}       # (bmp_path, mtime, mode) -> {payload, crc32, len}


# ─────────────────────────────────────────────────────────────
# Utilities
# ─────────────────────────────────────────────────────────────
def _epoch_ms_now() -> int:
    return int(time.time() * 1000)


def _safe_userid(v: str) -> str:
    """Normalize userid for safe internal usage."""
    return "".join(ch for ch in str(v or "") if ch.isalnum() or ch in "._-")[:64] or "guest"


def _safe_device_id(raw: str) -> str:
    """Normalize device_id for safe internal usage and file naming."""
    if not raw:
        return ""
    return "".join(ch for ch in raw if ch.isalnum() or ch in "._-")[:64]


def _no_cache_headers(resp):
    """Force no-cache semantics for all device endpoints."""
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


def _commit_log_safely():
    """Commit access log safely; rollback on failure."""
    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def _session_userid() -> str | None:
    """Return session-based userid (primarily for browser testing)."""
    try:
        uid = (current_userid_str() or "").strip()
        if uid and uid.lower() != "guest":
            return _safe_userid(uid)
    except Exception:
        pass
    return None


def _query_userid_with_hmac() -> str | None:
    """
    Validate query(userid, ts, sig) using HMAC and return userid if valid.
    Security Note:
        If signature fields are absent, this path is not accepted.
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
    Resolve userid from database ownership mapping.
    Implementation Note:
        Enforces an explicit join:
            EInkDevice.user_no == User.no  ->  User.userid
    """
    if not device_id:
        return None

    try:
        did = _safe_device_id(device_id)
        if not did:
            return None

        q = (
            db.session.query(User.userid)
            .join(EInkDevice, EInkDevice.user_no == User.no)
            .filter(EInkDevice.device_id == did)
            .order_by(EInkDevice.updated_at.desc(), EInkDevice.id.desc())
        )
        row = q.first()
        if row and row[0]:
            uid = _safe_userid(row[0])
            current_app.logger.debug(f"[device] userid via DB mapping: dev={did} -> uid={uid}")
            return uid
        return None
    except Exception as e:
        current_app.logger.debug(f"[device] DB mapping failed dev={device_id}: {e}")
        return None


def _resolve_userid(device_id: str) -> tuple[str | None, str]:
    """
    Resolve userid with the following precedence:
        1) Session userid (browser testing)
        2) Query HMAC userid (secure link mode)
        3) DB mapping based on device ownership
    If session userid exists but does not match device ownership, reject with mismatch.
    """
    uid_sess = _session_userid()
    uid_hmac = _query_userid_with_hmac()
    uid_db   = _device_owner_userid(device_id)

    if uid_sess and uid_db and uid_sess != uid_db:
        return (None, "mismatch")

    if uid_sess:
        return (uid_sess, "session")
    if uid_hmac:
        return (uid_hmac, "hmac")
    if uid_db:
        return (uid_db, "db")
    return (None, "none")


def _get_user_by_userid(userid: str) -> User | None:
    try:
        return User.query.filter(User.userid == userid).first()
    except Exception:
        return None


def _arg_int(name: str, default=None, lo=None, hi=None):
    v = request.args.get(name, None)
    if v is None or v == "":
        return default
    try:
        iv = int(v)
        if lo is not None and iv < lo:
            return default
        if hi is not None and iv > hi:
            return default
        return iv
    except Exception:
        return default


def _arg_str(name: str, default=None, maxlen=None):
    v = request.args.get(name, None)
    if v is None:
        return default
    v = str(v)
    if maxlen:
        v = v[:maxlen]
    return v


def _parse_device_telemetry() -> dict:
    """
    Parse optional telemetry fields.
    Contract Note:
        Firmware may not implement these fields yet; server must accept None gracefully.
    """
    battery_pct = _arg_int("battery_pct", None, lo=0, hi=100)
    battery_mv  = _arg_int("battery_mv", None, lo=0, hi=100000)
    temp_c_x10  = _arg_int("temp_c_x10", None, lo=-500, hi=1500)
    rssi_dbm    = _arg_int("rssi_dbm", None, lo=-200, hi=0)
    wake_reason = _arg_str("wake_reason", None, maxlen=16)
    dev_mono_ms = _arg_int("dev_mono_ms", None, lo=0)
    dev_local_epoch_ms = _arg_int("dev_local_epoch_ms", None, lo=0)
    fail_count  = _arg_int("fail_count", None, lo=0, hi=32767)
    backoff_level = _arg_int("backoff_level", None, lo=0, hi=32767)

    return {
        "battery_pct": battery_pct,
        "battery_mv": battery_mv,
        "temp_c_x10": temp_c_x10,
        "rssi_dbm": rssi_dbm,
        "wake_reason": wake_reason,
        "dev_mono_ms": dev_mono_ms,
        "dev_local_epoch_ms": dev_local_epoch_ms,
        "fail_count": fail_count,
        "backoff_level": backoff_level,
    }


def _default_bin_abs(res: str | None = None) -> str | None:
    """
    Resolve default.bin absolute path (resolution-aware).
    """
    try:
        base_rel = DEFAULT_BIN_REL

        # Rule 1: template replacement
        if res and "{res}" in base_rel:
            cand_rel = base_rel.replace("{res}", res)
            cand_abs = os.path.join(current_app.root_path, cand_rel.replace("/", os.sep))
            if os.path.isfile(cand_abs):
                return cand_abs

        # Rule 2: default_{res}.bin in same directory
        base_abs = os.path.join(current_app.root_path, base_rel.replace("/", os.sep))
        if res and os.path.isfile(base_abs):
            d = os.path.dirname(base_abs)
            cand_abs = os.path.join(d, f"default_{res}.bin")
            if os.path.isfile(cand_abs):
                return cand_abs

        # Rule 3: base default
        return base_abs if os.path.isfile(base_abs) else None
    except Exception:
        return None


def _read_crc32_from_bin_tail(bin_path: str) -> str:
    """
    Read CRC32 from the last 4 bytes of a payload file, little-endian.
    """
    with open(bin_path, "rb") as f:
        f.seek(-4, os.SEEK_END)
        crc_le = struct.unpack("<I", f.read(4))[0]
    return f"{crc_le:08x}"


def _load_default_meta(res: str | None = None) -> dict:
    """
    Load default.bin metadata.
    Assumption:
        Payload file ends with 4 bytes CRC32 (little-endian).
    """
    p = _default_bin_abs(res=res)
    if not p:
        return {}

    try:
        mtime = int(os.path.getmtime(p))
        key = (p, mtime)
        with _cache_lock:
            cached = _DEFAULT_META_CACHE.get(key)
        if isinstance(cached, dict):
            return cached

        st = os.stat(p)
        total_len = int(st.st_size)
        crc_hex = "00000000"
        try:
            crc_hex = _read_crc32_from_bin_tail(p)
        except Exception:
            pass

        w, h = 0, 0
        if res and "x" in res:
            try:
                w = int(res.split("x", 1)[0])
                h = int(res.split("x", 1)[1])
            except Exception:
                w, h = 0, 0

        meta = {
            "width": w,
            "height": h,
            "mode": DEFAULT_MODE,
            "total_len": total_len,
            "raw_len": max(0, total_len - 4),
            "crc32": crc_hex,
            "ver": mtime,          # Version based on mtime for default payload
            "file": os.path.basename(p),
            "is_default": True,
            "abs_path": p,
            "mtime": mtime,
        }
        with _cache_lock:
            _DEFAULT_META_CACHE.clear()
            _DEFAULT_META_CACHE[key] = meta
        return meta
    except Exception:
        return {}


def _load_meta_for_asset(user: User, asset) -> dict:
    """
    Load asset metadata with strict stability rules.

    Priority:
        1) asset.meta_relpath JSON (if present and readable)
        2) asset.meta_json (dict or JSON string)
        3) Constructed fallback

    Stability rules:
        - If meta["ver"] is missing or <= 0, it MUST be replaced with a stable version value.
          This prevents endless update loops caused by ver=0 or ver changing every request.
    """
    meta: dict = {}
    meta_abs: str | None = None

    # 1) meta_relpath file
    try:
        rel = getattr(asset, "meta_relpath", None)
        if rel:
            meta_abs = R.abs_path_from_rel(user, rel)
            if meta_abs and os.path.isfile(meta_abs):
                with open(meta_abs, "r", encoding="utf-8") as f:
                    obj = json.load(f) or {}
                if isinstance(obj, dict):
                    meta = obj
    except Exception as e:
        current_app.logger.debug(f"[device] meta_relpath read fail: {e}")

    # 2) meta_json field
    if not meta:
        try:
            mj = getattr(asset, "meta_json", None)
            if isinstance(mj, dict):
                meta = mj
            elif isinstance(mj, str) and mj.strip():
                obj = json.loads(mj)
                if isinstance(obj, dict):
                    meta = obj
        except Exception:
            meta = {}

    if not isinstance(meta, dict):
        meta = {}

    # Resolve bin absolute path when possible (used for stable ver/len derivation).
    bin_abs: str | None = None
    try:
        bin_rel = getattr(asset, "bin_relpath", None)
        if bin_rel:
            bin_abs = R.abs_path_from_rel(user, bin_rel)
            if not (bin_abs and os.path.isfile(bin_abs)):
                bin_abs = None
    except Exception:
        bin_abs = None

    # ── width / height / mode ──────────────────────────────────
    if not int(meta.get("width") or 0):
        meta["width"] = int(getattr(asset, "width", 0) or 0)
    if not int(meta.get("height") or 0):
        meta["height"] = int(getattr(asset, "height", 0) or 0)

    if not (meta.get("mode") or "").strip():
        meta["mode"] = str(getattr(asset, "mode", None) or DEFAULT_MODE)

    # ── total_len / raw_len ────────────────────────────────────
    # Prefer the actual bin file size when available.
    total_len = int(meta.get("total_len") or 0)
    raw_len = int(meta.get("raw_len") or 0)

    if bin_abs and os.path.isfile(bin_abs):
        try:
            st = os.stat(bin_abs)
            total_len = int(st.st_size)
            raw_len = max(0, total_len - 4)
        except Exception:
            pass
    else:
        if total_len <= 0:
            total_len = int(getattr(asset, "total_len", 0) or 0)
        if raw_len <= 0:
            raw_len = int(getattr(asset, "raw_len", 0) or 0)
            if raw_len <= 0 and total_len > 0:
                raw_len = max(0, total_len - 4)

    meta["total_len"] = int(total_len or 0)
    meta["raw_len"] = int(raw_len or 0)

    # ── crc32 ──────────────────────────────────────────────────
    # Normalize and fill from asset fields if missing/empty.
    crc = (meta.get("crc32") or "").strip().lower()
    if not crc:
        crc = (getattr(asset, "crc32_le", "") or "").strip().lower()
    if not crc:
        crc = (getattr(asset, "crc32", "") or "").strip().lower()
    meta["crc32"] = crc

    # ── ver (critical) ─────────────────────────────────────────
    # If meta_json contains ver=0, "setdefault" would not fix it.
    # Therefore, we explicitly validate and overwrite when <= 0.
    v = meta.get("ver", None)
    ver_int = 0
    try:
        ver_int = int(v or 0)
    except Exception:
        ver_int = 0

    if ver_int <= 0:
        # 1) Use asset.ver when available and valid.
        try:
            av = int(getattr(asset, "ver", 0) or 0)
        except Exception:
            av = 0

        if av > 0:
            ver_int = av
        else:
            # 2) Use bin file mtime (stable and naturally updated when payload changes).
            if bin_abs and os.path.isfile(bin_abs):
                try:
                    ver_int = int(os.path.getmtime(bin_abs))
                except Exception:
                    ver_int = 0

            # 3) Use meta file mtime if present.
            if ver_int <= 0 and meta_abs and os.path.isfile(meta_abs):
                try:
                    ver_int = int(os.path.getmtime(meta_abs))
                except Exception:
                    ver_int = 0

            # 4) Use asset.updated_at timestamp if present.
            if ver_int <= 0:
                try:
                    ua = getattr(asset, "updated_at", None)
                    if isinstance(ua, datetime):
                        ver_int = int(ua.timestamp())
                except Exception:
                    ver_int = 0

            # 5) Final fallback.
            if ver_int <= 0:
                ver_int = int(time.time())

        meta["ver"] = int(ver_int)

    # ── debug filenames (optional) ──────────────────────────────
    # "file" is legacy/debug only. Prefer bin file name when possible.
    if "bin" not in meta or not (meta.get("bin") or "").strip():
        files = meta.get("files") if isinstance(meta.get("files"), dict) else {}
        meta["bin"] = files.get("bin") or meta.get("bin") or "onelayer.bin"

    if "file" not in meta or not (meta.get("file") or "").strip():
        files = meta.get("files") if isinstance(meta.get("files"), dict) else {}
        # Prefer binary name for clarity (device downloads BIN).
        meta["file"] = files.get("bin") or meta.get("bin") or "onelayer.bin"

    return meta




def _compute_next_change_epoch_ms(now_dt, now_epoch_ms: int, cur, nxt) -> int:
    """
    Compute next change epoch:
        - If current posting has end_time in the future, prefer that.
        - Else if next posting has start_time in the future, use that.
        - Else fall back:
            * no_posting(cur=None and nxt=None) -> 1 hour
            * otherwise -> 4 hours
    """
    try:
        if cur is not None:
            endt = getattr(cur, "end_time", None)
            if isinstance(endt, datetime) and endt > now_dt:
                return int(endt.timestamp() * 1000)

        if nxt is not None:
            stt = getattr(nxt, "start_time", None)
            if isinstance(stt, datetime) and stt > now_dt:
                return int(stt.timestamp() * 1000)
    except Exception:
        pass

    # ===== Formal fallback policy =====
    # no_posting: cur/nxt 모두 없다면 계약 만료/정지 상태로 보고 더 짧게(예: 1h) 생존보고
    if cur is None and nxt is None:
        fallback_sec = DEFAULT_MAX_NO_POSTING_SEC
    else:
        # cur은 있는데 end_time 없음(무기한) 같은 경우: 4h 폴링 유지(배터리 보호)
        fallback_sec = DEFAULT_MAX_NO_CHANGE_SEC

    return int(now_epoch_ms + (int(fallback_sec) * 1000))



def _compute_sleep_planned_sec(now_epoch_ms: int, next_change_epoch_ms: int) -> int:
    """
    sleep_sec = clamp( (next_change - now)/1000 - guard, MIN_WAKE, MAX_POLL )
    """
    try:
        delta_ms = max(0, int(next_change_epoch_ms - now_epoch_ms))
        sec = int(delta_ms / 1000)
        # sec = max(0, sec - GUARD_SEC_DEFAULT)
        sec = max(0, sec + GUARD_SEC_DEFAULT) # expired 후 업데이트하도록 20초후에 wakeup
        sec = max(MIN_WAKE_SEC_DEFAULT, sec)
        sec = min(MAX_POLL_SEC_DEFAULT, sec)
        return int(sec)
    except Exception:
        return int(MAX_POLL_SEC_DEFAULT)


# ─────────────────────────────────────────────────────────────
# /device/info
# ─────────────────────────────────────────────────────────────
@bp.route("/info", methods=["GET"])
def device_info():
    """
    ESP32 status check and payload metadata request:
      GET /device/info?device_id=E07&cap=BWR&fw=1.0.0&res=1200x1600[&crc=........]

    Backward compatibility contract (legacy firmware):
        - Must include:
            "status": "ok"
            "bmp": { "url", "len", "crc32", "ver", "mode", "size", "file" }

    Forward-compatible extensions (ignored by legacy firmware):
        - server_epoch_ms, offset_ms, next_change_epoch_ms, sleep_planned_sec, etc.

    Important behavioral note:
        - If there is no active posting, the server MUST still provide a default payload meta
          and /device/bmp MUST serve default.bin to avoid exponential backoff loops on the device.
    """
    t0 = time.perf_counter()

    device_id = (request.args.get("device_id", "") or "").strip()
    cap       = (request.args.get("cap", "") or "").strip()
    fw        = (request.args.get("fw", "") or "").strip()
    res       = (request.args.get("res", "") or "").strip()

    # Optional device-side state hint (may be omitted by legacy firmware).
    dev_crc = (request.args.get("crc", "") or "").strip().lower()
    has_crc_param = ("crc" in request.args)  # Distinguish legacy (absent) vs present-but-empty.

    if not device_id or not cap or not fw:
        current_app.logger.debug(
            f"[device/info] 400 missing params dev={device_id}, cap={cap}, fw={fw}"
        )
        return _no_cache_headers(jsonify({"status": "error", "reason": "missing params"})), 400

    device_id_safe = _safe_device_id(device_id)

    # Server-observed remote address. This is the correct place to capture client IP.
    current_app.logger.debug(
        f"[info] request: dev={device_id_safe} cap={cap} fw={fw} res={res} "
        f"has_crc_param={has_crc_param} dev_crc8='{dev_crc[:8]}' remote_addr={request.remote_addr}"
    )

    userid, how = _resolve_userid(device_id_safe)
    current_app.logger.debug(
        f"[info] auth: dev={device_id_safe} how={how} userid={'<none>' if not userid else userid}"
    )

    if how == "mismatch":
        return _no_cache_headers(jsonify({
            "status": "error",
            "reason": "forbidden (session vs device owner mismatch)"
        })), 403

    if not userid:
        current_app.logger.debug(f"[device/info] 401 userid missing (how={how}, dev={device_id_safe})")
        return _no_cache_headers(jsonify({"status": "error", "reason": "no userid"})), 401

    user = _get_user_by_userid(userid)
    if not user:
        return _no_cache_headers(jsonify({"status": "error", "reason": "user_not_found"})), 404

    now = R.kst_now_naive()
    now_epoch_ms = _epoch_ms_now()

    tel = _parse_device_telemetry()
    current_app.logger.debug(
        f"[info] telemetry: dev={device_id_safe} "
        f"battery_pct={tel.get('battery_pct')} battery_mv={tel.get('battery_mv')} "
        f"temp_c_x10={tel.get('temp_c_x10')} rssi_dbm={tel.get('rssi_dbm')} wake_reason={tel.get('wake_reason')} "
        f"dev_mono_ms={tel.get('dev_mono_ms')} dev_local_epoch_ms={tel.get('dev_local_epoch_ms')}"
    )

    offset_ms = None
    if tel.get("dev_local_epoch_ms") is not None:
        try:
            offset_ms = int(now_epoch_ms - int(tel["dev_local_epoch_ms"]))
        except Exception:
            offset_ms = None

    # Determine current/next posting strictly via DB.
    cur, nxt = R.pick_current_and_next_posting(user.no, device_id_safe, now)
    current_app.logger.debug(
        f"[info] pick: dev={device_id_safe} now={now.isoformat()} "
        f"cur_id={getattr(cur,'id',None)} nxt_id={getattr(nxt,'id',None)}"
    )

    next_change_epoch_ms = _compute_next_change_epoch_ms(now, now_epoch_ms, cur, nxt)
    sleep_planned_sec = _compute_sleep_planned_sec(now_epoch_ms, next_change_epoch_ms)
    current_app.logger.debug(
        f"[info] sleep_plan: dev={device_id_safe} server_now_ms={now_epoch_ms} "
        f"next_change_ms={next_change_epoch_ms} sleep_sec={sleep_planned_sec} offset_ms={offset_ms}"
    )

    posting_id = None
    asset_id = None

    # Choose meta: asset meta when posting exists; otherwise default meta by resolution.
    if not cur or not getattr(cur, "asset", None):
        meta = _load_default_meta(res=res)
        current_app.logger.debug(
            f"[info] meta: dev={device_id_safe} selected=default res={res} meta_ok={bool(meta)}"
        )
    else:
        posting_id = getattr(cur, "id", None)
        asset = cur.asset
        asset_id = getattr(asset, "id", None)
        meta = _load_meta_for_asset(user, asset)
        current_app.logger.debug(
            f"[info] meta: dev={device_id_safe} selected=asset posting_id={posting_id} "
            f"asset_id={asset_id} meta_ok={bool(meta)}"
        )
    
    ver = int(meta.get("ver") or 0)
     # Optional device-side state hint (supports both legacy/new firmware)
    # - legacy: may send nothing
    # - new fw: has_crc_param=1 & dev_crc32=........ (and optionally dev_ver)
    args = request.args

    dev_crc = (args.get("crc", "") or args.get("dev_crc32", "") or "").strip().lower()
    dev_crc8 = dev_crc.replace("0x", "")[:8]

    # ✅ "CRC 참여 펌웨어" 판정 확장
    has_crc_param_flag = (args.get("has_crc_param", "") or "").strip().lower() in ("1", "true", "yes", "y")
    has_crc_param = has_crc_param_flag or ("crc" in args) or ("dev_crc32" in args)

    # Extract stable identifiers.
    srv_crc32 = (meta.get("crc32") or "").lower()
    srv_crc8 = srv_crc32[:8] if srv_crc32 else ""

    need_bmp = False
    need_bmp_reason = ""

    if has_crc_param:
        # ✅ CRC-based decision enabled (new firmware)
        if srv_crc8:
            # ✅ "00000000"도 first-boot/unknown으로 처리 → 업데이트 필요
            if (not dev_crc8) or (dev_crc8 == "00000000"):
                need_bmp = True
                need_bmp_reason = "dev_crc_missing_or_zero"
            elif dev_crc8 != srv_crc8:
                need_bmp = True
                need_bmp_reason = "crc_mismatch"
            else:
                need_bmp = False
                need_bmp_reason = "crc_same"
        else:
            need_bmp = False
            need_bmp_reason = "server_crc_missing"
    else:
        # Legacy mode: device handles update decision by its own legacy logic
        need_bmp = False
        need_bmp_reason = "legacy_no_crc_param"

    allow_update = bool(need_bmp)

    current_app.logger.debug(
        f"[info] crc_check: dev={device_id_safe} has_crc_param={has_crc_param} "
        f"dev_crc8='{dev_crc8}' srv_crc8='{srv_crc8}' "
        f"allow_update={allow_update} need_bmp={need_bmp} reason={need_bmp_reason}"
    )


    bmp_url = url_for(
        "device.send_bmp",
        device_id=device_id_safe,
        cap=cap,
        v=str(ver),
        _external=True,
    )

    elapsed = int((time.perf_counter() - t0) * 1000)

    # Access logging (best effort). Do NOT pass ip/user_agent/method/path (repo captures those itself).
    try:
        R.log_access(
            user_id=user.no,
            device_id=device_id_safe,
            api="info",
            ok=True,
            http_status=200,
            posting_id=posting_id,
            asset_id=asset_id,
            ver=(ver if ver else None),
            crc32=(srv_crc8 if srv_crc8 else None),
            bytes_sent=None,
            elapsed_ms=elapsed,
            error_msg=None,
            auth_ok=True,
            auth_mode=how,
            device_fp=None,

            # Telemetry
            battery_pct=tel.get("battery_pct"),
            battery_mv=tel.get("battery_mv"),
            temp_c_x10=tel.get("temp_c_x10"),
            rssi_dbm=tel.get("rssi_dbm"),
            wake_reason=tel.get("wake_reason"),

            # Time sync / sleep plan
            dev_mono_ms=tel.get("dev_mono_ms"),
            dev_local_epoch_ms=tel.get("dev_local_epoch_ms"),
            offset_ms=offset_ms,
            server_epoch_ms=now_epoch_ms,
            next_change_epoch_ms=next_change_epoch_ms,
            sleep_planned_sec=sleep_planned_sec,

            # Backoff state
            fail_count=tel.get("fail_count"),
            backoff_level=tel.get("backoff_level"),
        )
        _commit_log_safely()
        current_app.logger.debug(f"[info] access_log: dev={device_id_safe} committed=1 elapsed_ms={elapsed}")
    except Exception as e:
        current_app.logger.debug(f"[info] access_log: dev={device_id_safe} committed=0 err={e}")

    resp = {
        "status": "ok",
        "server_time": datetime.now().isoformat(timespec="seconds"),

        # Extensions
        "server_epoch_ms": int(now_epoch_ms),
        "offset_ms": (int(offset_ms) if offset_ms is not None else None),
        "next_change_epoch_ms": int(next_change_epoch_ms),
        "sleep_planned_sec": int(sleep_planned_sec),
        "max_poll_sec": MAX_POLL_SEC_DEFAULT,
        "min_wake_sec": MIN_WAKE_SEC_DEFAULT,
        "guard_sec": GUARD_SEC_DEFAULT,

        "allow_update": bool(allow_update),
        "need_bmp": bool(need_bmp),
        "need_bmp_reason": need_bmp_reason,

        # Debug echo (safe to remove after rollout)
        "echo": {
            "device_id": device_id,
            "cap": cap,
            "fw": fw,
            "res": res,
            "userid": userid,
            "resolved_via": how,
            "has_crc_param": bool(has_crc_param),
            "dev_crc8": dev_crc8,
            "srv_crc8": srv_crc8,
        },

        # Legacy payload block
        "bmp": {
            "url": bmp_url,
            "len": int(meta.get("total_len") or 0),
            "crc32": srv_crc32,
            "ver": int(ver or 0),
            "mode": str(meta.get("mode") or DEFAULT_MODE),
            "size": f"{int(meta.get('width') or 0)}x{int(meta.get('height') or 0)}",
            "file": meta.get("file") or "onelayer.bin",
            "is_default": bool(meta.get("is_default") is True),
        },
    }

    current_app.logger.debug(f"[info] response_to_device: dev={device_id_safe} bmp_ver={resp['bmp']['ver']} bmp_crc={resp['bmp']['crc32'][:8]}")
    current_app.logger.debug(f"all the data : {resp}")
    return _no_cache_headers(jsonify(resp)), 200


# ─────────────────────────────────────────────────────────────
# /device/bmp
# ─────────────────────────────────────────────────────────────
@bp.route("/bmp", methods=["GET"])
def send_bmp():
    """
    GET /device/bmp?device_id=E07&cap=BWR&v=.&res=1200x1600
    Responsibilities:
        - Serve active asset binary payload, or default payload when no posting is available.
        - Never trap the device into exponential backoff due to an expected "no posting" condition.
    """
    t0 = time.perf_counter()

    device_id = (request.args.get("device_id", "") or "").strip()
    cap = (request.args.get("cap", "BWR") or "BWR").strip()
    res = (request.args.get("res", "") or "").strip()
    _ = (request.args.get("v", "") or "").strip()

    if not device_id:
        return _no_cache_headers(jsonify({"ok": False, "reason": "missing device_id"})), 400

    device_id_safe = _safe_device_id(device_id)

    current_app.logger.debug(
        f"[bmp] request: dev={device_id_safe} cap={cap} res={res} remote_addr={request.remote_addr}"
    )

    userid, how = _resolve_userid(device_id_safe)
    if not userid:
        current_app.logger.debug(f"[bmp] auth: dev={device_id_safe} how={how} -> no userid")
        return _no_cache_headers(jsonify({"ok": False, "reason": "no userid"})), 401

    user = _get_user_by_userid(userid)
    if not user:
        return _no_cache_headers(jsonify({"ok": False, "reason": "user_not_found"})), 404

    now = R.kst_now_naive()
    now_epoch_ms = _epoch_ms_now()
    tel = _parse_device_telemetry()

    offset_ms = None
    if tel.get("dev_local_epoch_ms") is not None:
        try:
            offset_ms = int(now_epoch_ms - int(tel["dev_local_epoch_ms"]))
        except Exception:
            offset_ms = None

    cur, nxt = R.pick_current_and_next_posting(user.no, device_id_safe, now)
    next_change_epoch_ms = _compute_next_change_epoch_ms(now, now_epoch_ms, cur, nxt)
    sleep_planned_sec = _compute_sleep_planned_sec(now_epoch_ms, next_change_epoch_ms)

    current_app.logger.debug(
        f"[bmp] pick: dev={device_id_safe} now={now.isoformat()} cur_id={getattr(cur,'id',None)} nxt_id={getattr(nxt,'id',None)}"
    )

    # ------------------------------------------------------------
    # No active posting: serve default BIN (expected condition).
    # ------------------------------------------------------------
    if not cur or not getattr(cur, "asset", None):
        current_app.logger.debug(
            f"[bmp] default_path: dev={device_id_safe} reason=no_active_posting res={res}"
        )

        dmeta = _load_default_meta(res=res)
        if not dmeta:
            elapsed = int((time.perf_counter() - t0) * 1000)
            try:
                R.log_access(
                    user_id=user.no,
                    device_id=device_id_safe,
                    api="bmp",
                    ok=False,
                    http_status=404,
                    posting_id=None,
                    asset_id=None,
                    ver=None,
                    crc32=None,
                    bytes_sent=None,
                    elapsed_ms=elapsed,
                    error_msg="no_posting_no_default",
                    auth_ok=True,
                    auth_mode=how,
                    device_fp=None,

                    battery_pct=tel.get("battery_pct"),
                    battery_mv=tel.get("battery_mv"),
                    temp_c_x10=tel.get("temp_c_x10"),
                    rssi_dbm=tel.get("rssi_dbm"),
                    wake_reason=tel.get("wake_reason"),
                    dev_mono_ms=tel.get("dev_mono_ms"),
                    dev_local_epoch_ms=tel.get("dev_local_epoch_ms"),
                    offset_ms=offset_ms,
                    server_epoch_ms=now_epoch_ms,
                    next_change_epoch_ms=next_change_epoch_ms,
                    sleep_planned_sec=sleep_planned_sec,
                    fail_count=tel.get("fail_count"),
                    backoff_level=tel.get("backoff_level"),
                )
                _commit_log_safely()
            except Exception:
                pass
            return _no_cache_headers(jsonify({"ok": False, "reason": "no_posting_no_default"})), 404

        bin_path = dmeta.get("abs_path")
        if not bin_path or not os.path.isfile(bin_path):
            return _no_cache_headers(jsonify({"ok": False, "reason": "default_missing"})), 404

        st = os.stat(bin_path)
        total_len = int(st.st_size)
        mtime = int(os.path.getmtime(bin_path))
        crc_hex = (dmeta.get("crc32") or "00000000")[:8]
        ver = int(dmeta.get("ver") or mtime)
        elapsed = int((time.perf_counter() - t0) * 1000)

        current_app.logger.debug(
            f"[bmp] send_default: dev={device_id_safe} path='{bin_path}' len={total_len} ver={ver} crc={crc_hex}"
        )

        try:
            R.log_access(
                user_id=user.no,
                device_id=device_id_safe,
                api="bmp",
                ok=True,
                http_status=200,
                posting_id=None,
                asset_id=None,
                ver=ver,
                crc32=crc_hex,
                bytes_sent=total_len,
                elapsed_ms=elapsed,
                error_msg="default_bin",
                auth_ok=True,
                auth_mode=how,
                device_fp=None,

                battery_pct=tel.get("battery_pct"),
                battery_mv=tel.get("battery_mv"),
                temp_c_x10=tel.get("temp_c_x10"),
                rssi_dbm=tel.get("rssi_dbm"),
                wake_reason=tel.get("wake_reason"),
                dev_mono_ms=tel.get("dev_mono_ms"),
                dev_local_epoch_ms=tel.get("dev_local_epoch_ms"),
                offset_ms=offset_ms,
                server_epoch_ms=now_epoch_ms,
                next_change_epoch_ms=next_change_epoch_ms,
                sleep_planned_sec=sleep_planned_sec,
                fail_count=tel.get("fail_count"),
                backoff_level=tel.get("backoff_level"),
            )
            _commit_log_safely()
        except Exception:
            pass

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
        resp.headers["Content-Disposition"] = f'attachment; filename="{device_id_safe or "image"}.bin"'
        resp.headers["X-Default-Bin"] = "1"
        return _no_cache_headers(resp)

    # ------------------------------------------------------------
    # Active posting available: serve asset payload.
    # ------------------------------------------------------------
    asset = cur.asset
    meta = _load_meta_for_asset(user, asset)

    current_app.logger.debug(
        f"[bmp] asset_path: dev={device_id_safe} posting_id={getattr(cur,'id',None)} asset_id={getattr(asset,'id',None)}"
    )

    # Path 1: serve bin_relpath directly.
    bin_path = None
    if getattr(asset, "bin_relpath", None):
        try:
            bin_path = R.abs_path_from_rel(user, asset.bin_relpath)
        except Exception:
            bin_path = None

    if bin_path and os.path.isfile(bin_path):
        st = os.stat(bin_path)
        total_len = int(st.st_size)

        crc_hex = (meta.get("crc32") or "").lower() or "00000000"
        try:
            crc_hex = _read_crc32_from_bin_tail(bin_path)
        except Exception:
            pass

        ver = int(meta.get("ver") or 0)
        if ver <= 0:
            # Safety: ensure a stable non-zero version value.
            try:
                ver = int(os.path.getmtime(bin_path))
            except Exception:
                ver = int(time.time())

        mtime = int(os.path.getmtime(bin_path))
        elapsed = int((time.perf_counter() - t0) * 1000)

        current_app.logger.debug(
            f"[bmp] send_asset: dev={device_id_safe} path='{bin_path}' len={total_len} ver={ver} crc={crc_hex[:8]}"
        )

        try:
            R.log_access(
                user_id=user.no,
                device_id=device_id_safe,
                api="bmp",
                ok=True,
                http_status=200,
                posting_id=getattr(cur, "id", None),
                asset_id=getattr(asset, "id", None),
                ver=ver,
                crc32=crc_hex[:8],
                bytes_sent=total_len,
                elapsed_ms=elapsed,
                error_msg=None,
                auth_ok=True,
                auth_mode=how,
                device_fp=None,

                battery_pct=tel.get("battery_pct"),
                battery_mv=tel.get("battery_mv"),
                temp_c_x10=tel.get("temp_c_x10"),
                rssi_dbm=tel.get("rssi_dbm"),
                wake_reason=tel.get("wake_reason"),
                dev_mono_ms=tel.get("dev_mono_ms"),
                dev_local_epoch_ms=tel.get("dev_local_epoch_ms"),
                offset_ms=offset_ms,
                server_epoch_ms=now_epoch_ms,
                next_change_epoch_ms=next_change_epoch_ms,
                sleep_planned_sec=sleep_planned_sec,
                fail_count=tel.get("fail_count"),
                backoff_level=tel.get("backoff_level"),
            )
            _commit_log_safely()
        except Exception:
            pass

        resp = send_file(
            bin_path,
            mimetype="application/octet-stream",
            as_attachment=False,
            conditional=True,
            max_age=0,
        )
        resp.headers["Content-Length"] = str(total_len)
        resp.headers["X-CRC32"] = crc_hex[:8]
        resp.headers["X-Payload-Version"] = str(ver)
        resp.headers["ETag"] = f'W/"{ver}-{crc_hex[:8]}-{total_len}"'
        resp.headers["Last-Modified"] = datetime.utcfromtimestamp(mtime).strftime("%a, %d %b %Y %H:%M:%S GMT")
        resp.headers["Content-Disposition"] = f'attachment; filename="{device_id_safe or "image"}.bin"'
        return _no_cache_headers(resp)

    # Path 2 (optional): convert BMP to payload if bin is missing or broken.
    if ImageToBytes is not None:
        bmp_rel = getattr(asset, "preview_relpath", None)
        if bmp_rel:
            bmp_path = R.abs_path_from_rel(user, bmp_rel)
            if os.path.isfile(bmp_path):
                cache_key = (bmp_path, int(os.path.getmtime(bmp_path)), str(meta.get("mode") or DEFAULT_MODE))
                with _cache_lock:
                    cached = _payload_cache.get(cache_key)

                if cached:
                    payload = cached["payload"]
                    crc_hex = cached["crc32"]
                    total_len = cached["len"]
                    current_app.logger.debug(
                        f"[bmp] fallback_cache_hit: dev={device_id_safe} bmp='{bmp_path}' len={total_len} crc={crc_hex[:8]}"
                    )
                else:
                    payload = ImageToBytes.image_file_to_payload(bmp_path, str(meta.get("mode") or DEFAULT_MODE))
                    total_len = len(payload)
                    try:
                        crc_le = struct.unpack("<I", payload[-4:])[0]
                        crc_hex = f"{crc_le:08x}"
                    except Exception:
                        crc_hex = "00000000"
                    with _cache_lock:
                        _payload_cache[cache_key] = {"payload": payload, "crc32": crc_hex, "len": total_len}
                    current_app.logger.debug(
                        f"[bmp] fallback_generated: dev={device_id_safe} bmp='{bmp_path}' len={total_len} crc={crc_hex[:8]}"
                    )

                ver = int(meta.get("ver") or 0)
                if ver <= 0:
                    try:
                        ver = int(os.path.getmtime(bmp_path))
                    except Exception:
                        ver = int(time.time())

                mtime = int(os.path.getmtime(bmp_path))
                elapsed = int((time.perf_counter() - t0) * 1000)

                try:
                    R.log_access(
                        user_id=user.no,
                        device_id=device_id_safe,
                        api="bmp",
                        ok=True,
                        http_status=200,
                        posting_id=getattr(cur, "id", None),
                        asset_id=getattr(asset, "id", None),
                        ver=ver,
                        crc32=crc_hex[:8],
                        bytes_sent=total_len,
                        elapsed_ms=elapsed,
                        error_msg="fallback_payload",
                        auth_ok=True,
                        auth_mode=how,
                        device_fp=None,

                        battery_pct=tel.get("battery_pct"),
                        battery_mv=tel.get("battery_mv"),
                        temp_c_x10=tel.get("temp_c_x10"),
                        rssi_dbm=tel.get("rssi_dbm"),
                        wake_reason=tel.get("wake_reason"),
                        dev_mono_ms=tel.get("dev_mono_ms"),
                        dev_local_epoch_ms=tel.get("dev_local_epoch_ms"),
                        offset_ms=offset_ms,
                        server_epoch_ms=now_epoch_ms,
                        next_change_epoch_ms=next_change_epoch_ms,
                        sleep_planned_sec=sleep_planned_sec,
                        fail_count=tel.get("fail_count"),
                        backoff_level=tel.get("backoff_level"),
                    )
                    _commit_log_safely()
                except Exception:
                    pass

                resp = Response(payload, mimetype="application/octet-stream")
                resp.headers["Content-Length"] = str(total_len)
                resp.headers["X-CRC32"] = crc_hex[:8]
                resp.headers["X-Payload-Version"] = str(ver)
                resp.headers["ETag"] = f'W/"{ver}-{crc_hex[:8]}-{total_len}"'
                resp.headers["Last-Modified"] = datetime.utcfromtimestamp(mtime).strftime("%a, %d %b %Y %H:%M:%S GMT")
                resp.headers["Content-Disposition"] = f'attachment; filename="{device_id_safe or "image"}.bin"'
                return _no_cache_headers(resp)

    # Final failure (asset exists but no usable payload found).
    elapsed = int((time.perf_counter() - t0) * 1000)
    current_app.logger.debug(
        f"[bmp] payload_missing: dev={device_id_safe} posting_id={getattr(cur,'id',None)} asset_id={getattr(asset,'id',None)}"
    )

    try:
        R.log_access(
            user_id=user.no,
            device_id=device_id_safe,
            api="bmp",
            ok=False,
            http_status=404,
            posting_id=getattr(cur, "id", None),
            asset_id=getattr(asset, "id", None) if asset else None,
            ver=None,
            crc32=None,
            bytes_sent=None,
            elapsed_ms=elapsed,
            error_msg="payload_missing",
            auth_ok=True,
            auth_mode=how,
            device_fp=None,

            battery_pct=tel.get("battery_pct"),
            battery_mv=tel.get("battery_mv"),
            temp_c_x10=tel.get("temp_c_x10"),
            rssi_dbm=tel.get("rssi_dbm"),
            wake_reason=tel.get("wake_reason"),
            dev_mono_ms=tel.get("dev_mono_ms"),
            dev_local_epoch_ms=tel.get("dev_local_epoch_ms"),
            offset_ms=offset_ms,
            server_epoch_ms=now_epoch_ms,
            next_change_epoch_ms=next_change_epoch_ms,
            sleep_planned_sec=sleep_planned_sec,
            fail_count=tel.get("fail_count"),
            backoff_level=tel.get("backoff_level"),
        )
        _commit_log_safely()
    except Exception:
        pass

    return _no_cache_headers(jsonify({"ok": False, "reason": "payload_missing"})), 404


# ─────────────────────────────────────────────────────────────
# /device/ack
# ─────────────────────────────────────────────────────────────
@bp.route("/ack", methods=["GET", "POST"])
def device_ack():
    """
    Completion acknowledgement endpoint.
    Firmware should call this once after it prints "Display Done!!".
    Example:
        GET /device/ack?device_id=E07&posting_id=123&asset_id=456&ver=789&crc32=abcd1234&result=ok&display_ms=21500
    """
    t0 = time.perf_counter()

    device_id = (request.values.get("device_id", "") or "").strip()
    if not device_id:
        return _no_cache_headers(jsonify({"ok": False, "reason": "missing device_id"})), 400

    device_id_safe = _safe_device_id(device_id)

    current_app.logger.debug(
        f"[ack] request: dev={device_id_safe} remote_addr={request.remote_addr} method={request.method}"
    )

    userid, how = _resolve_userid(device_id_safe)
    if not userid:
        current_app.logger.debug(f"[ack] auth: dev={device_id_safe} how={how} -> no userid")
        return _no_cache_headers(jsonify({"ok": False, "reason": "no userid"})), 401

    user = _get_user_by_userid(userid)
    if not user:
        return _no_cache_headers(jsonify({"ok": False, "reason": "user_not_found"})), 404

    now_epoch_ms = _epoch_ms_now()
    tel = _parse_device_telemetry()

    posting_id = _arg_int("posting_id", None, lo=0)
    asset_id   = _arg_int("asset_id", None, lo=0)
    ver        = _arg_int("ver", None, lo=0)
    crc32      = (_arg_str("crc32", "", maxlen=16) or "").lower()[:8]
    result     = (_arg_str("result", "ok", maxlen=16) or "ok").lower()
    display_ms = _arg_int("display_ms", None, lo=0)

    ok = (result in ("ok", "done", "success", "1", "true", "y"))

    current_app.logger.debug(
        f"[ack] content: dev={device_id_safe} posting_id={posting_id} asset_id={asset_id} ver={ver} crc32='{crc32}' "
        f"result='{result}' ok={ok} display_ms={display_ms}"
    )

    elapsed = int((time.perf_counter() - t0) * 1000)

    try:
        R.log_access(
            user_id=user.no,
            device_id=device_id_safe,
            api="ack",
            ok=bool(ok),
            http_status=200 if ok else 202,
            posting_id=posting_id,
            asset_id=asset_id,
            ver=ver,
            crc32=crc32 or None,
            bytes_sent=None,
            elapsed_ms=elapsed,
            error_msg=(f"display_ms={display_ms}" if display_ms is not None else None),
            auth_ok=True,
            auth_mode=how,
            device_fp=None,

            battery_pct=tel.get("battery_pct"),
            battery_mv=tel.get("battery_mv"),
            temp_c_x10=tel.get("temp_c_x10"),
            rssi_dbm=tel.get("rssi_dbm"),
            wake_reason=tel.get("wake_reason"),
            dev_mono_ms=tel.get("dev_mono_ms"),
            dev_local_epoch_ms=tel.get("dev_local_epoch_ms"),
            offset_ms=None,
            server_epoch_ms=now_epoch_ms,
            next_change_epoch_ms=None,
            sleep_planned_sec=None,
            fail_count=tel.get("fail_count"),
            backoff_level=tel.get("backoff_level"),
        )
        _commit_log_safely()
        current_app.logger.debug(f"[ack] access_log: dev={device_id_safe} committed=1 elapsed_ms={elapsed}")
    except Exception as e:
        current_app.logger.debug(f"[ack] access_log: dev={device_id_safe} committed=0 err={e}")

    return _no_cache_headers(jsonify({
        "ok": True,
        "ack_ok": bool(ok),
        "server_epoch_ms": now_epoch_ms,
    })), 200
