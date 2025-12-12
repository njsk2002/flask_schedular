# controllers/bulletin_controller.py
import os, json, time, tempfile
from datetime import datetime
from io import BytesIO
from flask import (
    Blueprint, request, send_file, jsonify, abort,
    render_template, current_app, url_for, g, session
)

from ..service.file_management import (
    # dirs & engine
    get_upload_store, get_layer_store, next_upload_id, get_translation_service,
    ensure_asset_dirs, get_asset_dirs,

    # utils
    dbg, dump_json, req_info,

    # user/route/paths
    current_user_id, current_user_ids, safe_device_id,
    decide_target_dir, asset_paths, default_devices, default_routes,

    # layers/composite
    bind_sign_layer_user, log_layers_summary, apply_layers_to_image,
    composite_sign_on_slot, load_sign_image_for_current,

    # render/save
    place_into_canvas_and_quantize, image_to_payload,
    save_meta_bundle, render_preview_png, render_flat_image,

    # draft/direct
    save_draft_bundle,

    # move/find
    move_bundle, snapshot_to_signlayout_args, find_latest_pending_for_user,

    # tmp
    LAYER_TMP_DIR,
)

try:
    from ..repository.repository_eink import RepositoryEINK
except Exception:
    RepositoryEINK = None

bp = Blueprint("bulletin", __name__, url_prefix="/bulletin")

# 요청 단위로 디렉터리 보장
@bp.before_request
def _ensure_dirs():
    ensure_asset_dirs()

# ===== 템플릿 =====
@bp.route('/fileview', methods=['GET', 'POST'])
def file_view():
    dbg("file_view:req", **req_info())
    devices = default_devices()
    try:
        if RepositoryEINK is not None:
            devices = RepositoryEINK.get_devices_for_dashboard() or devices
            approval_routes = RepositoryEINK.get_approval_routes() or default_routes()
        else:
            approval_routes = default_routes()
    except Exception:
        current_app.logger.debug("[file_view] Repository fetch failed", exc_info=True)
        approval_routes = default_routes()

    uid = current_user_id()
    current_user = {"no": uid, "name": getattr(getattr(g, "user", None), "username", None) or "Guest"}

    return render_template(
        'bulletinboard/e_file_draft.html',
        devices=devices, current_user=current_user, approval_routes=approval_routes
    )

@bp.route('/bmpview', methods=['GET', 'POST'])
def bmp_view():
    t0 = time.time()
    dbg("bmp_view:req", **req_info())

    devices = default_devices()
    try:
        if RepositoryEINK is not None:
            devices = RepositoryEINK.get_devices_for_dashboard() or devices
            approval_routes = RepositoryEINK.get_approval_routes() or default_routes()
        else:
            approval_routes = default_routes()
    except Exception as e:
        current_app.logger.debug("[file_view] Repository fetch failed", exc_info=True)
        approval_routes = default_routes()

    uid = current_user_id()
    current_user = {
        "no": uid,
        "name": getattr(getattr(g, "user", None), "username", None) or "Guest",
    }

    dbg("file_view:context",
         devices=len(devices),
         routes=len(approval_routes),
         current_user= dump_json(current_user))

    resp = render_template(
        'bulletinboard/e_file_select.html',
        devices=devices,
        current_user=current_user,
        approval_routes=approval_routes
    )
    dbg("file_view:done", ms=int((time.time()-t0)*1000))
    return resp

# ===== 라우트 데이터 =====
@bp.route("/routes/list", methods=["GET"])
def routes_list():
    try:
        routes = RepositoryEINK.get_approval_routes() if RepositoryEINK is not None else default_routes()
        routes = routes or default_routes()
    except Exception:
        current_app.logger.debug("[routes_list] Repository error", exc_info=True)
        routes = default_routes()
    return jsonify({"routes": routes})

@bp.route("/departments", methods=["GET"])
def list_departments():
    try:
        if RepositoryEINK is None: return jsonify({"departments": []})
        depts = RepositoryEINK.list_departments() or []
        return jsonify({"departments": depts})
    except Exception:
        current_app.logger.debug("[departments] failed", exc_info=True)
        return jsonify({"departments": []})

@bp.route("/users", methods=["GET"])
def list_users_by_department():
    dept = request.args.get("department")
    try:
        if RepositoryEINK is None: return jsonify({"users": []})
        users = RepositoryEINK.list_users_by_department(dept) or []
        return jsonify({"users": users})
    except Exception:
        current_app.logger.debug("[users] failed", exc_info=True)
        return jsonify({"users": []})

# ===== 미리보기 =====
@bp.route("/preview_blob", methods=["POST"])
def preview_blob():
    created_id = None
    layers = []
    UPLOADS = get_upload_store()
    svc = get_translation_service()

    if request.mimetype and "multipart/form-data" in request.mimetype:
        f = request.files.get("file")
        if not f: abort(400, "file missing")
        suffix = os.path.splitext(f.filename or "")[1].lower() or ".bin"
        tmpdir = os.path.join(tempfile.gettempdir(), "eink_uploads"); os.makedirs(tmpdir, exist_ok=True)
        upload_id = next_upload_id()
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
        try:
            layers = json.loads(request.form.get("layers") or "[]")
        except Exception:
            layers = []
    else:
        js = request.get_json(silent=True) or {}
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
            abort(400, f"bad body: {e}")

    layers = bind_sign_layer_user(layers, current_user_id())
    log_layers_summary(layers, where="preview_blob")

    png = render_preview_png(
        svc=svc, upload_id=upload_id,
        width=width, height=height, mode=mode, scale=scale, percent=percent, rotate=rotate,
        raw=bool(raw), layers=layers
    )
    resp = send_file(png, mimetype="image/png")
    if created_id is not None: resp.headers["X-Upload-Id"] = str(created_id)
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

# ===== 전송/배포 =====
@bp.route("/sendfile", methods=["POST"])
def send_file_route():
    js = request.get_json(silent=True) or {}
    svc = get_translation_service()
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
        layers    = js.get("layers") or js.get("editor_layers") or []
        need_approval  = bool(js.get("need_approval", js.get("use_approval", True)))
        final_approval = bool(js.get("final_approval", False))
        route_id       = js.get("route_id")
        assignees      = js.get("assignees") or {}
        layout_snapshot= js.get("layout_snapshot") or {}
    except Exception as e:
        abort(400, f"bad body: {e}")

    if (width, height) == (480, 800):
        width, height = 800, 480

    layers = bind_sign_layer_user(layers, current_user_id())
    log_layers_summary(layers, where="send_file")

    im_proc, fmt = place_into_canvas_and_quantize(
        svc=svc, upload_id=upload_id, page=page,
        width=width, height=height, scale=scale, percent=percent, rotate=rotate, mode=mode, layers=layers
    )

    target_dir = decide_target_dir(need_approval=need_approval, final_approval=final_approval)
    bmp_path, meta_path, hdr_path, bin_path = asset_paths(device_id, width, height, fmt, target_dir=target_dir)

    payload, meta = save_meta_bundle(
        im=im_proc, fmt=fmt, size=(width, height),
        bmp_path=bmp_path, bin_path=bin_path, meta_path=meta_path,
        device_id=device_id, target_dir=target_dir,
        need_approval=need_approval, final_approval=final_approval,
        route_id=route_id, assignees=assignees
    )

    # 업로드 임시 정리
    info = get_upload_store().pop(upload_id, None)
    if info:
        try:
            path = info.get("path")
            if path and os.path.isfile(path): os.remove(path)
        except Exception:
            current_app.logger.debug("[CLEANUP] temp delete failed", exc_info=True)

    # DB 저장(옵션) — 상태 매핑
    upload_row_id = None
    sign_layout_id = None
    if RepositoryEINK is not None:
        try:
            db_status = ("uploads" if target_dir == "uploads" else
             "approved" if target_dir == "approved" else
             "checked"  if target_dir == "checked"  else
             "in_review")
            orig_filename = info.get("name") if info else os.path.basename(bmp_path)
            upload_row_id = RepositoryEINK.create_upload_record(
                user_id=current_user_id(), device_id=device_id,
                orig_filename=orig_filename, stored_path=bmp_path,
                target_dir=target_dir, need_approval=need_approval, status=db_status,
                pages=1, width=width, height=height, mode=fmt,
                scale=scale, percent=percent, rotate=rotate,
                route_id=route_id, sign_layout_id=None,
                route_snapshot={"route_id": route_id, "assignees": assignees} if route_id else None,
                layout_snapshot=layout_snapshot if layout_snapshot else None,
                metadata={"assignees": assignees} if assignees else None,
            )
            args = snapshot_to_signlayout_args(layout_snapshot) if layout_snapshot else None
            if args:
                sign_layout_id = RepositoryEINK.insert_sign_layout(
                    name=f"Device {device_id} Snapshot",
                    owner_user_id=current_user_id(),
                    canvas_w=args["canvas_w"], canvas_h=args["canvas_h"],
                    parent_box=args["parent_box"],
                    tpl_json=args["tpl_json"], slots_json=args["slots_json"], layers_json=args["layers_json"],
                    version=1,
                )
        except Exception:
            current_app.logger.debug("[DB] save skipped", exc_info=True)

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

# ===== 레이어 업로드/서빙 =====
@bp.route("/layer_upload", methods=["POST"])
def layer_upload():
    if not (request.mimetype and "multipart/form-data" in request.mimetype):
        abort(400, "multipart/form-data required")
    f = request.files.get("file")
    if not f: abort(400, "file missing")
    ext = (os.path.splitext(f.filename or "")[1] or ".png").lower()
    if ext not in (".png", ".jpg", ".jpeg"): abort(400, "only .png/.jpg supported")
    token = f"{int(time.time()*1000)}_{os.path.basename(f.filename or 'layer')}"
    safe_token = "".join(ch for ch in token if ch.isalnum() or ch in "._-")[:128]
    out_path = os.path.join(LAYER_TMP_DIR, safe_token)
    f.save(out_path)
    get_layer_store()[safe_token] = {
        "path": out_path, "name": f.filename or safe_token,
        "mimetype": "image/png" if ext == ".png" else "image/jpeg"
    }
    return jsonify({"upload_token": safe_token,
                    "preview_url": url_for("bulletin.layer_img", token=safe_token)})

@bp.route("/layer_img/<path:token>", methods=["GET"])
def layer_img(token):
    info = get_layer_store().get(token)
    if not info or not os.path.isfile(info["path"]): abort(404)
    return send_file(info["path"], mimetype=info.get("mimetype", "image/png"))

# ===== 레이아웃 배치 저장 =====
@bp.route("/sign_layout/save_batch", methods=["POST"])
def save_layout_batch():
    js = request.get_json(silent=True) or {}
    items = js.get("items") or []
    results = []
    dirs = get_asset_dirs()
    for it in items:
        device_id = safe_device_id(it.get("device_id", "UNKNOWN"))
        layout = it.get("layout") or {}
        path = os.path.join(dirs["root"], f"layout_{device_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(layout, f, ensure_ascii=False, indent=2)
            results.append({"device_id": device_id, "saved": True, "path": path})
        except Exception as e:
            results.append({"device_id": device_id, "saved": False, "error": str(e)})
    return jsonify({"ok": True, "saved": results})

# ===== 결재 대기 알림/페이지/프리뷰/액션 =====
@bp.route("/approval/pending", methods=["GET"])
def approval_pending():
    user_no, userid = current_user_ids()
    if not userid: return jsonify({"has": False})
    item = find_latest_pending_for_user(userid)
    if not item: return jsonify({"has": False})
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
        "goto": url_for("bulletin.approval_page",
                        device_id=item.get("device_id"),
                        meta=item.get("meta_path"),
                        status=item.get("status"))
    })

@bp.route("/approval/page", methods=["GET"])
def approval_page():
    device_id = request.args.get("device_id")
    meta_path = request.args.get("meta")
    status = request.args.get("status")
    if not (device_id and meta_path and os.path.isfile(meta_path)): abort(404, "meta missing")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    stage = "review" if status == "in_review" else ("approve" if status == "checked" else "unknown")
    preview_url = url_for("bulletin.approval_preview", meta=meta_path)
    return render_template("bulletinboard/e_file_approval.html",
                           device_id=device_id, meta_path=meta_path,
                           preview_url=preview_url, status=status, stage=stage,
                           width=meta.get("width", 1200), height=meta.get("height", 1600),
                           mode=meta.get("mode", "BWRYBG"), assignees=meta.get("assignees") or {})

@bp.route("/approval/preview", methods=["GET"])
def approval_preview():
    meta_path = request.args.get("meta") or ""
    if not (meta_path and os.path.isfile(meta_path)): abort(404)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    bmp_dir = os.path.dirname(meta_path)
    bmp_file = meta.get("file")
    bmp_path = os.path.join(bmp_dir, bmp_file)
    if not os.path.isfile(bmp_path): abort(404)
    return send_file(bmp_path, mimetype="image/bmp")

@bp.route("/approval/act", methods=["POST"])
def approval_act():
    js = request.get_json(silent=True) or {}
    def _fail(code, msg): abort(code, msg)

    meta_path_raw = js.get("meta_path")
    action = (js.get("action") or "").lower()
    if action not in ("review", "approve", "reject"): _fail(400, "action invalid")
    meta_path = os.path.normpath(meta_path_raw) if meta_path_raw else None
    if not (meta_path and os.path.isfile(meta_path)): _fail(404, f"meta not found: {meta_path_raw}")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    device_id = meta.get("device_id")
    width  = int(meta.get("width", 1200))
    height = int(meta.get("height", 1600))
    fmt    = meta.get("mode", "BWRYBG")
    target_dir_meta = (meta.get("dir") or "").strip()
    status_meta     = (meta.get("status") or "").strip()
    bmp_dir  = os.path.dirname(meta_path)            # ← 메타가 있는 실제 디렉터리
    bmp_file = meta.get("file")
    if not bmp_file: _fail(400, "meta.file missing")
    bmp_path = os.path.join(bmp_dir, bmp_file)
    bin_path = os.path.join(bmp_dir, os.path.splitext(bmp_file)[0] + ".bin")
    if not os.path.isfile(bmp_path): _fail(404, f"bmp missing: {bmp_path}")

    # (핵심) 실제 파일의 사용자 루트를 기준으로 src/dst 디렉터리 구성
    user_root = os.path.dirname(bmp_dir)             # .../{in_review} 의 상위 = 사용자 루트
    actual_dir = os.path.basename(bmp_dir)           # 현재 단계(in_review | checked | approved)
    src_in_review = os.path.join(user_root, "in_review")
    src_checked   = os.path.join(user_root, "checked")
    dst_checked   = os.path.join(user_root, "checked")
    dst_approved  = os.path.join(user_root, "approved")

    target_dir = target_dir_meta or actual_dir
    if not status_meta:
        status_meta = {"in_review":"in_review","checked":"checked","uploads":"uploads","approved":"approved"}.get(actual_dir,"in_review")

    # 레이어 스냅샷 로드(필요 시) & 서명 합성
    layers = []
    if RepositoryEINK is not None:
        try:
            snap = RepositoryEINK.get_layout_snapshot_by_meta(meta_path)
            if isinstance(snap, dict):
                layers = (snap.get("layers") or []) if "layers" in snap else (snap.get("layout", {}).get("layers") or [])
        except Exception:
            pass
    sign_img = load_sign_image_for_current()
    if action in ("review", "approve") and sign_img is not None and layers:
        from PIL import Image
        im = Image.open(bmp_path).convert("RGB")
        role = "review" if action == "review" else "approve"
        im = composite_sign_on_slot(im, width, height, layers, role, sign_img)
        im.save(bmp_path, format="BMP")
        payload = image_to_payload(im, fmt, size=(width, height))
        with open(bin_path, "wb") as f: f.write(payload)
        raw_len   = len(payload) - 4
        crc32_le  = int.from_bytes(payload[-4:], "little", signed=False)
        meta.update({
            "raw_len": raw_len, "total_len": raw_len + 4,
            "crc32": f"{crc32_le:08x}",
            "ver": int(os.path.getmtime(bmp_path)),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })

    moved = []
    new_status = meta.get("status") or status_meta
    new_dir    = target_dir

    if action == "review":
        # in_review → checked
        if target_dir not in ("in_review",) and actual_dir not in ("in_review",):
            _fail(400, "not in review stage")
        moved = move_bundle(src_in_review, dst_checked, bmp_file)
        new_status, new_dir = "checked", "checked"

    elif action == "approve":
        # checked → approved
        if target_dir not in ("checked",) and actual_dir not in ("checked",):
            _fail(400, "not in approve stage")
        moved = move_bundle(src_checked, dst_approved, bmp_file)
        new_status, new_dir = "approved", "approved"

    elif action == "reject":
        new_status, new_dir = "rejected", target_dir

    # 새 메타 위치 기록
    new_meta_path = os.path.join(
        (dst_checked if new_dir == "checked" else dst_approved if new_dir == "approved" else bmp_dir),
        os.path.basename(meta_path)
    )

    meta["dir"] = new_dir
    meta["need_approval"] = meta.get("need_approval", True) if action != "approve" else False
    meta["final_approval"] = (action == "approve")
    meta["status"] = new_status
    try:
        with open(new_meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
    except Exception:
        current_app.logger.debug("[approval_act] meta rewrite failed", exc_info=True)

    # 레포지토리 업데이트(옵션): approved → updates 로 매핑
    if RepositoryEINK is not None:
        try:
            repo_dir = "updates" if new_dir == "approved" else new_dir
            RepositoryEINK.update_upload_status_by_meta(
                old_meta_path=new_meta_path, new_dir=repo_dir, new_status=new_status, note=js.get("note")
            )
        except Exception:
            current_app.logger.debug("[approval_act] DB update failed", exc_info=True)

    return jsonify({"ok": True, "moved": moved, "new_status": new_status, "new_dir": new_dir, "meta_path": new_meta_path})

@bp.route("/approval/advance", methods=["POST"])
def approval_advance():
    js = request.get_json(silent=True) or {}
    stage = (js.get("stage") or "").lower()
    file_param = js.get("file") or ""
    if stage not in ("review", "approve"): abort(400, "stage must be 'review' or 'approve'")
    base = file_param
    if base.endswith(".meta.json"): base = base[:-10] + ".bmp"
    elif not base.endswith(".bmp"): abort(400, "file must be .bmp or .meta.json")
    dirs = get_asset_dirs()
    src_dir = dirs["in_review" if stage == "review" else "checked"]
    dst_dir = dirs["checked" if stage == "review" else "approved"]
    moved = move_bundle(src_dir, dst_dir, base)
    if not moved: abort(404, f"no files moved (src={src_dir}, file={base})")
    return jsonify({"ok": True, "stage": stage, "moved": moved})

# ===== Routes =====
@bp.route("/approval/mark_checked", methods=["POST"])
def approval_mark_checked():
    try:
        session['approval_checked'] = True
        return jsonify({"ok": True})
    except Exception:
        current_app.logger.debug("[approval_mark_checked] failed", exc_info=True)
        return jsonify({"ok": False}), 500

# ===== 에디터: 드래프트/내보내기 =====
@bp.route("/save_draft", methods=["POST"])
def save_draft():
    svc = get_translation_service()
    js = request.get_json(silent=True) or {}
    upload_id = int(js.get("upload_id") or 0)
    device_id = js.get("device_id") or ""
    memo      = js.get("memo") or ""
    filename  = js.get("filename") or ""
    p         = js.get("params") or {}
    layers    = js.get("editor_layers") or []
    strategy  = (js.get("strategy") or "draft").lower()
    width  = int(p.get("width", 800)); height = int(p.get("height", 480))
    mode   = p.get("mode", "BWRYBG"); scale = p.get("scale", "fit")
    percent= int(p.get("percent", 100)); rotate = int(p.get("rotate", 0))
    layers = bind_sign_layer_user(layers, current_user_id())

    if strategy == "direct":
        saved = save_draft_bundle(
            svc=svc, upload_id=upload_id,
            width=width, height=height, mode=mode,
            scale=scale, percent=percent, rotate=rotate,
            layers=layers, user_id=current_user_id(),
            device_id=device_id, memo=memo, filename=filename
        )
        return jsonify({"ok": True, "strategy": "direct", **saved})

    # draft 스냅샷만 저장 (사용자 루트)
    dirs = get_asset_dirs()
    snap_dir = os.path.join(dirs["root"], "draft_snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    meta = {
        "upload_id": upload_id, "device_id": device_id, "filename": filename, "memo": memo,
        "params": {"width":width,"height":height,"mode":mode,"scale":scale,"percent":percent,"rotate":rotate},
        "layers": layers, "user_id": current_user_id(),
        "saved_at": datetime.now().isoformat(timespec="seconds")
    }
    out = os.path.join(snap_dir, f"draft_{int(time.time())}.json")
    with open(out, "w", encoding="utf-8") as f: json.dump(meta, f, ensure_ascii=False, indent=2)
    return jsonify({"ok": True, "strategy": "draft", "snapshot": out})

@bp.route("/editor_export", methods=["POST"])
def editor_export():
    svc = get_translation_service()
    js = request.get_json(silent=True) or {}
    upload_id = int(js.get("upload_id") or 0)
    layers    = js.get("layers") or js.get("editor_layers") or []
    width     = int(js.get("width", 800) or 800)
    height    = int(js.get("height", 480) or 480)
    mode      = js.get("mode", "BWRYBG")
    scale     = js.get("scale", "fit")
    percent   = int(js.get("percent", 100) or 100)
    rotate    = int(js.get("rotate", 0) or 0)
    layers = bind_sign_layer_user(layers, current_user_id())
    png_bio = render_flat_image(svc=svc, upload_id=upload_id, width=width, height=height,
                                scale=scale, percent=percent, rotate=rotate, layers=layers)
    fname = f"editor_export_{int(time.time())}.png"
    return send_file(png_bio, mimetype="image/png", as_attachment=True, download_name=fname)
