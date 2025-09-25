# controllers/device_controller.py
import os, glob, json, time, threading
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, url_for, current_app

from ..service.image_to_bytes import ImageToBytes # 가변 해상도/모드 지원 버전

bp = Blueprint('device', __name__, url_prefix='/device')

# ==== 디바이스 자산 루트 (BMP + META(+H)) ====
ASSET_ROOT = r"D:/bmp_files/"
os.makedirs(ASSET_ROOT, exist_ok=True)

# ---- 유틸 ----
def _safe_device_id(raw: str) -> str:
    if not raw:
        return ""
    return "".join(ch for ch in raw if ch.isalnum() or ch in "._-")[:64]

def _pick_meta(device_id: str, res: str | None, mode: str | None):
    """
    device_id, (옵션)res='1600x1200', (옵션)mode='BW'|'BWRY'
    → 가장 적합한 meta.json 경로와 dict 반환
    파일명 패턴: <device>_<WxH>_<MODE>.meta.json
    """
    pattern = f"{_safe_device_id(device_id)}_*_*.meta.json"
    cand = glob.glob(os.path.join(ASSET_ROOT, pattern))
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
            if m.get("mode","").upper() == mode.upper():
                sc += 5
        # 최신 우선 (버전이 보통 mtime 기반)
        try:
            sc += int(m.get("ver", 0)) // 1000
        except Exception:
            pass
        return sc

    metas.sort(key=score, reverse=True)
    return metas[0]  # (path, meta)


# ---- 간단 바이너리 캐시 (파일 mtime+mode 기준) ----
_bin_cache = {}  # key: (bmp_path, mtime_int, mode) -> {"payload":bytes, "len":int, "crc32":str}
_cache_lock = threading.Lock()


@bp.route("/info", methods=["GET"])
def device_info():
    """
    ESP32가 상태 확인 및 다운로드 정보 요청:
    GET /device/info?device_id=E01&cap=BWR&fw=1.0.0[&res=1600x1200]
    """
    device_id = request.args.get("device_id", "").strip()
    cap       = request.args.get("cap", "").strip()    # 'BWR' 등
    fw        = request.args.get("fw", "").strip()
    res       = request.args.get("res", "").strip()    # 예: '1600x1200' (옵션)

    if not device_id or not cap or not fw:
        return jsonify({"status":"error","reason":"missing params"}), 400

    # cap 힌트로 모드 유추 (BWR* → BWRY, 아니면 BW)
    mode_hint = "BWRY" if cap.upper().startswith("BWR") else "BW"

    meta_path, meta = _pick_meta(device_id, res or None, mode_hint)
    if not meta:
        return jsonify({"status":"error","reason":"no prepared asset"}), 404

    bmp_url = url_for(
        "device.send_bmp",
        device_id=_safe_device_id(device_id),
        res=f"{meta['width']}x{meta['height']}",
        mode=meta["mode"],
        cap=cap,                     # ★ 추가
        v=meta["ver"],
        _external=True,
    )

    return jsonify({
        "status": "ok",
        "server_time": datetime.now().isoformat(timespec="seconds"),
        "echo": {"device_id": device_id, "cap": cap, "fw": fw},
        "bmp": {
            "url": bmp_url,
            "len": meta["total_len"],          # CRC 포함 길이
            "crc32": meta["crc32"],            # 8-hex string (소문자)
            "ver": meta["ver"],                # 보통 mtime(int)
            "mode": meta["mode"],              # 'BW' | 'BWRY'
            "size": f"{meta['width']}x{meta['height']}",
            "file": meta["file"],
        },
    }), 200


@bp.route("/bmp", methods=["GET"])
def send_bmp():
    """
    ESP32가 실제 바이너리 다운로드:
    GET /device/bmp?device_id=E01&res=1600x1200&mode=BWRY&v=1755842843
    - payload = (1bpp or 2bpp packed) + CRC32(LE)
    - 헤더로 CRC/버전/길이 제공
    """
    device_id = request.args.get("device_id", "").strip()
    res       = request.args.get("res", "").strip()      # '800x480' 등
    mode_q    = request.args.get("mode", "").strip()     # 'BW'|'BWRY'
    cap_q     = request.args.get("cap","BWR").strip()   # ★ 추가
    _         = request.args.get("v","").strip()

    if not device_id:
        return jsonify({"status":"error","reason":"missing device_id"}), 400

    meta_path, meta = _pick_meta(device_id, res or None, mode_q or None)
    if not meta:
        return jsonify({"status":"error","reason":"no asset"}), 404

    bmp_path = os.path.join(ASSET_ROOT, meta["file"])
    if not os.path.exists(bmp_path):
        return jsonify({"status":"error","reason":"file missing"}), 404

    mtime = int(os.path.getmtime(bmp_path))
    cache_key = (bmp_path, mtime, meta["mode"])
    with _cache_lock:
        cached = _bin_cache.get(cache_key)

    if cached:
        payload = cached["payload"]
        crc_hex = cached["crc32"]
        total_len = cached["len"]
    else:
        # BMP → 디바이스용 payload (가변 해상도/모드)
        # payload   = ImageToBytes.image_file_to_payload(bmp_path, meta["mode"], cap=cap_q)  # ★ cap 전달
        # (수정) 메타의 packing 반영. 없으면 BWRY는 2bpp 기본.
        packing = meta.get("packing", "2bpp" if meta["mode"].upper()=="BWRY" else "1bpp")
        payload = ImageToBytes.image_file_to_payload(bmp_path, meta["mode"])
        total_len = len(payload)
        # CRC32(LE) 추출 (메타의 crc32와 일치해야 정상)
        try:
            import struct
            crc_le = struct.unpack("<I", payload[-4:])[0]
            crc_hex = f"{crc_le:08x}"
        except Exception:
            crc_hex = meta.get("crc32", "00000000")

        with _cache_lock:
            _bin_cache[cache_key] = {"payload": payload, "crc32": crc_hex, "len": total_len}

    # 응답
    resp = Response(payload, mimetype="application/octet-stream")
    resp.headers["Content-Length"] = str(total_len)
    resp.headers["X-CRC32"] = crc_hex
    resp.headers["X-Payload-Version"] = str(meta["ver"])
    resp.headers["X-Colors"] = "BWR-2bit" if meta["mode"].upper() == "BWRY" else "BW-1bit"
    resp.headers["ETag"] = f'W/"{meta["ver"]}-{crc_hex}-{total_len}"'
    resp.headers["Last-Modified"] = datetime.utcfromtimestamp(mtime).strftime("%a, %d %b %Y %H:%M:%S GMT")
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Content-Disposition"] = f'attachment; filename="{_safe_device_id(device_id) or "image"}.bin"'

    current_app.logger.info(f"[BMP] send {os.path.basename(bmp_path)} → {request.remote_addr} "
                            f"(len={total_len}, crc=0x{crc_hex}, ver={meta['ver']})")
    return resp
