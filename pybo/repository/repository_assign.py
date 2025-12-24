# pybo/repository/repository_assign.py

from typing import Optional, List, Dict, Any
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func
from datetime import datetime, timezone, timedelta

from pybo import db
from ..models import EInkCompany, EInkBuilding, EInkBoard, EInkDevice, EInkBoardBinding

KST_TZ = timezone(timedelta(hours=9))

def kst_now_naive():
    return datetime.now(KST_TZ).replace(tzinfo=None)


class RepositoryAssign:
    # ============================================================
    # Utils
    # ============================================================
    @staticmethod
    def _norm_code(s: str, max_len: int = 10) -> str:
        s = (s or "").strip().upper()
        out = []
        for ch in s:
            if ("A" <= ch <= "Z") or ("0" <= ch <= "9"):
                out.append(ch)
        return "".join(out)[:max_len]

    @staticmethod
    def _safe_device_id(raw: str, max_len: int = 64) -> str:
        raw = (raw or "").strip()
        out = []
        for ch in raw:
            if ch.isalnum() or ch in "._-":
                out.append(ch)
        return "".join(out)[:max_len]

    @staticmethod
    def _floor_token(floor_no: int) -> str:
        if floor_no == 9999:
            return "O00"
        if floor_no >= 1:
            return f"F{floor_no:02d}"
        return f"B{abs(floor_no):02d}"

    @staticmethod
    def _board_token(board_no: int) -> str:
        return f"{board_no:03d}"

    @staticmethod
    def make_board_code(company_code: str, site_code: str, building_code: str,
                        floor_no: int, board_no: int) -> str:
        cc = RepositoryAssign._norm_code(company_code, 8)
        bc = RepositoryAssign._norm_code(building_code, 10)
        sc = RepositoryAssign._norm_code(site_code, 10) or "HQ"
        if not cc:
            raise ValueError("company_code가 비어있어 board_code 생성 불가")
        if not bc:
            raise ValueError("building_code가 비어있어 board_code 생성 불가")
        ft = RepositoryAssign._floor_token(floor_no)
        bt = RepositoryAssign._board_token(board_no)
        return f"{cc}-{sc}-{bc}-{ft}-{bt}"

    # ============================================================
    # TAB3: Device
    # ============================================================
    @staticmethod
    def create_device(
        company_id: int,
        device_id: str,
        device_name: str,
        panel_res: str,
        bpp: int,
        cap: str,
        user_no: Optional[int] = None,
        user_userid: Optional[str] = None,
    ) -> EInkDevice:
        comp = EInkCompany.query.get(company_id)
        if not comp:
            raise ValueError("존재하지 않는 company_id")

        # 운영 정책: 회사코드가 없으면 등록 불가
        if not (comp.code or "").strip():
            raise ValueError("회사코드(company.code)가 없어 디바이스 등록 불가(운영 정책)")

        did = RepositoryAssign._safe_device_id(device_id)
        if not did:
            raise ValueError("device_id가 올바르지 않아")

        dn = (device_name or "").strip()
        if not dn:
            raise ValueError("device_name은 필수야")

        pr = (panel_res or "").strip()
        if not pr:
            raise ValueError("panel_res required")

        try:
            bpp_i = int(bpp)
        except Exception:
            raise ValueError("bpp 값이 올바르지 않아")

        if not (1 <= bpp_i <= 8):
            raise ValueError("bpp 범위 오류(1~8)")

        cap = (cap or "BWR").strip() or "BWR"

        dev = EInkDevice(
            company_id=company_id,
            user_no=user_no,
            user_userid=(user_userid or "").strip() or None,

            device_id=did,
            device_name=dn,
            panel_res=pr,
            bpp=bpp_i,
            cap=cap,

            supports_partial=True,
            supports_rle=True,
            supports_zlib=True,

            auth_mode="none",
        )

        db.session.add(dev)
        db.session.commit()
        return dev

    # ============================================================
    # Binding helpers
    #   - active 직접 세팅 금지 (generated column)
    #   - active = (unbound_at IS NULL)
    # ============================================================
    @staticmethod
    def _get_active_binding_by_device(device_pk: int) -> Optional[EInkBoardBinding]:
        return (EInkBoardBinding.query
                .filter(EInkBoardBinding.device_id == device_pk,
                        EInkBoardBinding.unbound_at.is_(None))
                .order_by(EInkBoardBinding.id.desc())
                .first())

    @staticmethod
    def _get_active_bindings_by_board(board_id: int) -> List[EInkBoardBinding]:
        return (EInkBoardBinding.query
                .filter(EInkBoardBinding.board_id == board_id,
                        EInkBoardBinding.unbound_at.is_(None))
                .order_by(EInkBoardBinding.id.asc())
                .all())

    @staticmethod
    def count_active_bindings_by_board(board_id: int) -> int:
        n = (db.session.query(func.count(EInkBoardBinding.id))
             .filter(EInkBoardBinding.board_id == board_id)
             .filter(EInkBoardBinding.unbound_at.is_(None))
             .scalar())
        return int(n or 0)

    # ============================================================
    # TAB3: Bind (Board 1개에 Device 1~N, 기본 10개까지)
    #
    # 정책:
    #  - Board는 동시에 여러 Device 가능 (최대 max_devices_per_board)
    #  - Device는 동시에 한 Board만 가능(UNIQUE(device_id, active)로 강제)
    #  - auto_unbind=True면 "device 기준" 기존 active만 해제 후 재연결
    # ============================================================
    @staticmethod
    def bind_board_device(
        board_id: int,
        device_pk: int,
        reason: str = "",
        bound_by_user_no: Optional[int] = None,
        auto_unbind: bool = True,
        max_devices_per_board: int = 10,
    ) -> EInkBoardBinding:

        board = EInkBoard.query.get(board_id)
        if not board:
            raise ValueError("존재하지 않는 board_id")

        dev = EInkDevice.query.get(device_pk)
        if not dev:
            raise ValueError("존재하지 않는 device_id(pk)")

        # 회사 일치 검증
        company_id = board.building.company_id if board.building else None
        if dev.company_id and company_id and int(dev.company_id) != int(company_id):
            raise ValueError("디바이스 회사와 게시판 회사가 달라 연결 불가")

        # board 당 최대 개수 제한
        cur = RepositoryAssign.count_active_bindings_by_board(board_id)
        if cur >= int(max_devices_per_board):
            raise ValueError(f"이 게시판에는 이미 {cur}개 디바이스가 연결돼 있어. 최대 {max_devices_per_board}개까지 가능")

        now = kst_now_naive()
        reason = (reason or "").strip()

        # device는 동시에 1개만: 기존 active 처리
        active_dev = RepositoryAssign._get_active_binding_by_device(device_pk)
        if active_dev:
            if not auto_unbind:
                raise ValueError("이 디바이스는 이미 다른 게시판에 연결돼 있어(auto_unbind=False)")
            active_dev.unbound_at = now
            if reason and not (active_dev.reason or "").strip():
                active_dev.reason = f"auto-unbind: {reason}"
            db.session.add(active_dev)
            db.session.flush()

        # 새 binding 생성 (active는 generated column이 자동)
        binding = EInkBoardBinding(
            board_id=board_id,
            device_id=device_pk,
            bound_at=now,
            unbound_at=None,
            reason=reason or None,
            bound_by_user_no=bound_by_user_no,
        )

        db.session.add(binding)
        db.session.commit()
        return binding

    # ============================================================
    # TAB3: Unbind
    #   - 예전: board당 active 1개라 1개만 해제
    #   - 이제: board당 active N개 가능 -> "해당 board의 active 전부 해제"
    # ============================================================
    @staticmethod
    def unbind_by_board(
        board_id: int,
        reason: str = "",
        unbound_by_user_no: Optional[int] = None,  # 모델에 컬럼 없으니 현재는 미사용
    ) -> bool:
        actives = RepositoryAssign._get_active_bindings_by_board(board_id)
        if not actives:
            return False

        now = kst_now_naive()
        reason = (reason or "").strip()

        for b in actives:
            b.unbound_at = now
            if reason:
                # 기존 reason이 없으면 채우고, 있으면 덮어쓸지 정책 선택 가능
                # 지금은 "덮어쓰기"로 통일
                b.reason = reason or None
            db.session.add(b)

        db.session.commit()
        return True

    # ============================================================
    # API: 회사별 Board 리스트
    # ============================================================
    @staticmethod
    def list_boards_by_company(company_id: int) -> List[Dict[str, Any]]:
        rows = (db.session.query(EInkBoard.id, EInkBoard.board_code, EInkBoard.name)
                .join(EInkBuilding, EInkBuilding.id == EInkBoard.building_id)
                .filter(EInkBuilding.company_id == company_id)
                .order_by(EInkBoard.board_code.asc(), EInkBoard.id.asc())
                .all())

        return [{
            "id": int(r.id),
            "board_code": r.board_code,
            "name": r.name,
        } for r in rows]

    # ============================================================
    # API: 회사별 "미바인딩" 디바이스 리스트
    #   - device는 동시에 1개 board만 연결 가능(UNIQUE(device_id, active))
    #   - 따라서 active 바인딩된 device는 제외
    # ============================================================
    @staticmethod
    def list_unbound_devices_by_company(company_id: int) -> List[Dict[str, Any]]:
        subq = (db.session.query(EInkBoardBinding.device_id)
                .filter(EInkBoardBinding.unbound_at.is_(None))
                .subquery())

        rows = (EInkDevice.query
                .filter(EInkDevice.company_id == company_id)
                .filter(~EInkDevice.id.in_(subq))
                .order_by(EInkDevice.device_name.asc(), EInkDevice.id.asc())
                .all())

        return [{
            "id": int(d.id),
            "device_id": d.device_id,
            "device_name": d.device_name or "",
            "panel_res": d.panel_res,
        } for d in rows]

    # ============================================================
    # 화면표시: 디바이스별 현재 바인딩 맵
    # ============================================================
    @staticmethod
    def map_active_binding_for_devices(device_ids: List[int]) -> Dict[int, Dict[str, Any]]:
        if not device_ids:
            return {}

        rows = (db.session.query(
                    EInkBoardBinding.device_id,
                    EInkBoardBinding.id.label("binding_id"),
                    EInkBoard.board_code,
                    EInkBoard.name.label("board_name")
                )
                .join(EInkBoard, EInkBoard.id == EInkBoardBinding.board_id)
                .filter(EInkBoardBinding.device_id.in_(device_ids))
                .filter(EInkBoardBinding.unbound_at.is_(None))
                .all())

        out: Dict[int, Dict[str, Any]] = {}
        for r in rows:
            out[int(r.device_id)] = {
                "binding_id": int(r.binding_id),
                "board_code": r.board_code,
                "board_name": r.board_name,
            }
        return out

    # ============================================================
    # (선택) 보드별 현재 연결된 디바이스 목록이 필요하면 UI용으로 사용
    # ============================================================
    @staticmethod
    def list_active_devices_by_board(board_id: int) -> List[Dict[str, Any]]:
        rows = (db.session.query(
                    EInkBoardBinding.id.label("binding_id"),
                    EInkDevice.id.label("device_pk"),
                    EInkDevice.device_id,
                    EInkDevice.device_name,
                    EInkDevice.panel_res,
                    EInkBoardBinding.bound_at,
                    EInkBoardBinding.reason,
                )
                .join(EInkDevice, EInkDevice.id == EInkBoardBinding.device_id)
                .filter(EInkBoardBinding.board_id == board_id)
                .filter(EInkBoardBinding.unbound_at.is_(None))
                .order_by(EInkBoardBinding.id.asc())
                .all())

        return [{
            "binding_id": int(r.binding_id),
            "device_pk": int(r.device_pk),
            "device_id": r.device_id,
            "device_name": r.device_name or "",
            "panel_res": r.panel_res,
            "bound_at": r.bound_at,
            "reason": r.reason or "",
        } for r in rows]



