from __future__ import annotations

import hashlib
import json
from datetime import date
from typing import Any, Dict

from sqlalchemy.exc import SQLAlchemyError

from pybo import db
from pybo.models import BulletinRenderHistory


class BulletinRenderHistoryRepository:
    @staticmethod
    def make_content_hash(payload: Dict[str, Any]) -> str:
        txt = json.dumps(payload or {}, ensure_ascii=False, sort_keys=True, default=str)
        return hashlib.sha256(txt.encode("utf-8")).hexdigest()

    @staticmethod
    def latest_success(job_id: int | None, device_id: str) -> BulletinRenderHistory | None:
        try:
            q = BulletinRenderHistory.query.filter(BulletinRenderHistory.device_id == str(device_id))
            if job_id is not None:
                q = q.filter(BulletinRenderHistory.job_id == int(job_id))
            q = q.filter(BulletinRenderHistory.send_status == "success")
            return q.order_by(BulletinRenderHistory.id.desc()).first()
        except SQLAlchemyError:
            try:
                db.session.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def has_same_hash(
        *,
        job_id: int | None,
        device_id: str,
        content_hash: str,
        render_date: date,
    ) -> bool:
        try:
            q = BulletinRenderHistory.query.filter(
                BulletinRenderHistory.device_id == str(device_id),
                BulletinRenderHistory.content_hash == str(content_hash),
                BulletinRenderHistory.render_date == render_date,
            )
            if job_id is not None:
                q = q.filter(BulletinRenderHistory.job_id == int(job_id))
            return q.first() is not None
        except SQLAlchemyError:
            try:
                db.session.rollback()
            except Exception:
                pass
            return False

    @staticmethod
    def create_history(
        *,
        job_id: int | None,
        device_id: str,
        content_hash: str,
        render_date: date,
        png_path: str,
        bin_path: str,
        meta_path: str,
        revision_name: str | None,
        source_summary: Dict[str, Any] | None = None,
    ) -> BulletinRenderHistory:
        row = BulletinRenderHistory(
            job_id=(int(job_id) if job_id is not None else None),
            device_id=str(device_id),
            content_hash=str(content_hash),
            render_date=render_date,
            png_path=str(png_path),
            bin_path=str(bin_path),
            meta_path=str(meta_path),
            revision_name=(str(revision_name) if revision_name else None),
            send_status="pending",
            send_message=None,
            source_summary=source_summary or {},
        )
        db.session.add(row)
        db.session.flush()
        return row

    @staticmethod
    def update_send_result(history_id: int, *, ok: bool, message: str | None = None) -> None:
        row = BulletinRenderHistory.query.filter(BulletinRenderHistory.id == int(history_id)).first()
        if not row:
            return
        row.send_status = "success" if bool(ok) else "failed"
        row.send_message = (str(message or "")[:255] if message else None)
        db.session.flush()
