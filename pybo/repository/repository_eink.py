# repository/repository_eink.py
from typing import Optional, Dict, Any, List
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import desc
from pybo import db
import json, os
import logging

try:
    # Flask 컨텍스트가 있으면 current_app 로거 사용
    from flask import current_app
except Exception:  # pragma: no cover
    current_app = None  # type: ignore

# === 모델 임포트 (형이 준 models.py 기준) ===
from ..models import (
    User,
    Upload as UploadModel,
    SignLayout as SignLayoutModel,
    ApprovalRoute as ApprovalRouteModel,
    ApprovalRouteStep as ApprovalRouteStepModel,
    kst_now_naive as now_kst,
)

# (프로젝트 내 다른 기능 호환용: 없으면 무시)
try:
    from ..models import ImageData
except Exception:
    ImageData = None


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
    서버 플로우 확장: proceed(검토 대기) → checked(승인 대기) → updates(승인 완료)
    uploads: 전결 또는 결재 불필요
    """
    out = v if v in ("uploads", "proceed", "checked", "updates") else "proceed"
    _dbg("coerce_target_dir", input=v, output=out)
    return out

def _coerce_status(v: Optional[str]) -> str:
    """
    in_review (검토 대기), checked (검토 완료/승인 대기), approved, rejected, draft
    """
    out = v if v in ("draft", "in_review", "checked", "approved", "rejected") else "draft"
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
    E-INK 업로드/결재/레이아웃 레포지토리 (models.py 최신 스키마 대응)
    """

    # ================== 대시보드 장비 목록 ==================
    @staticmethod
    def get_devices_for_dashboard() -> Optional[List[Dict[str, Any]]]:
        """
        현재 Device 모델이 없으므로 컨트롤러의 _default_devices() 를 쓰게 하려면 None을 반환.
        추후 Device 테이블 추가 시 여기서 실제 목록 리턴.
        """
        _dbg("get_devices_for_dashboard:start")
        _dbg("get_devices_for_dashboard:return", value=None)
        return None  # 컨트롤러 폴백 사용

    # ================== 부서 목록 & 부서별 사용자 ==================
    @staticmethod
    def list_departments() -> List[str]:
        """
        User.department의 DISTINCT 목록 반환.
        """
        _dbg("list_departments:start")
        try:
            rows = db.session.query(User.department).filter(User.department.isnot(None)).distinct().all()
            depts = [r[0] for r in rows if r and r[0]]
            _dbg("list_departments:done", count=len(depts), depts=depts[:10])  # 최대 10개만 미리보기
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
                User.no, User.userid, User.username, User.department, User.position, User.photo_1
            )
            if department:
                q = q.filter(User.department == department)
            q = q.order_by(User.username.asc())
            rows = q.all()
            users: List[Dict[str, Any]] = []
            for (no, userid, username, dept, position, photo_1) in rows:
                users.append({
                    "id": no,
                    "userid": userid or "",
                    "username": username or "",
                    "department": dept or "",
                    "position": position or "",
                    "photo_1": photo_1 or "",
                    "display": username or userid or str(no),
                })
            _dbg("list_users_by_department:done", count=len(users), sample=users[:3])
            return users
        except SQLAlchemyError:
            _logger().debug("[list_users_by_department] DB error", exc_info=True)
            return []

    # ================== 결재선 목록 ==================
    @staticmethod
    def get_approval_routes() -> List[Dict[str, Any]]:
        """
        ApprovalRoute 및 steps를 프런트가 기대하는 구조로 직렬화.
        - 작성자(creator) 최신 필드 포함
        - 각 step의 최신 assignee 필드 + 스냅샷 동시 제공
        """
        _dbg("get_approval_routes:start")
        try:
            routes: List[Dict[str, Any]] = []
            route_rows = (
                db.session.query(ApprovalRouteModel)
                .order_by(ApprovalRouteModel.id.desc())
                .all()
            )
            _dbg("get_approval_routes:rows", count=len(route_rows))
            for r in route_rows:
                creator = r.creator
                creator_info = {
                    "id": getattr(creator, "no", None),
                    "userid": getattr(creator, "userid", None),
                    "username": getattr(creator, "username", None),
                    "department": getattr(creator, "department", None),
                    "position": getattr(creator, "position", None),
                    "photo_1": getattr(creator, "photo_1", None),
                } if creator else None

                steps_out: List[Dict[str, Any]] = []
                for st in (r.steps or []):
                    assignee = st.assignee
                    steps_out.append({
                        "id": int(st.id),
                        "step_order": int(st.step_order),
                        "role": st.role,  # 'author' | 'review' | 'approve' | 'review2' | 'approve2'
                        "sign_required": bool(st.sign_required),
                        "assignee": {
                            "id": getattr(assignee, "no", None) if assignee else None,
                            "userid": getattr(assignee, "userid", None) if assignee else None,
                            "username": getattr(assignee, "username", None) if assignee else None,
                            "department": getattr(assignee, "department", None) if assignee else None,
                            "position": getattr(assignee, "position", None) if assignee else None,
                            "photo_1": getattr(assignee, "photo_1", None) if assignee else None,
                            "display": _user_display_string(assignee),
                        },
                        "assignee_snapshot": {
                            "userid": getattr(st, "assignee_userid_snapshot", None),
                            "username": getattr(st, "assignee_username_snapshot", None),
                            "department": getattr(st, "assignee_department_snapshot", None),
                            "position": getattr(st, "assignee_position_snapshot", None),
                            "photo_1": getattr(st, "assignee_photo_1_snapshot", None),
                        },
                        "assignee_group_id": getattr(st, "assignee_group_id", None),
                    })
                routes.append({
                    "id": int(r.id),
                    "name": r.name,
                    "created_by": r.created_by,
                    "created_at": r.created_at,
                    "creator": creator_info,
                    "steps": steps_out,
                })
            _dbg("get_approval_routes:done", count=len(routes))
            return routes
        except SQLAlchemyError:
            _logger().debug("[get_approval_routes] DB error", exc_info=True)
            return []

    # ------------------------------------------------------------------
    # 업로드 레코드 생성
    # ------------------------------------------------------------------
    @staticmethod
    def create_upload_record(
        *,
        user_id: Optional[int],
        device_id: Optional[str],
        orig_filename: str,
        stored_path: str,
        target_dir: str,               # 'uploads' | 'proceed' | 'checked' | 'updates'
        need_approval: bool,
        status: str,                   # 'draft' | 'in_review' | 'checked' | 'approved' | 'rejected'
        pages: int = 1,
        width: Optional[int] = None,
        height: Optional[int] = None,
        mode: Optional[str] = None,    # 'BW' | 'BWRY' | 'BWRYBG'
        scale: Optional[str] = None,   # 'fit' | 'fill' | 'percent'
        percent: Optional[int] = None,
        rotate: Optional[int] = None,
        route_id: Optional[int] = None,
        sign_layout_id: Optional[int] = None,
        route_snapshot: Optional[Dict[str, Any]] = None,
        layout_snapshot: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """
        uploads 테이블에 1건 생성.
        - Enum 필드 값 검증을 가볍게 하고, 불일치 시 안전한 기본값으로 치환.
        - JSON 컬럼은 dict/list 그대로 저장.
        """
        _dbg("create_upload_record:start", device_id=device_id, target_dir=target_dir, status=status,
             width=width, height=height, mode=mode, scale=scale, percent=percent, rotate=rotate,
             route_id=route_id, sign_layout_id=sign_layout_id)
        row = UploadModel(
            user_id=user_id,
            device_id=device_id or None,
            orig_filename=orig_filename,
            stored_path=stored_path,
            target_dir=_coerce_target_dir(target_dir),
            need_approval=bool(need_approval),
            status=_coerce_status(status),
            pages=pages,
            width=width,
            height=height,
            mode=mode,
            scale=scale,
            percent=percent,
            rotate=rotate,
            route_id=route_id,
            sign_layout_id=sign_layout_id,
            route_snapshot_json=_json_passthrough(route_snapshot),
            layout_snapshot_json=_json_passthrough(layout_snapshot),
            metadata_json=_json_passthrough(metadata),
            created_at=now_kst(),
            updated_at=now_kst(),
        )
        try:
            db.session.add(row)
            db.session.commit()
            _dbg("create_upload_record:committed", upload_id=int(row.id))
            return int(row.id)
        except SQLAlchemyError as e:
            _logger().debug("[create_upload_record] DB error, rollback", exc_info=True)
            db.session.rollback()
            raise e

    # ------------------------------------------------------------------
    # 업로드 상태/디렉터리 업데이트
    # ------------------------------------------------------------------
    @staticmethod
    def update_upload_status(
        upload_id: int,
        *,
        status: Optional[str] = None,          # 'draft' | 'in_review' | 'checked' | 'approved' | 'rejected'
        target_dir: Optional[str] = None,      # 'uploads' | 'proceed' | 'checked' | 'updates'
        route_id: Optional[int] = None,
        sign_layout_id: Optional[int] = None,
        route_snapshot: Optional[Dict[str, Any]] = None,
        layout_snapshot: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        _dbg("update_upload_status:start", upload_id=upload_id, status=status, target_dir=target_dir,
             route_id=route_id, sign_layout_id=sign_layout_id)
        if not upload_id:
            _dbg("update_upload_status:invalid_id")
            return False
        try:
            row = db.session.get(UploadModel, upload_id)
            if not row:
                _dbg("update_upload_status:not_found", upload_id=upload_id)
                return False

            if status in ("draft", "in_review", "checked", "approved", "rejected"):
                row.status = status
            if target_dir in ("uploads", "proceed", "checked", "updates"):
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

            row.updated_at = now_kst()
            db.session.commit()
            _dbg("update_upload_status:committed", upload_id=upload_id,
                 status=row.status, target_dir=row.target_dir)
            return True
        except SQLAlchemyError:
            _logger().debug("[update_upload_status] DB error, rollback", exc_info=True)
            db.session.rollback()
            return False

    # ------------------------------------------------------------------
    # (옵션) 결재 단계 전진 헬퍼: proceed -> checked -> updates
    # ------------------------------------------------------------------
    @staticmethod
    def advance_upload_stage(upload_id: int, stage: str) -> bool:
        """
        stage:
          - 'review'  : 검토 완료 → checked / status='checked'
          - 'approve' : 승인 완료 → updates / status='approved'
        """
        _dbg("advance_upload_stage:start", upload_id=upload_id, stage=stage)
        stage = (stage or "").lower()
        try:
            row = db.session.get(UploadModel, upload_id)
            if not row:
                _dbg("advance_upload_stage:not_found", upload_id=upload_id)
                return False

            if stage == "review":
                row.status = "checked"
                row.target_dir = "checked"
            elif stage == "approve":
                row.status = "approved"
                row.target_dir = "updates"
            else:
                _dbg("advance_upload_stage:invalid_stage", stage=stage)
                return False

            row.updated_at = now_kst()
            db.session.commit()
            _dbg("advance_upload_stage:committed", upload_id=upload_id,
                 status=row.status, target_dir=row.target_dir)
            return True
        except SQLAlchemyError:
            _logger().debug("[advance_upload_stage] DB error, rollback", exc_info=True)
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
    @staticmethod
    def create_approval_route(
        *,
        name: str,
        created_by: Optional[int],
        steps: List[Dict[str, Any]],  # [{step_order, role, assignee_user_id, sign_required(True/False), assignee_group_id(optional)}]
    ) -> int:
        """
        예:
          steps = [
            {"step_order":1, "role":"review",  "assignee_user_id":101, "sign_required":True},
            {"step_order":2, "role":"approve", "assignee_user_id":202, "sign_required":True},
          ]
        role은 'author' | 'review' | 'approve' | 'review2' | 'approve2'
        """
        _dbg("create_approval_route:start", name=name, created_by=created_by, steps=_dump_json(steps, 400))
        route = ApprovalRouteModel(
            name=name,
            created_by=created_by,
            created_at=now_kst(),
        )
        try:
            db.session.add(route)
            db.session.flush()  # route.id 확보

            normalized = []
            for st in steps or []:
                role = st.get("role")
                if not _role_is_valid(role):
                    _dbg("create_approval_route:skip_invalid_role", role=role)
                    continue
                normalized.append({
                    "step_order": int(st.get("step_order", 0)),
                    "role": role,
                    "assignee_user_id": st.get("assignee_user_id"),
                    "assignee_group_id": st.get("assignee_group_id"),
                    "sign_required": bool(st.get("sign_required", True)),
                })
            normalized.sort(key=lambda x: x["step_order"] or 0)
            _dbg("create_approval_route:normalized", steps=normalized)

            for i, st in enumerate(normalized, start=1):
                row = ApprovalRouteStepModel(
                    route_id=route.id,
                    step_order=i,
                    role=st["role"],
                    assignee_user_id=st["assignee_user_id"],
                    assignee_group_id=st["assignee_group_id"],
                    sign_required=st["sign_required"],
                )
                db.session.add(row)

            db.session.commit()
            _dbg("create_approval_route:committed", route_id=int(route.id), step_count=len(normalized))
            return int(route.id)
        except SQLAlchemyError as e:
            _logger().debug("[create_approval_route] DB error, rollback", exc_info=True)
            db.session.rollback()
            raise e

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
        parent_box: Dict[str, int],     # {x,y,w,h}
        tpl_json: Dict[str, Any],
        slots_json: List[Dict[str, Any]],
        layers_json: Optional[Dict[str, Any]] = None,
        version: int = 1,
    ) -> int:
        """
        프론트의 layout 스냅샷을 DB형식에 맞춰 저장.
        - parent_box는 절대좌표(BASE 1200x1600 기준)여야 함.
        """
        _dbg("insert_sign_layout:start", name=name, owner_user_id=owner_user_id,
             canvas=f"{canvas_w}x{canvas_h}", parent_box=parent_box, version=version)
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
            slots_json=_json_passthrough(slots_json or []),
            layers_json=_json_passthrough(layers_json or {}),
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
            _logger().debug("[insert_sign_layout] DB error, rollback", exc_info=True)
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
                "parent": {"x": row.parent_x, "y": row.parent_y, "w": row.parent_w, "h": row.parent_h},
                "tpl_json": row.tpl_json,
                "slots_json": row.slots_json,
                "layers_json": row.layers_json,
                "version": row.version,
                "owner_user_id": row.owner_user_id,
                "created_at": row.created_at,
                "updated_at": row.updated_at,
            }
            _dbg("get_latest_sign_layout_by_name:done", sign_layout_id=row.id, version=row.version)
            return out
        except SQLAlchemyError:
            _logger().debug("[get_latest_sign_layout_by_name] DB error", exc_info=True)
            return None

    # ------------------------------------------------------------------
    # 업로드 1건 상세 조회 (스냅샷 포함) – 필요 시 사용
    # ------------------------------------------------------------------
    @staticmethod
    def get_upload(upload_id: int) -> Optional[UploadModel]:
        _dbg("get_upload:start", upload_id=upload_id)
        try:
            row = db.session.get(UploadModel, upload_id)
            _dbg("get_upload:done", found=bool(row))
            return row
        except SQLAlchemyError:
            _logger().debug("[get_upload] DB error", exc_info=True)
            return None

    @staticmethod
    def get_latest_pending_for_user(*, userid: str) -> Optional[Dict[str, Any]]:
        """
        userid가 검토(review) 또는 승인(approve) 담당인 최신 1건 리턴.
        DB status는 'in_review' 또는 'checked'를 대상으로 검색.
        target_dir는 'proceed' 또는 'checked'가 정상.
        """
        _dbg("get_latest_pending_for_user:start", userid=userid)
        try:
            q = (
                db.session.query(UploadModel)
                .filter(UploadModel.status.in_(["in_review", "checked"]))
                .filter(UploadModel.target_dir.in_(["proceed", "checked"]))
                .order_by(desc(UploadModel.id))
            )
            rows = q.all()
            for row in rows:
                assignees = None
                try:
                    md = row.metadata_json or {}
                    assignees = (md.get("assignees") or {}) if isinstance(md, dict) else {}
                except Exception:
                    assignees = {}

                is_review = (row.status == "in_review" and row.target_dir == "proceed" and assignees.get("review") == userid)
                is_approve = (row.status == "checked" and row.target_dir == "checked" and assignees.get("approve") == userid)
                if not (is_review or is_approve):
                    continue

                # 메타 파일 경로 추정 (같은 폴더, 같은 베이스명)
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
                    "assignees": assignees,
                    "meta_path": meta_path if os.path.isfile(meta_path) else None,
                    "width": row.width or 1200,
                    "height": row.height or 1600,
                    "mode": row.mode or "BWRYBG",
                    "created_at": row.created_at,
                }
            _dbg("get_latest_pending_for_user:none")
            return None
        except SQLAlchemyError:
            _logger().debug("[get_latest_pending_for_user] DB error", exc_info=True)
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
            _logger().debug("[get_user_sign_path_by_userid] DB error", exc_info=True)
            return None


    @staticmethod
    def get_layout_snapshot_by_meta(meta_path: str) -> Optional[Dict[str, Any]]:
        """
        meta의 bmp 베이스파일명으로 uploads 레코드를 추정해 layout_snapshot_json 반환.
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
            # stored_path LIKE %bmp_name
            q = (
                db.session.query(UploadModel)
                .filter(UploadModel.stored_path.like(f"%{bmp_name}"))
                .order_by(desc(UploadModel.id))
            )
            row = q.first()
            if not row:
                _dbg("get_layout_snapshot_by_meta:not_found_by_name", bmp_name=bmp_name)
                return None
            snap = row.layout_snapshot_json
            _dbg("get_layout_snapshot_by_meta:done", has=bool(snap))
            return snap if isinstance(snap, dict) else None
        except Exception:
            _logger().debug("[get_layout_snapshot_by_meta] error", exc_info=True)
            return None


    @staticmethod
    def update_upload_status_by_meta(*, old_meta_path: str, new_dir: str, new_status: str, note: Optional[str] = None) -> bool:
        """
        파일 번들을 이동한 뒤, 해당 건의 DB status/dir/stored_path 갱신.
        - new_dir: 'uploads' | 'proceed' | 'checked' | 'updates'
        - new_status: 'in_review' | 'checked' | 'approved' | 'rejected' | 'draft'
        - old_meta_path: 이동 전/후 어느 쪽이든 OK (아래에서 새 경로를 추정해본다)
        """
        _dbg("update_upload_status_by_meta:start", old_meta_path=old_meta_path, new_dir=new_dir, new_status=new_status)
        try:
            meta_path = old_meta_path

            # 1) 옛 경로가 이미 이동되어 없을 수 있으므로, 새 위치를 추정해본다.
            if not (meta_path and os.path.isfile(meta_path)):
                try:
                    base_dir = os.path.dirname(os.path.dirname(old_meta_path))  # D:/bmp_files
                    guess = os.path.join(base_dir, new_dir, os.path.basename(old_meta_path))
                    if os.path.isfile(guess):
                        meta_path = guess
                        _dbg("update_upload_status_by_meta:resolved_new_meta_path", meta_path=meta_path)
                    else:
                        _dbg("update_upload_status_by_meta:meta_missing", tried=guess)
                        return False
                except Exception:
                    _dbg("update_upload_status_by_meta:meta_missing_unresolvable")
                    return False

            # 2) 메타 열고 BMP 파일명 획득
            with open(meta_path, "r", encoding="utf-8") as f:
                js = json.load(f)
            bmp_name = js.get("file")
            if not bmp_name:
                _dbg("update_upload_status_by_meta:no_bmp_name")
                return False

            # 3) BMP 파일명으로 uploads 레코드를 역추적 (디렉터리 변동과 무관하게 매칭)
            q = (
                db.session.query(UploadModel)
                .filter(UploadModel.stored_path.like(f"%{bmp_name}"))
                .order_by(desc(UploadModel.id))
            )
            row = q.first()
            if not row:
                _dbg("update_upload_status_by_meta:not_found", bmp_name=bmp_name)
                return False

            # 4) 상태/디렉터리 갱신
            if new_status in ("draft", "in_review", "checked", "approved", "rejected"):
                row.status = new_status
            if new_dir in ("uploads", "proceed", "checked", "updates"):
                row.target_dir = new_dir

            # 5) stored_path도 이동 후 실제 경로로 동기화
            root = os.path.dirname(os.path.dirname(meta_path))  # D:/bmp_files
            new_bmp_path = os.path.join(root, new_dir, bmp_name)
            row.stored_path = new_bmp_path

            # 6) 비고 로그(optional)
            meta = row.metadata_json if isinstance(row.metadata_json, dict) else {}
            if note:
                logs = meta.get("notes", [])
                ts = now_kst().isoformat() if hasattr(now_kst(), "isoformat") else str(now_kst())
                logs.append({"ts": ts, "note": note})
                meta["notes"] = logs
            row.metadata_json = meta

            row.updated_at = now_kst()
            db.session.commit()
            _dbg("update_upload_status_by_meta:committed",
                upload_id=int(row.id), status=row.status, dir=row.target_dir, stored_path=row.stored_path)
            return True

        except SQLAlchemyError:
            _logger().debug("[update_upload_status_by_meta] DB error", exc_info=True)
            db.session.rollback()
            return False

