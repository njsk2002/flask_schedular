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
    def _safe_device_id(raw: str, max_len: int = 64) -> str:
        raw = (raw or "").strip()
        out = []
        for ch in raw:
            if ch.isalnum() or ch in "._-":
                out.append(ch)
        return "".join(out)[:max_len]


    @staticmethod
    def _norm_code(s: str, max_len: int = 10) -> str:
        s = (s or "").strip().upper()
        out = []
        for ch in s:
            if ("A" <= ch <= "Z") or ("0" <= ch <= "9"):
                out.append(ch)
        return "".join(out)[:max_len]

    @staticmethod
    def _floor_token(floor_no: int) -> str:
        # 정책:
        #  - 지상: 1..99 => F01..F99
        #  - 지하: -1..-10 => B01..B10
        #  - 옥외/미정: 9999 => O00
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
        # ✅ Board 등록 정책: company/building 코드는 필수
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

    # --------------------------
    # Company / Building (등록 탭 전용)
    # --------------------------
    @staticmethod
    def create_company(name: str, code: str) -> EInkCompany:
        name = (name or "").strip()
        code = RepositoryAssign._norm_code(code, 8)

        if not name:
            raise ValueError("company_name required")
        if not code:
            raise ValueError("company_code required")

        # 1) code가 이미 있으면 그 레코드 반환(이름 다르면 충돌)
        by_code = EInkCompany.query.filter(EInkCompany.code == code).first()
        if by_code:
            if by_code.name != name:
                raise ValueError(f"회사코드({code})는 이미 '{by_code.name}'에 사용 중")
            return by_code

        # 2) name이 이미 있으면 코드 보강 또는 충돌
        by_name = EInkCompany.query.filter(EInkCompany.name == name).first()
        if by_name:
            if by_name.code and by_name.code != code:
                raise ValueError(f"회사명({name})은 이미 코드 '{by_name.code}'로 등록됨")
            if not by_name.code:
                by_name.code = code
                db.session.add(by_name)
                db.session.commit()
            return by_name

        c = EInkCompany(name=name, code=code)
        db.session.add(c)
        db.session.commit()
        return c

    @staticmethod
    def create_building(company_id: int, name: str, code: str, address: str) -> EInkBuilding:
        name = (name or "").strip()
        code = RepositoryAssign._norm_code(code, 10)

        if not company_id:
            raise ValueError("company_id required")
        if not name:
            raise ValueError("building_name required")
        if not code:
            raise ValueError("building_code required")

        company = EInkCompany.query.get(company_id)
        if not company:
            raise ValueError("존재하지 않는 company_id")

        # 같은 회사 내 building_code 중복 방지(앱 레벨)
        by_code = (
            EInkBuilding.query
            .filter(EInkBuilding.company_id == company_id, EInkBuilding.code == code)
            .first()
        )
        if by_code and by_code.name != name:
            raise ValueError(f"건물코드({code})는 이미 '{by_code.name}'에 사용 중")

        # (company_id, name) unique
        by_name = (
            EInkBuilding.query
            .filter(EInkBuilding.company_id == company_id, EInkBuilding.name == name)
            .first()
        )
        if by_name:
            if by_name.code and by_name.code != code:
                raise ValueError(f"건물명({name})은 이미 코드 '{by_name.code}'로 등록됨")
            if not by_name.code:
                by_name.code = code
            if address and not by_name.address:
                by_name.address = address.strip()
            db.session.add(by_name)
            db.session.commit()
            return by_name

        b = EInkBuilding(
            company_id=company_id,
            name=name,
            code=code,
            address=(address or "").strip() or None
        )
        db.session.add(b)
        db.session.commit()
        return b

    # --------------------------
    # Board (선택 기반 등록 탭 전용)
    # --------------------------
    @staticmethod
    def _validate_floor_no(floor_no: int) -> None:
        if floor_no == 9999:
            return
        if 1 <= floor_no <= 99:
            return
        if -10 <= floor_no <= -1:
            return
        raise ValueError("floor_no 범위 오류 (지상 1~99, 지하 -1~-10, 미정 9999)")

    @staticmethod
    def _validate_board_no(board_no: int) -> None:
        if not (1 <= board_no <= 999):
            raise ValueError("board_no 범위 오류 (1~999)")

    @staticmethod
    def next_board_no(building_id: int, floor_no: int) -> int:
        m = (
            db.session.query(func.max(EInkBoard.board_no))
            .filter(EInkBoard.building_id == building_id, EInkBoard.floor_no == floor_no)
            .scalar()
        )
        return (int(m) if m is not None else 0) + 1

    @staticmethod
    def create_board_by_selection(
        company_id: int,
        building_id: int,
        site_code: str,
        floor_no: int,
        board_no: Optional[int],
        name: str,
        location_desc: str,
        max_retries: int = 5
    ) -> EInkBoard:
        company = EInkCompany.query.get(company_id)
        if not company:
            raise ValueError("존재하지 않는 company_id")

        building = EInkBuilding.query.get(building_id)
        if not building:
            raise ValueError("존재하지 않는 building_id")

        # ✅ building이 선택한 company에 속하는지 검증
        if building.company_id != company.id:
            raise ValueError("선택한 건물이 선택한 회사에 속하지 않아")

        # ✅ Board 등록 정책: 회사/건물 코드는 반드시 존재해야 함
        if not (company.code or "").strip():
            raise ValueError("회사코드(company.code)가 없어 게시판 등록 불가")
        if not (building.code or "").strip():
            raise ValueError("건물코드(building.code)가 없어 게시판 등록 불가")

        RepositoryAssign._validate_floor_no(floor_no)

        auto = (board_no is None)
        last_err = None

        for _ in range(max_retries):
            try:
                bn = board_no if not auto else RepositoryAssign.next_board_no(building.id, floor_no)
                RepositoryAssign._validate_board_no(bn)

                code = RepositoryAssign.make_board_code(
                    company_code=company.code,
                    site_code=site_code,
                    building_code=building.code,
                    floor_no=floor_no,
                    board_no=bn
                )

                board = EInkBoard(
                    building_id=building.id,
                    floor_no=floor_no,
                    board_no=bn,
                    board_code=code,
                    name=(name or "").strip(),
                    location_desc=(location_desc or "").strip() or None
                )

                if not board.name:
                    raise ValueError("게시판 name은 필수")

                db.session.add(board)
                db.session.commit()
                return board

            except IntegrityError as e:
                db.session.rollback()
                last_err = e
                if auto:
                    continue
                raise

        raise last_err or RuntimeError("board_no 자동할당 재시도 실패")

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



