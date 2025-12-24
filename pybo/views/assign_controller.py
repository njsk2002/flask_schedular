# pybo/views/assign_controller.py

from flask import Blueprint, render_template, request, redirect, url_for, jsonify, flash, current_app
from sqlalchemy.exc import IntegrityError

from pybo import db
from ..models import EInkCompany, EInkBuilding, EInkBoard, EInkDevice, EInkBoardBinding
from ..repository.repository_assign import RepositoryAssign as R

# 로그인 쓰는 경우 (형 프로젝트에 이미 있다면 활성화)
from flask_login import login_required, current_user

bp = Blueprint("assign", __name__, url_prefix="/assign")


def _current_user_no():
    # 형 프로젝트에서 current_user PK 필드가 no/id 중 뭐든 대응
    return getattr(current_user, "no", None) or getattr(current_user, "id", None)


def _current_user_userid():
    return getattr(current_user, "userid", None) or getattr(current_user, "user_id", None)


@bp.route("", methods=["GET"])
# @login_required   # 관리자만 접근이면 나중에 붙이기
def assign_home():
    companies = EInkCompany.query.order_by(EInkCompany.name.asc()).all()

    buildings = (
        EInkBuilding.query
        .order_by(EInkBuilding.id.desc())
        .limit(50)
        .all()
    )

    boards = (
        EInkBoard.query
        .order_by(EInkBoard.id.desc())
        .limit(30)
        .all()
    )

    devices = (
        EInkDevice.query
        .order_by(EInkDevice.id.desc())
        .limit(50)
        .all()
    )

    # ✅ 디바이스 목록에 "현재 바인딩"을 표시하려면 맵으로 같이 내려주기
    device_ids = [d.id for d in devices]
    device_active_bind_map = R.map_active_binding_for_devices(device_ids)

    return render_template(
        "bulletinboard/e_assign_register.html",
        companies=companies,
        buildings=buildings,
        boards=boards,
        devices=devices,   # 탭3에서 사용
        device_active_bind_map=device_active_bind_map,  # ✅ 추가
    )


@bp.route("/companies", methods=["POST"])
# @login_required
def company_register_post():
    name = (request.form.get("company_name") or "").strip()
    code = (request.form.get("company_code") or "").strip()

    if not name:
        flash("회사명은 필수야.", "warning")
        return redirect(url_for("assign.assign_home"))
    if not code:
        flash("회사코드는 필수야. (예: ICE)", "warning")
        return redirect(url_for("assign.assign_home"))

    try:
        R.create_company(name=name, code=code)
        flash("회사 등록 완료", "success")
    except IntegrityError:
        db.session.rollback()
        flash("회사명 또는 회사코드가 이미 존재해.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.debug("[company_register_post] failed", exc_info=True)
        flash(f"회사 등록 실패: {e}", "danger")

    return redirect(url_for("assign.assign_home"))


@bp.route("/buildings", methods=["POST"])
# @login_required
def building_register_post():
    company_id = (request.form.get("company_id") or "").strip()
    bname = (request.form.get("building_name") or "").strip()
    bcode = (request.form.get("building_code") or "").strip()
    addr = (request.form.get("building_address") or "").strip()

    if not company_id.isdigit():
        flash("회사 선택이 필요해.", "warning")
        return redirect(url_for("assign.assign_home"))
    if not bname:
        flash("건물명은 필수야.", "warning")
        return redirect(url_for("assign.assign_home"))
    if not bcode:
        flash("건물코드는 필수야. (예: B01)", "warning")
        return redirect(url_for("assign.assign_home"))

    try:
        R.create_building(company_id=int(company_id), name=bname, code=bcode, address=addr)
        flash("건물 등록 완료", "success")
    except IntegrityError:
        db.session.rollback()
        flash("같은 회사 내 건물명이 이미 존재하거나 코드 충돌이 있어.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.debug("[building_register_post] failed", exc_info=True)
        flash(f"건물 등록 실패: {e}", "danger")

    return redirect(url_for("assign.assign_home"))


@bp.route("/api/buildings", methods=["GET"])
def api_buildings():
    company_id = (request.args.get("company_id") or "").strip()
    if not company_id.isdigit():
        return jsonify({"buildings": []})

    rows = (
        EInkBuilding.query
        .filter(EInkBuilding.company_id == int(company_id))
        .order_by(EInkBuilding.name.asc())
        .all()
    )
    return jsonify({
        "buildings": [
            {"id": b.id, "name": b.name, "code": b.code or ""}
            for b in rows
        ]
    })


@bp.route("/boards", methods=["POST"])
# @login_required
def board_register_post():
    form = request.form

    company_id = (form.get("company_id") or "").strip()
    building_id = (form.get("building_id") or "").strip()

    site_code = (form.get("site_code") or "HQ").strip()
    floor_no_raw = (form.get("floor_no") or "1").strip()
    board_no_raw = (form.get("board_no") or "").strip()
    name = (form.get("name") or "").strip()
    location_desc = (form.get("location_desc") or "").strip()

    if not company_id.isdigit():
        flash("회사 선택이 필요해.", "warning")
        return redirect(url_for("assign.assign_home"))
    if not building_id.isdigit():
        flash("건물 선택이 필요해.", "warning")
        return redirect(url_for("assign.assign_home"))
    if not name:
        flash("게시판 이름(name)은 필수야.", "warning")
        return redirect(url_for("assign.assign_home"))

    try:
        floor_no = int(floor_no_raw)
    except Exception:
        flash("floor_no 값이 올바르지 않아.", "warning")
        return redirect(url_for("assign.assign_home"))

    board_no = None
    if board_no_raw:
        try:
            board_no = int(board_no_raw)
        except Exception:
            flash("board_no 값이 올바르지 않아.", "warning")
            return redirect(url_for("assign.assign_home"))

    try:
        board = R.create_board_by_selection(
            company_id=int(company_id),
            building_id=int(building_id),
            site_code=site_code,
            floor_no=floor_no,
            board_no=board_no,
            name=name,
            location_desc=location_desc,
        )
        flash(f"등록 완료: {board.board_code}", "success")
    except IntegrityError:
        db.session.rollback()
        flash("중복(UNIQUE) 충돌: 같은 건물/층/번호 또는 board_code가 이미 존재해.", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.debug("[board_register_post] failed", exc_info=True)
        flash(f"등록 실패: {e}", "danger")

    return redirect(url_for("assign.assign_home"))


# ============================================================
# TAB 3) Device register / Bind / Unbind
# ============================================================

@bp.route("/devices", methods=["POST"])
@login_required
def device_register_post():
    form = request.form

    company_id_raw = (form.get("company_id") or "").strip()
    device_id = (form.get("device_id") or "").strip()
    device_name = (form.get("device_name") or "").strip()
    panel_res = (form.get("panel_res") or "").strip()
    bpp_raw = (form.get("bpp") or "4").strip()
    cap = (form.get("cap") or "BWR").strip()

    # hidden(있으면 받고), 없으면 current_user 사용
    user_no_raw = (form.get("user_no") or "").strip()
    user_userid_raw = (form.get("user_userid") or "").strip()

    if not company_id_raw.isdigit():
        flash("회사 선택이 필요해.", "warning")
        return redirect(url_for("assign.assign_home"))
    if not device_id:
        flash("device_id는 필수야.", "warning")
        return redirect(url_for("assign.assign_home"))
    # ✅ 형 요구: device_name 필수
    if not device_name:
        flash("device_name은 필수야.", "warning")
        return redirect(url_for("assign.assign_home"))
    if not panel_res:
        flash("panel_res는 필수야.", "warning")
        return redirect(url_for("assign.assign_home"))

    try:
        bpp = int(bpp_raw)
    except Exception:
        flash("bpp 값이 올바르지 않아.", "warning")
        return redirect(url_for("assign.assign_home"))

    # ✅ 보안/무결성: hidden으로 왔다 해도 서버는 current_user로 확정(권장)
    user_no = _current_user_no()
    user_userid = _current_user_userid()

    # 만약 current_user가 없거나(관리자 로그인 미적용 상태)라면 hidden을 fallback
    if user_no is None and user_no_raw.isdigit():
        user_no = int(user_no_raw)
    if not user_userid and user_userid_raw:
        user_userid = user_userid_raw

    try:
        dev = R.create_device(
            company_id=int(company_id_raw),
            device_id=device_id,
            device_name=device_name,
            panel_res=panel_res,
            bpp=bpp,
            cap=cap,
            user_no=user_no,
            user_userid=user_userid,
        )
        flash(f"디바이스 등록 완료: {dev.device_id}", "success")
    except IntegrityError:
        db.session.rollback()
        flash("device_id가 이미 존재해(UNIQUE).", "danger")
    except Exception as e:
        db.session.rollback()
        current_app.logger.debug("[device_register_post] failed", exc_info=True)
        flash(f"디바이스 등록 실패: {e}", "danger")

    return redirect(url_for("assign.assign_home"))


@bp.route("/api/boards", methods=["GET"])
def api_boards():
    """
    회사 선택 후, 해당 회사의 boards 목록 (board_code + name)
    """
    company_id = (request.args.get("company_id") or "").strip()
    if not company_id.isdigit():
        return jsonify({"boards": []})

    rows = R.list_boards_by_company(int(company_id))
    return jsonify({"boards": rows})


@bp.route("/api/devices", methods=["GET"])
def api_devices():
    """
    ✅ 이미 바인딩된(device_id가 unbound_at IS NULL) 디바이스는 제외해서 반환
    """
    company_id = (request.args.get("company_id") or "").strip()
    if not company_id.isdigit():
        return jsonify({"devices": []})

    rows = R.list_unbound_devices_by_company(int(company_id))
    return jsonify({"devices": rows})

@bp.route("/api/board-bindings", methods=["GET"])
def api_board_bindings():
    board_id = (request.args.get("board_id") or "").strip()
    if not board_id.isdigit():
        return jsonify({"bindings": []})

    rows = R.list_active_devices_by_board(int(board_id))
    # rows: [{"binding_id","device_pk","device_id","device_name","panel_res","bound_at","reason"}, ...]
    return jsonify({"bindings": rows})

@bp.route("/bind", methods=["POST"])
@login_required
def bind_register_post():
    board_id_raw = (request.form.get("board_id") or "").strip()
    device_id_raw = (request.form.get("device_id") or "").strip()
    reason = (request.form.get("reason") or "").strip()

    if not board_id_raw.isdigit():
        flash("게시판 선택이 필요해.", "warning")
        return redirect(url_for("assign.assign_home"))
    if not device_id_raw.isdigit():
        flash("디바이스 선택이 필요해.", "warning")
        return redirect(url_for("assign.assign_home"))

    user_no = _current_user_no()

    try:
        R.bind_board_device(
            board_id=int(board_id_raw),
            device_pk=int(device_id_raw),
            reason=reason,
            # ✅ 형 요구: bound_by_user_no 저장
            bound_by_user_no=user_no,
            auto_unbind=True,
        )
        flash("연결(Bind) 완료", "success")

    except IntegrityError:
        db.session.rollback()
        current_app.logger.debug("[bind] IntegrityError", exc_info=True)
        flash("연결 중 UNIQUE 충돌이 발생했어.", "danger")

    except Exception as e:
        db.session.rollback()
        current_app.logger.debug("[bind] failed", exc_info=True)
        flash(f"연결 실패: {e}", "danger")

    return redirect(url_for("assign.assign_home"))


@bp.route("/unbind", methods=["POST"])
@login_required
def unbind_register_post():
    board_id_raw = (request.form.get("board_id") or "").strip()
    reason = (request.form.get("reason") or "").strip()

    if not board_id_raw.isdigit():
        flash("Board 선택이 필요해.", "warning")
        return redirect(url_for("assign.assign_home"))

    user_no = _current_user_no()

    try:
        changed = R.unbind_by_board(
            board_id=int(board_id_raw),
            reason=reason,
            unbound_by_user_no=user_no,
        )
        if changed:
            flash("연결 해제(Unbind) 완료", "success")
        else:
            flash("현재 활성 연결이 없어(이미 해제 상태).", "warning")
    except Exception as e:
        db.session.rollback()
        current_app.logger.debug("[unbind] failed", exc_info=True)
        flash(f"해제 실패: {e}", "danger")

    return redirect(url_for("assign.assign_home"))
