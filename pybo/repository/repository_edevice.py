# pybo/repository/repository_edevice.py
import os
import json
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

from flask import request, current_app
from sqlalchemy import case, or_
from sqlalchemy.exc import SQLAlchemyError
from pybo import db
from ..models import (
    User,
    DocumentInfo,   
    EInkDevice,
    EInkPosting,
    EInkAsset,
    DeviceAccessLog,
)



class RepositoryEDevice:
    """
    디바이스 Pull API(/edevice/info, /edevice/bmp) + 대시보드(/dashboard/board) 공용 Repository

    ✅ MySQL 주의:
      - ORDER BY ... NULLS LAST 문법 없음
      - SQLAlchemy nullslast() 쓰면 1064 발생
      - 대안: (start_time IS NULL) ASC, start_time DESC/ASC ...
    """

    # ─────────────────────────────────────────────
    # Debug helper
    # ─────────────────────────────────────────────
    @staticmethod
    def _dbg(tag: str, **kw) -> None:
        try:
            current_app.logger.debug(f"[RepositoryEDevice] {tag} | {kw}")
        except Exception:
            pass

    @staticmethod
    def _dbg_exc(tag: str, e: Exception, **kw) -> None:
        try:
            current_app.logger.debug(f"[RepositoryEDevice] {tag} | {kw}", exc_info=True)
        except Exception:
            pass

    @staticmethod   
    def _fmt_dt(d):
        if not d: return None
        return d.strftime("%Y-%m-%d %H:%M:%S")

    # ─────────────────────────────────────────────
    # Time / Request Utils
    # ─────────────────────────────────────────────
    @staticmethod
    def kst_now_naive() -> datetime:
        return datetime.now().replace(microsecond=0)

    @staticmethod
    def client_ip() -> str:
        return (request.headers.get("X-Forwarded-For") or request.remote_addr or "")[:64]

    @staticmethod
    def user_agent() -> str:
        return (request.headers.get("User-Agent") or "")[:255]

    @staticmethod
    def safe_device_id(raw: str) -> str:
        if not raw:
            return ""
        safe = "".join(ch for ch in raw if ch.isalnum() or ch in "._-")
        return safe[:64]

    # ─────────────────────────────────────────────
    # Device ↔ User mapping
    # ─────────────────────────────────────────────
    @staticmethod
    def get_device_owner(device_id: str) -> Optional[User]:
        if not device_id:
            return None

        dev = (EInkDevice.query
               .filter(EInkDevice.device_id == device_id)
               .order_by(EInkDevice.id.desc())
               .first())
        if not dev:
            RepositoryEDevice._dbg("get_device_owner:not_found", device_id=device_id)
            return None

        if getattr(dev, "revoked_at", None):
            RepositoryEDevice._dbg("get_device_owner:revoked", device_id=device_id, dev_id=dev.id)
            return None

        user = User.query.filter(User.no == dev.user_no).first()
        RepositoryEDevice._dbg("get_device_owner:ok", device_id=device_id, dev_id=dev.id, user_no=(user.no if user else None))
        return user

    # ─────────────────────────────────────────────
    # Posting selection (current/next)
    # ─────────────────────────────────────────────
    @staticmethod
    def pick_current_and_next_posting(
        user_id: int,
        device_id: str,
        now: Optional[datetime] = None
    ) -> Tuple[Optional[EInkPosting], Optional[EInkPosting]]:
        """
        current: now가 start/end window 안에 드는 posting 1개
        next   : now 이후 시작하는 scheduled 중 가장 빠른 것 1개

        ✅ MySQL:
          - NULLS LAST 없음 → (start_time IS NULL) ASC로 NULL을 뒤로 보냄
          - active를 scheduled보다 먼저 선택 (status_rank)
        """
        if now is None:
            now = RepositoryEDevice.kst_now_naive()

        RepositoryEDevice._dbg("pick:start", user_id=user_id, device_id=device_id, now=now.isoformat())

        status_rank = case(
            (EInkPosting.status == "active", 0),
            else_=1
        )

        # current
        q_cur = (EInkPosting.query
                 .filter_by(user_id=user_id, device_id=device_id)
                 .filter(EInkPosting.status.in_(["active", "scheduled"]))
                 .filter((EInkPosting.start_time.is_(None)) | (EInkPosting.start_time <= now))
                 .filter((EInkPosting.end_time.is_(None)) | (now < EInkPosting.end_time))
                 .order_by(
                     status_rank.asc(),
                     (EInkPosting.start_time.is_(None)).asc(),   # ✅ NULL last
                     EInkPosting.start_time.desc(),
                     EInkPosting.priority.asc(),
                     EInkPosting.id.desc(),
                 ))

        # next
        q_nxt = (EInkPosting.query
                 .filter_by(user_id=user_id, device_id=device_id, status="scheduled")
                 .filter(EInkPosting.start_time.isnot(None))
                 .filter(EInkPosting.start_time > now)
                 .order_by(
                     EInkPosting.start_time.asc(),
                     EInkPosting.priority.asc(),
                     EInkPosting.id.asc(),
                 ))

        # try:
        #     RepositoryEDevice._dbg("pick:sql_cur", sql=str(q_cur.statement))
        #     RepositoryEDevice._dbg("pick:sql_nxt", sql=str(q_nxt.statement))
        # except Exception:
        #     pass

        try:
            cur = q_cur.first()
            nxt = q_nxt.first()
            # RepositoryEDevice._dbg("pick:done",
            #                        cur_id=(cur.id if cur else None),
            #                        nxt_id=(nxt.id if nxt else None),
            #                        cur_asset_id=(cur.asset_id if cur else None),
            #                        nxt_asset_id=(nxt.asset_id if nxt else None))
            return cur, nxt
        except Exception as e:
            RepositoryEDevice._dbg_exc("pick:failed", e, user_id=user_id, device_id=device_id, now=now.isoformat())
            raise

    # ─────────────────────────────────────────────
    # Path resolution
    # ─────────────────────────────────────────────
    @staticmethod
    def user_root_dir(user: User) -> str:
        key = (getattr(user, "userid", None)
               or getattr(user, "id", None)
               or getattr(user, "no", None))
        return fr"D:\eink_docs\{key}"

    @staticmethod
    def abs_path_from_rel(user: User, relpath: str) -> str:
        base = RepositoryEDevice.user_root_dir(user)
        rel = (relpath or "").replace("/", os.sep).lstrip("\\/")
        return os.path.normpath(os.path.join(base, rel))

    @staticmethod
    def find_first_file(abs_dir: str, suffix: str) -> Optional[str]:
        try:
            for name in os.listdir(abs_dir):
                if name.lower().endswith(suffix.lower()):
                    return os.path.join(abs_dir, name)
        except Exception:
            return None
        return None

    # ─────────────────────────────────────────────
    # Asset meta build
    # ─────────────────────────────────────────────


    @staticmethod
    def build_device_meta(device_id: str, asset: EInkAsset) -> dict:
        meta = asset.meta_json or {}

        # ✅ 신/구 포맷 동시 지원
        files = meta.get("files") or {}
        bin_name = meta.get("bin") or files.get("bin") or os.path.basename(asset.bin_relpath or "") or "onelayer.bin"
        bmp_name = meta.get("file") or files.get("bmp") or "onelayer.bmp"

        # dir은 펌웨어가 안 쓸 수도 있지만, 예전 응답 호환용으로 유지
        # bucket이 있으면 bucket을 dir로 보내도 되고, 무조건 "uploads"로 고정해도 됨.
        dir_name = meta.get("dir") or meta.get("bucket") or "uploads"

        # packing은 meta의 "3bpp" 같은 문자열이 틀릴 수 있으니 DB 스펙(asset.bpp)을 우선
        packing = f"{int(getattr(asset, 'bpp', 4) or 4)}bpp"

        return {
            "device_id": device_id,
            "dir": dir_name,
            "file": bmp_name,      # ✅ onelayer.bmp
            "bin": bin_name,       # ✅ onelayer.bin
            "width": int(asset.width),
            "height": int(asset.height),
            "mode": asset.mode,
            "packing": packing,    # ✅ 4bpp로 나가게
            "raw_len": int(asset.raw_len),
            "total_len": int(asset.total_len),
            "crc32": asset.crc32_le,
            "ver": int(asset.ver),
            "updated_at": (asset.updated_at.isoformat() if asset.updated_at else None),
            "need_approval": bool(asset.need_approval),
            "final_approval": bool(asset.final_approval),
            "route_id": meta.get("route_id"),
            "assignees": meta.get("assignees") or {"draft": [], "check": []},
            "status": meta.get("bucket") or meta.get("status") or "uploads",
        }


    # ─────────────────────────────────────────────
    # Logging + device summary update
    # ─────────────────────────────────────────────
    @staticmethod
    def log_access(
        *,
        user_id: int,
        device_id: str,
        api: str,
        ok: bool,
        http_status: int,
        posting_id=None,
        asset_id=None,
        ver=None,
        crc32=None,
        bytes_sent=None,
        elapsed_ms=None,
        error_msg=None,
        auth_ok: bool = True,
        auth_mode: str = "none",
        device_fp: Optional[str] = None,
        # ===== Additional (sensor/state) =====
        battery_pct: Optional[int] = None,
        battery_mv: Optional[int] = None,
        temp_c_x10: Optional[int] = None,
        rssi_dbm: Optional[int] = None,
        wake_reason: Optional[str] = None,
        # ===== Additional (time sync / sleep planning) =====
        dev_mono_ms: Optional[int] = None,
        dev_local_epoch_ms: Optional[int] = None,
        offset_ms: Optional[int] = None,
        server_epoch_ms: Optional[int] = None,
        next_change_epoch_ms: Optional[int] = None,
        sleep_planned_sec: Optional[int] = None,
        fail_count: Optional[int] = None,
        backoff_level: Optional[int] = None,
    ) -> None:
        """
        Persist a device access log row.

        Formal Notes:
            - IP/User-Agent/Method/Path are extracted from Flask request context.
              This ensures that callers do not need to pass these fields explicitly.
            - All string fields are truncated to match column length constraints.
            - Optional telemetry fields may be None when firmware has not implemented them.
        """

        db.session.add(DeviceAccessLog(
            user_id=user_id,
            device_id=device_id,
            api=api,

            # Request envelope
            method=(request.method or "")[:8],
            path=(request.path or "")[:128],

            # Authentication information
            auth_ok=bool(auth_ok),
            auth_mode=(auth_mode or "")[:16],
            device_fp=(device_fp or "")[:64] if device_fp else None,

            # Outcome
            ok=bool(ok),
            http_status=int(http_status) if http_status is not None else None,
            error_msg=(str(error_msg)[:255] if error_msg else None),

            # Payload context
            posting_id=posting_id,
            asset_id=asset_id,
            ver=ver,
            crc32=(str(crc32)[:8] if crc32 else None),
            bytes_sent=bytes_sent,

            # Client context
            ip=RepositoryEDevice.client_ip(),
            user_agent=RepositoryEDevice.user_agent(),
            elapsed_ms=elapsed_ms,
            created_at=RepositoryEDevice.kst_now_naive(),

            # ===== Additional (sensor/state) =====
            battery_pct=battery_pct,
            battery_mv=battery_mv,
            temp_c_x10=temp_c_x10,
            rssi_dbm=rssi_dbm,
            wake_reason=(wake_reason or "")[:16] if wake_reason else None,

            # ===== Additional (time sync / sleep planning) =====
            dev_mono_ms=dev_mono_ms,
            dev_local_epoch_ms=dev_local_epoch_ms,
            offset_ms=offset_ms,
            server_epoch_ms=server_epoch_ms,
            next_change_epoch_ms=next_change_epoch_ms,
            sleep_planned_sec=sleep_planned_sec,
            fail_count=fail_count,
            backoff_level=backoff_level,
        ))

    @staticmethod
    def touch_device_summary(
        user: User,
        device_id: str,
        *,
        api: str,
        http_status: int,
        error_msg: Optional[str],
        ver: Optional[int],
    ) -> None:
        dev = (EInkDevice.query
               .filter_by(user_no=user.no, device_id=device_id)
               .first())
        if not dev:
            RepositoryEDevice._dbg("touch:no_device_row", user_no=user.no, device_id=device_id)
            return

        dev.last_seen = RepositoryEDevice.kst_now_naive()
        dev.last_ip = RepositoryEDevice.client_ip()
        dev.last_user_agent = RepositoryEDevice.user_agent()
        dev.last_api = (api or "")[:32]
        dev.last_http_status = int(http_status) if http_status is not None else None
        dev.last_error_msg = (error_msg[:255] if error_msg else None)

        if ver is not None:
            try:
                dev.current_ver = max(int(dev.current_ver or 0), int(ver))
            except Exception:
                pass

        RepositoryEDevice._dbg("touch:done",
                               user_no=user.no, device_id=device_id,
                               http_status=http_status, ver=ver,
                               last_seen=(dev.last_seen.isoformat() if dev.last_seen else None))

    # ─────────────────────────────────────────────
    # High-level helpers
    # ─────────────────────────────────────────────
    @staticmethod
    def get_current_asset_for_device(user: User, device_id: str, now: Optional[datetime] = None):
        cur, nxt = RepositoryEDevice.pick_current_and_next_posting(user.no, device_id, now)
        if not cur:
            return None, None, None
        return cur, cur.asset, nxt

    @staticmethod
    def stat_and_validate_bin(asset: EInkAsset, bin_path: str) -> int:
        st = os.stat(bin_path)
        if asset.total_len and int(st.st_size) != int(asset.total_len):
            raise RuntimeError(f"bin size mismatch {st.st_size}!={asset.total_len}")
        return int(st.st_size)

    # ─────────────────────────────────────────────
    # (선택) DocumentInfo -> EInkAsset 생성 헬퍼 (대시보드 Activate/Schedule에서 사용)
    # ─────────────────────────────────────────────
    @staticmethod
    def ensure_asset_from_docinfo(user: User, device_id: str, channel: str, doc: DocumentInfo) -> EInkAsset:
        """
        DocumentInfo(approved/bulletin payload) -> EInkAsset 생성/재사용

        핵심 정책(안정 버전):
        1) DB에는 channel을 "approved" 또는 "bulletin"만 저장한다. (normalize)
        2) base_rel/abs_dir(실제 파일 경로)는 channel(ch) 기준으로 결정한다.
        3) meta_json.bucket은 "참고용"으로만 두고, 경로(base_rel)를 뒤집지 않는다.
        (bucket이 경로와 엇갈리는 순간 relpath/DB channel이 꼬이는 문제 방지)
        """
        # ── 1) channel normalize (DB 저장값 고정) ──────────────────────────
        ch = (channel or "").strip().lower()
        print(f"CHANNEL = {ch}")

        if ch in ("bulletin", "bulletin_files", "bulletinfile", "bulletins"):
            ch = "bulletin"
        elif ch in ("approved", "approval", "approval_process", "approve"):
            ch = "approved"
        else:
            ch = "approved"

        # ── 2) 이미 만든 asset 재사용 ─────────────────────────────────────
        exist = (
            EInkAsset.query
            .filter_by(user_id=user.no, device_id=device_id, document_info_id=doc.id, channel=ch)
            .order_by(EInkAsset.id.desc())
            .first()
        )
        if exist:
            return exist

        # ── 3) 경로 분기 (ch 기준) ────────────────────────────────────────
        if ch == "approved":
            base_rel = f"approval_process/{doc.id}/"
            source_kind = "approval_process"
        else:
            base_rel = f"bulletin_files/{doc.id}/"
            source_kind = "bulletin_files"

        abs_dir = RepositoryEDevice.abs_path_from_rel(user, base_rel)

        # ── 4) meta/bin/bmp 찾기 ─────────────────────────────────────────
        meta_abs = RepositoryEDevice.find_meta_file(abs_dir, device_id=device_id)
        bin_abs = RepositoryEDevice.find_bin_file(abs_dir, device_id=device_id)

        bmp_abs = os.path.join(abs_dir, "onelayer.bmp")
        if not os.path.isfile(bmp_abs):
            bmp_abs = RepositoryEDevice.find_first_file(abs_dir, ".bmp") or bmp_abs

        if not meta_abs or not os.path.isfile(meta_abs):
            raise RuntimeError(f"meta not found in {abs_dir}")
        if not bin_abs or not os.path.isfile(bin_abs):
            raise RuntimeError(f"bin not found in {abs_dir}")

        with open(meta_abs, "r", encoding="utf-8") as f:
            meta_json = json.load(f)

        # ── 5) meta_json.bucket은 참고용(경로/채널 뒤집지 않음) ───────────
        # bucket이 들어있으면 source_kind에 반영만(옵션)
        bucket = (meta_json.get("bucket") or "").strip().lower()
        if bucket in ("approval_process", "bulletin_files"):
            source_kind = bucket

        # ── 6) 메타 파싱 ────────────────────────────────────────────────
        width = int(meta_json.get("width") or 0)
        height = int(meta_json.get("height") or 0)
        mode = (meta_json.get("mode") or "BWR").strip()

        # packing: "4bpp" / "3bpp" / "packing_mode" / "bpp" 등 대응
        packing = str(
            meta_json.get("packing")
            or meta_json.get("packing_mode")
            or meta_json.get("bpp")
            or "4bpp"
        ).strip().lower()

        bpp = 4
        # "4bpp" -> 4, "3bpp" -> 3 등
        digits = "".join([c for c in packing if c.isdigit()])
        if digits:
            try:
                bpp = int(digits[0])
            except Exception:
                bpp = 4
        bpp = 4 if bpp not in (1, 2, 3, 4) else bpp

        raw_len = int(meta_json.get("raw_len") or 0)
        total_len = int(meta_json.get("total_len") or 0)
        crc32 = (meta_json.get("crc32") or "").lower().strip()[:8]
        ver = int(meta_json.get("ver") or int(datetime.now().timestamp()))
        u = str(uuid.uuid4())

        # 파일명은 meta/bin 실제 파일명 우선 반영
        meta_fn = os.path.basename(meta_abs)
        bin_fn = os.path.basename(bin_abs)

        # fallback 길이 계산
        if raw_len <= 0 and width and height:
            if bpp == 4:
                raw_len = (width * height) // 2
            elif bpp == 3:
                raw_len = (width * height * 3) // 8
            elif bpp == 2:
                raw_len = (width * height) // 4
            elif bpp == 1:
                raw_len = (width * height) // 8

        if total_len <= 0:
            total_len = int(os.path.getsize(bin_abs))

        # ── 7) Asset 생성 ────────────────────────────────────────────────
        asset = EInkAsset(
            user_id=user.no,
            device_id=device_id,
            document_info_id=doc.id,

            # ✅ DB 저장값은 normalize한 ch
            channel=ch,

            title=(getattr(doc, "orig_filename", None) or f"doc#{doc.id}")[:200],
            preview_relpath=(base_rel + os.path.basename(bmp_abs)) if os.path.isfile(bmp_abs) else None,
            source_kind=source_kind,

            width=width,
            height=height,
            mode=mode,
            bpp=bpp,
            ver=ver,
            uuid=u,

            bin_relpath=(base_rel + bin_fn),
            meta_relpath=(base_rel + meta_fn),

            raw_len=raw_len,
            total_len=total_len,
            crc32_le=crc32 if crc32 else "00000000",

            meta_json=meta_json,
            need_approval=bool(meta_json.get("need_approval", False)),
            final_approval=bool(meta_json.get("final_approval", False)),
        )
        db.session.add(asset)
        db.session.flush()  # asset.id 확보
        return asset



    # ─────────────────────────────────────────────
    # Boards
    # ─────────────────────────────────────────────
    @staticmethod
    def list_boards(*, building_id: int, floor_no: int) -> Tuple[List[dict], int]:
        """
        GET /dashboard/boards?building_id=..&floor_no=..
        → {items:[{board_no, board_code}], default_board_no}

        정책:
        - (building_id,floor_no)로 필터링
        - default_board_no는 1을 우선(있으면), 없으면 첫 번째 board_no
        """
        try:
            from pybo.models import EInkBoard  # 실제 모델명에 맞게 필요시 수정
        except Exception:
            return [], 1

        q = (
            EInkBoard.query
            .filter(EInkBoard.building_id == int(building_id))
            .filter(EInkBoard.floor_no == int(floor_no))
            .order_by(EInkBoard.board_no.asc())
        )

        rows = q.all() or []
        items = []
        for r in rows:
            items.append({
                "board_no": int(getattr(r, "board_no", 0) or 0),
                "board_code": (getattr(r, "board_code", None) or "")[:64],
            })

        default_board_no = 1
        if items:
            if not any(int(x["board_no"]) == 1 for x in items):
                default_board_no = int(items[0]["board_no"] or 1)

        return items, default_board_no

    # ─────────────────────────────────────────────
    # Schedule helpers
    # ─────────────────────────────────────────────
    @staticmethod
    def _parse_period_seconds(v: Any) -> int:
        """
        posting_period_time 입력을 초(int)로 통일.
        - int/float: 초로 간주
        - "DD:HH:MM" / "HH:MM" / "MM" 문자열도 허용
        """
        if v is None:
            return 0
        if isinstance(v, (int, float)):
            return max(0, int(v))

        s = str(v).strip()
        if not s:
            return 0

        # "DD:HH:MM" or "HH:MM" or "MM"
        parts = [p for p in s.split(":") if p != ""]
        try:
            if len(parts) == 3:
                dd, hh, mm = [int(x) for x in parts]
                return max(0, dd * 86400 + hh * 3600 + mm * 60)
            if len(parts) == 2:
                hh, mm = [int(x) for x in parts]
                return max(0, hh * 3600 + mm * 60)
            if len(parts) == 1:
                # "MM"로 들어오면 분으로 간주(현장 UX에 맞춰서)
                mm = int(parts[0])
                return max(0, mm * 60)
        except Exception:
            return 0
        return 0

    @staticmethod
    def _as_naive_dt(v: Any) -> Optional[datetime]:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.replace(tzinfo=None)
        s = str(v).strip()
        if not s:
            return None
        # "YYYY-MM-DD HH:MM" / ISO 허용
        try:
            # ISO
            return datetime.fromisoformat(s.replace("Z", "")).replace(tzinfo=None)
        except Exception:
            pass
        for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
            try:
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        return None

    # ─────────────────────────────────────────────
    # Schedule list
    # ─────────────────────────────────────────────


    @staticmethod
    def schedule_list(*, user_id: int, device_id: str, now: Optional[datetime] = None) -> Dict[str, Any]:
        """
        Posting 기준
        GET /dashboard/schedule/list?device_id=...
        -> {active_expire_time, items:[{asset_id,id,orig_filename,status,expect_post_time,posting_period_time,expire_time}]}
        """

        if now is None:
            now = RepositoryEDevice.kst_now_naive()

        # 1) active 1개(있으면)
        active = (EInkPosting.query
            .filter_by(user_id=user_id, device_id=device_id, status="active")
            .filter(or_(EInkPosting.start_time.is_(None), EInkPosting.start_time <= now))
            .filter(or_(EInkPosting.end_time.is_(None), now < EInkPosting.end_time))
            .order_by(EInkPosting.start_time.desc(), EInkPosting.id.desc())
            .first()
        )

        active_expire_time = getattr(active, "end_time", None)

        # 2) active + wait만(만료/취소 제외)  ← Posting이 “큐”를 가진다는 설계 B
        rows = (db.session.query(EInkPosting, EInkAsset, DocumentInfo)
            .join(EInkAsset, EInkAsset.id == EInkPosting.asset_id)
            .outerjoin(DocumentInfo, DocumentInfo.id == EInkAsset.document_info_id)
            .filter(
                EInkPosting.user_id == user_id,
                EInkPosting.device_id == device_id,
                EInkPosting.status.in_(["active", "wait"])
            )
            .order_by(
                db.case((EInkPosting.status == "active", 0), else_=1),   # active 먼저
                (EInkPosting.start_time.is_(None)).desc(),              # NULL 먼저(MySQL-safe)
                EInkPosting.start_time.asc(),
                EInkPosting.id.asc(),
            )
            .all()
        )

        items: List[dict] = []
        for p, a, d in rows:
            # 파일명: DocumentInfo 우선 → 없으면 asset.title/meta_json
            fn = ""
            if d is not None:
                fn = (getattr(d, "orig_filename", None) or getattr(d, "original_name", None) or "") or ""
            if not fn and getattr(a, "title", None):
                fn = a.title
            if not fn and isinstance(getattr(a, "meta_json", None), dict):
                fn = a.meta_json.get("original_name") or a.meta_json.get("orig_filename") or ""

            start = getattr(p, "start_time", None)
            end = getattr(p, "end_time", None)

            # period: posting에 end_time 있으면 start/end로 계산, 없으면 asset.posting_period_sec
            period_sec = 0
            if start and end:
                period_sec = max(0, int((end - start).total_seconds()))
            elif getattr(a, "posting_period_sec", None):
                try:
                    period_sec = int(a.posting_period_sec or 0)
                except Exception:
                    period_sec = 0

            items.append({
                "asset_id": int(a.id),
                "id": int(p.id),  # posting_id
                "orig_filename": fn,
                "status": str(p.status),
                "expect_post_time": RepositoryEDevice._fmt_dt(start),
                "posting_period_time": int(period_sec),
                "expire_time": RepositoryEDevice._fmt_dt(end),
                # ✅ 추가: next preview fallback 용
                "preview_url": f"/dashboard/preview/asset/{int(a.id)}",
            })

        return {
            "active_expire_time": RepositoryEDevice._fmt_dt(active_expire_time),
            "items": items
        }


    # ─────────────────────────────────────────────
    # Schedule reorder (and normalize times)
    # ─────────────────────────────────────────────

    @staticmethod
    def schedule_reorder(*, user_id: int, device_id: str, items: List[dict], now: Optional[datetime] = None) -> Dict[str, Any]:

        if now is None:
            now = RepositoryEDevice.kst_now_naive()

        # active 만료 시각(기준 anchor)
        active_post = (
            EInkPosting.query
            .filter_by(user_id=user_id, device_id=device_id, status="active")
            .filter(or_(EInkPosting.start_time.is_(None), EInkPosting.start_time <= now))
            .filter(or_(EInkPosting.end_time.is_(None), now < EInkPosting.end_time))
            .order_by(EInkPosting.start_time.desc(), EInkPosting.id.desc())
            .first()
        )
        active_expire = getattr(active_post, "end_time", None)
        base_time = active_expire if isinstance(active_expire, datetime) and active_expire > now else now

        # ✅ wait posting들을 잠그고(MySQL) 정렬 (NULLS FIRST 대체)
        wait_posts = (EInkPosting.query
            .filter_by(user_id=user_id, device_id=device_id, status="wait")
            .order_by(
                (EInkPosting.start_time.is_(None)).desc(),  # NULL 먼저
                EInkPosting.start_time.asc(),
                EInkPosting.id.asc(),
            )
            .with_for_update()
            .all()
        )

        # asset_id -> posting 매핑
        by_asset = {int(p.asset_id): p for p in wait_posts if p.asset_id is not None}

        updated = []
        for idx, it in enumerate(items or []):
            try:
                aid = int(it.get("asset_id"))
            except Exception:
                continue

            # active는 reorder 대상에서 제외(프론트가 섞어서 보내도 서버에서 무시)
            if active_post and int(active_post.asset_id) == aid:
                continue

            # 기간
            period_sec = RepositoryEDevice._parse_period_seconds(it.get("posting_period_time"))
            if period_sec <= 0:
                period_sec = 60

            # 요청 start (없으면 base_time)
            req_expect = RepositoryEDevice._as_naive_dt(it.get("expect_post_time"))
            expect = req_expect if isinstance(req_expect, datetime) else base_time
            if expect < base_time:
                expect = base_time

            expire = expect + timedelta(seconds=period_sec)

            # posting 가져오거나 없으면 생성(wait)
            p = by_asset.get(aid)
            if not p:
                p = EInkPosting(
                    user_id=user_id,
                    device_id=device_id,
                    asset_id=aid,
                    status="wait",
                    reason="schedule_reorder",
                    priority=int(idx) + 1,
                )
                db.session.add(p)
                by_asset[aid] = p

            p.start_time = expect
            p.end_time = expire
            p.priority = int(idx) + 1

            # (선택) asset에도 동기화(UI/메타 유지용)
            a = EInkAsset.query.filter_by(id=aid, user_id=user_id, device_id=device_id).first()
            if a:
                if hasattr(a, "expect_post_time"):
                    a.expect_post_time = expect
                if hasattr(a, "posting_period_time"):
                    a.posting_period_time = int(period_sec)
                if hasattr(a, "expire_time"):
                    a.expire_time = expire

            updated.append({
                "asset_id": aid,
                "expect_post_time": expect.isoformat(sep=" ", timespec="seconds"),
                "posting_period_time": int(period_sec),
            })

            base_time = expire  # 다음은 이전 expire 이후로 자동 연결

        db.session.commit()
        return {"device_id": device_id, "items": updated}




    @staticmethod
    def list_devices_by_board(*, user_id: int, building_id: int, floor_no: int, board_no: int):
        """
        board에 바인딩된 디바이스만 반환 (EInkBoardBinding JOIN 기반)
        """
        from pybo.models import EInkDevice, EInkBoard, EInkBoardBinding

        # 1) board 찾기
        b = (EInkBoard.query
            .filter(EInkBoard.building_id == int(building_id))
            .filter(EInkBoard.floor_no == int(floor_no))
            .filter(EInkBoard.board_no == int(board_no))
            .first())

        if not b:
            current_app.logger.debug("[list_devices_by_board] board not found bld=%s floor=%s no=%s",
                                    building_id, floor_no, board_no)
            return []

        # 2) 바인딩 테이블 JOIN으로 device 필터
        q = (
            EInkDevice.query
            .join(EInkBoardBinding, EInkBoardBinding.device_id == EInkDevice.id)
            .filter(EInkBoardBinding.board_id == int(b.id))
        )

        # 3) 권한/스코프 필터(선택)
        #    - device는 company_id 소유 모델이라 user_no가 NULL이면 user_no 필터로는 누락될 수 있음
        #    - 형이 "현재 유저가 관리하는 것만" 원하면 여기 정책을 정해야 함.
        if hasattr(EInkDevice, "user_no"):
            q = q.filter((EInkDevice.user_no == int(user_id)) | (EInkDevice.user_no.is_(None)))

        rows = q.order_by(EInkDevice.device_id.asc()).all() or []

        items = [{
            "device_id": getattr(d, "device_id", "") or "",
            "panel_res": getattr(d, "panel_res", "") or "",
            "device_name": getattr(d, "device_name", "") or "",
        } for d in rows]

        current_app.logger.debug(
            "[list_devices_by_board] board_id=%s return_count=%s device_ids=%s",
            int(b.id), len(items), [x["device_id"] for x in items]
        )
        return items


    @staticmethod
    def _get_device_or_404(user_id: int, device_id: str):
        dev = EInkDevice.query.filter_by(user_no=user_id, device_id=device_id).first()
        return dev

    @staticmethod
    def _parse_expect(s: str):
        if not s: return None
        s = str(s).strip().replace("T", " ")
        if len(s) == 16:
            s += ":00"
        try:
            return datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    @staticmethod
    def schedule_list_legacy_asset_based(*, user_id: int, device_id: str):
        """
        GET /dashboard/schedule/list
        -> {active_expire_time, items:[{asset_id,id,orig_filename,status,expect_post_time,posting_period_time,expire_time}]}
        """

        if now is None:
            now = RepositoryEDevice.kst_now_naive()
        # active 1개(있으면)
        active = (EInkPosting.query
            .filter_by(user_id=user_id, device_id=device_id, status="active")
            .filter(or_(EInkPosting.start_time.is_(None), EInkPosting.start_time <= now))
            .filter(or_(EInkPosting.end_time.is_(None), now < EInkPosting.end_time))
            .order_by(EInkPosting.start_time.desc(), EInkPosting.id.desc())
            .first()
        )

        active_expire_time = getattr(active, "end_time", None)

        # active + wait만(만료/취소 제외)
        rows = (db.session.query(EInkPosting, EInkAsset, DocumentInfo)
            .join(EInkAsset, EInkAsset.id == EInkPosting.asset_id)
            .outerjoin(DocumentInfo, DocumentInfo.id == EInkAsset.document_info_id)
            .filter(
                EInkPosting.user_id == user_id,
                EInkPosting.device_id == device_id,
                EInkPosting.status.in_(["active", "wait"])
            )
            .order_by(
                db.case((EInkPosting.status == "active", 0), else_=1),   # active 먼저
                (EInkPosting.start_time.is_(None)).desc(),              # NULLS FIRST (MySQL식)
                EInkPosting.start_time.asc(),
                EInkPosting.id.asc(),
            )
            .all()
        )

        items = []
        for p, a, d in rows:
            # 파일명: DocumentInfo 우선, 없으면 meta_json/original_name
            fn = None
            if d is not None:
                fn = getattr(d, "orig_filename", None) or getattr(d, "original_name", None)
            if not fn and isinstance(getattr(a, "meta_json", None), dict):
                fn = a.meta_json.get("original_name") or a.meta_json.get("orig_filename")

            start = getattr(p, "start_time", None)
            end = getattr(p, "end_time", None)
            period_sec = None
            if start and end:
                period_sec = int((end - start).total_seconds())
            elif getattr(a, "posting_period_sec", None):
                period_sec = int(a.posting_period_sec)

            items.append({
                "asset_id": a.id,
                "id": p.id,
                "orig_filename": fn or "",
                "status": p.status,
                "expect_post_time": RepositoryEDevice._fmt_dt(start),
                "posting_period_time": int(period_sec or 0),
                "expire_time": RepositoryEDevice._fmt_dt(end),
            })

        return {"active_expire_time": RepositoryEDevice._fmt_dt(active_expire_time), "items": items}

    @staticmethod
    def enqueue_posting_wait(*, user_id: int, device_id: str, asset_id: int,
                            expect_post_time: datetime, expire_time: datetime|None,
                            priority: int = 10, reason: str = ""):
        p = EInkPosting(
            user_id=user_id,
            device_id=device_id,
            asset_id=asset_id,
            status="wait",
            start_time=expect_post_time,
            end_time=expire_time,
            priority=priority,
            reason=reason,
        )
        db.session.add(p)
        db.session.flush()
        return p

 
    @staticmethod
    def schedule_set_expired(*, user_id: int, device_id: str, asset_ids: List[int], now: Optional[datetime] = None) -> Dict[str, Any]:
        if now is None:
            now = datetime.now()

        if not asset_ids:
            return {"ok": True, "changed": 0}

        try:
            q = (
                EInkPosting.query
                .filter_by(user_id=user_id, device_id=device_id)
                .filter(EInkPosting.asset_id.in_(asset_ids))
                .filter(EInkPosting.status.in_(["wait", "active"]))
            )

            changed = 0
            for p in q.all():
                prev_status = getattr(p, "status", "")
                p.status = "expired"

                if prev_status == "active":
                    p.end_time = now

                changed += 1

            db.session.commit()
            return {"ok": True, "changed": changed}

        except SQLAlchemyError:
            db.session.rollback()
            return {"ok": False, "changed": 0}

    @staticmethod
    def _asset_preview_png_url(asset: Optional[EInkAsset]) -> str:
        """
        프로젝트에 이미 preview 라우트가 있으면 그걸로 교체.
        아래는 예시:
          /dashboard/asset/<asset_id>/preview.png
        """
        if not asset:
            return ""
        return f"/dashboard/asset/{int(asset.id)}/preview.png"