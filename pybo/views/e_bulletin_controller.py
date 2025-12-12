# controllers/bulletin_controller.py
import os, json, time, tempfile
from datetime import datetime
from io import BytesIO
from flask_login import login_required, current_user

from pybo import db
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

    convert_editor_layers_to_render_layers,


    # tmp
    LAYER_TMP_DIR,
)

try:
    from ..repository.repository_eink import RepositoryEINK
except Exception:
    RepositoryEINK = None

from ..models import DocumentInfo

bp = Blueprint("bulletin", __name__, url_prefix="/bulletin")


# 요청 단위로 디렉터리 보장
@bp.before_request
def _ensure_dirs():
    ensure_asset_dirs()


# ===== 템플릿 =====
@bp.route('/fileview', methods=['GET', 'POST'])
@login_required
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
    current_user = {
        "no": uid,
        "name": getattr(getattr(g, "user", None), "username", None) or "Guest"
    }

    dbg(
        "file_view:context",
        devices=len(devices),
        routes=len(approval_routes),
        current_user=dump_json(current_user),
    )

    return render_template(
        'bulletinboard/e_file_draft.html',
        devices=devices,
        current_user=current_user,
        approval_routes=approval_routes
    )


@bp.route('/bmpview', methods=['GET', 'POST'])
@login_required
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
    except Exception:
        current_app.logger.debug("[bmp_view] Repository fetch failed", exc_info=True)
        approval_routes = default_routes()

    uid = current_user_id()
    current_user = {
        "no": uid,
        "name": getattr(getattr(g, "user", None), "username", None) or "Guest",
    }

    dbg(
        "bmp_view:context",
        devices=len(devices),
        routes=len(approval_routes),
        current_user=dump_json(current_user)
    )

    resp = render_template(
        'bulletinboard/e_file_select.html',
        devices=devices,
        current_user=current_user,
        approval_routes=approval_routes
    )
    dbg("bmp_view:done", ms=int((time.time() - t0) * 1000))
    return resp


# ===== 라우트 데이터 =====
@bp.route("/routes/list", methods=["GET"])
@login_required
def routes_list():
    try:
        routes = RepositoryEINK.get_approval_routes() if RepositoryEINK is not None else default_routes()
        routes = routes or default_routes()
    except Exception:
        current_app.logger.debug("[routes_list] Repository error", exc_info=True)
        routes = default_routes()
    return jsonify({"routes": routes})


@bp.route("/departments", methods=["GET"])
@login_required
def list_departments():
    print("ENGINE:", db.engine.url)
    try:
        if RepositoryEINK is None:
            return jsonify({"departments": []})
        depts = RepositoryEINK.list_departments() or []
        print(f"department: {depts}")
        return jsonify({"departments": depts})
    except Exception:
        current_app.logger.debug("[departments] failed", exc_info=True)
        return jsonify({"departments": []})


@bp.route("/users", methods=["GET"])
@login_required
def list_users_by_department():
    dept = request.args.get("department")
    try:
        if RepositoryEINK is None:
            return jsonify({"users": []})
        users = RepositoryEINK.list_users_by_department(dept) or []
        return jsonify({"users": users})
    except Exception:
        current_app.logger.debug("[users] failed", exc_info=True)
        return jsonify({"users": []})


# ======================================================================
# 1) 엑셀/워드/PPT 원본 업로드 전용 API
#    - 레이어 X, apply_layers X
#    - 서버에는 원본 파일만 저장 + UPLOADS 스토어에 등록
#    - 브라우저는 이 응답으로 upload_id / relpath만 받아가서
#      "원본 탭" 미리보기 및 이후 register/bmp_preview에 활용
# ======================================================================
@bp.route("/document/upload_original", methods=["POST"])
@login_required
def document_upload_original():
    """
    엑셀/워드/PPT/PDF/이미지 등 '원본 문서' 업로드 전용 엔드포인트.

    - multipart/form-data 로 file 필수
    - 여기서는:
        * temp 변환이나 BMP/E-INK 스타일 적용 없음
        * UPLOADS에 경로 + 페이지 수 등록만 수행
        * root 기준 상대경로를 original_relpath로 반환
    """
    dbg("document_upload_original:req", **req_info())

    if not (request.mimetype and "multipart/form-data" in request.mimetype):
        abort(400, "multipart/form-data required")

    f = request.files.get("file")
    if not f:
        abort(400, "file missing")

    upload_id = next_upload_id()
    dirs = get_asset_dirs()
    root_dir = dirs.get("root")  # 사용자별 루트 디렉터리
    if not root_dir:
        abort(500, "asset root directory not configured")

    # approval_process/tmp_uploads/doc_{upload_id}/original.ext
    sub_dir = os.path.join(root_dir, "approval_process", "tmp_uploads", f"doc_{upload_id}")
    os.makedirs(sub_dir, exist_ok=True)

    orig_name = f.filename or f"upload_{upload_id}"
    _, ext = os.path.splitext(orig_name)
    ext = (ext or "").lower() or ".bin"

    # 파일명 sanitize
    safe_name = "".join(ch for ch in os.path.basename(orig_name) if ch.isalnum() or ch in "._- ")
    if not safe_name:
        safe_name = f"original_{upload_id}{ext}"
    if not safe_name.lower().endswith(ext):
        safe_name = safe_name + ext

    abs_orig_path = os.path.join(sub_dir, safe_name)
    f.save(abs_orig_path)

    # 페이지 수는 우선 1로 두고, 실제 Office→PDF 변환/페이지 카운트는
    # translation_service 또는 Repository 쪽에서 확장
    page_count = 1
    source_ext = ext.lstrip(".").lower()

    # UPLOADS 스토어에도 등록 (기존 preview/render 파이프라인 재사용용)
    UPLOADS = get_upload_store()
    UPLOADS[upload_id] = {
        "path": abs_orig_path,
        "pages": page_count,
        "name": safe_name,
        "source_ext": source_ext,
    }

    # root 기준 상대경로
    try:
        original_relpath = os.path.relpath(abs_orig_path, root_dir)
    except ValueError:
        # 드문 케이스지만, relpath 실패 시엔 절대경로 그대로 돌려줌
        original_relpath = abs_orig_path

    # normalized/pdf 경로는 지금은 original과 동일하게 돌려주고,
    # 실제 표준화(PDF) 변환은 나중에 Repository/Service에서 구현
    normalized_relpath = original_relpath

    dbg(
        "document_upload_original:saved",
        upload_id=upload_id,
        root=root_dir,
        original_relpath=original_relpath,
        normalized_relpath=normalized_relpath,
        pages=page_count,
        source_ext=source_ext,
    )

    return jsonify({
        "ok": True,
        "upload_id": upload_id,
        "source_ext": source_ext,
        "original_relpath": original_relpath,
        "pdf_relpath": normalized_relpath,
        "page_count": page_count,
    })


# ======================================================================
# 2) BMP / E-INK 스타일 미리보기 전용 API
#    - 항상 render_params + layout_snapshot 기반으로 레이어 적용
#    - 기존 preview_blob JSON 브랜치를 정리해 분리
# ======================================================================
@bp.route("/bmp_preview", methods=["POST"])
@login_required
def bmp_preview():
    """
    E-INK 디바이스 스타일의 BMP/PNG 미리보기 전용 엔드포인트.

    기대 JSON 형식 예시:
    {
      "upload_id": 123,              # 신규 문서 편집 중인 경우
      "document_info_id": 456,       # (선택) 이미 등록된 문서의 미리보기
      "page": 1,                     # (현재는 무시 / 확장 포인트)

      "render_params": {
        "width": 1200,
        "height": 1600,
        "mode": "BWRYBG",
        "scale": "fit",
        "percent": 100,
        "rotate": 270
      },

      "layout_snapshot": {
        "version": 1,
        "canvas": {...},
        "editor_layers": [ ... ],
        "layers": [ ... ]           # 둘 중 하나만 있어도 됨
      }
    }

    - 항상 레이어(결재란/직인/유효기간/메시지)를 적용해서 디바이스 감성 미리보기 생성
    - 원본 탭은 /document/upload_original + 브라우저 렌더, 여기서는 "BMP 탭" 용
    """
    svc = get_translation_service()
    js = request.get_json(silent=True) or {}

    dbg(
        "bmp_preview:req",
        **req_info(),
        has_upload_id=('upload_id' in js),
        has_doc_id=('document_info_id' in js),
        has_render_params=('render_params' in js),
        has_layout=('layout_snapshot' in js)
    )

    if not svc:
        abort(500, "translation service not available")

    upload_id = js.get("upload_id")
    document_info_id = js.get("document_info_id")

    # 1) upload_id 기반 (신규 편집 중인 문서)
    if upload_id is not None:
        try:
            upload_id = int(upload_id)
        except Exception:
            abort(400, "upload_id must be integer")

    # 2) document_info_id 기반 (이미 등록된 문서 미리보기)
    #    → Repository에서 PDF/원본 경로를 찾아서 UPLOADS에 등록하고 사용
    if upload_id is None and document_info_id is not None:
        if RepositoryEINK is None:
            abort(400, "document preview not available (no repository)")
        try:
            document_info_id = int(document_info_id)
        except Exception:
            abort(400, "document_info_id must be integer")

        try:
            # 이 메서드는 다음 단계에서 repository_eink.py 수정 시 구현 예정
            # 기대 반환 예:
            # {
            #   "abs_path": "/.../normalized.pdf",
            #   "pages": 1,
            #   "name": "original.pptx"
            # }
            src = RepositoryEINK.get_document_preview_source(document_info_id)
        except Exception:
            current_app.logger.debug("[bmp_preview] get_document_preview_source failed", exc_info=True)
            src = None

        if not src or "abs_path" not in src:
            abort(404, f"document_info_id={document_info_id} preview source not found")

        path = src["abs_path"]
        pages = int(src.get("pages", 1) or 1)
        name = src.get("name") or os.path.basename(path)
        upload_id = next_upload_id()
        UPLOADS = get_upload_store()
        UPLOADS[upload_id] = {
            "path": path,
            "pages": pages,
            "name": name,
            "source": "document_info",
            "document_info_id": document_info_id,
        }
        dbg(
            "bmp_preview:register_from_document",
            upload_id=upload_id,
            document_info_id=document_info_id,
            path=path,
            pages=pages,
        )

    if upload_id is None:
        abort(400, "upload_id or document_info_id is required")

    render_params = js.get("render_params") or {}
    width = int(render_params.get("width", 800) or 800)
    height = int(render_params.get("height", 480) or 480)
    mode = render_params.get("mode", "BWRYBG")
    scale = render_params.get("scale", "fit")
    percent = int(render_params.get("percent", 100) or 100)
    rotate = int(render_params.get("rotate", 0) or 0)
    page = int(js.get("page", 1) or 1)  # 현재는 사용하지 않지만, 디버그는 남겨둠

    layout_snapshot = js.get("layout_snapshot") or {}
    # editor_layers / layers 둘 다 지원
    layers = (
        layout_snapshot.get("layers")
        or layout_snapshot.get("editor_layers")
        or js.get("layers")
        or []
    )

    # 현재 로그인 사용자 기준으로 서명 레이어 user_id 바인딩
    layers = bind_sign_layer_user(layers, current_user_id())
    log_layers_summary(layers, where="bmp_preview")

    dbg(
        "bmp_preview:params",
        upload_id=upload_id,
        width=width,
        height=height,
        mode=mode,
        scale=scale,
        percent=percent,
        rotate=rotate,
        page=page,
        layer_count=len(layers),
    )

    # raw=False → E-INK 팔레트/디더링 적용
    png = render_preview_png(
        svc=svc,
        upload_id=upload_id,
        width=width,
        height=height,
        mode=mode,
        scale=scale,
        percent=percent,
        rotate=rotate,
        raw=False,
        layers=layers,
    )

    resp = send_file(png, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


# ======================================================================
# 3) (선택) 문서 정식 등록 API 스켈레톤
#     - DocumentInfo / DocumentApprovalStep / SignSlot 생성은 Repository에서 처리
#     - 실제 구현은 repository_eink.py 단계에서 이어서
# ======================================================================
@bp.route("/document/register", methods=["POST"])
@login_required
def document_register():
    """
    문서 정식 등록 엔드포인트 (sendfile 리팩토링 버전).

    기대 JSON 형식 예시:
    {
      "source_ext": "pptx",
      "original_relpath": "approval_process/tmp_uploads/abcd/original.pptx",
      "pdf_relpath": "approval_process/tmp_uploads/abcd/normalized.pdf",
      "page_count": 1,

      "doc_name": "회의실 안내문 2025-12",
      "device_id": "E01",

      "need_approval": true,
      "route_id": 1,

      "layout_snapshot": { ... },   # editor_layers + process_map + process_runtime
      "metadata": { ... },          # title, assignees, period, message, etc.
      "render_params": {
        "width": 1200,
        "height": 1600,
        "mode": "BWRYBG",
        "scale": "fit",
        "percent": 100,
        "rotate": 270
      },

      "target_type": "approval"     # "approval" | "bulletin"
    }
    """
    js = request.get_json(silent=True) or {}
    dbg(
        "document_register:req",
        **req_info(),
        keys=list(js.keys())
    )

    if RepositoryEINK is None:
        abort(500, "RepositoryEINK is not available")

    source_ext = (js.get("source_ext") or "").lower()
    original_relpath = js.get("original_relpath") or ""
    pdf_relpath = js.get("pdf_relpath") or original_relpath
    page_count = int(js.get("page_count") or 1)

    doc_name = js.get("doc_name") or ""
    device_id = js.get("device_id") or None

    need_approval = bool(js.get("need_approval", True))
    route_id = js.get("route_id")

    layout_snapshot = js.get("layout_snapshot") or {}
    metadata = js.get("metadata") or {}
    render_params = js.get("render_params") or {}
    target_type = (js.get("target_type") or "approval").lower()

    width = int(render_params.get("width", 0) or 0)
    height = int(render_params.get("height", 0) or 0)
    mode = render_params.get("mode")
    scale = render_params.get("scale")
    percent = int(render_params.get("percent", 0) or 0)
    rotate = int(render_params.get("rotate", 0) or 0)

    user_id = current_user_id()

    dbg(
        "document_register:parsed",
        user_id=user_id,
        doc_name=doc_name,
        device_id=device_id,
        need_approval=need_approval,
        route_id=route_id,
        source_ext=source_ext,
        original_relpath=original_relpath,
        pdf_relpath=pdf_relpath,
        page_count=page_count,
        target_type=target_type,
    )

    try:
        # 구체적인 DocumentInfo / DocumentApprovalStep / SignSlot 생성은
        # repository_eink.py 에서 구현 예정.
        #
        # 예상 시그니처:
        #   RepositoryEINK.register_document(
        #       user_id=...,
        #       device_id=...,
        #       doc_name=...,
        #       source_ext=...,
        #       original_relpath=...,
        #       pdf_relpath=...,
        #       page_count=...,
        #       need_approval=...,
        #       route_id=...,
        #       layout_snapshot=...,
        #       metadata=...,
        #       render_params=...,
        #       target_type=...,
        #   ) -> document_info_id
        document_info_id = RepositoryEINK.register_document(
            user_id=user_id,
            device_id=device_id,
            doc_name=doc_name,
            source_ext=source_ext,
            original_relpath=original_relpath,
            pdf_relpath=pdf_relpath,
            page_count=page_count,
            need_approval=need_approval,
            route_id=route_id,
            layout_snapshot=layout_snapshot,
            metadata=metadata,
            render_params=render_params,
            target_type=target_type,
        )
    except AttributeError:
        # 아직 register_document가 구현되지 않은 상태에서 호출되면 명시적으로 알려줌
        abort(500, "RepositoryEINK.register_document is not implemented yet")
    except Exception:
        current_app.logger.debug("[document_register] register_document failed", exc_info=True)
        abort(500, "document register failed")

    dbg(
        "document_register:done",
        document_info_id=document_info_id
    )

    return jsonify({
        "ok": True,
        "document_info_id": document_info_id
    })


# ======================================================================
# 4) (기존) preview_blob
#    - 기존 코드와 호환을 위해 유지
#    - 새 프론트에서는 /document/upload_original + /bmp_preview 사용 권장
# ======================================================================
@bp.route("/preview_blob", methods=["POST"])
@login_required
def preview_blob():
    """
    기존 E-INK 미리보기 엔드포인트.
    - multipart/form-data: 파일 업로드 + 바로 PNG 응답
    - application/json: upload_id + 파라미터 기반 PNG 응답

    신규 설계에서는:
    - 원본 업로드 → /document/upload_original
    - BMP/E-INK 미리보기 → /bmp_preview
    를 사용하는 것이 권장이며,
    이 엔드포인트는 하위호환 용도로만 유지.
    """
    created_id = None
    layers = []
    UPLOADS = get_upload_store()
    svc = get_translation_service()

    # multipart/form-data 브랜치: "원샷 업로드 + 미리보기"
    if request.mimetype and "multipart/form-data" in request.mimetype:
        f = request.files.get("file")
        if not f:
            abort(400, "file missing")
        suffix = os.path.splitext(f.filename or "")[1].lower() or ".bin"

        # 예전 구현은 tempfile.gettempdir() 사용
        # → 기존 동작을 깨지 않기 위해 그대로 유지
        tmpdir = os.path.join(tempfile.gettempdir(), "eink_uploads")
        os.makedirs(tmpdir, exist_ok=True)
        upload_id = next_upload_id()
        path = os.path.join(tmpdir, f"{upload_id}{suffix}")
        f.save(path)
        UPLOADS[upload_id] = {"path": path, "pages": 1, "name": f.filename or path}
        created_id = upload_id

        width = int(request.form.get("width", 800))
        height = int(request.form.get("height", 480))
        mode = request.form.get("mode", "BW")
        scale = request.form.get("scale", "fit")
        percent = int(request.form.get("percent", 100))
        rotate = int(request.form.get("rotate", 0))
        raw = int(request.form.get("raw", 0))
        try:
            layers = json.loads(request.form.get("layers") or "[]")
        except Exception:
            layers = []
    else:
        # JSON 브랜치: 사실상 /bmp_preview와 동일한 역할
        js = request.get_json(silent=True) or {}
        try:
            upload_id = int(js["upload_id"])
            width = int(js.get("width", 800))
            height = int(js.get("height", 480))
            mode = js.get("mode", "BW")
            scale = js.get("scale", "fit")
            percent = int(js.get("percent", 100))
            rotate = int(js.get("rotate", 0))
            raw = int(js.get("raw", 0))
            layers = js.get("layers") or []
        except Exception as e:
            abort(400, f"bad body: {e}")

    layers = bind_sign_layer_user(layers, current_user_id())
    log_layers_summary(layers, where="preview_blob")

    png = render_preview_png(
        svc=svc,
        upload_id=upload_id,
        width=width,
        height=height,
        mode=mode,
        scale=scale,
        percent=percent,
        rotate=rotate,
        raw=bool(raw),
        layers=layers
    )
    resp = send_file(png, mimetype="image/png")
    if created_id is not None:
        resp.headers["X-Upload-Id"] = str(created_id)
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp





# ----------------------------------------------------------------------
# HELPER: 특정 type 레이어 찾기
# ----------------------------------------------------------------------
def _find_layer(layers, layer_type: str):
    """
    layers(list[dict]) 에서 type 이 layer_type 인 첫 레이어를 반환.
    없으면 None.
    """
    for layer in layers:
        if layer.get("type") == layer_type:
            return layer
    return None


# ----------------------------------------------------------------------
# /sendfile : Front에서 editor JSON 받아서
#            - 이미지 렌더링 (임시)
#            - 레이아웃/메타 snapshot 저장
#            - Upload 레코드 + SignLayout 생성(옵션)
# ----------------------------------------------------------------------
@bp.route("/sendfile", methods=["POST"])
@login_required
def send_file_route():
    js = request.get_json(silent=True) or {}
    # 원본 바디 전체를 한 번 남겨두기 (디버그용)
    current_app.logger.debug(f"[sendfile] FullData(raw): {js}")
    current_app.logger.debug(f"[sendfile] JSON body(pretty): {dump_json(js)}")

    svc = get_translation_service()

    try:
        # --------------------------------------------------------------
        # 1) 기본 파라미터 파싱
        # --------------------------------------------------------------
        upload_id = int(js["upload_id"])
        page = int(js.get("page", 1))
        device_id = js["device_id"]

        # 13.3" e-ink 기본 좌표계 (1200x1600) 기준
        width = int(js.get("width") or 1200)
        height = int(js.get("height") or 1600)
        mode = js.get("mode") or "BWRYBG"
        scale = js.get("scale") or "fit"
        percent = int(js.get("percent") or 100)
        rotate = int(js.get("rotate") or 0)

        # --------------------------------------------------------------
        # 2) 레이아웃 / 메타 파싱
        # --------------------------------------------------------------
        layers = js.get("editor_layers") or js.get("layers") or []
        memo = js.get("memo") or ""
        meta = js.get("meta") or {}

        approval_meta = meta.get("approval") or {}
        stamp_meta = meta.get("stamp") or {}
        qrcode_meta = meta.get("qrcode") or {}
        period_meta = meta.get("period") or {}
        message_meta = meta.get("message")  # 문자열 or None

        # approval 사용 여부는 meta.approval.use 기준
        need_approval = bool(approval_meta.get("use", False))
        final_approval = bool(js.get("final_approval", False))

        route_id = js.get("route_id")

        # approval columns → assignees 기본 구성 (없으면 js.assignees 우선)
        columns = approval_meta.get("columns") or []
        assignees = js.get("assignees") or {
            "draft": [
                {
                    "user_id": c.get("user_id"),
                    "user_name": c.get("user_name"),
                    "dept": c.get("dept"),
                    "role": c.get("role"),
                    "col_id": c.get("id"),
                }
                for c in columns
                if c.get("group") == "draft"
            ],
            "check": [
                {
                    "user_id": c.get("user_id"),
                    "user_name": c.get("user_name"),
                    "dept": c.get("dept"),
                    "role": c.get("role"),
                    "col_id": c.get("id"),
                }
                for c in columns
                if c.get("group") == "check"
            ],
        }

        # --------------------------------------------------------------
        # 3) editor_layers 기반 레이아웃 스냅샷 구성
        # --------------------------------------------------------------
        approval_box = _find_layer(layers, "approval_box")
        qr_box = _find_layer(layers, "qr_box")
        period_box = _find_layer(layers, "period_box")
        message_box = _find_layer(layers, "message_box")

        parent_box = None
        if approval_box is not None:
            parent_box = {
                "x": approval_box.get("x", 0),
                "y": approval_box.get("y", 0),
                "w": approval_box.get("w", 0),
                "h": approval_box.get("h", 0),
                "layout": approval_box.get("layout") or {},
            }

        layout_snapshot = {
            "canvas_w": width,
            "canvas_h": height,
            "parent_box": parent_box,
            "tpl_json": {
                "approval_box": approval_box,
                "qr_box": qr_box,
                "period_box": period_box,
                "message_box": message_box,
            },
            "slots_json": {
                "approval": approval_meta,
                "stamp": stamp_meta,
                "qrcode": qrcode_meta,
                "period": period_meta,
                "message": message_meta,
            },
            "layers_json": layers,
            "memo": memo,
        }

        # --------------------------------------------------------------
        # 4) 파싱 결과 디버그 로그
        # --------------------------------------------------------------
        dbg(
            "sendfile:parsed",
            upload_id=upload_id,
            device_id=device_id,
            page=page,
            canvas=f"{width}x{height}",
            mode=mode,
            scale=scale,
            percent=percent,
            rotate=rotate,
            layers_count=len(layers),
            need_approval=need_approval,
            final_approval=final_approval,
            approval_box=bool(approval_box),
            approval_cols=len(columns),
            has_qr=bool(qr_box),
            has_period=bool(period_box),
            has_message=bool(message_box),
            memo_len=len(memo or ""),
        )
        current_app.logger.debug(
            "[sendfile] layout_snapshot keys=%s, slots=%s",
            list(layout_snapshot.keys()),
            list(layout_snapshot.get("slots_json", {}).keys()),
        )
        current_app.logger.debug(
            "[sendfile] approval_meta=%s", dump_json(approval_meta)
        )
        current_app.logger.debug(
            "[sendfile] period_meta=%s", dump_json(period_meta)
        )

    except Exception as e:
        current_app.logger.debug("[sendfile] bad body", exc_info=True)
        abort(400, f"bad body: {e}")

    # 기존 4.2" 보드 호환 로직 (필요 시 유지)
    if (width, height) == (480, 800):
        width, height = 800, 480
        dbg("sendfile:adjusted_small_board", width=width, height=height)

    # --------------------------------------------------------------
    # 5) 레이어에 사용자 정보 bind + 요약 로그
    # --------------------------------------------------------------
    layers = bind_sign_layer_user(layers, current_user_id())
    log_layers_summary(layers, where="send_file")

    render_layers = convert_editor_layers_to_render_layers(layers)

    # --------------------------------------------------------------
    # 6) 이미지 렌더링 (현재는 즉시 BMP/BIN 생성 – 추후 승격 시점으로 이동 예정)
    # --------------------------------------------------------------
    im_proc, fmt = place_into_canvas_and_quantize(
        svc=svc,
        upload_id=upload_id,
        page=page,
        width=width,
        height=height,
        scale=scale,
        percent=percent,
        rotate=rotate,
        mode=mode,
        layers=render_layers,
    )

    target_dir = decide_target_dir(
        need_approval=need_approval,
        final_approval=final_approval,
    )
    bmp_path, meta_path, hdr_path, bin_path = asset_paths(
        device_id,
        width,
        height,
        fmt,
        target_dir=target_dir,
        userid= current_user_id(),
    )

    dbg(
        "sendfile:asset_paths",
        target_dir=target_dir,
        bmp=bmp_path,
        bin=bin_path,
        meta=meta_path,
        hdr=hdr_path,
    )

    payload, meta_bundle = save_meta_bundle(
        im=im_proc,
        fmt=fmt,
        size=(width, height),
        bmp_path=bmp_path,
        bin_path=bin_path,
        meta_path=meta_path,
        device_id=device_id,
        target_dir=target_dir,
        need_approval=need_approval,
        final_approval=final_approval,
        route_id=route_id,
        assignees=assignees,
    )

    current_app.logger.debug(
        "[sendfile] meta_bundle saved: %s", dump_json(meta_bundle)
    )

    # --------------------------------------------------------------
    # 7) 업로드 임시파일 정리
    # --------------------------------------------------------------
    info = get_upload_store().pop(upload_id, None)
    if info:
        try:
            path = info.get("path")
            if path and os.path.isfile(path):
                os.remove(path)
                dbg("sendfile:cleanup_temp", path=path, removed=True)
            else:
                dbg("sendfile:cleanup_temp", path=path, removed=False)
        except Exception:
            current_app.logger.debug("[CLEANUP] temp delete failed", exc_info=True)

    # --------------------------------------------------------------
    # 8) DB 저장 (Upload 레코드 + SignLayout 템플릿)
    # --------------------------------------------------------------

    upload_row_id = None
    sign_layout_id = None

    if RepositoryEINK is not None:
        try:
            # 8-1) status / target_dir 매핑
            db_status = (
                "uploads"
                if target_dir in ("uploads", "bulletin_files")
                else "approved"
                if target_dir == "approved"
                else "checked"
                if target_dir == "checked"
                else "in_review"
            )

            # 업로드 원본 이름 (없으면 BMP 파일명으로 대체)
            orig_filename = info.get("name") if info else os.path.basename(bmp_path)

            route_snapshot = (
                {"route_id": route_id, "assignees": assignees}
                if route_id
                else None
            )

            metadata = {
                "meta": meta,
                "memo": memo,
                "assignees": assignees,
            }

            current_app.logger.debug(
                "[sendfile][DB] status=%s, route_snapshot=%s, metadata=%s",
                db_status,
                route_snapshot,
                dump_json(metadata),
            )

            # 8-2) DocumentInfo 생성
            upload_row_id = RepositoryEINK.create_upload_record(
                user_id=current_user_id(),
                device_id=device_id,
                orig_filename=orig_filename,
                stored_path=bmp_path,           # ✅ 실제 BMP 경로
                target_dir=target_dir,          # ✅ 실제 디렉터리 ('uploads' / 'in_review' / ...)
                need_approval=need_approval,
                status=db_status,               # ✅ 매핑된 상태
                pages=1,
                width=width,
                height=height,
                mode=fmt,                       # 예: 'BWRYBG'
                scale=scale,
                percent=percent,
                rotate=rotate,
                route_id=route_id,
                sign_layout_id=None,            # 아래에서 생성 후 update
                route_snapshot=route_snapshot,
                layout_snapshot=layout_snapshot if layout_snapshot else None,
                metadata=metadata,
            )

            # 8-3) layout_snapshot → SignLayout 템플릿으로 승격
            args_for_layout = (
                snapshot_to_signlayout_args(layout_snapshot)
                if layout_snapshot
                else None
            )

            current_app.logger.debug("ARGS_FOR_LAYOUT: %s", dump_json(args_for_layout))

            if args_for_layout:
                sign_layout_id = RepositoryEINK.insert_sign_layout(
                    name=f"Device {device_id} Snapshot",
                    owner_user_id=current_user_id(),
                    canvas_w=args_for_layout["canvas_w"],
                    canvas_h=args_for_layout["canvas_h"],
                    parent_box=args_for_layout["parent_box"],
                    tpl_json=args_for_layout["tpl_json"],
                    slots_json=args_for_layout["slots_json"],
                    layers_json=args_for_layout["layers_json"],
                    version=1,
                )
                dbg(
                    "sendfile:sign_layout_saved",
                    sign_layout_id=sign_layout_id,
                    canvas=f"{args_for_layout['canvas_w']}x{args_for_layout['canvas_h']}",
                )

                # DocumentInfo에 sign_layout_id 반영
                RepositoryEINK.update_upload_status(
                    upload_row_id,
                    sign_layout_id=sign_layout_id,
                )

            # 8-4) 결재 열 / 슬롯 인스턴스 생성
            RepositoryEINK.create_doc_approval_steps_from_layout(
                document_info_id=upload_row_id,
                tpl_json=layout_snapshot["tpl_json"],
            )

            RepositoryEINK.create_sign_slots_from_layout(
                document_info_id=upload_row_id,
                tpl_json=layout_snapshot["tpl_json"],
                slots_json=layout_snapshot["slots_json"],
            )

        except Exception:
            current_app.logger.debug("[DB] save skipped", exc_info=True)


    # --------------------------------------------------------------
    # 9) 응답
    # --------------------------------------------------------------
    job_id = int(time.time() * 1000)

    dbg(
        "sendfile:response",
        status="prepared",
        job_id=job_id,
        device_id=device_id,
        dir=target_dir,
        file=os.path.basename(bmp_path),
        upload_row_id=upload_row_id,
        sign_layout_id=sign_layout_id,
    )

    return jsonify(
        {
            "status": "prepared",
            "job_id": job_id,
            "device_id": device_id,
            "dir": target_dir,
            "file": os.path.basename(bmp_path),
            "meta": meta_bundle,
            "upload_row_id": upload_row_id,
            "sign_layout_id": sign_layout_id,
        }
    )


# ===== 레이어 업로드/서빙 =====
@bp.route("/layer_upload", methods=["POST"])
@login_required
def layer_upload():
    if not (request.mimetype and "multipart/form-data" in request.mimetype):
        abort(400, "multipart/form-data required")
    f = request.files.get("file")
    if not f:
        abort(400, "file missing")
    ext = (os.path.splitext(f.filename or "")[1] or ".png").lower()
    if ext not in (".png", ".jpg", ".jpeg"):
        abort(400, "only .png/.jpg supported")
    token = f"{int(time.time() * 1000)}_{os.path.basename(f.filename or 'layer')}"
    safe_token = "".join(ch for ch in token if ch.isalnum() or ch in "._-")[:128]
    out_path = os.path.join(LAYER_TMP_DIR, safe_token)
    f.save(out_path)
    get_layer_store()[safe_token] = {
        "path": out_path,
        "name": f.filename or safe_token,
        "mimetype": "image/png" if ext == ".png" else "image/jpeg"
    }
    return jsonify({
        "upload_token": safe_token,
        "preview_url": url_for("bulletin.layer_img", token=safe_token)
    })


@bp.route("/layer_img/<path:token>", methods=["GET"])
@login_required
def layer_img(token):
    info = get_layer_store().get(token)
    if not info or not os.path.isfile(info["path"]):
        abort(404)
    return send_file(info["path"], mimetype=info.get("mimetype", "image/png"))


# ===== 레이아웃 배치 저장 =====
@bp.route("/sign_layout/save_batch", methods=["POST"])
@login_required
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
@login_required
def approval_pending():
    user_no, userid = current_user_ids()
    if not userid:
        return jsonify({"has": False})
    item = find_latest_pending_for_user(userid)
    if not item:
        return jsonify({"has": False})
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
        "goto": url_for(
            "bulletin.approval_page",
            device_id=item.get("device_id"),
            meta=item.get("meta_path"),
            status=item.get("status")
        )
    })


@bp.route("/approval/page", methods=["GET"])
@login_required
def approval_page():
    device_id = request.args.get("device_id")
    meta_path = request.args.get("meta")
    status = request.args.get("status")
    if not (device_id and meta_path and os.path.isfile(meta_path)):
        abort(404, "meta missing")
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    stage = "review" if status == "in_review" else ("approve" if status == "checked" else "unknown")
    preview_url = url_for("bulletin.approval_preview", meta=meta_path)
    return render_template(
        "bulletinboard/e_file_approval.html",
        device_id=device_id,
        meta_path=meta_path,
        preview_url=preview_url,
        status=status,
        stage=stage,
        width=meta.get("width", 1200),
        height=meta.get("height", 1600),
        mode=meta.get("mode", "BWRYBG"),
        assignees=meta.get("assignees") or {}
    )


@bp.route("/approval/preview", methods=["GET"])
@login_required
def approval_preview():
    meta_path = request.args.get("meta") or ""
    if not (meta_path and os.path.isfile(meta_path)):
        abort(404)
    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    bmp_dir = os.path.dirname(meta_path)
    bmp_file = meta.get("file")
    bmp_path = os.path.join(bmp_dir, bmp_file)
    if not os.path.isfile(bmp_path):
        abort(404)
    return send_file(bmp_path, mimetype="image/bmp")


@bp.route("/approval/act", methods=["POST"])
@login_required
def approval_act():
    js = request.get_json(silent=True) or {}

    def _fail(code, msg):
        abort(code, msg)

    meta_path_raw = js.get("meta_path")
    action = (js.get("action") or "").lower()
    if action not in ("review", "approve", "reject"):
        _fail(400, "action invalid")
    meta_path = os.path.normpath(meta_path_raw) if meta_path_raw else None
    if not (meta_path and os.path.isfile(meta_path)):
        _fail(404, f"meta not found: {meta_path_raw}")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)

    device_id = meta.get("device_id")
    width = int(meta.get("width", 1200))
    height = int(meta.get("height", 1600))
    fmt = meta.get("mode", "BWRYBG")
    target_dir_meta = (meta.get("dir") or "").strip()
    status_meta = (meta.get("status") or "").strip()
    bmp_dir = os.path.dirname(meta_path)  # ← 메타가 있는 실제 디렉터리
    bmp_file = meta.get("file")
    if not bmp_file:
        _fail(400, "meta.file missing")
    bmp_path = os.path.join(bmp_dir, bmp_file)
    bin_path = os.path.join(bmp_dir, os.path.splitext(bmp_file)[0] + ".bin")
    if not os.path.isfile(bmp_path):
        _fail(404, f"bmp missing: {bmp_path}")

    # (핵심) 실제 파일의 사용자 루트를 기준으로 src/dst 디렉터리 구성
    user_root = os.path.dirname(bmp_dir)  # .../{in_review} 의 상위 = 사용자 루트
    actual_dir = os.path.basename(bmp_dir)  # 현재 단계(in_review | checked | approved)
    src_in_review = os.path.join(user_root, "in_review")
    src_checked = os.path.join(user_root, "checked")
    dst_checked = os.path.join(user_root, "checked")
    dst_approved = os.path.join(user_root, "approved")

    target_dir = target_dir_meta or actual_dir
    if not status_meta:
        status_meta = {
            "in_review": "in_review",
            "checked": "checked",
            "uploads": "uploads",
            "approved": "approved",
            "bulletin_files": "uploads",  # 게시판용 폴더 → 업로드 상태로 취급
        }.get(actual_dir, "in_review")

    # 레이어 스냅샷 로드(필요 시) & 서명 합성
    layers = []
    if RepositoryEINK is not None:
        try:
            snap = RepositoryEINK.get_layout_snapshot_by_meta(meta_path)
            if isinstance(snap, dict):
                layers = (
                    snap.get("layers") or
                    snap.get("layout", {}).get("layers") or
                    []
                )
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
        with open(bin_path, "wb") as f:
            f.write(payload)
        raw_len = len(payload) - 4
        crc32_le = int.from_bytes(payload[-4:], "little", signed=False)
        meta.update({
            "raw_len": raw_len,
            "total_len": raw_len + 4,
            "crc32": f"{crc32_le:08x}",
            "ver": int(os.path.getmtime(bmp_path)),
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        })

    moved = []
    new_status = meta.get("status") or status_meta
    new_dir = target_dir

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
            # DB/파일 시스템 모두 동일하게:
            #   target_dir ∈ {in_review, checked, approved, uploads, bulletin_files}
            repo_dir = new_dir
            RepositoryEINK.update_upload_status_by_meta(
                old_meta_path=new_meta_path,
                new_dir=repo_dir,
                new_status=new_status,
                note=js.get("note"),
            )
        except Exception:
            current_app.logger.debug("[approval_act] DB update failed", exc_info=True)

    return jsonify({
        "ok": True,
        "moved": moved,
        "new_status": new_status,
        "new_dir": new_dir,
        "meta_path": new_meta_path
    })


@bp.route("/approval/advance", methods=["POST"])
@login_required
def approval_advance():
    js = request.get_json(silent=True) or {}
    stage = (js.get("stage") or "").lower()
    file_param = js.get("file") or ""
    if stage not in ("review", "approve"):
        abort(400, "stage must be 'review' or 'approve'")
    base = file_param
    if base.endswith(".meta.json"):
        base = base[:-10] + ".bmp"
    elif not base.endswith(".bmp"):
        abort(400, "file must be .bmp or .meta.json")
    dirs = get_asset_dirs()
    src_dir = dirs["in_review" if stage == "review" else "checked"]
    dst_dir = dirs["checked" if stage == "review" else "approved"]
    moved = move_bundle(src_dir, dst_dir, base)
    if not moved:
        abort(404, f"no files moved (src={src_dir}, file={base})")
    return jsonify({"ok": True, "stage": stage, "moved": moved})


# ===== Routes =====
@bp.route("/approval/mark_checked", methods=["POST"])
@login_required
def approval_mark_checked():
    try:
        session['approval_checked'] = True
        return jsonify({"ok": True})
    except Exception:
        current_app.logger.debug("[approval_mark_checked] failed", exc_info=True)
        return jsonify({"ok": False}), 500


# ===== 에디터: 드래프트/내보내기 =====
@bp.route("/save_draft", methods=["POST"])
@login_required
def save_draft():
    svc = get_translation_service()
    js = request.get_json(silent=True) or {}
    upload_id = int(js.get("upload_id") or 0)
    device_id = js.get("device_id") or ""
    memo = js.get("memo") or ""
    filename = js.get("filename") or ""
    p = js.get("params") or {}
    layers = js.get("editor_layers") or []
    strategy = (js.get("strategy") or "draft").lower()
    width = int(p.get("width", 800))
    height = int(p.get("height", 480))
    mode = p.get("mode", "BWRYBG")
    scale = p.get("scale", "fit")
    percent = int(p.get("percent", 100))
    rotate = int(p.get("rotate", 0))
    layers = bind_sign_layer_user(layers, current_user_id())

    dbg(
        "save_draft:req",
        upload_id=upload_id,
        device_id=device_id,
        strategy=strategy,
        width=width,
        height=height,
        mode=mode,
        scale=scale,
        percent=percent,
        rotate=rotate,
        layer_count=len(layers),
    )

    if strategy == "direct":
        saved = save_draft_bundle(
            svc=svc,
            upload_id=upload_id,
            width=width,
            height=height,
            mode=mode,
            scale=scale,
            percent=percent,
            rotate=rotate,
            layers=layers,
            user_id=current_user_id(),
            device_id=device_id,
            memo=memo,
            filename=filename
        )
        return jsonify({"ok": True, "strategy": "direct", **saved})

    # draft 스냅샷만 저장 (사용자 루트)
    dirs = get_asset_dirs()
    snap_dir = os.path.join(dirs["root"], "draft_snapshots")
    os.makedirs(snap_dir, exist_ok=True)
    meta = {
        "upload_id": upload_id,
        "device_id": device_id,
        "filename": filename,
        "memo": memo,
        "params": {
            "width": width,
            "height": height,
            "mode": mode,
            "scale": scale,
            "percent": percent,
            "rotate": rotate
        },
        "layers": layers,
        "user_id": current_user_id(),
        "saved_at": datetime.now().isoformat(timespec="seconds")
    }
    out = os.path.join(snap_dir, f"draft_{int(time.time())}.json")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    dbg("save_draft:done", snapshot=out)

    return jsonify({"ok": True, "strategy": "draft", "snapshot": out})


@bp.route("/editor_export", methods=["POST"])
@login_required
def editor_export():
    svc = get_translation_service()
    js = request.get_json(silent=True) or {}
    upload_id = int(js.get("upload_id") or 0)
    layers = js.get("layers") or js.get("editor_layers") or []
    width = int(js.get("width", 800) or 800)
    height = int(js.get("height", 480) or 480)
    mode = js.get("mode", "BWRYBG")
    scale = js.get("scale", "fit")
    percent = int(js.get("percent", 100) or 100)
    rotate = int(js.get("rotate", 0) or 0)
    layers = bind_sign_layer_user(layers, current_user_id())

    dbg(
        "editor_export:req",
        upload_id=upload_id,
        width=width,
        height=height,
        mode=mode,
        scale=scale,
        percent=percent,
        rotate=rotate,
        layer_count=len(layers),
    )

    png_bio = render_flat_image(
        svc=svc,
        upload_id=upload_id,
        width=width,
        height=height,
        scale=scale,
        percent=percent,
        rotate=rotate,
        layers=layers
    )
    fname = f"editor_export_{int(time.time())}.png"
    return send_file(png_bio, mimetype="image/png", as_attachment=True, download_name=fname)


@bp.route("/files")
@login_required
def file_table():
    """
    e_file_table.html
    - 탭: 작성문서 / 결재대기 / 결재진행사항 / 결재완료
    - 쿼리파라미터:
        ?tab=author|pending|progress|completed
        &q=검색어
        &status=all|draft|in_review|...
        &date_from=YYYY-MM-DD
        &date_to=YYYY-MM-DD
    """
    tab = request.args.get("tab", "author")
    search = request.args.get("q", "").strip() or None
    status = request.args.get("status", "all")
    date_from = request.args.get("date_from") or None
    date_to = request.args.get("date_to") or None

    user_id = current_user.no

    # 🔹 RepositoryEINK 가 없는 경우: 빈 리스트로 안전하게 처리
    if RepositoryEINK is None:
        current_app.logger.debug("[file_table] RepositoryEINK is None, return empty lists")
        return render_template(
            "e_file_table.html",
            tab=tab,
            search=search or "",
            status=status,
            date_from=date_from or "",
            date_to=date_to or "",
            docs_author=[],
            pending_rows=[],
            docs_progress=[],
            docs_completed=[],
        )

    docs_author = []
    pending_rows = []   # (DocumentInfo, SignSlot)
    docs_progress = []
    docs_completed = []

    # 필요한 탭만 로딩해서 부담 줄이기
    if tab == "author":
        docs_author = RepositoryEINK.list_author_documents(
            user_id=user_id,
            search=search,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
    elif tab == "pending":
        pending_rows = RepositoryEINK.list_my_pending_documents(
            user_id=user_id,
            search=search,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
    elif tab == "progress":
        docs_progress = RepositoryEINK.list_my_progress_documents(
            user_id=user_id,
            search=search,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
    elif tab == "completed":
        docs_completed = RepositoryEINK.list_my_completed_documents(
            user_id=user_id,
            search=search,
            status=status,
            date_from=date_from,
            date_to=date_to,
        )
    else:
        tab = "author"
        docs_author = RepositoryEINK.list_author_documents(user_id=user_id)

    return render_template(
        "bulletinboard/e_file_table.html",
        tab=tab,
        search=search or "",
        status=status,
        date_from=date_from or "",
        date_to=date_to or "",
        docs_author=docs_author,
        pending_rows=pending_rows,
        docs_progress=docs_progress,
        docs_completed=docs_completed,
    )

@bp.route("/files/<int:doc_id>", methods=["GET"])
@login_required
def file_detail(doc_id):
    """
    전자결재 문서 상세 페이지
    - 목록에서 클릭한 한 개 문서를 보여주는 화면
    - 템플릿: bulletinboard/e_file_detail.html
    """
    if RepositoryEINK is None:
        abort(500, "RepositoryEINK is not available")

    # 1) 기본 문서 정보 로드 (DocumentInfo ORM 기준)
    doc: DocumentInfo = DocumentInfo.query.get_or_404(doc_id)

    # 2) 현재 사용자 기본 정보
    user_no, userid = current_user_ids()
    cur_username = getattr(current_user, "username", None)
    cur_dept     = getattr(current_user, "department", None)

    # 3) 권한 체크 (작성자이거나, 결재선/서명 슬롯에 포함된 사람만 볼 수 있게)
    # 3-1) 작성자인가?
    is_author = (doc.user_id == user_no)

    # 3-2) 서명 슬롯 기준: 명시적으로 지정된 서명자/서명 완료자
    is_approver = False
    for slot in getattr(doc, "sign_slots", []):
        # 이 문서의 어떤 서명 슬롯이라도 내 user_no와 연결되어 있으면 OK
        if slot.target_user_id == user_no or slot.filled_by_id == user_no:
            is_approver = True
            break

    # 3-3) 결재 열(DocumentApprovalStep) 기준:
    #      - 나에게 할당된 열(snapshot 기준)
    #      - 이미 내가 서명한 열
    if not is_approver:
        for step in getattr(doc, "approval_steps", []):
            # 이미 내가 서명한 경우
            if step.signed_by_user_id == user_no:
                is_approver = True
                break

            # 스냅샷 기준 매칭 (userid / username / department)
            if step.userid_snapshot and step.userid_snapshot == userid:
                is_approver = True
                break

            if cur_username and step.username_snapshot and step.username_snapshot == cur_username:
                is_approver = True
                break

            if cur_dept and step.dept_snapshot and step.dept_snapshot == cur_dept:
                is_approver = True
                break

    # 3-4) 필요하면 여기서 관리자/운영자 권한 같은 추가 조건도 넣을 수 있음
    # ex) if current_user.security == '9': is_approver = True

    # 3-5) 최종 권한 판정
    if not (is_author or is_approver):
        abort(403, "문서를 볼 권한이 없습니다.")

    # 4) 템플릿 렌더
    return render_template(
        "bulletinboard/e_file_detail.html",
        doc=doc,
    )
