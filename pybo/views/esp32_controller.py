# controllers/device_controller.py
import os, glob, json, time, threading
from datetime import datetime
from flask import Blueprint, request, jsonify, Response, url_for, current_app

from ..service.image_to_bytes import ImageToBytes # 가변 해상도/모드 지원 버전

bp = Blueprint('device', __name__, url_prefix='/device')

# ==== 디바이스 자산 루트 (BMP + META(+H) + BIN) ====
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


# ---- 간단 바이너리 캐시 (파일 경로/mtime 기준) ----
#   ※ 이제 .bin을 우선 사용하므로 캐시 키도 bin_path 기준으로 바꿈
_bin_cache = {}  # key: (path, mtime_int) -> {"payload":bytes, "len":int, "crc32":str}
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
        cap=cap,                     # 에코용
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
            "file": meta["file"],              # 디버깅 BMP 파일명
            # 필요 시 "bin": meta.get("bin") 도 내려줄 수 있음
        },
    }), 200


@bp.route("/bmp", methods=["GET"])
def send_bmp():
    """
    ESP32가 실제 바이너리 다운로드:
    GET /device/bmp?device_id=E01&res=1600x1200&mode=BWRY&v=1755842843
    - payload = (1bpp or 2bpp packed + EJOB header 등) + CRC32(LE)
    - 헤더로 CRC/버전/길이 제공
    - 이제 .bin(EJOB payload, CRC 포함)을 우선적으로 직접 스트리밍
      (.bin 없을 때만 구버전 폴백: .bmp 읽어 payload 생성)
    """
    device_id = request.args.get("device_id", "").strip()
    res       = request.args.get("res", "").strip()      # '800x480' 등
    mode_q    = request.args.get("mode", "").strip()     # 'BW'|'BWRY'
    cap_q     = request.args.get("cap","BWR").strip()
    _         = request.args.get("v","").strip()

    if not device_id:
        return jsonify({"status":"error","reason":"missing device_id"}), 400

    meta_path, meta = _pick_meta(device_id, res or None, mode_q or None)
    if not meta:
        return jsonify({"status":"error","reason":"no asset"}), 404

    # 우선 .bin 경로를 시도
    bin_name = meta.get("bin")
    bin_path = os.path.join(ASSET_ROOT, bin_name) if bin_name else None

    bmp_path = os.path.join(ASSET_ROOT, meta["file"])  # 디버깅 BMP
    use_bin = bin_path and os.path.exists(bin_path)

    # mtime/경로 기준 캐시 키
    path_for_cache = bin_path if use_bin else bmp_path
    if not os.path.exists(path_for_cache):
        return jsonify({"status":"error","reason":"file missing"}), 404

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
            # ★ 새로운 표준: .bin 파일을 그대로 스트리밍
            try:
                with open(bin_path, "rb") as f:
                    payload = f.read()
            except Exception as e:
                current_app.logger.error(f"[BIN] read fail: {e}")
                return jsonify({"status":"error","reason":"bin read fail"}), 500
            total_len = len(payload)
            # CRC32(LE) 추출 (메타의 crc32와 일치해야 정상)
            try:
                import struct
                crc_le = struct.unpack("<I", payload[-4:])[0]
                crc_hex = f"{crc_le:08x}"
            except Exception:
                crc_hex = meta.get("crc32", "00000000")
        else:
            # ★ 폴백(구버전 자산): BMP → payload 생성
            #   가능하면 send_file_route()에서 bin을 만들도록 이전 권장대로 전환하세요.
            packing = meta.get("packing", "2bpp" if meta["mode"].upper()=="BWRY" else "1bpp")
            # cap 전달 필요 시 image_file_to_payload 인자에 cap_q 추가 가능
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
        f"[BMP] send ({src_tag}) {_safe_device_id(device_id)} "
        f"(len={total_len}, crc=0x{crc_hex}, ver={meta['ver']}) → {request.remote_addr}"
    )
    return resp
