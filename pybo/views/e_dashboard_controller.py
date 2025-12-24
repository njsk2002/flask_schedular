# pybo/views/eink_dashboard_controller.py
import os
import json
import time
import uuid
from datetime import datetime,timedelta
from typing import Optional, Tuple

from flask import (
    Blueprint, jsonify, request, abort, send_file, render_template, current_app, redirect
)
from flask_login import login_required, current_user
from sqlalchemy import case, func, or_

from pybo import db
from pybo.models import (
    User,
    DocumentInfo,     # ✅ DocumentInfo 기반 docs 선택
    EInkDevice,
    EInkAsset,
    EInkPosting,
)

# 기존 RepositoryEDevice는 device pull 쪽(/edevice)에서 계속 쓸 수 있음
from pybo.repository.repository_edevice import RepositoryEDevice as R

bp = Blueprint("dashboard", __name__, url_prefix="/dashboard")


# ─────────────────────────────────────────────────────────────
# Debug helper
# ─────────────────────────────────────────────────────────────
def _dbg(tag: str, **kw):
    try:
        current_app.logger.debug(f"[eink_dashboard] {tag} | {kw}")
    except Exception:
        pass


# ─────────────────────────────────────────────────────────────
# Common utils
# ─────────────────────────────────────────────────────────────
def _kst_now_naive() -> datetime:
    # 프로젝트 정책: KST naive
    return datetime.now().replace(microsecond=0)


def _safe_device_id(raw: str) -> str:
    return R.safe_device_id(raw or "")

def _fmt_dt(d):
    if not d: return None
    return d.strftime("%Y-%m-%d %H:%M:%S")


def _parse_int(v, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _parse_res(panel_res: str):
    """
    '1200x1600' -> (1200,1600)
    """
    if not panel_res:
        return None, None
    s = str(panel_res).lower().replace(" ", "")
    if "x" not in s:
        return None, None
    a, b = s.split("x", 1)
    if a.isdigit() and b.isdigit():
        return int(a), int(b)
    return None, None


def _dt_from_local(s: str | None) -> datetime | None:
    """
    datetime-local: 'YYYY-MM-DDTHH:MM'
    -> 서버는 KST naive로 해석
    """
    if not s:
        return None
    try:
        return datetime.fromisoformat(s).replace(second=0, microsecond=0)
    except Exception:
        return None


def _user_key() -> str:
    return str(getattr(current_user, "userid", None) or getattr(current_user, "id", None) or getattr(current_user, "no", None))


def _user_root_dir() -> str:
    # 형이 말한 디스크 구조: D:\eink_docs\{user.userid or user.id}\...
    return fr"D:\eink_docs\{_user_key()}"


def _abs_from_rel(relpath: str) -> str:
    base = _user_root_dir()
    rel = (relpath or "").replace("/", os.sep).lstrip("\\/").strip()
    return os.path.normpath(os.path.join(base, rel))


def _find_onelayer_bmp(doc_dir: str) -> Optional[str]:
    """
    1) {doc_dir}/onelayer.bmp
    2) 폴더 내 onelayer*.bmp fallback
    """
    p0 = os.path.join(doc_dir, "onelayer.bmp")
    if os.path.exists(p0):
        return p0

    if not os.path.isdir(doc_dir):
        return None

    try:
        cands = []
        for fn in os.listdir(doc_dir):
            low = fn.lower()
            if low.endswith(".bmp") and ("onelayer" in low):
                cands.append(os.path.join(doc_dir, fn))
        if cands:
            # 최신 파일 우선
            cands.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            return cands[0]
    except Exception:
        return None
    return None


def _doc_base_dir_by_status(doc_status: str, doc_id: int) -> str:
    """
    approved      -> approval_process/{doc_id}/
    bulletin_files-> bulletin_files/{doc_id}/
    """
    base = _user_root_dir()
    if doc_status == "approved":
        return os.path.join(base, "approval_process", str(doc_id))
    if doc_status == "bulletin_files":
        return os.path.join(base, "bulletin_files", str(doc_id))
    # fallback
    return os.path.join(base, "docs", str(doc_id))


def _find_doc_payload_files(doc_dir: str, device_id: str) -> Tuple[Optional[str], Optional[str]]:
    """
    doc_dir 안에서 (bin, meta.json) 찾기
    - 우선 device_id로 시작하는 것 우선
    - 없으면 *.bin / *.meta.json
    """
    if not os.path.isdir(doc_dir):
        return None, None

    bin_path = None
    meta_path = None
    did = (device_id or "").strip()

    try:
        files = os.listdir(doc_dir)
    except Exception:
        return None, None

    # 1) device_id prefix 우선
    if did:
        for fn in files:
            if fn.startswith(did) and fn.lower().endswith(".bin"):
                bin_path = os.path.join(doc_dir, fn)
                break
        for fn in files:
            if fn.startswith(did) and fn.lower().endswith("_meta.json"):
                meta_path = os.path.join(doc_dir, fn)
                break

    # 2) fallback
    if not bin_path:
        for fn in files:
            if fn.lower().endswith(".bin"):
                bin_path = os.path.join(doc_dir, fn)
                break
    if not meta_path:
        for fn in files:
            if fn.lower().endswith("_meta.json"):
                meta_path = os.path.join(doc_dir, fn)
                break

    return bin_path, meta_path


def _rel_from_abs(abs_path: str) -> str:
    """
    abs_path 를 D:\eink_docs\{user}\ 기준 relpath로 변환
    """
    base = _user_root_dir()
    ap = os.path.normpath(abs_path)
    bb = os.path.normpath(base)
    if ap.startswith(bb):
        rel = ap[len(bb):].lstrip("\\/")
        return rel.replace(os.sep, "/")
    return abs_path.replace(os.sep, "/")


def _mysql_nulls_last_order_for_datetime(col, desc: bool = True):
    """
    MySQL에는 NULLS LAST 문법이 없어서 CASE로 대체
    - NULL이면 1, 아니면 0 → (0 먼저)로 정렬하면 NULL이 뒤로 감
    """
    null_rank = case((col.is_(None), 1), else_=0)
    return (null_rank.asc(), col.desc() if desc else col.asc())


def _pick_current_and_next_posting_mysql(
    user_id: int,
    device_id: str,
    now: Optional[datetime] = None
) -> Tuple[Optional[EInkPosting], Optional[EInkPosting]]:
    """
    RepositoryEDevice의 NULLS LAST 문제를 피하기 위해 dashboard에서는 자체 pick 사용.
    """
    if now is None:
        now = _kst_now_naive()

    # current: now window 포함
    cur_q = (
        EInkPosting.query
        .filter_by(user_id=user_id, device_id=device_id)
        .filter(EInkPosting.status.in_(["active", "scheduled"]))
        .filter(or_(EInkPosting.start_time.is_(None), EInkPosting.start_time <= now))
        .filter(or_(EInkPosting.end_time.is_(None), now < EInkPosting.end_time))
    )

    # start_time DESC, NULLS LAST 대체
    o1 = _mysql_nulls_last_order_for_datetime(EInkPosting.start_time, desc=True)
    if hasattr(EInkPosting, "priority"):
        cur_q = cur_q.order_by(*o1, EInkPosting.priority.asc(), EInkPosting.id.desc())
    else:
        cur_q = cur_q.order_by(*o1, EInkPosting.id.desc())

    cur = cur_q.first()

    # next: now 이후 scheduled 중 가장 빠른 것
    nxt_q = (
        EInkPosting.query
        .filter_by(user_id=user_id, device_id=device_id, status="wait")
        .filter(EInkPosting.start_time.isnot(None))
        .filter(EInkPosting.start_time > now)
    )
    if hasattr(EInkPosting, "priority"):
        nxt_q = nxt_q.order_by(EInkPosting.start_time.asc(), EInkPosting.priority.asc(), EInkPosting.id.asc())
    else:
        nxt_q = nxt_q.order_by(EInkPosting.start_time.asc(), EInkPosting.id.asc())

    nxt = nxt_q.first()
    return cur, nxt


def _pack_posting_for_board(p: Optional[EInkPosting]) -> Optional[dict]:
    if not p:
        return None
    a = getattr(p, "asset", None)
    if not a:
        return None

    # preview_url: onelayer.bmp (가능하면 doc preview 우선)
    preview_url = None
    doc_id = getattr(a, "document_info_id", None)
    if doc_id:
        preview_url = f"/dashboard/preview/doc/{int(doc_id)}"
    else:
        preview_url = f"/dashboard/preview/asset/{a.id}"

    return {
        "posting_id": p.id,
        "asset_id": a.id,
        "doc_id": doc_id,
        "title": getattr(a, "title", None) or (f"asset#{a.id}"),
        "ver": getattr(a, "ver", None),
        "crc32": getattr(a, "crc32_le", None),
        "preview_url": preview_url,
        "start_time": p.start_time.isoformat(timespec="minutes") if p.start_time else None,
        "end_time": p.end_time.isoformat(timespec="minutes") if p.end_time else None,
        "status": p.status,
    }


# ─────────────────────────────────────────────────────────────
# 0) Pages
# ─────────────────────────────────────────────────────────────
@bp.get("/upload")
@login_required
def eink_upload_page_redirect():
    """
    /dashboard/upload 로 들어오면 첫 디바이스로 리다이렉트
    """
    dev = (
        EInkDevice.query
        .filter(EInkDevice.user_no == current_user.no)
        .order_by(EInkDevice.device_id.asc())
        .first()
    )
    if not dev:
        abort(404, "No devices")
    return redirect(f"/dashboard/device/{dev.device_id}")


@bp.get("/device/<device_id>")
@login_required
def eink_upload_device_page(device_id: str):
    """
    디바이스별 업로드/선택/프리뷰 페이지
    - 템플릿: bulletinboard/e_file_upload.html (형이 만든 새 버전)
    """
    device_id = _safe_device_id(device_id)
    _dbg("page:device", user_no=current_user.no, device_id=device_id)

    devs = (
        EInkDevice.query
        .filter(EInkDevice.user_no == current_user.no)
        .order_by(EInkDevice.device_id.asc())
        .all()
    )
    if not devs:
        abort(404, "No devices")

    # 접근 디바이스가 내 소유인지 확인
    ok = any(d.device_id == device_id for d in devs)
    if not ok:
        abort(404)

    return render_template(
        "bulletinboard/e_file_upload.html",
        devices=devs,
        device_id=device_id,
    )


@bp.get("/presentation")
@login_required
def eink_presentation_page():
    devs = (
        EInkDevice.query
        .filter(EInkDevice.user_no == current_user.no)
        .order_by(EInkDevice.device_id.asc())
        .all()
    )
    return render_template(
        "bulletinboard/e_dashboard_presentation.html",
        devices=devs
    )


# ─────────────────────────────────────────────────────────────
# 1) Docs API (DocumentInfo 기반)  ✅ 프론트 /dashboard/docs
# ─────────────────────────────────────────────────────────────
@bp.get("/docs")
@login_required
def docs_list():
    t0 = time.perf_counter()

    device_id = _safe_device_id((request.args.get("device_id") or "").strip())
    channel = (request.args.get("channel") or "approved").strip()
    q = (request.args.get("q") or "").strip()
    sort = (request.args.get("sort") or "newest").strip()

    page = max(1, _parse_int(request.args.get("page"), 1))
    limit = min(50, max(1, _parse_int(request.args.get("limit"), 10)))
    offset = (page - 1) * limit

    if channel == "bulletin":
        want_status = "bulletin_files"
    else:
        want_status = "approved"
        channel = "approved"

    _dbg("docs:start",
         user_no=current_user.no, device_id=device_id,
         channel=channel, want_status=want_status,
         q=q, sort=sort, page=page, limit=limit)

    # device 존재 확인(페이지에서 이미 들어오지만 API도 보호)
    dev = (
        EInkDevice.query
        .filter_by(user_no=current_user.no, device_id=device_id)
        .first()
    )
    if not dev:
        return jsonify({"items": [], "has_next": False})

    # DocumentInfo 조회
    dq = (
        DocumentInfo.query
        .filter(DocumentInfo.user_id == current_user.no)
        .filter(DocumentInfo.status == want_status)
    )

    if q:
        # orig_filename 검색(컬럼명이 다르면 여기만 바꾸면 됨)
        if hasattr(DocumentInfo, "orig_filename"):
            dq = dq.filter(DocumentInfo.orig_filename.like(f"%{q}%"))
        elif hasattr(DocumentInfo, "original_filename"):
            dq = dq.filter(DocumentInfo.original_filename.like(f"%{q}%"))

    # 정렬
    if sort == "name":
        if hasattr(DocumentInfo, "orig_filename"):
            dq = dq.order_by(DocumentInfo.orig_filename.asc(), DocumentInfo.id.desc())
        else:
            dq = dq.order_by(DocumentInfo.id.desc())
    elif sort == "oldest":
        if hasattr(DocumentInfo, "created_at"):
            dq = dq.order_by(DocumentInfo.created_at.asc(), DocumentInfo.id.asc())
        else:
            dq = dq.order_by(DocumentInfo.id.asc())
    else:  # newest
        if hasattr(DocumentInfo, "created_at"):
            dq = dq.order_by(DocumentInfo.created_at.desc(), DocumentInfo.id.desc())
        else:
            dq = dq.order_by(DocumentInfo.id.desc())

    rows = dq.offset(offset).limit(limit + 1).all()
    has_next = len(rows) > limit
    rows = rows[:limit]

    items = []
    for d in rows:
        doc_id = d.id
        orig = getattr(d, "orig_filename", None) or getattr(d, "original_filename", None) or "-"
        stored_path = getattr(d, "stored_path", None) or getattr(d, "file_path", None) or ""

        created_at = getattr(d, "created_at", None) or getattr(d, "updated_at", None)
        approved_at = getattr(d, "approved_at", None) or getattr(d, "final_approved_at", None)

        # 게시기간 문자열(있는 컬럼만)
        post_start = getattr(d, "post_start_time", None) or getattr(d, "start_time", None)
        post_end = getattr(d, "post_end_time", None) or getattr(d, "end_time", None)
        if post_start or post_end:
            ps = post_start.strftime("%Y-%m-%d %H:%M") if post_start else "-"
            pe = post_end.strftime("%Y-%m-%d %H:%M") if post_end else "-"
            post_period = f"{ps} ~ {pe}"
        else:
            post_period = "-"

        items.append({
            "id": doc_id,
            "orig_filename": orig,
            "stored_path": stored_path,
            "created_at": created_at.isoformat(timespec="minutes") if created_at else None,
            "approved_at": approved_at.isoformat(timespec="minutes") if approved_at else None,
            "post_period": post_period,
            "preview_url": f"/dashboard/preview/doc/{doc_id}",
        })

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    _dbg("docs:done", count=len(items), has_next=has_next, elapsed_ms=elapsed_ms)

    return jsonify({"items": items, "has_next": has_next})


# ─────────────────────────────────────────────────────────────
# 2) Preview: DocumentInfo (onelayer.bmp) ✅ /dashboard/preview/doc/<id>
# ─────────────────────────────────────────────────────────────
@bp.get("/preview/doc/<int:doc_id>")
@login_required
def preview_doc_onelayer(doc_id: int):
    t0 = time.perf_counter()

    d = (
        DocumentInfo.query
        .filter(DocumentInfo.id == doc_id, DocumentInfo.user_id == current_user.no)
        .first_or_404()
    )

    doc_status = getattr(d, "status", "") or ""
    doc_dir = _doc_base_dir_by_status(doc_status, doc_id)
    bmp_path = _find_onelayer_bmp(doc_dir)

    _dbg("preview_doc",
         doc_id=doc_id, status=doc_status,
         doc_dir=doc_dir, bmp_path=bmp_path)

    if not bmp_path or not os.path.exists(bmp_path):
        abort(404)

    resp = send_file(bmp_path, mimetype="image/bmp", as_attachment=False)
    resp.headers["Cache-Control"] = "no-store"
    _dbg("preview_doc:done", doc_id=doc_id, elapsed_ms=int((time.perf_counter() - t0) * 1000))
    return resp


# ─────────────────────────────────────────────────────────────
# 3) Preview: Asset (fallback) ✅ /dashboard/preview/asset/<id>
# ─────────────────────────────────────────────────────────────
@bp.get("/preview/asset/<int:asset_id>")
@login_required
def preview_asset_onelayer(asset_id: int):
    t0 = time.perf_counter()
    a = (
        EInkAsset.query
        .filter(EInkAsset.id == asset_id, EInkAsset.user_id == current_user.no)
        .first_or_404()
    )

    # 1) doc 연결되어 있으면 doc 프리뷰 우선
    doc_id = getattr(a, "document_info_id", None)
    if doc_id:
        return redirect(f"/dashboard/preview/doc/{int(doc_id)}")

    # 2) asset.meta_json or preview_relpath로 탐색
    rel = (getattr(a, "preview_relpath", None) or "").strip()
    if not rel:
        meta = getattr(a, "meta_json", None) or {}
        rel = (meta.get("preview_relpath") or "").strip()

    if not rel:
        # meta_relpath 폴더에서 onelayer.bmp 찾기 시도
        meta_rel = (getattr(a, "meta_relpath", None) or "").strip()
        if meta_rel:
            meta_abs = _abs_from_rel(meta_rel)
            base_dir = os.path.dirname(meta_abs)
            bmp_path = _find_onelayer_bmp(base_dir)
            if bmp_path and os.path.exists(bmp_path):
                resp = send_file(bmp_path, mimetype="image/bmp", as_attachment=False)
                resp.headers["Cache-Control"] = "no-store"
                _dbg("preview_asset:done", asset_id=asset_id, elapsed_ms=int((time.perf_counter() - t0) * 1000))
                return resp
        abort(404)

    abs_path = _abs_from_rel(rel)
    _dbg("preview_asset", asset_id=asset_id, rel=rel, abs_path=abs_path)

    if not os.path.exists(abs_path):
        abort(404)

    resp = send_file(abs_path, mimetype="image/bmp", as_attachment=False)
    resp.headers["Cache-Control"] = "no-store"
    _dbg("preview_asset:done", asset_id=asset_id, elapsed_ms=int((time.perf_counter() - t0) * 1000))
    return resp


# ─────────────────────────────────────────────────────────────
# 4) Board API (single) ✅ 프론트: /dashboard/board?device_id=E01
#    - RepositoryEDevice 대신 MySQL-safe pick 사용
# ─────────────────────────────────────────────────────────────
@bp.get("/board")
@login_required
def eink_board_single():
    t0 = time.perf_counter()
    now = _kst_now_naive()

    device_id = _safe_device_id((request.args.get("device_id") or "").strip())
    if not device_id:
        return jsonify({"current": None, "next": None})

    dev = (
        EInkDevice.query
        .filter_by(user_no=current_user.no, device_id=device_id)
        .first()
    )
    if not dev:
        return jsonify({"current": None, "next": None})

    cur, nxt = _pick_current_and_next_posting_mysql(current_user.no, device_id, now)

    payload = {
        "server_time": now.isoformat(timespec="seconds"),
        "device_id": device_id,
        "current": _pack_posting_for_board(cur),
        "next": _pack_posting_for_board(nxt),
    }

    _dbg("board_single:done", device_id=device_id, elapsed_ms=int((time.perf_counter() - t0) * 1000))
    return jsonify(payload)


# ─────────────────────────────────────────────────────────────
# 5) Presentation Board (all devices) ✅ /dashboard/presentation_board
# ─────────────────────────────────────────────────────────────
@bp.get("/presentation_board")
@login_required
def eink_presentation_board():
    t0 = time.perf_counter()
    now = _kst_now_naive()

    devs = (
        EInkDevice.query
        .filter(EInkDevice.user_no == current_user.no)
        .order_by(EInkDevice.device_id.asc())
        .all()
    )

    devices = {}
    for d in devs:
        cur, _ = _pick_current_and_next_posting_mysql(current_user.no, d.device_id, now)
        devices[d.device_id] = {"current": _pack_posting_for_board(cur)}

    _dbg("presentation_board:done", count=len(devs), elapsed_ms=int((time.perf_counter() - t0) * 1000))
    return jsonify({"server_time": now.isoformat(timespec="seconds"), "devices": devices})


# ─────────────────────────────────────────────────────────────
# 6) Upload selected list ✅ /dashboard/upload/list
#    - "업로드로 선택된 항목"은 posting 히스토리로 보여주기
# ─────────────────────────────────────────────────────────────
@bp.get("/upload/list")
@login_required
def upload_selected_list():
    t0 = time.perf_counter()

    device_id = _safe_device_id((request.args.get("device_id") or "").strip())
    page = max(1, _parse_int(request.args.get("page"), 1))
    limit = min(50, max(1, _parse_int(request.args.get("limit"), 10)))
    offset = (page - 1) * limit

    if not device_id:
        return jsonify({"items": [], "has_next": False})

    q = (
        EInkPosting.query
        .filter_by(user_id=current_user.no, device_id=device_id)
        .order_by(EInkPosting.created_at.desc(), EInkPosting.id.desc())
    )

    rows = q.offset(offset).limit(limit + 1).all()
    has_next = len(rows) > limit
    rows = rows[:limit]

    items = []
    for p in rows:
        a = getattr(p, "asset", None)
        if not a:
            continue

        doc_id = getattr(a, "document_info_id", None)
        orig = None
        if doc_id:
            doc = DocumentInfo.query.filter(DocumentInfo.id == doc_id, DocumentInfo.user_id == current_user.no).first()
            if doc:
                orig = getattr(doc, "orig_filename", None) or getattr(doc, "original_filename", None)

        preview_url = f"/dashboard/preview/doc/{int(doc_id)}" if doc_id else f"/dashboard/preview/asset/{a.id}"

        items.append({
            "id": int(doc_id) if doc_id else int(a.id),
            "orig_filename": orig or getattr(a, "title", None) or f"asset#{a.id}",
            "selected_at": p.created_at.isoformat(timespec="minutes") if p.created_at else None,
            "status": p.status,
            "preview_url": preview_url,
        })

    _dbg("upload_list:done", device_id=device_id, count=len(items), elapsed_ms=int((time.perf_counter() - t0) * 1000))
    return jsonify({"items": items, "has_next": has_next})


# ─────────────────────────────────────────────────────────────
# 7) Upload select ✅ /dashboard/upload/select
#    - docs에서 선택한 DocumentInfo를 "현재 표시"로 만들기
#    - 구현: doc_dir에서 (bin, meta.json) 읽고 EInkAsset 생성/재사용 → posting activate
# ─────────────────────────────────────────────────────────────

@bp.post("/upload/select")
@login_required
def upload_select_doc():
    t0 = time.perf_counter()
    data = request.get_json(silent=True) or {}

    device_id = _safe_device_id((data.get("device_id") or "").strip())
    doc_id = data.get("doc_id")
    channel = (data.get("channel") or "approved").strip().lower()

    if channel == "bulletin":
        want_status = "bulletin_files"
    else:
        want_status = "approved"
        channel = "approved"

    _dbg("upload_select:start", device_id=device_id, doc_id=doc_id, channel=channel)

    if not device_id or not isinstance(doc_id, int):
        return jsonify({"ok": False, "reason": "bad_request"}), 400

    dev = EInkDevice.query.filter_by(user_no=current_user.no, device_id=device_id).first()
    if not dev:
        return jsonify({"ok": False, "reason": "device_not_found"}), 404

    doc = (DocumentInfo.query
        .filter(DocumentInfo.id == doc_id, DocumentInfo.user_id == current_user.no)
        .first())
    if not doc or getattr(doc, "status", None) != want_status:
        return jsonify({"ok": False, "reason": "doc_not_allowed"}), 403

    # doc payload 위치
    doc_dir = _doc_base_dir_by_status(want_status, doc_id)
    bin_abs, meta_abs = _find_doc_payload_files(doc_dir, device_id)
    if not bin_abs or not meta_abs:
        _dbg("upload_select:payload_missing", doc_dir=doc_dir, bin_abs=bin_abs, meta_abs=meta_abs)
        return jsonify({"ok": False, "reason": "payload_missing"}), 404

    # meta 읽기
    try:
        with open(meta_abs, "r", encoding="utf-8") as f:
            meta = json.load(f)
    except Exception as e:
        _dbg("upload_select:meta_read_fail", meta_abs=meta_abs, err=str(e))
        return jsonify({"ok": False, "reason": "meta_read_fail"}), 500

    width = int(meta.get("width") or 0)
    height = int(meta.get("height") or 0)
    mode = str(meta.get("mode") or "BWRYBG")
    packing = str(meta.get("packing") or meta.get("packing_mode") or "4bpp")
    try:
        bpp = int("".join([c for c in packing if c.isdigit()]) or 4)
    except Exception:
        bpp = 4

    ver = int(meta.get("ver") or int(time.time()))
    raw_len = int(meta.get("raw_len") or 0)
    total_len = int(meta.get("total_len") or 0)
    crc32 = str(meta.get("crc32") or "").lower()

    bin_rel = _rel_from_abs(bin_abs)
    meta_rel = _rel_from_abs(meta_abs)

    # 1) Asset upsert (콘텐츠)
    asset = (EInkAsset.query
        .filter_by(user_id=current_user.no, device_id=device_id, ver=ver)
        .first())

    now = _kst_now_naive()

    if not asset:
        asset = EInkAsset(
            user_id=current_user.no,
            device_id=device_id,
            document_info_id=doc_id,
            channel=channel,
            width=width, height=height, mode=mode, bpp=bpp, ver=ver,
            uuid=str(uuid.uuid4()),
            bin_relpath=bin_rel,
            meta_relpath=meta_rel,
            raw_len=raw_len,
            total_len=total_len,
            crc32_le=crc32,
            meta_json=meta,
            need_approval=(want_status == "approved"),
            final_approval=True,
            approval_snapshot_json=getattr(doc, "approval_snapshot_json", None) if hasattr(doc, "approval_snapshot_json") else None,
        )
        db.session.add(asset)
        db.session.flush()
    else:
        # 최신 문서/경로/메타만 갱신
        asset.document_info_id = doc_id
        asset.channel = channel
        asset.meta_json = meta
        asset.bin_relpath = bin_rel
        asset.meta_relpath = meta_rel
        asset.updated_at = now

    # 2) Schedule 파싱 → Posting wait enqueue
    schedule = data.get("schedule") or {}
    enabled = bool(schedule.get("enabled"))

    start_mode = (schedule.get("start_mode") or "now").strip().lower()
    period_sec = int(schedule.get("posting_period_time") or 0) if enabled else 0
    if enabled:
        period_sec = max(60, period_sec)
    else:
        # 스케줄 OFF 정책: "즉시 게시, 무기한" (end_time=None)
        period_sec = 0

    # tail = max(active end_time, wait end_time). active end_time이 None이면 tail로 막지 않음(= preempt 허용)
    mx_wait = (db.session.query(func.max(EInkPosting.end_time))
        .filter(EInkPosting.user_id == current_user.no,
                EInkPosting.device_id == device_id,
                EInkPosting.status == "wait",
                EInkPosting.end_time.isnot(None),
                EInkPosting.end_time > now)
        .scalar())
    mx_active = (db.session.query(func.max(EInkPosting.end_time))
        .filter(EInkPosting.user_id == current_user.no,
                EInkPosting.device_id == device_id,
                EInkPosting.status == "active",
                EInkPosting.end_time.isnot(None),
                EInkPosting.end_time > now)
        .scalar())
    tail = mx_wait
    if mx_active and (tail is None or mx_active > tail):
        tail = mx_active

    # expect 계산
    expect = None
    if not enabled:
        expect = now
    else:
        if start_mode == "at":
            user_expect = R._parse_expect(schedule.get("expect_post_time"))
            if not user_expect:
                return jsonify({"ok": False, "reason": "bad_expect_post_time"}), 400
            expect = user_expect
        else:
            expect = now

        # ✅ 겹치면 자동으로 뒤로 밀기(shift)
        if tail and expect < tail:
            expect = tail

    expire = None
    if enabled:
        expire = expect + timedelta(seconds=period_sec)

    # (옵션) asset에도 snapshot로 남겨두기(디버그/추적)
    asset.expect_post_time = expect
    asset.posting_period_sec = period_sec if enabled else None
    asset.expire_time = expire

    # Posting enqueue (wait)
    p = EInkPosting(
        user_id=current_user.no,
        device_id=device_id,
        asset_id=asset.id,
        status="wait",
        start_time=expect,
        end_time=expire,
        priority=10,
        reason=f"upload_select:{channel}:{'off' if not enabled else start_mode}",
    )
    db.session.add(p)
    db.session.commit()

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    _dbg("upload_select:done",
         device_id=device_id, doc_id=doc_id, asset_id=asset.id, posting_id=p.id,
         expect=_fmt_dt(expect), expire=_fmt_dt(expire), elapsed_ms=elapsed_ms)

    return jsonify({
        "ok": True,
        "asset_id": asset.id,
        "posting_id": p.id,
        "expect_post_time": _fmt_dt(expect),
        "expire_time": _fmt_dt(expire),
    })



@bp.get("/boards")
@login_required
def api_boards():
    """
    GET /dashboard/boards?building_id=2&floor_no=2
    -> {items:[{board_no, board_code}], default_board_no}
    """
    t0 = time.perf_counter()
    building_id = int(request.args.get("building_id") or 0)
    floor_no = int(request.args.get("floor_no") or 0)

    items, default_board_no = R.list_boards(building_id=building_id, floor_no=floor_no)

    # debug log (device_access_logs)
    try:
        R.log_access(   
            user_id=current_user.no,
            device_id="",  # boards는 device가 없을 수 있음
            api="dashboard.boards",
            ok=True,
            http_status=200,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
            error_msg=None,
        )
    except Exception:
        pass

    return jsonify({"items": items, "default_board_no": int(default_board_no)})

@bp.get("/board_devices")
@login_required
def api_board_devices():
    """
    GET /dashboard/board_devices?building_id=2&floor_no=2&board_no=1
    -> {items:[{device_id,panel_res,device_name}]}
    """
    building_id = int(request.args.get("building_id") or 0)
    floor_no = int(request.args.get("floor_no") or 0)
    board_no = int(request.args.get("board_no") or 0)

    items = R.list_devices_by_board(
        user_id=current_user.no,
        building_id=building_id,
        floor_no=floor_no,
        board_no=board_no
    )
    return jsonify({"items": items})



@bp.get("/schedule/list")
@login_required
def api_schedule_list():
    """
    GET /dashboard/schedule/list?device_id=...
    -> {active_expire_time, items:[...]}
    """
    t0 = time.perf_counter()
    device_id = _safe_device_id((request.args.get("device_id") or "").strip())
    if not device_id:
        return jsonify({"active_expire_time": None, "items": []})

    out = R.schedule_list(user_id=current_user.no, device_id=device_id)

    try:
        R.log_access(   
            user_id=current_user.no,
            device_id=device_id,
            api="dashboard.schedule_list",
            ok=True,
            http_status=200,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
            error_msg=None,
        )
    except Exception:
        pass

    return jsonify(out)


@bp.post("/schedule/reorder")
@login_required
def api_schedule_reorder():
    """
    POST /dashboard/schedule/reorder
    body: {device_id, items:[{asset_id, expect_post_time, posting_period_time}]}
    -> {device_id, items:[...]}
    """
    t0 = time.perf_counter()
    data = request.get_json(silent=True) or {}
    device_id = _safe_device_id((data.get("device_id") or "").strip())
    items = data.get("items") or []
    if not device_id or not isinstance(items, list):
        return jsonify({"ok": False, "reason": "bad_request"}), 400
    
    current_app.logger.debug(f"리오더: {items}")

    out = R.schedule_reorder(
        user_id=current_user.no,
        device_id=device_id,
        items=items,
    )

    try:
        R.log_access(   
            user_id=current_user.no,
            device_id=device_id,
            api="dashboard.schedule_reorder",
            ok=True,
            http_status=200,
            elapsed_ms=int((time.perf_counter() - t0) * 1000),
            error_msg=None,
        )
    except Exception:
        pass

    return jsonify(out)


@bp.route("/schedule/status", methods=["POST"])
@login_required
def schedule_status_patch():
    """
    (요구사항 2)
    wait/active 상태의 posting을 expired로 변경(배치 지원)

    요청:
    {
      "device_id": "DEV001",
      "items": [
        {"asset_id": 123, "status": "expired"},
        {"asset_id": 124, "status": "expired"}
      ]
    }
    """
    body = request.get_json(silent=True) or {}
    device_id = (body.get("device_id") or "").strip()
    items = body.get("items") or []
    if not device_id:
        return jsonify({"ok": False, "reason": "device_id required"}), 400

    # status는 현재는 expired만 허용(요구사항)
    changes = []
    for it in items:
        if not isinstance(it, dict):
            continue
        asset_id = it.get("asset_id")
        stt = (it.get("status") or "").strip().lower()
        if not asset_id:
            continue
        if stt != "expired":
            continue
        changes.append(int(asset_id))

    if not changes:
        return jsonify({"ok": True, "changed": 0})

 
    # current_app.logger.debug(f"user_id ={current_user.no}, device_id= { device_id}, asset_ids= {changes}")
    out = R.schedule_set_expired(
        user_id=current_user.no,
        device_id=device_id,
        asset_ids=changes,
        now=_kst_now_naive()
    )
    return jsonify(out)

@bp.post("/device/log")
@login_required
def api_device_log():
    data = request.get_json(silent=True) or {}
    device_id = _safe_device_id((data.get("device_id") or "").strip())

    # 실패해도 기능에 영향 없게 "항상 OK" 형태 추천
    try:
        R.log_access(
            user_id=current_user.no,
            device_id=device_id or "",
            api=str(data.get("api") or "client.log"),
            ok=bool(data.get("ok", True)),
            http_status=int(data.get("http_status") or 200),
            elapsed_ms=int(data.get("elapsed_ms") or 0),
            error_msg=(data.get("error_msg") or None),
        )
    except Exception:
        pass

    return jsonify({"ok": True})