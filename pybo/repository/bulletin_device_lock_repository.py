from __future__ import annotations

from typing import Dict, Iterable, List, Tuple

from sqlalchemy.exc import SQLAlchemyError

from pybo import db
from pybo.cache.bulletin_manual_lock_cache import BulletinManualLockCache
from pybo.models import BulletinAutoJob, BulletinDeviceAutoLock


class BulletinDeviceLockRepository:
    _table_available: bool | None = None

    @classmethod
    def _set_table_unavailable(cls) -> None:
        cls._table_available = False
        BulletinManualLockCache.clear()

    @classmethod
    def _is_table_available(cls) -> bool:
        if cls._table_available is True:
            return True
        if cls._table_available is False:
            return False
        try:
            BulletinDeviceAutoLock.query.limit(1).all()
            cls._table_available = True
            return True
        except SQLAlchemyError:
            try:
                db.session.rollback()
            except Exception:
                pass
            cls._set_table_unavailable()
            return False

    @staticmethod
    def list_locks() -> List[BulletinDeviceAutoLock]:
        if not BulletinDeviceLockRepository._is_table_available():
            return []
        try:
            return BulletinDeviceAutoLock.query.order_by(BulletinDeviceAutoLock.device_id.asc()).all()
        except SQLAlchemyError:
            try:
                db.session.rollback()
            except Exception:
                pass
            BulletinDeviceLockRepository._set_table_unavailable()
            return []

    @classmethod
    def get_lock_map(cls, use_cache: bool = True) -> Dict[str, bool]:
        if use_cache:
            cached = BulletinManualLockCache.get_lock_map()
            if cached:
                return cached

        rows = cls.list_locks()
        lock_map = {str(r.device_id): bool(r.is_manual_locked) for r in rows}
        BulletinManualLockCache.set_lock_map(lock_map, ttl_seconds=20)
        return lock_map

    @classmethod
    def get_lock_info_map(cls, use_cache: bool = False) -> Dict[str, Dict[str, object]]:
        out: Dict[str, Dict[str, object]] = {}
        rows = cls.list_locks()
        for row in rows:
            out[str(row.device_id)] = {
                "is_manual_locked": bool(row.is_manual_locked),
                "reason": row.reason or "",
                "auto_job_id": int(row.auto_job_id) if row.auto_job_id else None,
            }
        if use_cache:
            BulletinManualLockCache.set_lock_map(
                {k: bool(v.get("is_manual_locked")) for k, v in out.items()},
                ttl_seconds=20,
            )
        return out

    @classmethod
    def is_manual_upload_locked(cls, device_id: str) -> bool:
        try:
            if cls._is_table_available():
                lock_map = cls.get_lock_map(use_cache=True)
                if device_id in lock_map:
                    return bool(lock_map[device_id])

                row = BulletinDeviceAutoLock.query.filter(BulletinDeviceAutoLock.device_id == str(device_id)).first()
                if row:
                    return bool(row.is_manual_locked)

            # lock row가 아직 없으면 활성 Job 설정으로 즉시 판정
            fallback = (
                BulletinAutoJob.query
                .filter(
                    BulletinAutoJob.target_device_id == str(device_id),
                    BulletinAutoJob.is_enabled.is_(True),
                    BulletinAutoJob.auto_post_enabled.is_(True),
                    BulletinAutoJob.lock_manual_upload.is_(True),
                )
                .first()
            )
            return fallback is not None
        except SQLAlchemyError:
            try:
                db.session.rollback()
            except Exception:
                pass
            cls._set_table_unavailable()
            return False

    @staticmethod
    def upsert_lock(
        *,
        device_id: str,
        auto_job_id: int | None,
        is_manual_locked: bool,
        reason: str | None = None,
    ) -> BulletinDeviceAutoLock:
        if not BulletinDeviceLockRepository._is_table_available():
            raise RuntimeError("bulletin_device_auto_lock table is not available")
        row = BulletinDeviceAutoLock.query.filter(BulletinDeviceAutoLock.device_id == str(device_id)).first()
        if not row:
            row = BulletinDeviceAutoLock(device_id=str(device_id))
            db.session.add(row)

        row.auto_job_id = int(auto_job_id) if auto_job_id else None
        row.is_manual_locked = bool(is_manual_locked)
        row.reason = (str(reason)[:255] if reason else None)
        db.session.flush()
        BulletinManualLockCache.clear()
        return row

    @classmethod
    def sync_from_jobs(cls, jobs: Iterable[BulletinAutoJob]) -> None:
        if not cls._is_table_available():
            return

        desired: Dict[str, Tuple[int | None, bool, str | None]] = {}

        for job in jobs or []:
            device_id = str(job.target_device_id or "").strip()
            if not device_id:
                continue
            if not bool(job.is_enabled) or not bool(job.auto_post_enabled):
                continue
            lock_flag = bool(job.lock_manual_upload)
            reason = f"자동 게시 Job: {job.job_name}" if lock_flag else None
            desired[device_id] = (int(job.id), lock_flag, reason)

        try:
            existing = {r.device_id: r for r in cls.list_locks()}

            for device_id, (job_id, locked, reason) in desired.items():
                row = existing.get(device_id)
                if not row:
                    row = BulletinDeviceAutoLock(device_id=device_id)
                    db.session.add(row)
                row.auto_job_id = job_id
                row.is_manual_locked = locked
                row.reason = reason

            # 활성 auto job에서 빠진 디바이스는 잠금 해제
            for device_id, row in existing.items():
                if device_id in desired:
                    continue
                row.auto_job_id = None
                row.is_manual_locked = False
                row.reason = None

            db.session.flush()
            BulletinManualLockCache.clear()
        except SQLAlchemyError:
            db.session.rollback()
            cls._set_table_unavailable()
            BulletinManualLockCache.clear()
