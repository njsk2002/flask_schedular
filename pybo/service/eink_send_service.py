from __future__ import annotations

import json
import os
import shutil
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict

from PIL import Image
from flask import current_app, has_app_context

from pybo import db
from pybo.models import EInkAsset, EInkPosting, EInkDevice, User

# ✅ 정상 경로와 동일한 번들 저장 함수를 그대로 재사용
from pybo.service.file_management import save_meta_bundle


class EInkSendService:
    """
    Auto bulletin / groupware 렌더 결과를
    D:\\eink_docs\\{userid}\\auto_send_files\\{no}\\
    구조로 저장하고, EInkAsset / EInkPosting 까지 등록한다.

    [핵심 원칙]
    - auto-send도 정상 경로와 동일하게 "최종 이미지 기준"으로
      BMP / BIN / meta를 함께 생성해야 한다.
    - 즉, render_result.bin_path를 신뢰해서 복사하지 않고,
      png_path(최종 렌더 결과) -> PIL Image -> save_meta_bundle(...) 로 처리한다.
    """

    def __init__(self, doc_root: str | None = None):
        self.doc_root = Path(doc_root or r"D:\eink_docs")

    # ------------------------------------------------------------------
    # logging helper
    # ------------------------------------------------------------------
    def _log(self, level: str, msg: str, **kw: Any) -> None:
        line = msg if not kw else f"{msg} | {kw}"
        if has_app_context():
            logger = current_app.logger
        else:
            import logging
            logger = logging.getLogger(__name__)
        getattr(logger, level, logger.info)(line)

    # ------------------------------------------------------------------
    # owner resolve
    # ------------------------------------------------------------------
    def _get_owner_user(self, device_id: str) -> User:
        row = (
            db.session.query(User)
            .join(EInkDevice, EInkDevice.user_no == User.no)
            .filter(EInkDevice.device_id == str(device_id))
            .order_by(EInkDevice.id.desc())
            .first()
        )
        if not row:
            raise RuntimeError(f"device owner not found: {device_id}")
        return row

    # ------------------------------------------------------------------
    # path helpers
    # ------------------------------------------------------------------
    def _user_root(self, userid: str) -> Path:
        return self.doc_root / str(userid)

    def _auto_send_root(self, userid: str) -> Path:
        return self._user_root(userid) / "auto_send_files"

    def _next_folder_no(self, userid: str) -> int:
        base = self._auto_send_root(userid)
        base.mkdir(parents=True, exist_ok=True)

        max_no = 0
        for p in base.iterdir():
            if p.is_dir() and p.name.isdigit():
                try:
                    max_no = max(max_no, int(p.name))
                except Exception:
                    pass

        return max_no + 1

    # ------------------------------------------------------------------
    # file helpers
    # ------------------------------------------------------------------
    def _copy_or_raise(self, src: str | Path, dst: str | Path) -> None:
        src_p = Path(src)
        dst_p = Path(dst)

        if not src_p.is_file():
            raise FileNotFoundError(f"source file not found: {src_p}")

        dst_p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_p, dst_p)

    def _read_json_file(self, path: str | Path) -> Dict[str, Any]:
        p = Path(path)
        if not p.is_file():
            return {}
        with open(p, "r", encoding="utf-8") as f:
            obj = json.load(f) or {}
        return obj if isinstance(obj, dict) else {}

    # ------------------------------------------------------------------
    # posting housekeeping
    # ------------------------------------------------------------------
    def _expire_existing_postings(self, *, device_id: str, now: datetime) -> int:
        rows = (
            EInkPosting.query
            .filter(
                EInkPosting.device_id == device_id,
                EInkPosting.status != "expired",
            )
            .all()
        )

        changed = 0
        for row in rows:
            old_status = row.status
            row.status = "expired"
            row.end_time = now
            row.reason = f"auto_send_replaced_from_{old_status}"[:255]
            row.updated_at = now
            changed += 1

        return changed

    # ------------------------------------------------------------------
    # meta builders
    # ------------------------------------------------------------------
    def _build_onelayer_meta_json(
        self,
        *,
        render_result,
        device_id: str,
        width: int,
        height: int,
        mode: str,
        packing: str,
        raw_len: int,
        total_len: int,
        crc32_le: str,
        ver: int,
        has_render_json: bool,
    ) -> Dict[str, Any]:
        rr_meta = getattr(render_result, "metadata", None) or {}
        if not isinstance(rr_meta, dict):
            rr_meta = {}

        # packing -> mode_bpp 역산
        packing_l = str(packing or "").lower()
        if packing_l.startswith("1"):
            mode_bpp = 1
        elif packing_l.startswith("2"):
            mode_bpp = 2
        elif packing_l.startswith("3"):
            mode_bpp = 3
        elif packing_l.startswith("4"):
            mode_bpp = 4
        else:
            # fallback
            mode_bpp = int(rr_meta.get("bpp") or 4)

        now_str = datetime.now().replace(microsecond=0).isoformat()

        return {
            "mode": mode,
            "crc32": crc32_le,
            "files": {
                "bin": "onelayer.bin",
                "bmp": "onelayer.bmp",
                "metadata_json": "metadata.json",
                "layout_snapshot_json": "render_data.json" if has_render_json else "",
            },
            "width": width,
            "bucket": "bulletin_files",
            "doc_id": None,
            "height": height,
            "packing": packing,
            "raw_len": raw_len,
            "route_id": None,
            "assignees": {
                "check": [],
                "draft": [],
            },
            "device_id": device_id,
            "total_len": total_len,
            "updated_at": now_str,
            "need_approval": False,
            "original_name": str(rr_meta.get("original_name") or ""),
            "final_approval": False,

            # 내부 추적용 추가 필드
            "ver": ver,
            "mode_bpp": mode_bpp,
            "job_type": str(getattr(render_result, "job_type", "") or ""),
            "content_hash": str(getattr(render_result, "content_hash", "") or ""),
            "revision_name": str(getattr(render_result, "revision_name", "") or ""),
        }

    # ------------------------------------------------------------------
    # main
    # ------------------------------------------------------------------
    def send(self, render_result) -> Dict[str, Any]:
        now = datetime.now().replace(microsecond=0)
        expire_at = now + timedelta(hours=24)

        try:
            # ----------------------------------------------------------
            # 1) 입력 검증
            # ----------------------------------------------------------
            device_id = str(getattr(render_result, "device_id", "") or "").strip()
            if not device_id:
                raise RuntimeError("render_result.device_id is required")

            png_path = str(getattr(render_result, "png_path", "") or "").strip()
            meta_path = str(getattr(render_result, "meta_path", "") or "").strip()
            render_json_path = str(getattr(render_result, "render_json_path", "") or "").strip()

            if not png_path or not os.path.isfile(png_path):
                raise FileNotFoundError(f"png_path not found: {png_path}")
            if not meta_path or not os.path.isfile(meta_path):
                raise FileNotFoundError(f"meta_path not found: {meta_path}")

            # ----------------------------------------------------------
            # 2) 소유자 확인
            # ----------------------------------------------------------
            user = self._get_owner_user(device_id)
            userid = str(getattr(user, "userid", None) or getattr(user, "no", None) or "").strip()
            if not userid:
                raise RuntimeError(f"userid missing for device owner: {device_id}")

            # ----------------------------------------------------------
            # 3) 저장 폴더 생성
            # ----------------------------------------------------------
            folder_no = self._next_folder_no(userid)
            save_dir = self._auto_send_root(userid) / str(folder_no)
            save_dir.mkdir(parents=True, exist_ok=True)

            # ----------------------------------------------------------
            # 4) 최종 파일 경로
            # ----------------------------------------------------------
            dst_bin = save_dir / "onelayer.bin"
            dst_bmp = save_dir / "onelayer.bmp"
            dst_metadata_json = save_dir / "metadata.json"
            dst_onelayer_meta_json = save_dir / "onelayer_meta.json"
            dst_render_json = save_dir / "render_data.json"

            # ----------------------------------------------------------
            # 5) 원본 메타 읽기
            # ----------------------------------------------------------
            original_meta_json = self._read_json_file(meta_path)
            rr_meta = getattr(render_result, "metadata", None) or {}
            if not isinstance(rr_meta, dict):
                rr_meta = {}

            width = int(original_meta_json.get("width") or rr_meta.get("width") or 0)
            height = int(original_meta_json.get("height") or rr_meta.get("height") or 0)
            mode = str(original_meta_json.get("mode") or rr_meta.get("mode") or "BWRYBG").upper()

            if width <= 0 or height <= 0:
                raise RuntimeError(f"invalid size resolved: {width}x{height}")

            # ----------------------------------------------------------
            # 6) metadata.json / render_data.json 복사
            # ----------------------------------------------------------
            self._copy_or_raise(meta_path, dst_metadata_json)

            if render_json_path and os.path.isfile(render_json_path):
                self._copy_or_raise(render_json_path, dst_render_json)

            # ----------------------------------------------------------
            # 7) PNG -> PIL image 로드
            #    정상 경로와 동일하게 "최종 이미지 기준"으로 번들 생성
            # ----------------------------------------------------------
            with Image.open(png_path) as im:
                final_im = im.convert("RGB")

                # 정상 경로와 동일 함수 사용:
                # - BMP 저장
                # - BIN 생성
                # - raw_len / total_len / crc32 계산
                payload, base_meta = save_meta_bundle(
                    final_im,
                    mode,                         # ✅ 위치 인자 fmt
                    (width, height),
                    str(dst_bmp),
                    str(dst_bin),
                    str(dst_metadata_json),      # 먼저 metadata.json 자리에 생성
                    device_id,
                    "uploads",
                    False,
                    True,
                    None,
                    {"check": [], "draft": []},
                    doc_id=None,
                    upload_row_id=None,
                )

            raw_len = int(base_meta.get("raw_len") or 0)
            total_len = int(base_meta.get("total_len") or 0)
            crc32_le = str(base_meta.get("crc32") or "").lower()
            packing = str(base_meta.get("packing") or "")

            if raw_len <= 0 or total_len <= 0 or not crc32_le:
                raise RuntimeError(
                    f"invalid bundle meta from save_meta_bundle: raw_len={raw_len}, total_len={total_len}, crc32={crc32_le}"
                )

            # ----------------------------------------------------------
            # 8) ver = 10자리 epoch seconds
            # ----------------------------------------------------------
            ver = int(now.timestamp())

            # ----------------------------------------------------------
            # 9) onelayer_meta.json 생성
            #    metadata.json은 save_meta_bundle 산출물 그대로 두고,
            #    별도로 onelayer_meta.json 작성
            # ----------------------------------------------------------
            onelayer_meta_json = self._build_onelayer_meta_json(
                render_result=render_result,
                device_id=device_id,
                width=width,
                height=height,
                mode=mode,
                packing=packing,
                raw_len=raw_len,
                total_len=total_len,
                crc32_le=crc32_le,
                ver=ver,
                has_render_json=dst_render_json.exists(),
            )

            with open(dst_onelayer_meta_json, "w", encoding="utf-8") as f:
                json.dump(onelayer_meta_json, f, ensure_ascii=False, indent=2)

            # ----------------------------------------------------------
            # 10) 상대경로
            # ----------------------------------------------------------
            bin_relpath = f"auto_send_files/{folder_no}/onelayer.bin"
            meta_relpath = f"auto_send_files/{folder_no}/onelayer_meta.json"
            preview_relpath = f"auto_send_files/{folder_no}/onelayer.bmp"

            # ----------------------------------------------------------
            # 11) 기존 posting 정리
            # ----------------------------------------------------------
            expired_count = self._expire_existing_postings(
                device_id=device_id,
                now=now,
            )

            # ----------------------------------------------------------
            # 12) EInkAsset 생성
            # ----------------------------------------------------------
            asset = EInkAsset(
                user_id=int(user.no),
                device_id=device_id,
                document_info_id=None,

                channel="bulletin",
                title=f"auto_send_{getattr(render_result, 'job_type', 'unknown')}_{now.strftime('%Y%m%d_%H%M%S')}",
                preview_relpath=preview_relpath,
                source_kind="bulletin_files",

                width=width,
                height=height,
                mode=mode,
                bpp=int(rr_meta.get("bpp") or original_meta_json.get("bpp") or 4),

                ver=ver,
                uuid=str(uuid.uuid4()),

                bin_relpath=bin_relpath,
                meta_relpath=meta_relpath,

                raw_len=raw_len,
                total_len=total_len,
                crc32_le=crc32_le,

                sha256=None,
                is_encrypted=False,
                asset_partial_ready=False,

                meta_json=onelayer_meta_json,

                expect_post_time=now,
                posting_period_sec=24 * 60 * 60,
                expire_time=expire_at,

                need_approval=False,
                final_approval=True,
                approval_snapshot_json=None,

                created_at=now,
                updated_at=now,
            )
            db.session.add(asset)
            db.session.flush()

            # ----------------------------------------------------------
            # 13) EInkPosting 생성
            # ----------------------------------------------------------
            posting = EInkPosting(
                user_id=int(user.no),
                device_id=device_id,
                asset_id=int(asset.id),
                status="active",
                start_time=now,
                end_time=expire_at,
                reason="auto_send_registered",
                priority=1,
                created_at=now,
                updated_at=now,
            )
            db.session.add(posting)
            db.session.commit()

            self._log(
                "info",
                "[EINK-SEND] registered auto_send asset/posting",
                user_id=int(user.no),
                userid=userid,
                device_id=device_id,
                asset_id=int(asset.id),
                posting_id=int(posting.id),
                folder_no=folder_no,
                save_dir=str(save_dir),
                expired_count=expired_count,
                bin_relpath=bin_relpath,
                meta_relpath=meta_relpath,
                preview_relpath=preview_relpath,
                raw_len=raw_len,
                total_len=total_len,
                crc32=crc32_le,
                ver=ver,
            )

            return {
                "ok": True,
                "device_id": device_id,
                "user_id": int(user.no),
                "userid": userid,
                "asset_id": int(asset.id),
                "posting_id": int(posting.id),
                "message": "registered_auto_send_success",
                "save_dir": str(save_dir),
                "bin_path": str(dst_bin),
                "meta_path": str(dst_onelayer_meta_json),
                "metadata_json_path": str(dst_metadata_json),
                "bmp_path": str(dst_bmp),
                "render_json_path": str(dst_render_json) if dst_render_json.exists() else "",
                "bin_relpath": bin_relpath,
                "meta_relpath": meta_relpath,
                "preview_relpath": preview_relpath,
                "raw_len": raw_len,
                "total_len": total_len,
                "crc32": crc32_le,
                "ver": ver,
            }

        except Exception as e:
            db.session.rollback()
            self._log("exception", "[EINK-SEND] register failed", err=str(e))
            return {
                "ok": False,
                "message": "registered_auto_send_failed",
                "reason": str(e),
            }