import os, time
from flask import Blueprint, request, jsonify, abort, Response, send_file
from pybo import db
from ..models import User, EInkDevice
from ..repository.repository_edevice import RepositoryEDevice as R

bp = Blueprint('edevice', __name__, url_prefix='/edevice')

def _safe_device_id(raw: str) -> str:
    if not raw:
        return ""
    safe = "".join(ch for ch in raw if ch.isalnum() or ch in "._-")
    return safe[:64]

def _get_device_owner(device_id: str) -> User:
    # 현재는 device_id로만 매핑 (추후 보안 auth 붙일 때 여기서 인증 연계)
    dev = EInkDevice.query.filter(EInkDevice.device_id == device_id).first()
    if not dev:
        abort(404, "device not registered")
    user = User.query.filter(User.no == dev.user_no).first()
    if not user:
        abort(404, "device owner not found")
    return user

@bp.get("/info")
def device_info():
    t0 = time.perf_counter()
    device_id = _safe_device_id(request.args.get("device_id", "").strip())
    cap = request.args.get("cap")  # optional
    fw  = request.args.get("fw")   # optional

    if not device_id:
        return jsonify({"status": "error", "reason": "missing device_id"}), 400

    user = _get_device_owner(device_id)
    now = R.kst_now_naive()

    try:
        cur, nxt = R.pick_current_and_next_posting(user.no, device_id, now)
        if not cur:
            elapsed = int((time.perf_counter() - t0) * 1000)
            R.log_access(user_id=user.no, device_id=device_id, api="info",
                       ok=True, http_status=200, elapsed_ms=elapsed, error_msg="no_posting")
            R.touch_device_summary(user, device_id, api="info", http_status=200, error_msg="no_posting", ver=None)
            db.session.commit()
            return jsonify({"status":"ok", "allow_update": False, "reason":"no_posting"}), 200

        asset = cur.asset
        meta = R.build_device_meta(device_id, asset)

        elapsed = int((time.perf_counter() - t0) * 1000)
        R.log_access(user_id=user.no, device_id=device_id, api="info",
                   ok=True, http_status=200,
                   posting_id=cur.id, asset_id=asset.id,
                   ver=asset.ver, crc32=asset.crc32_le,
                   elapsed_ms=elapsed)
        R.touch_device_summary(user, device_id, api="info", http_status=200, error_msg=None, ver=asset.ver)
        db.session.commit()

        # 형이 원래 쓰던 meta 응답 형태로 그대로 리턴
        meta["status"] = "ok"
        meta["allow_update"] = True
        meta["server_time"] = now.isoformat(timespec="seconds")
        meta["echo"] = {"device_id": device_id, "cap": cap, "fw": fw}
        return jsonify(meta), 200

    except Exception as e:
        elapsed = int((time.perf_counter() - t0) * 1000)
        R.log_access(user_id=user.no, device_id=device_id, api="info",
                   ok=False, http_status=500, elapsed_ms=elapsed, error_msg=str(e))
        R.touch_device_summary(user, device_id, api="info", http_status=500, error_msg=str(e), ver=None)
        db.session.commit()
        raise

@bp.get("/bmp")
def send_bmp():
    t0 = time.perf_counter()
    device_id = _safe_device_id(request.args.get("device_id", "").strip())
    if not device_id:
        abort(400)

    user = _get_device_owner(device_id)
    now = R.kst_now_naive()

    try:
        cur, _ = R.pick_current_and_next_posting(user.no, device_id, now)
        if not cur:
            elapsed = int((time.perf_counter() - t0) * 1000)
            R.log_access(user_id=user.no, device_id=device_id, api="bmp",
                       ok=False, http_status=404, elapsed_ms=elapsed, error_msg="no_posting")
            R.touch_device_summary(user, device_id, api="bmp", http_status=404, error_msg="no_posting", ver=None)
            db.session.commit()
            abort(404)

        asset = cur.asset
        bin_path = R.abs_path_from_rel(user, asset.bin_relpath)
        if not os.path.exists(bin_path):
            elapsed = int((time.perf_counter() - t0) * 1000)
            R.log_access(user_id=user.no, device_id=device_id, api="bmp",
                       ok=False, http_status=404,
                       posting_id=cur.id, asset_id=asset.id,
                       ver=asset.ver, crc32=asset.crc32_le,
                       elapsed_ms=elapsed, error_msg="bin_not_found")
            R.touch_device_summary(user, device_id, api="bmp", http_status=404, error_msg="bin_not_found", ver=asset.ver)
            db.session.commit()
            abort(404)

        st = os.stat(bin_path)
        # total_len 검증(있으면)
        if asset.total_len and int(st.st_size) != int(asset.total_len):
            elapsed = int((time.perf_counter() - t0) * 1000)
            msg = f"size_mismatch {st.st_size}!={asset.total_len}"
            R.log_access(user_id=user.no, device_id=device_id, api="bmp",
                       ok=False, http_status=500,
                       posting_id=cur.id, asset_id=asset.id,
                       ver=asset.ver, crc32=asset.crc32_le,
                       bytes_sent=st.st_size, elapsed_ms=elapsed, error_msg=msg)
            R.touch_device_summary(user, device_id, api="bmp", http_status=500, error_msg=msg, ver=asset.ver)
            db.session.commit()
            abort(500)

        elapsed = int((time.perf_counter() - t0) * 1000)
        R.log_access(user_id=user.no, device_id=device_id, api="bmp",
                   ok=True, http_status=200,
                   posting_id=cur.id, asset_id=asset.id,
                   ver=asset.ver, crc32=asset.crc32_le,
                   bytes_sent=st.st_size, elapsed_ms=elapsed)
        R.touch_device_summary(user, device_id, api="bmp", http_status=200, error_msg=None, ver=asset.ver)
        db.session.commit()

        # 바이너리 그대로 전달
        return send_file(bin_path, mimetype="application/octet-stream", as_attachment=False)

    except Exception as e:
        elapsed = int((time.perf_counter() - t0) * 1000)
        R.log_access(user_id=user.no, device_id=device_id, api="bmp",
                   ok=False, http_status=500, elapsed_ms=elapsed, error_msg=str(e))
        R.touch_device_summary(user, device_id=device_id, api="bmp", http_status=500, error_msg=str(e), ver=None)
        db.session.commit()
        raise
