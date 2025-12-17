# controllers/bulletin_controller.py
import os, json, time, tempfile, glob, uuid,shutil
from datetime import datetime
from io import BytesIO
from flask_login import login_required, current_user
import hashlib
from pathlib import Path
from werkzeug.utils import secure_filename
from PIL import Image

from pybo import db
from flask import (
    Blueprint, request, send_file, jsonify, abort,
    render_template, current_app, url_for, g, session, send_from_directory, flash, redirect  # ✅ 추가
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

    decide_doc_bucket,save_doc_master_bundle,

    current_userid_str,


    # tmp
    LAYER_TMP_DIR,
)

try:
    from ..repository.repository_eink import RepositoryEINK
except Exception:
    RepositoryEINK = None

from ..models import DocumentInfo, StampAsset

bp = Blueprint("bulletin", __name__, url_prefix="/bulletin")


STAMP_DIR_DEFAULT = r"D:\bmp_files\admin\stamp"


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
import glob

def _resolve_doc_dir_from_stored_path(stored_path: str) -> str:
    """
    DocumentInfo.stored_path 가
    - 문서 마스터 폴더(권장): D:\\eink_docs\\{userid}\\approval_process\\{doc_id}
    - 또는 파일 경로(구형): ...\\something.bmp
    - 또는 상대경로: userid/approval_process/doc_id
    를 모두 커버해서 "폴더" 절대경로로 정규화.
    """
    if not stored_path:
        return ""

    p = os.path.normpath(stored_path)

    # 파일이면 dirname
    if os.path.isfile(p):
        p = os.path.dirname(p)

    # 상대경로면 루트 붙이기
    if not os.path.isabs(p):
        base = current_app.config.get("EINK_DOC_ROOT") or os.path.join("D:/", "eink_docs")
        p = os.path.normpath(os.path.join(base, p))

    return p


def _pick_original_filename(doc_dir: str) -> str | None:
    """
    doc_dir 아래 original.* (original.pdf/original.pptx 등) 중 1개 선택
    """
    if not doc_dir or not os.path.isdir(doc_dir):
        return None
    cands = sorted(glob.glob(os.path.join(doc_dir, "original.*")))
    return os.path.basename(cands[0]) if cands else None


def _exists_in_doc_dir(doc_dir: str, fname: str) -> str | None:
    """
    doc_dir/fname 존재하면 fname 반환, 아니면 None
    """
    if not doc_dir:
        return None
    p = os.path.join(doc_dir, fname)
    return fname if os.path.isfile(p) else None


def _is_allowed_download_name(fname: str, original_name: str | None) -> bool:
    """
    경로 탈출/임의 파일 다운로드 방지용 화이트리스트.

    ✅ 허용(형이 현재 쓰는 번들)
    - normalized.pdf
    - onelayer.bmp
    - preview_merged.png
    - + original.* (실제 존재하는 original_name만 허용)
    """
    if not fname:
        return False

    # 경로 탈출 차단
    if "/" in fname or "\\" in fname:
        return False

    allowed_fixed = {
        "normalized.pdf",
        "onelayer.bmp",
        "preview_merged.png",
    }
    if fname in allowed_fixed:
        return True

    # original.* 은 실제 저장된 파일명(original_name) 1개만 허용
    if original_name and fname == original_name and fname.startswith("original."):
        return True

    return False



# ======================================================================
# 2) BMP / E-INK 스타일 미리보기 전용 API
#    - 항상 render_params + layout_snapshot 기반으로 레이어 적용
#    - 기존 preview_blob JSON 브랜치를 정리해 분리
# ======================================================================

def _upload_doc_dir(upload_id: int) -> str:
    dirs = get_asset_dirs()
    root_dir = dirs.get("root")
    if not root_dir:
        abort(500, "asset root directory not configured")
    # ✅ 컨셉: uploads/{upload_id}/source.ext
    doc_dir = os.path.join(root_dir, "uploads", str(upload_id))
    os.makedirs(doc_dir, exist_ok=True)
    os.makedirs(os.path.join(doc_dir, "render"), exist_ok=True)
    return doc_dir

def _cache_name_normalized(width:int, height:int, scale:str, percent:int, rotate:int, page:int=1) -> str:
    # 파일명으로 캐시 재사용 가능하게
    return f"normalized_w{width}_h{height}_{scale}_p{percent}_r{rotate}_pg{page}.png"

def _ensure_normalized_cached(svc, upload_id:int, width:int, height:int, scale:str, percent:int, rotate:int, page:int=1) -> str:
    UPLOADS = get_upload_store()
    info = UPLOADS.get(upload_id)
    if not info or not os.path.isfile(info.get("path","")):
        abort(404, f"upload_id={upload_id} source not found")

    doc_dir = info.get("doc_dir") or _upload_doc_dir(upload_id)
    render_dir = os.path.join(doc_dir, "render")
    os.makedirs(render_dir, exist_ok=True)

    fname = _cache_name_normalized(width, height, scale, percent, rotate, page)
    out_path = os.path.join(render_dir, fname)

    # 캐시 존재하면 그대로
    if os.path.isfile(out_path):
        return out_path

    # ✅ raw=True, layers=[] 로 “정규화 PNG” 생성
    png_io = render_preview_png(
        svc=svc,
        upload_id=upload_id,
        width=width,
        height=height,
        mode="BW",          # raw=True에서는 사실상 의미 약함(그대로 두기)
        scale=scale,
        percent=percent,
        rotate=rotate,
        raw=True,
        layers=[],
        page=page,
    )
    with open(out_path, "wb") as f:
        f.write(png_io.getvalue())

    return out_path


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
        upload_id = next_upload_id()

        # ✅ uploads/{upload_id}/source.ext 저장
        doc_dir = _upload_doc_dir(upload_id)
        source_path = os.path.join(doc_dir, f"source{suffix}")
        f.save(source_path)

        UPLOADS[upload_id] = {
            "path": source_path,
            "pages": 1,
            "name": f.filename or os.path.basename(source_path),
            "doc_dir": doc_dir,
        }
        created_id = upload_id

        width = int(request.form.get("width", 1200))
        height = int(request.form.get("height", 1600))
        scale = request.form.get("scale", "fit")
        percent = int(request.form.get("percent", 100))
        rotate = int(request.form.get("rotate", 0))
        page = int(request.form.get("page", 1))

        # ✅ 무조건 “정규화 PNG” 반환
        cached = _ensure_normalized_cached(
            svc=svc,
            upload_id=upload_id,
            width=width,
            height=height,
            scale=scale,
            percent=percent,
            rotate=rotate,
            page=page,
        )

        # review_blob 내부 파싱 끝난 다음에 위치 (성능/일관성 목적)
        _ = _ensure_normalized_cached(svc, upload_id, width, height, scale, percent, rotate, page)

        resp = send_file(cached, mimetype="image/png")
        resp.headers["X-Upload-Id"] = str(created_id)
        resp.headers["X-Pages"] = "1"
        resp.headers["Cache-Control"] = "no-store, max-age=0"
        resp.headers["Pragma"] = "no-cache"
        resp.headers["Expires"] = "0"
        return resp




@bp.route("/review_blob", methods=["POST"])
@login_required
def review_blob():
    """
    BMP(E-INK) 확인 전용 엔드포인트.
    - application/json: upload_id + 파라미터 기반 PNG 응답 (E-INK 팔레트/룰 적용)
    - 원본(raw) 미리보기는 /preview_blob (multipart + raw=1)에서 1회만 사용
    """
    layers = []
    svc = get_translation_service()

    js = request.get_json(silent=True) or {}
    try:
        upload_id = int(js["upload_id"])
        width = int(js.get("width", 800))
        height = int(js.get("height", 480))
        mode = js.get("mode", "BW")
        scale = js.get("scale", "fit")
        percent = int(js.get("percent", 100))
        rotate = int(js.get("rotate", 0))
        page = int(js.get("page", 1))
        layers = js.get("layers") or []
    except Exception as e:
        abort(400, f"bad body: {e}")

    # 결재 user bind 등 동일 처리
    layers = bind_sign_layer_user(layers, current_user_id())
    log_layers_summary(layers, where="review_blob")

    # ✅ raw=False 고정 (E-INK/BMP 스타일)
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
        page=page,   # render_preview_png가 page를 받는다면 전달
    )

    resp = send_file(png, mimetype="image/png")
    resp.headers["Cache-Control"] = "no-store, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp


@bp.route("/original_blob", methods=["POST"])
@login_required
def original_blob():
    svc = get_translation_service()
    js = request.get_json(silent=True) or {}

    try:
        upload_id = int(js["upload_id"])
        width  = int(js.get("width", 1200))
        height = int(js.get("height", 1600))
        scale  = js.get("scale", "fit")
        percent= int(js.get("percent", 100))
        rotate = int(js.get("rotate", 0))
        page   = int(js.get("page", 1))
    except Exception as e:
        abort(400, f"bad body: {e}")

    cached = _ensure_normalized_cached(
        svc=svc,
        upload_id=upload_id,
        width=width,
        height=height,
        scale=scale,
        percent=percent,
        rotate=rotate,
        page=page,
    )

    resp = send_file(cached, mimetype="image/png")
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
    current_app.logger.debug(f"[sendfile] FullData(raw): {js}")
    current_app.logger.debug(f"[sendfile] JSON body(pretty): {dump_json(js)}")

    svc = get_translation_service()

    # ✅ 함수 시작 시점 초기화 (절대 중간에 None으로 덮어쓰지 말 것)
    upload_row_id = None
    sign_layout_id = None
    meta_bundle = None

    # ✅ pop 전에 끝까지 사용할 info_get
    info_get = None

    # --------------------------------------------------------------
    # ✅ HELPER: photo_1 경로 안전 처리
    # - 파일명만 허용(경로 탈출 방지)
    # - 실제 파일 존재할 때만 반환
    # --------------------------------------------------------------
    def _safe_photo_abs(photo_filename: str) -> str | None:
        if not photo_filename:
            return None

        # 파일명만 허용 (경로 포함 금지)
        base = os.path.basename(photo_filename)
        if base != photo_filename:
            return None
        if any(x in base for x in ("..", "/", "\\")):
            return None

        upload_folder = current_app.config.get("SIGN_BASE_DIR")  # ✅ 여기서 전역 설정 읽기
        if not upload_folder:
            return None

        abs_path = os.path.join(upload_folder, base)
        return abs_path if os.path.isfile(abs_path) else None

    try:
        # --------------------------------------------------------------
        # 1) 기본 파라미터 파싱
        # --------------------------------------------------------------
        upload_id = int(js["upload_id"])
        page = int(js.get("page", 1))
        device_id = js["device_id"]

        width = int(js.get("width") or 1200)
        height = int(js.get("height") or 1600)
        mode = js.get("mode") or "BWRYBG"
        scale = js.get("scale") or "fit"
        percent = int(js.get("percent") or 100)
        rotate = int(js.get("rotate") or 0)

        # ✅ 여기서 info_get 잡기 (아직 pop 금지)
        info_get = get_upload_store().get(upload_id)

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

        need_approval = bool(approval_meta.get("use", False))
        final_approval = bool(js.get("final_approval", False))
        route_id = js.get("route_id")

        columns = approval_meta.get("columns") or []
        if not isinstance(columns, list):
            columns = []

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

        # --------------------------------------------------------------
        # ✅ (핵심) sendfile 시점에만: 작성자 photo_1 -> columns 주입
        # - 프리뷰에서는 안 찍힘
        # - sendfile 눌렀을 때 생성되는 BMP에만 반영됨
        # --------------------------------------------------------------
        try:
            # 로그인 사용자 photo_1 파일명
            photo_1 = getattr(current_user, "photo_1", None) or getattr(getattr(g, "user", None), "photo_1", None)
            photo_abs = _safe_photo_abs(photo_1) if photo_1 else None

            if photo_abs and columns:
                me = int(current_user_id())
                injected = 0

                # 정책: draft 그룹의 role=="작성" 칸에 작성자 도장 주입
                for c in columns:
                    group = (c.get("group") or "").strip()
                    role = (c.get("role") or "").strip()

                    if group == "draft" and role == "작성":
                        c["user_id"] = me
                        c["user_photo_1"] = os.path.basename(photo_1)  # ✅ 파일명만 (경로 노출 최소화)
                        injected += 1

                # columns를 meta에도 다시 반영
                approval_meta["columns"] = columns
                meta["approval"] = approval_meta

                # ✅ convert_editor_layers_to_render_layers()는 approval_box["columns"]를 읽으므로 동기화 필수
                if approval_box is not None:
                    approval_box["columns"] = columns

                dbg("sendfile:inject_photo_1", ok=True, injected=injected, photo=os.path.basename(photo_1))
            else:
                dbg("sendfile:inject_photo_1", ok=False, reason="no photo or no columns")
        except Exception:
            current_app.logger.debug("[sendfile] inject photo_1 failed", exc_info=True)

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

    # ✅ 여기서 convert 실행 -> signbox slots에 user_photo_1이 실리게 됨(위에서 columns에 주입했기 때문)
    render_layers = convert_editor_layers_to_render_layers(layers)

    # --------------------------------------------------------------
    # 6) 이미지 렌더링 (base → merged → quantize)
    # --------------------------------------------------------------
    im_src = svc.load_upload_image(upload_id, page=page)
    if rotate in (90, 180, 270):
        im_src = im_src.rotate(rotate, expand=True)

    base_canvas = svc._place_into_canvas(
        im_src, width, height,
        mode=scale,
        percent=percent
    )  # RGB

    merged_rgb = apply_layers_to_image(base_canvas, width, height, render_layers)  # RGB

    mode_up = (mode or "BW").upper()
    if mode_up == "BWRY":
        final_im = svc.quantize_to_BWRY(merged_rgb)
        fmt = "BWRY"
    elif mode_up in ("BWRYBG", "SPECTRA6", "COLOR6"):
        final_im = svc.quantize_to_BWRYBG(merged_rgb)
        fmt = "BWRYBG"
    else:
        final_im = svc.quantize_to_BW(merged_rgb)
        fmt = "BW"

    # --------------------------------------------------------------
    # 6-1) dir/bucket/path 계산
    # --------------------------------------------------------------
    # target_dir = decide_target_dir(need_approval, final_approval)
    asset_dir = decide_target_dir(need_approval, final_approval)
    
    doc_bucket = decide_doc_bucket(need_approval)
    userid_str = current_userid_str()

    bmp_path, meta_path, hdr_path, bin_path = asset_paths(
        device_id, width, height, fmt, asset_dir, userid=userid_str
    )

    # --------------------------------------------------------------
    # 6-2) DB status / route_snapshot / metadata
    # --------------------------------------------------------------
    # db_status = (
    #     "bulletin_files"
    #     if target_dir in ("uploads", "bulletin_files")
    #     else "approved"
    #     if target_dir == "approved"
    #     else "checked"
    #     if target_dir == "checked"
    #     else "in_review"
    # )

    # if target_dir == "bulletin_files":
    #     db_status = "bulletin_files"
    # elif target_dir == "approved":
    #     db_status = "approved"
    # elif target_dir == "checked":
    #     db_status = "checked"
    # else:
    #     db_status = "in_review"


    # --- B안: DocumentInfo.status는 큰 상태만 ---
    if need_approval:
        # 결재 흐름이면 무조건 in_review에서 시작 (단계는 Step으로 계산)
        doc_status = "approved" if final_approval else "in_review"
        doc_target_dir = "approved" if final_approval else "in_review"
    else:
        # 결재 없이 게시면 bulletin_files로 고정 (큰 상태)
        doc_status = "bulletin_files"
        doc_target_dir = "bulletin_files"

    route_snapshot = {"route_id": route_id, "assignees": assignees} if route_id else None

    metadata = {
        "meta": meta,
        "memo": memo,
        "assignees": assignees,
    }

    orig_filename = (info_get.get("name") if info_get else None) or os.path.basename(bmp_path)
    temp_path = info_get.get("path") if info_get else None

    current_app.logger.debug(f"ORIN_FILENAME: {orig_filename}")
    current_app.logger.debug(f"temp_path: {temp_path}")

    # --------------------------------------------------------------
    # 6-3) DocumentInfo 생성 (DB는 1회만!)
    # --------------------------------------------------------------
    if RepositoryEINK is not None:
        try:
            upload_row_id = RepositoryEINK.create_upload_record(
                user_id=current_user_id(),
                device_id=device_id,
                orig_filename=orig_filename,
                stored_path="",                 # doc_dir은 뒤에서 채움
                target_dir=doc_target_dir,      # ✅ 문서 큰 상태 기준
                need_approval=need_approval,
                status=doc_status,              # ✅ 문서 큰 상태만
                pages=1,
                width=width,
                height=height,
                mode=fmt,
                scale=scale,
                percent=percent,
                rotate=rotate,
                route_id=route_id,
                sign_layout_id=None,
                route_snapshot=route_snapshot,
                layout_snapshot=layout_snapshot,
                metadata=metadata,
            )

        except Exception:
            current_app.logger.debug("[sendfile][DB] create_upload_record failed", exc_info=True)
            upload_row_id = None

    # --------------------------------------------------------------
    # 6-4) 디바이스 배포용 저장 (BMP/BIN/meta.json)
    # --------------------------------------------------------------
    payload, meta_bundle = save_meta_bundle(
        im=final_im,
        fmt=fmt,
        size=(width, height),
        bmp_path=bmp_path,
        bin_path=bin_path,
        meta_path=meta_path,
        device_id=device_id,
        target_dir=asset_dir,           # ✅ 에셋 dir
        need_approval=need_approval,
        final_approval=final_approval,
        route_id=route_id,
        assignees=assignees,
        doc_id=upload_row_id,
        upload_row_id=upload_row_id,
    )

    # --------------------------------------------------------------
    # 6-5) 문서 마스터 저장 (doc_id가 있어야 하므로 DB 이후)
    # --------------------------------------------------------------
    if upload_row_id:
        doc_paths = None
        try:
            payload2, onelayer_meta, doc_paths = save_doc_master_bundle(
                userid=userid_str,
                doc_id=upload_row_id,
                bucket=doc_bucket,

                im=final_im,
                fmt=fmt,
                size=(width, height),
                device_id=device_id,
                upload_temp_path=temp_path,
                orig_filename=orig_filename,
                normalized_pdf_path=None,
                layout_snapshot=layout_snapshot,
                metadata=metadata,

                preview_base_im=base_canvas,
                # preview_merged_im=final_im,
                preview_merged_im=merged_rgb,  # ✅ 프론트와 동일(레이어 합성 직후 RGB)

                need_approval=need_approval,
                final_approval=final_approval,
                route_id=route_id,
                assignees=assignees,
            )

            doc_dir = (doc_paths or {}).get("doc_dir")
            if doc_dir:
                RepositoryEINK.update_upload_status(
                    upload_row_id,
                    stored_path=doc_dir,
                )

        except Exception:
            current_app.logger.debug("[sendfile][DocMaster] save_doc_master_bundle failed", exc_info=True)

    # --------------------------------------------------------------
    # 6-6) layout_snapshot → SignLayout + 결재 Steps/Slots
    # --------------------------------------------------------------
    if upload_row_id and RepositoryEINK is not None:
        try:
            args_for_layout = snapshot_to_signlayout_args(layout_snapshot) if layout_snapshot else None
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

                dbg("sendfile:sign_layout_saved", sign_layout_id=sign_layout_id, canvas=f"{args_for_layout['canvas_w']}x{args_for_layout['canvas_h']}")

                RepositoryEINK.update_upload_status(upload_row_id, sign_layout_id=sign_layout_id)

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
            current_app.logger.debug("[sendfile][DB] sign_layout/steps/slots failed", exc_info=True)

    # --------------------------------------------------------------
    # 7) 업로드 임시파일 정리 (마지막에 pop)
    # --------------------------------------------------------------
    # info_pop = get_upload_store().pop(upload_id, None)
    # if info_pop:
    #     try:
    #         path = info_pop.get("path")
    #         if path and os.path.isfile(path):
    #             os.remove(path)
    #             dbg("sendfile:cleanup_temp", path=path, removed=True)
    #         else:
    #             dbg("sendfile:cleanup_temp", path=path, removed=False)
    #     except Exception:
    #         current_app.logger.debug("[CLEANUP] temp delete failed", exc_info=True)



    info_pop = get_upload_store().pop(upload_id, None)
    if info_pop:
        try:
            path = info_pop.get("path")

            if not path:
                dbg("sendfile:cleanup_temp", path=None, removed=False)
            else:
                # ✅ path가 파일이면: 그 파일이 들어있는 폴더를 삭제
                # ✅ path가 폴더면: 그 폴더를 삭제
                dir_to_delete = path
                if os.path.isfile(path):
                    dir_to_delete = os.path.dirname(path)

                # 안전: 너무 상위 폴더 지우는 실수 방지(uploads 바로 아래까지만 허용)
                # 예: .../uploads/3 까지만 삭제하도록 최소 조건 체크
                dir_norm = os.path.normpath(dir_to_delete)
                base_name = os.path.basename(dir_norm)  # "3"
                parent_name = os.path.basename(os.path.dirname(dir_norm))  # "uploads" 기대

                if parent_name.lower() != "uploads" or not base_name.isdigit():
                    dbg("sendfile:cleanup_temp", path=path, removed=False, reason="unsafe_target")
                else:
                    if os.path.isdir(dir_norm):
                        shutil.rmtree(dir_norm)
                        dbg("sendfile:cleanup_temp_dir", dir=dir_norm, removed=True)
                    else:
                        dbg("sendfile:cleanup_temp_dir", dir=dir_norm, removed=False)

        except Exception:
            current_app.logger.debug("[CLEANUP] temp dir delete failed", exc_info=True)


    # --------------------------------------------------------------
    # 8) 응답
    # --------------------------------------------------------------
    job_id = int(time.time() * 1000)

    dbg(
        "sendfile:response",
        status="prepared",
        job_id=job_id,
        device_id=device_id,
        dir=asset_dir,
        file=os.path.basename(bmp_path),
        upload_row_id=upload_row_id,
        sign_layout_id=sign_layout_id,
    )

    return jsonify(
        {
            "status": "prepared",
            "job_id": job_id,
            "device_id": device_id,
            "dir": asset_dir,            # ✅ 에셋 dir
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
    is_author = (doc.user_id == user_no)

    is_approver = False
    for slot in getattr(doc, "sign_slots", []):
        if slot.target_user_id == user_no or slot.filled_by_id == user_no:
            is_approver = True
            break

    if not is_approver:
        for step in getattr(doc, "approval_steps", []):
            if step.signed_by_user_id == user_no:
                is_approver = True
                break
            if step.userid_snapshot and step.userid_snapshot == userid:
                is_approver = True
                break
            if cur_username and step.username_snapshot and step.username_snapshot == cur_username:
                is_approver = True
                break
            if cur_dept and step.dept_snapshot and step.dept_snapshot == cur_dept:
                is_approver = True
                break

    if not (is_author or is_approver):
        abort(403, "문서를 볼 권한이 없습니다.")

    # ------------------------------------------------------------
    # ✅ doc master 경로 기준으로 파일 존재 여부를 계산해서 files dict 구성
    #    ★ stored_path는 폴더/파일/상대경로 등 다양하므로 반드시 정규화
    # ------------------------------------------------------------
    doc_dir = _resolve_doc_dir_from_stored_path(getattr(doc, "stored_path", "") or "")

    files = {
        "doc_dir": doc_dir,

        # ✅ 다운로드 (bin 제거 원하면 아래 onelayer_bin 관련도 지우면 됨)
        "original": None,              # original.*
        "preview_merged": None,        # preview_merged.png
        "normalized_pdf": None,        # normalized.pdf
        "onelayer_bmp": None,          # onelayer.bmp
        # "onelayer_bin": None,          # onelayer.bin (원하면 유지/삭제)
    }

    # 파일명 대소문자 꼬임까지 대응하고 싶으면 glob로 잡는 게 안전
    def _exists_case_insensitive(name: str) -> str | None:
        if not doc_dir or not os.path.isdir(doc_dir):
            return None
        # 정확히 있으면 바로
        p = os.path.join(doc_dir, name)
        if os.path.isfile(p):
            return name
        # 대소문자/확장자 차이 대응
        cands = glob.glob(os.path.join(doc_dir, name))
        if cands:
            return os.path.basename(cands[0])
        # 완전 case-insensitive 탐색(윈도우면 거의 필요없지만, 서버/마운트 환경 대비)
        low = name.lower()
        for fn in os.listdir(doc_dir):
            if fn.lower() == low:
                return fn
        return None

    if doc_dir and os.path.isdir(doc_dir):
        # 1) original.* (파일명 그대로)
        originals = sorted(glob.glob(os.path.join(doc_dir, "original.*")))
        if originals:
            files["original"] = os.path.basename(originals[0])
        else:
            # fallback: DB orig_filename이 doc_dir에 그대로 있을 수도 있으니 체크
            if doc.orig_filename:
                cand = os.path.join(doc_dir, os.path.basename(doc.orig_filename))
                if os.path.isfile(cand):
                    files["original"] = os.path.basename(cand)

        # 2) preview_merged.png
        files["preview_merged"] = _exists_case_insensitive("preview_merged.png")

        # 3) normalized.pdf
        files["normalized_pdf"] = _exists_case_insensitive("normalized.pdf")

        # 4) onelayer.bmp
        files["onelayer_bmp"] = _exists_case_insensitive("onelayer.bmp")

        # 5) onelayer.bin (형이 안 쓴다 했으면 아래 2줄 삭제해도 됨)
        # files["onelayer_bin"] = _exists_case_insensitive("onelayer.bin")

    # 4-1) 현재 pending step 계산 (첫 번째 미서명 step)
    steps = list(getattr(doc, "approval_steps", []) or [])

    def _step_key(s):
        for k in ("step_order", "col_index", "id"):
            v = getattr(s, k, None)
            if v is not None:
                return int(v)
        return 10**9

    unsigned = [s for s in steps if not getattr(s, "signed_by_user_id", None)]
    pending_step = sorted(unsigned, key=_step_key)[0] if unsigned else None

    current_col_index = None
    if pending_step is not None:
        current_col_index = getattr(pending_step, "col_index", None) or getattr(pending_step, "step_order", None)

    # ✅ 미리보기용 URL (inline=1) - 실제 파일명(files에 들어간 값) 사용
    preview_merged_inline_url = (
        url_for("bulletin.file_download", doc_id=doc.id, fname=files["preview_merged"], inline=1)
        if files["preview_merged"] else None
    )
    onelayer_bmp_inline_url = (
        url_for("bulletin.file_download", doc_id=doc.id, fname=files["onelayer_bmp"], inline=1)
        if files["onelayer_bmp"] else None
    )

    current_app.logger.debug("[detail] doc.id=%s status=%s stored_path=%r doc_dir=%r",
                             doc.id, doc.status, doc.stored_path, doc_dir)
    current_app.logger.debug("[detail] files=%s", files)

    return render_template(
        "bulletinboard/e_file_detail.html",
        doc=doc,
        files=files,

        preview_merged_inline_url=preview_merged_inline_url,
        onelayer_bmp_inline_url=onelayer_bmp_inline_url,

        pending_step=pending_step,
        current_col_index=current_col_index,
    )





def _resolve_doc_dir_from_stored_path(stored_path: str) -> str:
    """
    stored_path 가
    - 폴더 경로 (권장)
    - 파일 경로 (구형)
    - 상대경로 (userid/approval_process/doc_id 또는 .../fname)
    어떤 형태든 최종적으로 "문서 폴더 절대경로"로 정규화한다.
    """
    if not stored_path:
        return ""

    p = os.path.normpath(stored_path)

    # 1) 상대경로면 루트 붙여서 먼저 절대경로로 만든다 (중요!)
    if not os.path.isabs(p):
        base = current_app.config.get("EINK_DOC_ROOT") or os.path.normpath(os.path.join("D:/", "eink_docs"))
        p = os.path.normpath(os.path.join(base, p))

    # 2) 이제 절대경로 기준으로 파일이면 dirname 처리
    #    (상대 파일경로였던 케이스도 여기서 정상 판정됨)
    if os.path.isfile(p):
        p = os.path.dirname(p)

    # 3) 그래도 파일 확장자가 있고, 폴더가 아니라면 "파일경로로 간주"해서 dirname 처리
    #    (파일이 아직 생성 전이거나, 파일 존재 체크가 애매한 케이스 방어)
    if (not os.path.isdir(p)) and os.path.splitext(p)[1]:
        p2 = os.path.dirname(p)
        if p2 and os.path.isdir(p2):
            p = p2

    return p



def _pick_original_filename(doc_dir: str) -> str | None:
    """
    doc_dir 아래 original.* (original.pdf/original.pptx 등) 중 1개 선택
    """
    if not doc_dir or not os.path.isdir(doc_dir):
        return None
    cands = sorted(glob.glob(os.path.join(doc_dir, "original.*")))
    return os.path.basename(cands[0]) if cands else None


def _exists_in_doc_dir(doc_dir: str, fname: str) -> str | None:
    """
    doc_dir/fname 존재하면 fname 반환, 아니면 None
    """
    if not doc_dir:
        return None
    p = os.path.join(doc_dir, fname)
    return fname if os.path.isfile(p) else None


@bp.route("/files/<int:doc_id>/download/<path:fname>", methods=["GET"])
@login_required
def file_download(doc_id: int, fname: str):
    if RepositoryEINK is None:
        abort(500, "RepositoryEINK is not available")

    doc: DocumentInfo = DocumentInfo.query.get_or_404(doc_id)

    # --- 권한 체크(형 코드 유지) ---
    user_no, userid = current_user_ids()
    cur_username = getattr(current_user, "username", None)
    cur_dept     = getattr(current_user, "department", None)

    is_author = (doc.user_id == user_no)

    is_approver = False
    for slot in getattr(doc, "sign_slots", []):
        if slot.target_user_id == user_no or slot.filled_by_id == user_no:
            is_approver = True
            break

    if not is_approver:
        for step in getattr(doc, "approval_steps", []):
            if step.signed_by_user_id == user_no:
                is_approver = True
                break
            if step.userid_snapshot and step.userid_snapshot == userid:
                is_approver = True
                break
            if cur_username and step.username_snapshot and step.username_snapshot == cur_username:
                is_approver = True
                break
            if cur_dept and step.dept_snapshot and step.dept_snapshot == cur_dept:
                is_approver = True
                break

    if not (is_author or is_approver):
        abort(403, "문서를 볼 권한이 없습니다.")

    # ✅ stored_path -> 문서 마스터 폴더
    doc_dir = _resolve_doc_dir_from_stored_path(getattr(doc, "stored_path", "") or "")
    original_name = _pick_original_filename(doc_dir)

    # --- 여기서부터 디버그 로그 (404 원인 추적용) ---
    current_app.logger.debug("[download] doc_id=%s fname=%r stored_path=%r", doc_id, fname, doc.stored_path)
    current_app.logger.debug("[download] doc_dir=%r isdir=%s original_name=%r", doc_dir, os.path.isdir(doc_dir), original_name)

    if not doc_dir or not os.path.isdir(doc_dir):
        abort(404, "document directory not found")

    allowed = _is_allowed_download_name(fname, original_name)
    current_app.logger.debug("[download] allowed=%s", allowed)
    if not allowed:
        abort(404)

    abs_path = os.path.join(doc_dir, fname)
    current_app.logger.debug("[download] abs_path=%r exists=%s", abs_path, os.path.isfile(abs_path))
    if not os.path.isfile(abs_path):
        abort(404)

    inline = request.args.get("inline") == "1"
    return send_from_directory(doc_dir, fname, as_attachment=(not inline))



@bp.route("/files/<int:doc_id>/onelayer", methods=["GET"])
@login_required
def file_onelayer(doc_id: int):
    doc: DocumentInfo = DocumentInfo.query.get_or_404(doc_id)

    # ✅ detail과 동일한 권한 체크 로직을 재사용하거나 여기에도 동일 적용(권장: 함수로 분리)
    user_no, userid = current_user_ids()
    cur_username = getattr(current_user, "username", None)
    cur_dept     = getattr(current_user, "department", None)

    is_author = (doc.user_id == user_no)

    is_approver = False
    for slot in getattr(doc, "sign_slots", []):
        if slot.target_user_id == user_no or slot.filled_by_id == user_no:
            is_approver = True
            break

    if not is_approver:
        for step in getattr(doc, "approval_steps", []):
            if step.signed_by_user_id == user_no:
                is_approver = True
                break
            if step.userid_snapshot and step.userid_snapshot == userid:
                is_approver = True
                break
            if cur_username and step.username_snapshot == cur_username:
                is_approver = True
                break
            if cur_dept and step.dept_snapshot == cur_dept:
                is_approver = True
                break

    if not (is_author or is_approver):
        abort(403, "문서를 볼 권한이 없습니다.")

    return jsonify({
        "ok": True,
        "doc_id": doc.id,
        "layout_snapshot": doc.layout_snapshot_json or {},
        "metadata": doc.metadata_json or {},
        "status": doc.status,
        "target_dir": doc.target_dir,
    })

############################################################
#########################  STAMP ###########################
############################################################

def _stamp_dir() -> Path:
    d = current_app.config.get("STAMP_DIR", STAMP_DIR_DEFAULT)
    p = Path(d)
    p.mkdir(parents=True, exist_ok=True)
    return p

def _allowed_stamp(filename: str) -> bool:
    ext = (filename.rsplit(".", 1)[-1].lower() if "." in filename else "")
    return ext in ("png", "jpg", "jpeg", "webp")

@bp.route("/admin/stamps", methods=["GET"])
@login_required
def stamp_register_form():
    if RepositoryEINK is None:
        abort(500, "RepositoryEINK is not available")

    stamps = RepositoryEINK.list_stamp_assets(active_only=False)
    return render_template("bulletinboard/register_form.html", stamps=stamps)

@bp.route("/admin/stamps", methods=["POST"])
@login_required
def stamp_register_post():
    if RepositoryEINK is None:
        abort(500, "RepositoryEINK is not available")

    name = (request.form.get("name") or "").strip()
    f = request.files.get("stamp_file")

    if not name:
        abort(400, "name is required")
    if not f or not f.filename:
        abort(400, "stamp_file is required")
    if not _allowed_stamp(f.filename):
        abort(400, "Only png/jpg/jpeg/webp allowed")

    # 저장 파일명
    safe = secure_filename(f.filename)
    ext = safe.rsplit(".", 1)[-1].lower()
    out_name = f"stamp_{uuid.uuid4().hex}.{ext}"
    out_path = _stamp_dir() / out_name

    # 저장
    f.save(str(out_path))

    # 이미지 메타(가급적 PNG 권장)
    w = h = None
    mime = f.mimetype
    try:
        with Image.open(str(out_path)) as im:
            w, h = im.size
    except Exception:
        current_app.logger.debug("[Stamp] image open failed", exc_info=True)

    stamp_id = RepositoryEINK.create_stamp_asset(
        name=name,
        filename=out_name,
        stored_path=str(out_path),
        created_by=current_user_id(),   # 형 프로젝트 함수로 교체
        mime=mime,
        width=w,
        height=h,
    )

    return redirect(url_for("bulletin.stamp_register_form"))  # bp 이름에 맞게 수정

@bp.route("/api/stamps", methods=["GET"])
@login_required
def api_list_stamps():
    if RepositoryEINK is None:
        return jsonify({"stamps": []})

    stamps = RepositoryEINK.list_stamp_assets(active_only=True)
    data = []
    for s in stamps:
        data.append({
            "id": int(s.id),
            "name": s.name,
            "width": s.width,
            "height": s.height,
            "url": url_for("bulletin.stamp_image", stamp_id=int(s.id)),  # endpoint 수정 필요
        })
    return jsonify({"stamps": data})

@bp.route("/stamps/<int:stamp_id>/image", methods=["GET"])
@login_required
def stamp_image(stamp_id: int):
    if RepositoryEINK is None:
        abort(404)

    s = RepositoryEINK.get_stamp_asset(stamp_id)
    if not s:
        abort(404)

    path = s.stored_path
    if not path or not os.path.isfile(path):
        abort(404)

    return send_file(path, as_attachment=False)

