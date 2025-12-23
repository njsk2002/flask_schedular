# repository/repository_eink.py
from __future__ import annotations

from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc, or_, and_,asc
from sqlalchemy.orm import joinedload
from pybo import db
import json
import os
import logging, inspect


try:
    # Flask 컨텍스트가 있으면 current_app 로거 사용
    from flask import current_app
except Exception:  # pragma: no cover
    current_app = None  # type: ignore

# === 모델 임포트 (형이 준 models.py 기준) ===
from ..models import (
    User,
    DocumentInfo as DocumentInfoModel,
    SignLayout as SignLayoutModel,
    # ApprovalRoute as ApprovalRouteModel,
    # ApprovalRouteStep as ApprovalRouteStepModel,
    SignSlot as SignSlotModel,
    DocumentApprovalStep as DocumentApprovalStepModel,
    StampAsset,
    kst_now_naive as now_kst,
)

# (프로젝트 내 다른 기능 호환용: 없으면 무시)
try:
    from ..models import ImageData, EInkDevice, User, kst_now_naive as now_kst  # type: ignore[assignment]
except Exception:  # pragma: no cover
    ImageData = None            # type: ignore[assignment]
    EInkDevice = None           # type: ignore[assignment]


# --------------------------------------------
# 내부 유틸 (디버그)
# --------------------------------------------
def _logger():
    """Flask가 있으면 current_app.logger, 없으면 모듈 로거 반환."""
    if current_app is not None:
        return current_app.logger
    return logging.getLogger(__name__)


def _dump_json(obj: Any, max_len: int = 800) -> str:
    try:
        s = json.dumps(obj, ensure_ascii=False, default=str)
        return (s[:max_len] + "...") if len(s) > max_len else s
    except Exception:
        return str(obj)


def _dbg(tag: str, **kw):
    try:
        parts = [f"{k}={_dump_json(v)}" for k, v in kw.items()]
        _logger().debug(f"[RepositoryEINK:{tag}] " + " ".join(parts))
    except Exception:
        _logger().debug(f"[RepositoryEINK:{tag}] <log-failed>")


# --------------------------------------------
# 내부 유틸 (비즈니스)
# --------------------------------------------
def _json_passthrough(obj: Any) -> Any:
    """
    SQLAlchemy JSON 컬럼은 dict/list를 그대로 넣으면 자동 직렬화됨.
    문자열로 미리 dumps하지 않는다.
    """
    return obj


def _coerce_target_dir(v: Optional[str]) -> str:
    """
    DocumentInfo.target_dir 허용값:
      - 'in_review'     : 결재 진행 중
      - 'checked'       : 검토 완료 / 최종 승인 대기
      - 'approved'      : 결재 완료(게시 후보)
      - 'bulletin_files': 결재 없이 게시용으로 복사된 문서
      - 'uploads'       : 즉시배포/특수 플로우용
    """
    allowed = ("uploads", "in_review", "checked", "approved", "bulletin_files")
    out = v if v in allowed else "in_review"
    _dbg("coerce_target_dir", input=v, output=out)
    return out


def _coerce_status(v: Optional[str]) -> str:
    """
    DocumentInfo.status (큰 상태만)
      - draft / in_review / checked / approved / rejected / bulletin_files
      - (호환) uploads 는 과거 데이터 호환용으로만 남겨둠
    """
    allowed = ("draft", "in_review", "checked", "approved", "rejected", "bulletin_files", "uploads")
    out = v if v in allowed else "draft"
    _dbg("coerce_status", input=v, output=out)
    return out



def _role_is_valid(role: Optional[str]) -> bool:
    valid = role in ("author", "review", "approve", "review2", "approve2")
    _dbg("role_is_valid", role=role, valid=valid)
    return valid


def _user_display_string(user: Optional[User]) -> Optional[str]:
    """
    프런트에서 select에 보여줄 사용자 표시 문자열.
    우선순위: username > userid > email > (fallback) no
    """
    if not user:
        return None
    for attr in ("username", "userid", "email"):
        val = getattr(user, attr, None)
        if val:
            return str(val)
    if getattr(user, "no", None) is not None:
        return str(user.no)
    return None


class RepositoryEINK:
    """
    E-INK 문서/레이아웃/결재 레포지토리 (DocumentInfo 기반).
    컨트롤러에서 사용하는 것 위주 + 향후 DocumentInfo 확장 대응.
    """

    # ================== 결재선 목록 (임시 스텁 구현) ==================
    @staticmethod
    def get_approval_routes() -> List[Dict[str, Any]]:
        """
        컨트롤러와의 호환을 위한 임시 구현.
        - 현재 ApprovalRouteModel을 사용하지 않으므로 빈 리스트를 반환하고,
          컨트롤러에서 default_routes()로 폴백하게 둔다.
        - 나중에 ApprovalRoute 테이블을 도입하면, 이 함수 내부 구현만 교체하면 된다.
        """
        _dbg("get_approval_routes:start (stub)")
        return []


    @staticmethod
    def register_document(
        *,
        user_id: Optional[int],
        device_id: Optional[str],
        doc_name: str,
        source_ext: str,
        original_relpath: str,
        pdf_relpath: str,
        page_count: int,
        need_approval: bool,
        route_id: Optional[int],
        layout_snapshot: Dict[str, Any],
        metadata: Dict[str, Any],
        render_params: Dict[str, Any],
        target_type: str,   # 'approval' | 'bulletin'
    ) -> int:
        """
        /document/register 엔드포인트용 DocumentInfo 생성 함수.

        - original_relpath / pdf_relpath 는 메타데이터에 함께 저장
        - stored_path 는 우선 pdf_relpath 를 그대로 넣어둔다 (상대경로 허용)
        - need_approval / target_type 에 따라 status / target_dir 기본값 결정
        """
        _dbg(
            "register_document:start",
            user_id=user_id,
            device_id=device_id,
            doc_name=doc_name,
            source_ext=source_ext,
            original_relpath=original_relpath,
            pdf_relpath=pdf_relpath,
            page_count=page_count,
            need_approval=need_approval,
            route_id=route_id,
            target_type=target_type,
        )

        # 1) status / target_dir 기본값 결정
        target_type = (target_type or "approval").lower()
        if need_approval:
            # 결재가 필요한 문서: 기본적으로 in_review에 올려 둔다
            status = "in_review"
            target_dir = "in_review"
        else:
            # 결재 없이 게시용: bulletin_files + uploads 상태로 취급
            if target_type == "bulletin":
                status = "uploads"
                target_dir = "bulletin_files"
            else:
                # 그 외는 업로드 전용
                status = "uploads"
                target_dir = "uploads"

        status = _coerce_status(status)
        target_dir = _coerce_target_dir(target_dir)

        # 2) 렌더링 파라미터 파싱
        width = int(render_params.get("width", 0) or 0)
        height = int(render_params.get("height", 0) or 0)
        mode = render_params.get("mode")
        scale = render_params.get("scale")
        percent = int(render_params.get("percent", 0) or 0)
        rotate = int(render_params.get("rotate", 0) or 0)

        # 3) 파일 이름 및 stored_path 결정
        orig_filename = os.path.basename(original_relpath) if original_relpath else doc_name
        stored_path = pdf_relpath or original_relpath or ""

        # 4) metadata 확장 (원본/표준화 경로 등 포함)
        meta_full: Dict[str, Any] = {}
        meta_full.update(metadata or {})
        meta_full.setdefault("file_info", {})
        meta_full["file_info"].update(
            {
                "source_ext": source_ext,
                "original_relpath": original_relpath,
                "pdf_relpath": pdf_relpath,
                "target_type": target_type,
            }
        )

        # 5) route_snapshot 는 간단하게 route_id만 넣어두고,
        route_snapshot = {"route_id": route_id} if route_id else None

        row = DocumentInfoModel(
            user_id=user_id,
            device_id=(device_id or None),
            doc_name=doc_name or orig_filename,
            orig_filename=orig_filename,
            stored_path=stored_path,
            target_dir=target_dir,
            need_approval=bool(need_approval),
            need_stamp=False,
            status=status,
            expire_time=None,
            pages=page_count or 1,
            width=width or None,
            height=height or None,
            mode=mode,
            scale=scale,
            percent=percent or None,
            rotate=rotate or None,
            route_id=route_id,
            sign_layout_id=None,
            route_snapshot_json=_json_passthrough(route_snapshot),
            layout_snapshot_json=_json_passthrough(layout_snapshot or {}),
            metadata_json=_json_passthrough(meta_full),
            final_doc_relpath=pdf_relpath or None,
            created_at=now_kst(),
            updated_at=now_kst(),
        )

        try:
            db.session.add(row)
            db.session.commit()
            _dbg("register_document:committed", document_info_id=int(row.id))
            return int(row.id)
        except SQLAlchemyError as e:
            _logger().debug("[register_document] DB error, rollback", exc_info=True)
            db.session.rollback()
            raise e
        

    @staticmethod
    def get_document_preview_source(document_info_id: int) -> Optional[Dict[str, Any]]:
        """
        /bmp_preview 에서 document_info_id로 미리보기 소스 찾을 때 사용.

        - 현재 구현:
          * DocumentInfo.stored_path 를 abs_path 로 그대로 사용
          * pages 는 DocumentInfo.pages 또는 1
          * name 은 doc_name → orig_filename 순으로 사용

        - 나중에:
          * stored_path 를 BMP, final_doc_relpath 를 normalized.pdf 로 구분해서,
            상황에 따라 어떤 경로를 쓸지 여기서 결정하도록 확장 가능.
        """
        _dbg("get_document_preview_source:start", document_info_id=document_info_id)
        try:
            row = db.session.get(DocumentInfoModel, int(document_info_id))
            if not row:
                _dbg("get_document_preview_source:not_found", document_info_id=document_info_id)
                return None

            abs_path = row.stored_path
            if not abs_path:
                _dbg("get_document_preview_source:no_stored_path", document_info_id=document_info_id)
                return None

            # 이름은 doc_name -> orig_filename 우선
            name = row.doc_name or row.orig_filename or os.path.basename(abs_path)
            pages = int(row.pages or 1)

            out = {
                "abs_path": abs_path,
                "pages": pages,
                "name": name,
            }
            _dbg("get_document_preview_source:done", out=out)
            return out
        except SQLAlchemyError:
            _logger().debug("[get_document_preview_source] DB error", exc_info=True)
            return None
        except Exception:
            _logger().debug("[get_document_preview_source] error", exc_info=True)
            return None
        

    # ================== 대시보드 장비 목록 ==================
    @staticmethod
    def get_devices_for_dashboard() -> Optional[List[Dict[str, Any]]]:
        """
        현재 EInkDevice 모델을 쓰지 않도록 컨트롤러 폴백을 유지.
        추후 Device 테이블 구현 시 여기서 실제 목록 리턴.
        """
        _dbg("get_devices_for_dashboard:start")
        if EInkDevice is None:
            _dbg("get_devices_for_dashboard:return", value=None)
            return None

        try:
            rows = (
                db.session.query(EInkDevice)
                .order_by(EInkDevice.id.desc())
                .all()
            )
            devices: List[Dict[str, Any]] = []
            for r in rows:
                devices.append(
                    {
                        "id": r.id,
                        "device_id": r.device_id,
                        "name": getattr(r, "device_name", None),
                        "panel_res": r.panel_res,
                        "cap": getattr(r, "cap", None),
                        "bpp": getattr(r, "bpp", None),
                        "supports_partial": getattr(r, "supports_partial", True),
                        "supports_rle": getattr(r, "supports_rle", True),
                        "supports_zlib": getattr(r, "supports_zlib", True),
                    }
                )
            _dbg("get_devices_for_dashboard:return", count=len(devices))
            return devices or None
        except SQLAlchemyError:
            _logger().debug("[get_devices_for_dashboard] DB error", exc_info=True)
            return None

    # ================== 부서 목록 & 부서별 사용자 ==================
    @staticmethod
    def list_departments() -> List[str]:
        """
        User.department의 DISTINCT 목록 반환.
        """
        print("REPO ENGINE:", db.engine.url)
        _dbg("list_departments:start")
        try:
            rows = (
                db.session.query(User.department)
                .filter(User.department.isnot(None))
                .distinct()
                .all()
            )
            depts = [r[0] for r in rows if r and r[0]]
            _dbg("list_departments:done", count=len(depts), depts=depts[:10])
            return depts
        except SQLAlchemyError:
            _logger().debug("[list_departments] DB error", exc_info=True)
            return []

    @staticmethod
    def list_users_by_department(department: Optional[str]) -> List[Dict[str, Any]]:
        """
        특정 부서의 사용자 목록을 select 용도로 반환.
        """
        _dbg("list_users_by_department:start", department=department)
        try:
            q = db.session.query(
                User.no,
                User.userid,
                User.username,
                User.department,
                User.position,
                User.photo_1,
            )
            if department:
                q = q.filter(User.department == department)
            q = q.order_by(User.username.asc())
            rows = q.all()
            users: List[Dict[str, Any]] = []
            for (no, userid, username, dept, position, photo_1) in rows:
                users.append(
                    {
                        "id": no,
                        "userid": userid or "",
                        "username": username or "",
                        "department": dept or "",
                        "position": position or "",
                        "photo_1": photo_1 or "",
                        "display": username or userid or str(no),
                    }
                )
            _dbg("list_users_by_department:done", count=len(users), sample=users[:3])
            return users
        except SQLAlchemyError:
            _logger().debug("[list_users_by_department] DB error", exc_info=True)
            return []

    # ================== 결재선 목록 ==================
    # @staticmethod
    # def get_approval_routes() -> List[Dict[str, Any]]:
    #     """
    #     ApprovalRoute 및 steps를 프런트가 기대하는 구조로 직렬화.
    #     - creator 정보 포함
    #     - 각 step의 assignee + 스냅샷 동시 제공
    #     """
    #     _dbg("get_approval_routes:start")
    #     try:
    #         routes: List[Dict[str, Any]] = []
    #         route_rows = (
    #             db.session.query(ApprovalRouteModel)
    #             .order_by(ApprovalRouteModel.id.desc())
    #             .all()
    #         )
    #         _dbg("get_approval_routes:rows", count=len(route_rows))
    #         for r in route_rows:
    #             creator = r.creator
    #             creator_info = (
    #                 {
    #                     "id": getattr(creator, "no", None),
    #                     "userid": getattr(creator, "userid", None),
    #                     "username": getattr(creator, "username", None),
    #                     "department": getattr(creator, "department", None),
    #                     "position": getattr(creator, "position", None),
    #                     "photo_1": getattr(creator, "photo_1", None),
    #                 }
    #                 if creator
    #                 else None
    #             )

    #             steps_out: List[Dict[str, Any]] = []
    #             for st in (r.steps or []):
    #                 assignee = st.assignee
    #                 steps_out.append(
    #                     {
    #                         "id": int(st.id),
    #                         "step_order": int(st.step_order),
    #                         "role": st.role,
    #                         "sign_required": bool(st.sign_required),
    #                         "assignee": {
    #                             "id": getattr(assignee, "no", None) if assignee else None,
    #                             "userid": getattr(assignee, "userid", None)
    #                             if assignee
    #                             else None,
    #                             "username": getattr(assignee, "username", None)
    #                             if assignee
    #                             else None,
    #                             "department": getattr(assignee, "department", None)
    #                             if assignee
    #                             else None,
    #                             "position": getattr(assignee, "position", None)
    #                             if assignee
    #                             else None,
    #                             "photo_1": getattr(assignee, "photo_1", None)
    #                             if assignee
    #                             else None,
    #                             "display": _user_display_string(assignee),
    #                         },
    #                         "assignee_snapshot": {
    #                             "userid": getattr(
    #                                 st, "assignee_userid_snapshot", None
    #                             ),
    #                             "username": getattr(
    #                                 st, "assignee_username_snapshot", None
    #                             ),
    #                             "department": getattr(
    #                                 st, "assignee_department_snapshot", None
    #                             ),
    #                             "position": getattr(
    #                                 st, "assignee_position_snapshot", None
    #                             ),
    #                             "photo_1": getattr(
    #                                 st, "assignee_photo_1_snapshot", None
    #                             ),
    #                         },
    #                         "assignee_group_id": getattr(st, "assignee_group_id", None),
    #                     }
    #                 )
    #             routes.append(
    #                 {
    #                     "id": int(r.id),
    #                     "name": r.name,
    #                     "created_by": r.created_by,
    #                     "created_at": r.created_at,
    #                     "creator": creator_info,
    #                     "steps": steps_out,
    #                 }
    #             )
    #         _dbg("get_approval_routes:done", count=len(routes))
    #         return routes
    #     except SQLAlchemyError:
    #         _logger().debug("[get_approval_routes] DB error", exc_info=True)
    #         return []

    # ------------------------------------------------------------------
    # DocumentInfo 레코드 생성 (컨트롤러 send_file_route에서 사용)
    # ------------------------------------------------------------------
    # repository/repository_eink.py (발췌)
    @staticmethod
    def _coerce_fit_mode(v: str | None) -> str:
        v = (v or "fit").lower().strip()
        return v if v in ("fit", "fill", "percent") else "fit"


    @staticmethod
    def create_upload_record(
        *,
        user_id: Optional[int],
        device_id: Optional[str],
        orig_filename: str,
        stored_path: str,
        target_dir: str,
        need_approval: bool,
        status: str,
        pages: int = 1,
        width: Optional[int] = None,
        height: Optional[int] = None,
        mode: Optional[str] = None,
        scale: Optional[str] = None,   # ✅ DB에는 fit_mode로 저장
        percent: Optional[int] = None,
        rotate: Optional[int] = None,
        route_id: Optional[int] = None,
        sign_layout_id: Optional[int] = None,
        route_snapshot: Optional[Dict[str, Any]] = None,
        layout_snapshot: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expire_time: Optional[datetime] = None,
        final_doc_relpath: Optional[str] = None,
    ) -> int:

        row = DocumentInfoModel(
            user_id=user_id,
            device_id=(device_id or None),
            doc_name=orig_filename,
            orig_filename=orig_filename,

            # ✅ 처음엔 모를 수 있으니 "" 허용(모델 default="") + 이후 update에서 채움
            stored_path=stored_path or "",

            target_dir=_coerce_target_dir(target_dir),
            need_approval=bool(need_approval),
            need_stamp=False,
            status=_coerce_status(status),
            expire_time=expire_time,

            # ✅ pages 컬럼 반영
            pages=max(1, int(pages or 1)),
            # (선택) 기존 source_pages도 같이 맞춰두면 혼동 줄어듦
            source_pages=max(1, int(pages or 1)),

            # ✅ 디바이스 렌더 파라미터 저장
            width=width,
            height=height,
            mode=(mode or None),

            # ✅ scale은 fit_mode로 저장
            fit_mode= RepositoryEINK._coerce_fit_mode(scale),
            percent=percent,
            rotate=rotate,

            # ✅ route_id 저장
            route_id=route_id,
            sign_layout_id=sign_layout_id,

            route_snapshot_json=_json_passthrough(route_snapshot),
            layout_snapshot_json=_json_passthrough(layout_snapshot),
            metadata_json=_json_passthrough(metadata),
            final_doc_relpath=final_doc_relpath,

            created_at=now_kst(),
            updated_at=now_kst(),
        )

        db.session.add(row)
        db.session.commit()
        return int(row.id)


    # ------------------------------------------------------------------
    # DocumentInfo 상태/디렉터리 업데이트
    # ------------------------------------------------------------------
    @staticmethod
    def update_upload_status(
        upload_id: int,
        *,
        status: Optional[str] = None,
        target_dir: Optional[str] = None,
        route_id: Optional[int] = None,
        sign_layout_id: Optional[int] = None,
        route_snapshot: Optional[Dict[str, Any]] = None,
        layout_snapshot: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
        expire_time: Optional[datetime] = None,
        final_doc_relpath: Optional[str] = None,
        stored_path: Optional[str] = None,

        # ✅ (선택) 페이지 수/렌더 파라미터도 업데이트 가능하게
        pages: Optional[int] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        mode: Optional[str] = None,
        scale: Optional[str] = None,
        percent: Optional[int] = None,
        rotate: Optional[int] = None,
    ) -> bool:
        row = db.session.get(DocumentInfoModel, upload_id)
        if not row:
            return False

        if status in ("draft", "in_review", "checked", "approved", "rejected", "bulletin_files", "uploads"):
            row.status = status
        if target_dir in ("in_review", "checked", "approved", "uploads", "bulletin_files"):
            row.target_dir = target_dir

        if route_id is not None:
            row.route_id = route_id
        if sign_layout_id is not None:
            row.sign_layout_id = sign_layout_id

        if route_snapshot is not None:
            row.route_snapshot_json = _json_passthrough(route_snapshot)
        if layout_snapshot is not None:
            row.layout_snapshot_json = _json_passthrough(layout_snapshot)
        if metadata is not None:
            row.metadata_json = _json_passthrough(metadata)

        if expire_time is not None:
            row.expire_time = expire_time
        if final_doc_relpath is not None:
            row.final_doc_relpath = final_doc_relpath
        if stored_path is not None:
            row.stored_path = stored_path

        # ✅ pages/렌더 파라미터 업데이트(필요할 때만)
        if pages is not None:
            row.pages = max(1, int(pages or 1))
            row.source_pages = row.pages
        if width is not None:
            row.width = width
        if height is not None:
            row.height = height
        if mode is not None:
            row.mode = mode
        if scale is not None:
            row.fit_mode = RepositoryEINK._coerce_fit_mode(scale)
        if percent is not None:
            row.percent = percent
        if rotate is not None:
            row.rotate = rotate

        row.updated_at = now_kst()
        db.session.commit()
        return True



    # ------------------------------------------------------------------
    # (옵션) 결재 단계 전진 헬퍼: in_review -> checked -> approved
    # ------------------------------------------------------------------
    @staticmethod
    def advance_upload_stage(upload_id: int, stage: str) -> bool:
        """
        stage:
        - 'review'  : 검토 완료 → checked / status='checked'
        - 'approve' : 승인 완료 → approved / status='approved'
        """
        _dbg("advance_upload_stage:start", upload_id=upload_id, stage=stage)
        stage = (stage or "").lower()
        try:
            row = db.session.get(DocumentInfoModel, upload_id)
            if not row:
                _dbg("advance_upload_stage:not_found", upload_id=upload_id)
                return False

            if stage == "review":
                row.status = "checked"
                row.target_dir = "checked"
            elif stage == "approve":
                row.status = "approved"
                row.target_dir = "approved"
            else:
                _dbg("advance_upload_stage:invalid_stage", stage=stage)
                return False

            row.updated_at = now_kst()
            db.session.commit()
            _dbg(
                "advance_upload_stage:committed",
                upload_id=upload_id,
                status=row.status,
                target_dir=row.target_dir,
            )
            return True
        except SQLAlchemyError:
            _logger().debug(
                "[advance_upload_stage] DB error, rollback", exc_info=True
            )
            db.session.rollback()
            return False

    # ------------------------------------------------------------------
    # 사용자 서명 이미지 경로 (User.photo_1)
    # ------------------------------------------------------------------
    @staticmethod
    def get_user_sign_path(user_id: int) -> Optional[str]:
        _dbg("get_user_sign_path:start", user_id=user_id)
        try:
            u = db.session.get(User, user_id)
            path = getattr(u, "photo_1", None) if u else None
            _dbg("get_user_sign_path:done", exists=bool(path), path=path)
            return path
        except SQLAlchemyError:
            _logger().debug("[get_user_sign_path] DB error", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # 결재 라우트 생성 (ApprovalRoute + ApprovalRouteStep[])
    # ------------------------------------------------------------------
    # @staticmethod
    # def create_approval_route(
    #     *,
    #     name: str,
    #     created_by: Optional[int],
    #     steps: List[Dict[str, Any]],
    # ) -> int:
    #     """
    #     예:
    #       steps = [
    #         {"step_order":1, "role":"review",  "assignee_user_id":101, "sign_required":True},
    #         {"step_order":2, "role":"approve", "assignee_user_id":202, "sign_required":True},
    #       ]
    #     role은 'author' | 'review' | 'approve' | 'review2' | 'approve2'
    #     """
    #     _dbg(
    #         "create_approval_route:start",
    #         name=name,
    #         created_by=created_by,
    #         steps=_dump_json(steps, 400),
    #     )
    #     route = ApprovalRouteModel(
    #         name=name,
    #         created_by=created_by,
    #         created_at=now_kst(),
    #     )
    #     try:
    #         db.session.add(route)
    #         db.session.flush()  # route.id 확보

    #         normalized: List[Dict[str, Any]] = []
    #         for st in steps or []:
    #             role = st.get("role")
    #             if not _role_is_valid(role):
    #                 _dbg("create_approval_route:skip_invalid_role", role=role)
    #                 continue
    #             normalized.append(
    #                 {
    #                     "step_order": int(st.get("step_order", 0)),
    #                     "role": role,
    #                     "assignee_user_id": st.get("assignee_user_id"),
    #                     "assignee_group_id": st.get("assignee_group_id"),
    #                     "sign_required": bool(st.get("sign_required", True)),
    #                 }
    #             )
    #         normalized.sort(key=lambda x: x["step_order"] or 0)
    #         _dbg("create_approval_route:normalized", steps=normalized)

    #         for i, st in enumerate(normalized, start=1):
    #             row = ApprovalRouteStepModel(
    #                 route_id=route.id,
    #                 step_order=i,
    #                 role=st["role"],
    #                 assignee_user_id=st["assignee_user_id"],
    #                 assignee_group_id=st["assignee_group_id"],
    #                 sign_required=st["sign_required"],
    #             )
    #             db.session.add(row)

    #         db.session.commit()
    #         _dbg(
    #             "create_approval_route:committed",
    #             route_id=int(route.id),
    #             step_count=len(normalized),
    #         )
    #         return int(route.id)
    #     except SQLAlchemyError as e:
    #         _logger().debug(
    #             "[create_approval_route] DB error, rollback", exc_info=True
    #         )
    #         db.session.rollback()
    #         raise e

    # ------------------------------------------------------------------
    # 레이아웃 저장 (SignLayout INSERT – 버전업 개념으로 누적 저장 권장)
    # ------------------------------------------------------------------
    @staticmethod
    def insert_sign_layout(
        *,
        name: str,
        owner_user_id: Optional[int],
        canvas_w: int,
        canvas_h: int,
        parent_box: Dict[str, int],  # {x,y,w,h}
        tpl_json: Dict[str, Any],
        slots_json: Dict[str, Any],      # ✅ dict 로 수정
        layers_json: Optional[List[Dict[str, Any]]] = None,  # ✅ list 로 수정
        version: int = 1,
    ) -> int:
        """
        프론트의 layout 스냅샷을 DB형식에 맞춰 저장.
        - parent_box는 절대좌표(BASE 1200x1600 기준)여야 함.
        """
        _dbg(
            "insert_sign_layout:start",
            name=name,
            owner_user_id=owner_user_id,
            canvas=f"{canvas_w}x{canvas_h}",
            parent_box=parent_box,
            version=version,
        )
        row = SignLayoutModel(
            name=name,
            owner_user_id=owner_user_id,
            canvas_w=int(canvas_w),
            canvas_h=int(canvas_h),
            parent_x=int(parent_box.get("x", 0)),
            parent_y=int(parent_box.get("y", 0)),
            parent_w=int(parent_box.get("w", 0)),
            parent_h=int(parent_box.get("h", 0)),
            tpl_json=_json_passthrough(tpl_json or {}),
            slots_json=_json_passthrough(slots_json or {}),      # ✅ dict 기본값
            layers_json=_json_passthrough(layers_json or []),    # ✅ list 기본값
            version=int(version),
            created_at=now_kst(),
            updated_at=now_kst(),
        )
        try:
            db.session.add(row)
            db.session.commit()
            _dbg("insert_sign_layout:committed", sign_layout_id=int(row.id))
            return int(row.id)
        except SQLAlchemyError as e:
            _logger().debug(
                "[insert_sign_layout] DB error, rollback", exc_info=True
            )
            db.session.rollback()
            raise e

    # ------------------------------------------------------------------
    # 최신 레이아웃 조회 (이름 기준/또는 소유자 기준) – 필요 시 사용
    # ------------------------------------------------------------------
    @staticmethod
    def get_latest_sign_layout_by_name(name: str) -> Optional[Dict[str, Any]]:
        _dbg("get_latest_sign_layout_by_name:start", name=name)
        try:
            q = (
                db.session.query(SignLayoutModel)
                .filter(SignLayoutModel.name == name)
                .order_by(desc(SignLayoutModel.version), desc(SignLayoutModel.id))
            )
            row = q.first()
            if not row:
                _dbg("get_latest_sign_layout_by_name:empty", name=name)
                return None
            out = {
                "id": row.id,
                "name": row.name,
                "canvas_w": row.canvas_w,
                "canvas_h": row.canvas_h,
                "parent": {
                    "x": row.parent_x,
                    "y": row.parent_y,
                    "w": row.parent_w,
                    "h": row.parent_h,
                },
                "tpl_json": row.tpl_json,
                "slots_json": row.slots_json,
                "layers_json": row.layers_json,
                "version": row.version,
                "owner_user_id": row.owner_user_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            _dbg(
                "get_latest_sign_layout_by_name:done",
                sign_layout_id=row.id,
                version=row.version,
            )
            return out
        except SQLAlchemyError:
            _logger().debug(
                "[get_latest_sign_layout_by_name] DB error", exc_info=True
            )
            return None

    # ------------------------------------------------------------------
    # DocumentInfo 1건 상세 조회 (스냅샷 포함)
    # ------------------------------------------------------------------
    @staticmethod
    def get_upload(upload_id: int) -> Optional[DocumentInfoModel]:
        _dbg("get_upload:start", upload_id=upload_id)
        try:
            row = db.session.get(DocumentInfoModel, upload_id)
            _dbg("get_upload:done", found=bool(row))
            return row
        except SQLAlchemyError:
            _logger().debug("[get_upload] DB error", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # 결재 대기 문서 1건 조회 (구/신 metadata 구조 모두 지원 시도)
    # ------------------------------------------------------------------
    @staticmethod
    def get_latest_pending_for_user(*, userid: str) -> Optional[Dict[str, Any]]:
        """
        userid가 결재 대상인 최신 DocumentInfo 1건 리턴.
        - 상태: status in ('in_review', 'checked') AND target_dir in ('in_review', 'checked')
        - metadata_json.assignees 구조는 2가지 케이스를 지원:
          1) 구형: {"review": "njsk2006", "approve": "njsk2003"}
          2) 신형: {"draft":[{...}], "check":[{...}]}
        """
        _dbg("get_latest_pending_for_user:start", userid=userid)
        try:
            q = (
                db.session.query(DocumentInfoModel)
                .filter(DocumentInfoModel.status.in_(["in_review", "checked"]))
                .filter(DocumentInfoModel.target_dir.in_(["in_review", "checked"]))
                .order_by(desc(DocumentInfoModel.id))
            )
            rows = q.all()
            for row in rows:
                assignees_raw: Dict[str, Any] = {}
                try:
                    md = row.metadata_json or {}
                    if isinstance(md, dict):
                        assignees_raw = md.get("assignees") or {}
                except Exception:
                    assignees_raw = {}

                is_review = False
                is_approve = False

                # 1) 구형: {"review": "userid", "approve": "userid"}
                if isinstance(assignees_raw, dict) and (
                    isinstance(assignees_raw.get("review"), str)
                    or isinstance(assignees_raw.get("approve"), str)
                ):
                    is_review = (
                        row.status == "in_review"
                        and row.target_dir == "in_review"
                        and assignees_raw.get("review") == userid
                    )
                    is_approve = (
                        row.status == "checked"
                        and row.target_dir == "checked"
                        and assignees_raw.get("approve") == userid
                    )
                else:
                    # 2) 신형: {"draft":[{userid/...}], "check":[{userid/...}]}
                    try:
                        draft_list = assignees_raw.get("draft") or []
                        check_list = assignees_raw.get("check") or []
                        if isinstance(draft_list, list) and row.status == "in_review":
                            for a in draft_list:
                                if not isinstance(a, dict):
                                    continue
                                if a.get("userid") == userid or a.get("user_id") == userid:
                                    is_review = True
                                    break
                        if isinstance(check_list, list) and row.status == "checked":
                            for a in check_list:
                                if not isinstance(a, dict):
                                    continue
                                if a.get("userid") == userid or a.get("user_id") == userid:
                                    is_approve = True
                                    break
                    except Exception:
                        pass

                if not (is_review or is_approve):
                    continue

                stored_path = row.stored_path or ""
                base = os.path.splitext(os.path.basename(stored_path))[0]
                meta_name = base + ".meta.json"
                meta_path = os.path.join(os.path.dirname(stored_path), meta_name)

                return {
                    "id": int(row.id),
                    "device_id": row.device_id,
                    "stored_path": stored_path,
                    "target_dir": row.target_dir,
                    "status": row.status,
                    "assignees": assignees_raw,
                    "meta_path": meta_path if os.path.isfile(meta_path) else None,
                    "width": row.width or 1200,
                    "height": row.height or 1600,
                    "mode": row.mode or "BWRYBG",
                    "created_at": row.created_at,
                }
            _dbg("get_latest_pending_for_user:none")
            return None
        except SQLAlchemyError:
            _logger().debug(
                "[get_latest_pending_for_user] DB error", exc_info=True
            )
            return None

    @staticmethod
    def get_user_sign_path_by_userid(userid: str) -> Optional[str]:
        _dbg("get_user_sign_path_by_userid:start", userid=userid)
        try:
            u = db.session.query(User).filter(User.userid == userid).first()
            path = getattr(u, "photo_1", None) if u else None
            _dbg("get_user_sign_path_by_userid:done", exists=bool(path), path=path)
            return path
        except SQLAlchemyError:
            _logger().debug(
                "[get_user_sign_path_by_userid] DB error", exc_info=True
            )
            return None

    # ------------------------------------------------------------------
    # meta(.meta.json) → DocumentInfo.layout_snapshot_json 조회
    # ------------------------------------------------------------------
    @staticmethod
    def get_layout_snapshot_by_meta(meta_path: str) -> Optional[Dict[str, Any]]:
        """
        meta의 bmp 베이스파일명으로 DocumentInfo 레코드를 추정해 layout_snapshot_json 반환.
        """
        _dbg("get_layout_snapshot_by_meta:start", meta_path=meta_path)
        try:
            if not (meta_path and os.path.isfile(meta_path)):
                return None
            with open(meta_path, "r", encoding="utf-8") as f:
                js = json.load(f)
            bmp_name = js.get("file")  # 예: E01_1200x1600_BWRYBG.bmp
            if not bmp_name:
                return None
            q = (
                db.session.query(DocumentInfoModel)
                .filter(DocumentInfoModel.stored_path.like(f"%{bmp_name}"))
                .order_by(desc(DocumentInfoModel.id))
            )
            row = q.first()
            if not row:
                _dbg(
                    "get_layout_snapshot_by_meta:not_found_by_name",
                    bmp_name=bmp_name,
                )
                return None
            snap = row.layout_snapshot_json
            _dbg(
                "get_layout_snapshot_by_meta:done",
                has=bool(snap),
                upload_id=int(row.id),
            )
            return snap if isinstance(snap, dict) else None
        except Exception:
            _logger().debug(
                "[get_layout_snapshot_by_meta] error", exc_info=True
            )
            return None

    # ------------------------------------------------------------------
    # meta 기반으로 DocumentInfo 상태/디렉터리/stored_path 갱신
    # ------------------------------------------------------------------
    @staticmethod
    def update_upload_status_by_meta(
        *, old_meta_path: str, new_dir: str, new_status: str, note: Optional[str] = None
    ) -> bool:
        """
        파일 번들을 이동한 뒤, 해당 건의 DocumentInfo.status/target_dir/stored_path 갱신.
        - new_dir:
            'uploads' | 'in_review' | 'checked' | 'approved' | 'bulletin_files'
        - new_status:
            'draft' | 'in_review' | 'checked' | 'approved' | 'rejected' | 'uploads'
        - old_meta_path: 이동 전/후 어느 쪽이든 OK (아래에서 새 경로를 추정)
        """
        _dbg(
            "update_upload_status_by_meta:start",
            old_meta_path=old_meta_path,
            new_dir=new_dir,
            new_status=new_status,
        )
        try:
            meta_path = old_meta_path

            # 1) 옛 경로가 이미 이동되어 없을 수 있으므로, 새 위치를 추정
            if not (meta_path and os.path.isfile(meta_path)):
                try:
                    base_dir = os.path.dirname(os.path.dirname(old_meta_path))  # root
                    guess = os.path.join(
                        base_dir, new_dir, os.path.basename(old_meta_path)
                    )
                    if os.path.isfile(guess):
                        meta_path = guess
                        _dbg(
                            "update_upload_status_by_meta:resolved_new_meta_path",
                            meta_path=meta_path,
                        )
                    else:
                        _dbg(
                            "update_upload_status_by_meta:meta_missing", tried=guess
                        )
                        return False
                except Exception:
                    _dbg(
                        "update_upload_status_by_meta:meta_missing_unresolvable",
                    )
                    return False

            # 2) 메타 열고 BMP 파일명 획득
            with open(meta_path, "r", encoding="utf-8") as f:
                js = json.load(f)
            bmp_name = js.get("file")
            if not bmp_name:
                _dbg("update_upload_status_by_meta:no_bmp_name")
                return False

            # 3) BMP 파일명으로 DocumentInfo 레코드를 역추적
            q = (
                db.session.query(DocumentInfoModel)
                .filter(DocumentInfoModel.stored_path.like(f"%{bmp_name}"))
                .order_by(desc(DocumentInfoModel.id))
            )
            row = q.first()
            if not row:
                _dbg("update_upload_status_by_meta:not_found", bmp_name=bmp_name)
                return False

            # 4) 상태/디렉터리 갱신
            if new_status in (
                "draft",
                "in_review",
                "checked",
                "approved",
                "rejected",
                "uploads",
            ):
                row.status = new_status

            if new_dir in (
                "uploads",
                "in_review",
                "checked",
                "approved",
                "bulletin_files",
            ):
                row.target_dir = new_dir

            # 5) stored_path도 이동 후 실제 경로로 동기화
            root = os.path.dirname(os.path.dirname(meta_path))  # root
            new_bmp_path = os.path.join(root, new_dir, bmp_name)
            row.stored_path = new_bmp_path

            # 6) 비고 로그(optional)
            meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            if note:
                logs = meta.get("notes", [])
                ts = (
                    now_kst().isoformat()
                    if hasattr(now_kst(), "isoformat")
                    else str(now_kst())
                )
                logs.append({"ts": ts, "note": note})
                meta["notes"] = logs
            row.metadata_json = meta

            row.updated_at = now_kst()
            db.session.commit()
            _dbg(
                "update_upload_status_by_meta:committed",
                upload_id=int(row.id),
                status=row.status,
                dir=row.target_dir,
                stored_path=row.stored_path,
            )
            return True

        except SQLAlchemyError:
            _logger().debug(
                "[update_upload_status_by_meta] DB error", exc_info=True
            )
            db.session.rollback()
            return False

    # ===== USERID별 디바이스 등록 =====
    @staticmethod
    def upsert_device_for_user(
        *,
        user_no: int,
        device_id: str,
        panel_res: str,
        cap: str = "BWR",
        bpp: int = 4,
        device_name: str | None = None,
        supports_partial: bool = True,
        supports_rle: bool = True,
        supports_zlib: bool = True,
    ) -> int:
        """
        (1) 특정 사용자(user_no)에게 device_id를 등록/갱신.
        - (user_no, device_id) UNIQUE 제약 준수
        - 경로 생성 용도로 user_userid 캐시 사용
        """
        if EInkDevice is None:
            raise RuntimeError("EInkDevice 모델이 정의되어 있지 않습니다.")

        _dbg(
            "upsert_device_for_user:start",
            user_no=user_no,
            device_id=device_id,
            panel_res=panel_res,
            cap=cap,
            bpp=bpp,
        )

        if not user_no or not device_id or not panel_res:
            raise ValueError("user_no, device_id, panel_res 는 필수입니다.")

        try:
            # 1) 사용자 조회 (userid 캐시용)
            u = db.session.get(User, int(user_no))
            if not u:
                _dbg("upsert_device_for_user:user_not_found", user_no=user_no)
                raise ValueError("user_no에 해당하는 User가 없습니다.")
            userid_cache = (u.userid or "").strip() or None

            # 2) (user_no, device_id)로 기존 행 조회
            row = (
                db.session.query(EInkDevice)
                .filter(
                    EInkDevice.user_no == user_no,
                    EInkDevice.device_id == device_id,
                )
                .first()
            )

            now = now_kst()

            if row:
                # === UPDATE 경로 ===
                row.panel_res = panel_res
                row.cap = cap or row.cap
                row.bpp = int(bpp or row.bpp or 4)
                if device_name is not None:
                    row.device_name = device_name
                row.supports_partial = bool(supports_partial)
                row.supports_rle = bool(supports_rle)
                row.supports_zlib = bool(supports_zlib)
                # userid 캐시 최신화
                row.user_userid = userid_cache
                row.updated_at = now
                db.session.commit()
                _dbg("upsert_device_for_user:updated", id=row.id)
                return int(row.id)

            # === INSERT 경로 ===
            row = EInkDevice(
                user_no=int(user_no),
                user_userid=userid_cache,
                device_id=device_id.strip(),
                device_name=(device_name or None),
                panel_res=panel_res.strip(),
                bpp=int(bpp or 4),
                cap=(cap or "BWR"),
                supports_partial=bool(supports_partial),
                supports_rle=bool(supports_rle),
                supports_zlib=bool(supports_zlib),
                current_ver=0,
                last_seen=None,
                created_at=now,
                updated_at=now,
            )
            db.session.add(row)
            db.session.commit()
            _dbg("upsert_device_for_user:inserted", id=row.id)
            return int(row.id)

        except Exception:
            _logger().debug("[upsert_device_for_user] error", exc_info=True)
            db.session.rollback()
            raise

    @staticmethod
    def touch_device_seen_and_version(
        *,
        device_id: str,
        new_version: int | None = None,
        last_seen_ts=None,
    ) -> bool:
        """
        디바이스가 폴링될 때 상태 갱신:
          - current_ver, last_seen 업데이트
          - device_id 는 전역 유니크가 아닐 수 있으므로 "최근 등록된" 1건 기준으로 갱신
        """
        if EInkDevice is None:
            return False

        _dbg(
            "touch_device_seen_and_version:start",
            device_id=device_id,
            new_ver=new_version,
        )

        try:
            q = (
                db.session.query(EInkDevice)
                .filter(EInkDevice.device_id == device_id)
                .order_by(EInkDevice.id.desc())
            )
            row = q.first()
            if not row:
                _dbg(
                    "touch_device_seen_and_version:not_found", device_id=device_id
                )
                return False

            if new_version is not None:
                try:
                    row.current_ver = int(new_version)
                except Exception:
                    pass

            row.last_seen = last_seen_ts or now_kst()
            row.updated_at = now_kst()
            db.session.commit()
            _dbg(
                "touch_device_seen_and_version:done",
                id=row.id,
                current_ver=row.current_ver,
            )
            return True

        except Exception:
            _logger().debug("[touch_device_seen_and_version] error", exc_info=True)
            db.session.rollback()
            return False

    @staticmethod
    def get_userid_by_device_id(device_id: str) -> str | None:
        """
        device_id → userid 문자열(경로용) 해석
        우선순위:
          1) 캐시 컬럼(EInkDevice.user_userid)이 있으면 그대로 사용
          2) 없으면 user_no로 User 조인하여 userid 획득
        """
        if EInkDevice is None:
            return None

        _dbg("get_userid_by_device_id:start", device_id=device_id)
        try:
            row = (
                db.session.query(EInkDevice)
                .filter(EInkDevice.device_id == device_id)
                .order_by(EInkDevice.id.desc())
                .first()
            )
            if not row:
                _dbg("get_userid_by_device_id:not_found", device_id=device_id)
                return None

            if getattr(row, "user_userid", None):
                return str(row.user_userid)

            u = db.session.get(User, row.user_no)
            return str(u.userid) if (u and u.userid) else None
        except Exception:
            _logger().debug("[get_userid_by_device_id] error", exc_info=True)
            return None


    @staticmethod
    def create_doc_approval_steps_from_layout(
        *,
        document_info_id: int,
        tpl_json: Dict[str, Any],
    ) -> None:
        """
        tpl_json["approval_box"]["columns"] 를 기준으로
        DocumentApprovalStep 행들을 생성.
        """
        box = (tpl_json or {}).get("approval_box") or {}
        cols = box.get("columns") or []
        if not isinstance(cols, list):
            _dbg("create_doc_approval_steps_from_layout:no_columns")
            return

        for idx, col in enumerate(cols, start=1):
            step_type = col.get("role")  # '작성','검토','승인' 등
            if step_type not in ("작성", "검토", "승인"):
                continue

            dept = col.get("dept") or ""
            userid = col.get("user_id") or ""
            username = col.get("user_name") or ""

            row = DocumentApprovalStepModel(
                document_info_id=document_info_id,
                col_index=idx,             # 1..5
                step_type=step_type,       # Enum('작성','검토','승인')
                dept_snapshot=dept,
                userid_snapshot=userid,
                username_snapshot=username,
                photo_1_snapshot=None,     # 필요시 User 조회해서 채워도 됨
                status="wait",
            )
            db.session.add(row)

        db.session.commit()
        _dbg(
            "create_doc_approval_steps_from_layout:done",
            document_info_id=document_info_id,
            count=len(cols),
        )
        

    @staticmethod
    def create_sign_slots_from_layout(
        *,
        document_info_id: int,
        tpl_json: Dict[str, Any],
        slots_json: Dict[str, Any],
    ) -> None:
        """
        approval_box + slots_json을 이용해 SignSlot 좌표/타겟을 생성.
        (1차 버전: approval 칼럼만 체크 박스라고 가정)
        """
        approval_slot_cfg = (slots_json or {}).get("approval") or {}
        # 나중에 mode, label, target_user_id 등 확장 가능
        box = (tpl_json or {}).get("approval_box") or {}
        cols = box.get("columns") or []
        if not isinstance(cols, list) or not cols:
            _dbg("create_sign_slots_from_layout:no_columns")
            return

        parent_x = int(box.get("x", 0))
        parent_y = int(box.get("y", 0))
        parent_w = int(box.get("w", 0))
        parent_h = int(box.get("h", 0))
        n = len(cols)
        if n <= 0 or parent_w <= 0:
            return

        col_w = parent_w // n

        for idx, col in enumerate(cols):
            slot_key = col.get("id") or f"APP-COL-{idx+1}"
            userid = col.get("user_id")  # "njsk2002" 같은 문자열

            # 사용자 FK를 걸고 싶으면 User.userid → User.no 조회
            target_user_id = None
            if userid:
                u = db.session.query(User).filter(User.userid == userid).first()
                if u:
                    target_user_id = u.no

            x = parent_x + col_w * idx
            y = parent_y
            w = col_w
            h = parent_h

            slot = SignSlotModel(
                document_info_id=document_info_id,
                slot_key=slot_key,
                mode="check",      # 기본값: 체크박스. 나중에 photo로 구분 가능.
                target_user_id=target_user_id,
                label=col.get("role") or "",
                x=x,
                y=y,
                w=w,
                h=h,
                filled=False,
            )
            db.session.add(slot)

        db.session.commit()
        _dbg(
            "create_sign_slots_from_layout:done",
            document_info_id=document_info_id,
            count=len(cols),
        )



    # ─────────────────────────────
    # 공통 필터 헬퍼
    # ─────────────────────────────
    @staticmethod
    def _apply_common_filters(
        query,
        search: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ):
        """
        search      : 문서명/원본파일명 LIKE 검색
        status      : DocumentInfo.status (draft/in_review/...)
        date_from   : 작성일 시작 (YYYY-MM-DD)
        date_to     : 작성일 끝   (YYYY-MM-DD)
        """
        if search:
            like = f"%{search.strip()}%"
            query = query.filter(
                or_(
                    DocumentInfoModel.doc_name.ilike(like),
                    DocumentInfoModel.orig_filename.ilike(like),
                )
            )

        if status and status != "all":
            query = query.filter(DocumentInfoModel.status == status)

        def _parse_date(s: str) -> Optional[datetime]:
            try:
                return datetime.strptime(s, "%Y-%m-%d")
            except Exception:
                return None

        dt_from = _parse_date(date_from) if date_from else None
        dt_to = _parse_date(date_to) if date_to else None

        if dt_from:
            query = query.filter(DocumentInfoModel.created_at >= dt_from)
        if dt_to:
            # dt_to 의 하루 끝까지 포함시키고 싶으면 +1일로 처리해도 됨
            query = query.filter(DocumentInfoModel.created_at <= dt_to)

        return query.order_by(DocumentInfoModel.created_at.desc())

    # ─────────────────────────────
    # Tab 1: 결재작성문서 (내가 작성자)
    # ─────────────────────────────
    @staticmethod
    def list_author_documents(
        user_id: int,
        search: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[DocumentInfoModel]:
        q = (
            DocumentInfoModel.query
            .options(joinedload(DocumentInfoModel.approval_steps))
            .filter(
                DocumentInfoModel.user_id == user_id,
                DocumentInfoModel.need_approval == 1,     # ✅ 결재라인과 Bulletin 구분
                )
        )
        q = RepositoryEINK._apply_common_filters(q, search, status, date_from, date_to)

        # current_app.logger.debug("[ENUM] DocumentApprovalStepModel file=%s", inspect.getfile(DocumentApprovalStepModel))
        # current_app.logger.debug("[ENUM] DocumentApprovalStepModel enums=%s", DocumentApprovalStepModel.__table__.c.status.type.enums)
        return q.limit(limit).all()

    # ─────────────────────────────
    # Tab 2: 결재대기 (내가 검토/승인 등 해야 할 문서)
    #  - SignSlot.target_user_id == me AND filled == False 기준
    # ─────────────────────────────


    @staticmethod
    def list_my_pending_documents(
        user_id: int,
        user_userid: str,  # ✅ current_user.userid 같은 로그인 아이디(문자열)
        search: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[DocumentInfoModel]:

        q = (
            DocumentInfoModel.query
            .join(
                DocumentApprovalStepModel,
                DocumentApprovalStepModel.document_info_id == DocumentInfoModel.id,
            )
            .options(joinedload(DocumentInfoModel.approval_steps))
            .filter(
                DocumentInfoModel.need_approval == 1,
                DocumentApprovalStepModel.status == "pending",
                or_(
                    DocumentApprovalStepModel.userid_snapshot == user_userid,   # ✅ 문자열 userid 매칭
                    DocumentApprovalStepModel.userid_snapshot == user_id,      # ✅ (있다면) 숫자 id 매칭
                ),
            )
        )

        q = RepositoryEINK._apply_common_filters(q, search=search, status=status, date_from=date_from, date_to=date_to)
        q = q.order_by(DocumentInfoModel.id.desc()).distinct(DocumentInfoModel.id)

        return q.limit(limit).all()



    # ─────────────────────────────
    # Tab 3: 결재진행사항
    #  - 내가 작성 OR 내가 결재에 참여한 문서
    # ─────────────────────────────
    @staticmethod
    def list_my_progress_documents(
        user_id: int,
        search: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[DocumentInfoModel]:
        q = (
            DocumentInfoModel.query
            .outerjoin(
                DocumentApprovalStepModel,
                DocumentApprovalStepModel.document_info_id == DocumentInfoModel.id,
            )
            .options(joinedload(DocumentInfoModel.approval_steps))
            .filter(
                DocumentInfoModel.need_approval == 1, 
                or_(
                    DocumentInfoModel.user_id == user_id,                 # 내가 작성한 문서
                    DocumentApprovalStepModel.signed_by_user_id == user_id,  # 내가 결재한 문서
                ),
                DocumentInfoModel.status.in_(
                    ["in_review", "checked", "approved", "rejected"]
                ),
            )
        )

        q = RepositoryEINK._apply_common_filters(
            q, search=search, status=status, date_from=date_from, date_to=date_to
        )
        q = q.distinct(DocumentInfoModel.id)  # 중복 제거

        return q.limit(limit).all()


    # ─────────────────────────────
    # Tab 4: 결재완료
    #  - status=='approved' AND (내가 작성 OR 내가 결재 참여)
    # ─────────────────────────────
    @staticmethod
    def list_my_completed_documents(
        user_id: int,
        search: Optional[str] = None,
        status: Optional[str] = None,  # 기본은 무시하고 approved로 강제
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[DocumentInfoModel]:
        q = (
            DocumentInfoModel.query
            .outerjoin(
                DocumentApprovalStepModel,
                DocumentApprovalStepModel.document_info_id == DocumentInfoModel.id,
            )
            .options(joinedload(DocumentInfoModel.approval_steps))
            .filter(
                DocumentInfoModel.need_approval == 1,
                DocumentInfoModel.status == "approved",
                or_(
                    DocumentInfoModel.user_id == user_id,
                    DocumentApprovalStepModel.signed_by_user_id == user_id,
                ),
            )
        )

        # status 인자는 무시하고 나머지 필터만 적용
        q = RepositoryEINK._apply_common_filters(
            q, search=search, status=None, date_from=date_from, date_to=date_to
        )
        q = q.distinct(DocumentInfoModel.id)

        return q.limit(limit).all()

    # ─────────────────────────────
    # Tab 5: 반려함
    #  - status=='approved' AND (내가 작성 OR 내가 결재 참여)
    # ─────────────────────────────    
    @staticmethod
    def list_my_rejected_documents(
        user_id: int,
        user_userid: str | None = None,
        search: Optional[str] = None,
        status: Optional[str] = None,   # 무시 가능(반려 고정)
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[DocumentInfoModel]:

        q = (
            DocumentInfoModel.query
            .outerjoin(
                DocumentApprovalStepModel,
                DocumentApprovalStepModel.document_info_id == DocumentInfoModel.id,
            )
            .options(joinedload(DocumentInfoModel.approval_steps))
            .filter(
                DocumentInfoModel.need_approval == 1,
                DocumentInfoModel.status == "rejected",
                or_(
                    DocumentInfoModel.user_id == user_id,                    # ✅ 내가 작성자
                    DocumentApprovalStepModel.signed_by_user_id == user_id,  # ✅ 내가 결재 참여자(서명 이력)
                    # (선택) snapshot 기반 참여까지 포함하고 싶으면:
                    # DocumentApprovalStepModel.userid_snapshot == user_userid,
                )
            )
        )

        # status는 rejected로 고정이니 공통필터에 넘길 때는 status=None로 두는게 안전
        q = RepositoryEINK._apply_common_filters(
            q, search=search, status=None, date_from=date_from, date_to=date_to
        )
        q = q.distinct(DocumentInfoModel.id).order_by(DocumentInfoModel.id.desc())

        return q.limit(limit).all()

    # ─────────────────────────────
    # Tab 5: Bulletin_Files
    #  - need_approval=0 AND status='bulletin_files'
    #  - 결재라인 없는 문서만 "완전 분리"
    # ─────────────────────────────
    @staticmethod
    def list_bulletin_files_documents(
        search: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 200,
    ) -> List[DocumentInfoModel]:
        q = (
            DocumentInfoModel.query
            .filter(
                DocumentInfoModel.need_approval == 0,
                DocumentInfoModel.status == "bulletin_files",
            )
        )

        # bulletin_files는 status가 고정이니까 공통필터에서 status는 빼는게 안전
        q = RepositoryEINK._apply_common_filters(q, search=search, status=None, date_from=date_from, date_to=date_to)

        return q.limit(limit).all()


#######################################################
################  STAMP    ############################
#######################################################

    @staticmethod
    def create_stamp_asset(
        *,
        name: str,
        filename: str,
        stored_path: str,
        created_by: Optional[int] = None,
        mime: Optional[str] = None,
        width: Optional[int] = None,
        height: Optional[int] = None,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> int:
        row = StampAsset(
            name=name,
            filename=filename,
            stored_path=stored_path,
            created_by=created_by,
            mime=mime,
            width=width,
            height=height,
            sort_order=int(sort_order or 0),
            is_active=bool(is_active),
        )
        db.session.add(row)
        db.session.commit()
        return int(row.id)

    @staticmethod
    def list_stamp_assets(active_only: bool = True) -> List[StampAsset]:
        q = db.session.query(StampAsset)
        if active_only:
            q = q.filter(StampAsset.is_active.is_(True))
        return (
            q.order_by(asc(StampAsset.sort_order), desc(StampAsset.created_at), desc(StampAsset.id))
             .all()
        )

    @staticmethod
    def get_stamp_asset(stamp_id: int, active_only: bool = False) -> Optional[StampAsset]:
        q = db.session.query(StampAsset).filter(StampAsset.id == int(stamp_id))
        if active_only:
            q = q.filter(StampAsset.is_active.is_(True))
        return q.first()

    @staticmethod
    def get_stamp_stored_path(stamp_id: int, active_only: bool = True) -> Optional[str]:
        """
        stamp_id → StampAsset.stored_path 반환.
        active_only=True면 비활성 도장은 None 처리.
        """
        if not stamp_id:
            return None

        q = db.session.query(StampAsset).filter(StampAsset.id == int(stamp_id))
        if active_only:
            q = q.filter(StampAsset.is_active.is_(True))

        row = q.first()
        return (row.stored_path if row else None)


    @staticmethod
    def init_approval_flow(document_info_id: int, drafter_user_id: int) -> None:
        """
        A안 정책 초기화:
        - 모든 step: wait
        - 작성(step_type='작성', col_index=1 우선): done (+ signed_by, signed_at)
        - 다음 step 1개: pending
        - 나머지: wait
        """
        try:
            steps = (DocumentApprovalStepModel.query
                     .filter(DocumentApprovalStepModel.document_info_id == document_info_id)
                     .order_by(DocumentApprovalStepModel.col_index.asc())
                     .all())

            if not steps:
                return

            now = now_kst()

            # 1) 전체 wait로 초기화 (기존 pending 남는 것 방지)
            for s in steps:
                s.status = 'wait'

            # 2) 작성 step 선정: (col_index=1 & 작성) 우선
            drafter_step = None
            for s in steps:
                if s.col_index == 1 and s.step_type == '작성':
                    drafter_step = s
                    break
            if drafter_step is None:
                for s in steps:
                    if s.step_type == '작성':
                        drafter_step = s
                        break
            if drafter_step is None:
                drafter_step = steps[0]  # 최후 fallback

            # 3) 작성은 sendfile 순간 완료 처리
            drafter_step.status = 'done'
            drafter_step.signed_by_user_id = drafter_user_id
            drafter_step.signed_at = now

            # 4) 다음 step 1개만 pending
            next_step = None
            for s in steps:
                if s.col_index > drafter_step.col_index:
                    next_step = s
                    break
            if next_step is not None:
                next_step.status = 'pending'

            # 5) 문서 큰 상태는 in_review 유지(need_approval 문서라면)
            doc = DocumentInfoModel.query.get(document_info_id)
            if doc is not None:
                if doc.status != 'in_review':
                    doc.status = 'in_review'
                if getattr(doc, "target_dir", None) != 'in_review':
                    doc.target_dir = 'in_review'

            db.session.commit()

        except SQLAlchemyError:
            db.session.rollback()
            raise

    @staticmethod
    def get_user_by_no(user_no: int) -> Optional[User]:
        try:
            return db.session.get(User, int(user_no))
        except Exception:
            return None

    @staticmethod
    def _step_doc_fk_col():
        for name in ("doc_id", "document_info_id", "document_id"):
            if hasattr(DocumentApprovalStepModel, name):
                return getattr(DocumentApprovalStepModel, name)
        raise RuntimeError("DocumentApprovalStepModel has no doc fk column (doc_id/document_info_id/document_id)")



    @staticmethod
    def find_pending_step_for_actor(*, doc_id: int, actor_no: int | None, actor_userid: str | None):
        """
        ✅ 정확 기준:
          - status='pending'
          - userid_snapshot == actor_userid  (1순위)
          - username_snapshot == actor.username (2순위 fallback)
        """
        doc_fk = RepositoryEINK._step_doc_fk_col()

        q = (
            db.session.query(DocumentApprovalStepModel)
            .filter(doc_fk == int(doc_id))
            .filter(DocumentApprovalStepModel.status == "pending")
        )

        # actor_username 확보 (username_snapshot 비교용)
        actor_username = None
        if actor_no is not None:
            try:
                u = db.session.get(User, int(actor_no))
                actor_username = getattr(u, "username", None)
            except Exception:
                actor_username = None

        # ✅ 매칭 조건 (userid_snapshot / username_snapshot만 사용)
        conds = []

        if actor_userid and hasattr(DocumentApprovalStepModel, "userid_snapshot"):
            conds.append(DocumentApprovalStepModel.userid_snapshot == str(actor_userid).strip())

        if actor_username and hasattr(DocumentApprovalStepModel, "username_snapshot"):
            conds.append(DocumentApprovalStepModel.username_snapshot == str(actor_username).strip())

        if not conds:
            return None

        st = (
            q.filter(or_(*conds))
             .order_by(asc(DocumentApprovalStepModel.col_index), asc(DocumentApprovalStepModel.id))
             .first()
        )

        # ✅ 디버그(원인 추적용)
        try:
            current_app.logger.debug(
                "[find_pending_step_for_actor] doc_id=%s actor_no=%s actor_userid=%r actor_username=%r -> found=%s col=%s",
                doc_id, actor_no, actor_userid, actor_username,
                bool(st),
                getattr(st, "col_index", None) if st else None
            )
        except Exception:
            pass

        return st


    @staticmethod
    def _patch_layout_snapshot_mark(
        *,
        doc: DocumentInfoModel,
        col_index: int,
        mark_status: str,            # 'done' | 'rejected'
        mark_text: Optional[str],    # '완료' | '반려'
        actor_photo_1: Optional[str] # 파일명만(또는 DB값), file_management에서 basename 처리
    ) -> Dict[str, Any]:
        snap = doc.layout_snapshot_json if isinstance(doc.layout_snapshot_json, dict) else {}
        editor_layers = snap.get("editor_layers") or []
        if not isinstance(editor_layers, list):
            return snap

        for L in editor_layers:
            if (L.get("type") or "").lower() != "approval_box":
                continue
            cols = L.get("columns") or []
            if not isinstance(cols, list):
                continue

            # col_index는 1-based
            idx0 = int(col_index) - 1
            if idx0 < 0 or idx0 >= len(cols):
                continue

            c = cols[idx0] if isinstance(cols[idx0], dict) else {}
            c["status"] = mark_status  # ✅ 렌더링에서 사용
            if mark_text:
                c["stamp_text"] = mark_text
            # 승인 시 서명 파일이 있으면 넣어둠(없으면 렌더에서 "완료")
            if actor_photo_1:
                c["user_photo_1"] = actor_photo_1
            cols[idx0] = c
            L["columns"] = cols
            break

        snap["editor_layers"] = editor_layers
        return snap


    @staticmethod
    def apply_approval_action(
        doc_id: int,
        actor_db_id: int,          # ✅ document_approval_steps.signed_by_user_id에 넣을 user.id
        actor_userid: str,         # ✅ userid_snapshot 비교
        actor_username: str,       # ✅ username_snapshot 비교
        action: str,               # "approve" | "reject"
        note: str | None = None,
    ) -> dict:
        doc = DocumentInfoModel.query.get(doc_id)
        if not doc:
            return {"ok": False, "why": "doc_not_found"}

        steps = list(getattr(doc, "approval_steps", []) or [])

        def _step_key(s):
            for k in ("step_order", "col_index", "id"):
                v = getattr(s, k, None)
                if v is not None:
                    return int(v)
            return 10**9

        steps_sorted = sorted(steps, key=_step_key)

        pending_list = [s for s in steps_sorted if getattr(s, "status", None) == "pending"]
        pending = pending_list[0] if pending_list else None
        if not pending:
            return {"ok": False, "why": "no_pending_step"}

        p_uid = (getattr(pending, "userid_snapshot", None) or "").strip()
        p_unm = (getattr(pending, "username_snapshot", None) or "").strip()
        a_uid = (actor_userid or "").strip()
        a_unm = (actor_username or "").strip()

        # ✅ 정확 기준: userid_snapshot / username_snapshot 일치만 허용
        is_match = (a_uid and p_uid and a_uid == p_uid) or (a_unm and p_unm and a_unm == p_unm)

        current_app.logger.debug(
            "[apply_approval_action] doc_id=%s action=%s pending_col=%s pending_uid=%r pending_unm=%r actor_uid=%r actor_unm=%r match=%s",
            doc_id, action, getattr(pending, "col_index", None), p_uid, p_unm, a_uid, a_unm, is_match
        )

        if not is_match:
            return {
                "ok": False,
                "why": "not_your_pending_step",
                "pending": {"col_index": getattr(pending, "col_index", None), "userid_snapshot": p_uid, "username_snapshot": p_unm},
                "actor": {"userid": a_uid, "username": a_unm},
            }

        now = datetime.now()  # 프로젝트가 naive KST를 쓰는 편이면 이게 가장 안전

        # ✅ 승인/반려 공통: 현재 pending step에 서명자/시간은 반드시 기록
        pending.signed_by_user_id = int(actor_db_id)  # (1) 형 요구: user.id
        pending.signed_at = now                       # (2) 형 요구: 현재시간
        if note is not None and hasattr(pending, "note"):
            pending.note = note

        if action == "approve":
            pending.status = "done"

            # 다음 스텝 pending 승격(있으면)
            # - 보통 wait → pending
            next_step = None
            for s in steps_sorted:
                if getattr(s, "status", None) in ("wait", "pending") and _step_key(s) > _step_key(pending):
                    next_step = s
                    break

            if next_step and next_step.status != "done":
                next_step.status = "pending"
                doc.status = "in_review"
            else:
                # 더 이상 결재할 사람이 없으면 문서 승인 완료
                doc.status = "approved"

            db.session.commit()
            return {
                "ok": True,
                "action": "approve",
                "doc_status": doc.status,
                "signed_step": {"id": pending.id, "col_index": getattr(pending, "col_index", None)},
                "next_step": {"id": getattr(next_step, "id", None), "col_index": getattr(next_step, "col_index", None)} if next_step else None,
            }

        if action == "reject":
            pending.status = "rejected"
            doc.status = "rejected"

            # (선택) 뒤 스텝을 wait로 돌리고 싶으면 여기서 정리
            for s in steps_sorted:
                if _step_key(s) > _step_key(pending) and getattr(s, "status", None) in ("pending", "wait"):
                    s.status = "wait"

            db.session.commit()
            return {
                "ok": True,
                "action": "reject",
                "doc_status": doc.status,
                "signed_step": {"id": pending.id, "col_index": getattr(pending, "col_index", None)},
            }

        return {"ok": False, "why": "invalid_action", "action": action}
    


    @staticmethod
    def get_approval_runtime_map(doc_id: int) -> dict[int, dict]:
        """
        document_approval_steps에서 col_index별 status를 읽어서
        렌더러가 쓰기 쉬운 runtime map으로 반환.
        return 예:
          {2: {"status":"done","stamp_text":"완료","step_id":210}, ...}
        """

        try:
            rows = (
                DocumentApprovalStepModel.query
                .filter(DocumentApprovalStepModel.document_info_id == int(doc_id))
                .order_by(DocumentApprovalStepModel.col_index.asc())
                .all()
            )

            out: dict[int, dict] = {}
            for r in rows:
                col = int(getattr(r, "col_index", 0) or 0)
                st = (getattr(r, "status", "") or "").strip().lower()

                # 텍스트 정책(원하면 여기서 바꾸면 됨)
                stamp_text = None
                if st in ("reject", "rejected", "deny", "denied", "returned"):
                    stamp_text = "반려"
                elif st in ("done", "approved", "approve", "signed"):
                    stamp_text = "완료"

                out[col] = {
                    "status": st,
                    "stamp_text": stamp_text,
                    "step_id": int(getattr(r, "id", 0) or 0),
                }

            current_app.logger.debug(
                "[approval_runtime_map] doc_id=%s steps=%s sample=%s",
                doc_id, len(out), list(out.items())[:3]
            )
            return out

        except Exception:
            current_app.logger.debug("[approval_runtime_map] failed doc_id=%s", doc_id, exc_info=True)
            return {}



