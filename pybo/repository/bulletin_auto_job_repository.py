from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Tuple, Set

from sqlalchemy import or_
from sqlalchemy.exc import SQLAlchemyError

from pybo import db
from pybo.cache.bulletin_job_cache import BulletinJobCache
from pybo.models import (
    BulletinAutoJob,
    BulletinAutoJobKeyword,
    BulletinAutoJobSchedule,
)


class BulletinAutoJobRepository:
    """
    자동 게시(Job) 관련 Repository.

    이 Repository의 책임:
    - 자동 게시 Job CRUD
    - 스케줄(run_time) 조회
    - 키워드 조회
    - 현재 활성 Job 목록 조회
    - 수동 업로드 잠금 대상 device 조회

    ----------------------------------------------------------------------
    [이번 추가의 핵심]
    ----------------------------------------------------------------------
    e_file_upload.html 에서 자동 관리 device를 비활성화하려면,
    백엔드가 "어떤 device가 자동관리 + 수동업로드잠금 상태인지"를
    판단해서 내려줘야 한다.

    그 기준 데이터는 BulletinAutoJob 테이블에 이미 있다.
    즉:
      - is_enabled = True
      - auto_post_enabled = True
      - lock_manual_upload = True
      - target_device_id 가 존재
    인 Job이 잡고 있는 device는
    "수동 업로드 잠금 대상"으로 보면 된다.

    그래서 아래 helper 2개를 추가한다.
      1) list_locked_device_ids(...)
      2) is_manual_upload_locked(...)
    """

    @staticmethod
    def _safe_empty_jobs() -> List[BulletinAutoJob]:
        try:
            db.session.rollback()
        except Exception:
            pass
        return []

    @staticmethod
    def _normalize_run_time(run_time: str) -> str:
        s = str(run_time or "").strip()
        if not s:
            raise ValueError("run_time is required")

        if len(s) == 4 and s[1] == ":":
            s = f"0{s}"

        if len(s) != 5 or s[2] != ":":
            raise ValueError("run_time format must be HH:MM")

        hh = int(s[:2])
        mm = int(s[3:])

        if hh < 0 or hh > 23 or mm < 0 or mm > 59:
            raise ValueError("run_time out of range")

        return f"{hh:02d}:{mm:02d}"

    @staticmethod
    def _normalize_optional_date(value: Any) -> date | None:
        s = str(value or "").strip()
        if not s:
            return None
        try:
            return date.fromisoformat(s)
        except ValueError as e:
            raise ValueError("date format must be YYYY-MM-DD") from e

    @classmethod
    def list_active_jobs(cls) -> List[BulletinAutoJob]:
        """
        현재 활성화된 자동 게시 Job 목록 반환.

        활성 조건:
        - is_enabled = True
        - auto_post_enabled = True
        """
        try:
            return (
                BulletinAutoJob.query
                .filter(
                    BulletinAutoJob.is_enabled.is_(True),
                    BulletinAutoJob.auto_post_enabled.is_(True),
                )
                .order_by(BulletinAutoJob.priority.asc(), BulletinAutoJob.id.asc())
                .all()
            )
        except SQLAlchemyError:
            return cls._safe_empty_jobs()

    @classmethod
    def list_active_jobs_brief(cls, use_cache: bool = True) -> List[Dict[str, Any]]:
        """
        프론트/상위 서비스에서 가볍게 사용할 활성 Job 목록 반환.
        캐시 사용 가능.
        """
        if use_cache:
            cached = BulletinJobCache.get_active_jobs()
            if cached:
                return cached

        rows = []
        for job in cls.list_active_jobs():
            rows.append(
                {
                    "id": int(job.id),
                    "job_name": job.job_name,
                    "job_type": job.job_type,
                    "target_device_id": job.target_device_id,
                    "template_code": job.template_code,
                    "priority": int(job.priority or 0),
                    "lock_manual_upload": bool(job.lock_manual_upload),
                }
            )

        BulletinJobCache.set_active_jobs(rows, ttl_seconds=30)
        return rows

    @classmethod
    def list_locked_device_ids(
        cls,
        owner_user_no: int | None = None,
        *,
        use_cache: bool = True,
    ) -> Set[str]:
        """
        수동 업로드가 잠긴(auto managed + lock_manual_upload) device_id 집합 반환.

        ------------------------------------------------------------------
        [잠금 기준]
        ------------------------------------------------------------------
        아래 조건을 모두 만족하는 Job의 target_device_id 를 잠금 대상으로 본다.
        - is_enabled = True
        - auto_post_enabled = True
        - lock_manual_upload = True

        ------------------------------------------------------------------
        [owner_user_no]
        ------------------------------------------------------------------
        - owner_user_no 가 주어지면 해당 사용자 소유 Job 기준으로만 본다.
        - None 이면 전체 활성 Job 기준으로 본다.

        ------------------------------------------------------------------
        [왜 Set[str] 로 반환하나]
        ------------------------------------------------------------------
        - device 기준으로 빠르게 membership 체크하려고
          set 형태가 가장 효율적이다.
        """
        locked: Set[str] = set()

        try:
            # 캐시된 brief 목록을 재활용할 수 있으면 우선 사용
            # 다만 owner_user_no 필터가 필요하면 DB 직접 조회가 더 명확하다.
            if use_cache and owner_user_no is None:
                for row in cls.list_active_jobs_brief(use_cache=True):
                    if not bool(row.get("lock_manual_upload")):
                        continue

                    did = str(row.get("target_device_id") or "").strip()
                    if did:
                        locked.add(did)
                return locked

            q = BulletinAutoJob.query.filter(
                BulletinAutoJob.is_enabled.is_(True),
                BulletinAutoJob.auto_post_enabled.is_(True),
                BulletinAutoJob.lock_manual_upload.is_(True),
            )

            if owner_user_no is not None:
                q = q.filter(BulletinAutoJob.owner_user_no == int(owner_user_no))

            rows = (
                q.order_by(BulletinAutoJob.priority.asc(), BulletinAutoJob.id.asc())
                .all()
            )

            for job in rows:
                did = str(job.target_device_id or "").strip()
                if did:
                    locked.add(did)

            return locked

        except SQLAlchemyError:
            try:
                db.session.rollback()
            except Exception:
                pass
            return set()

    @classmethod
    def is_manual_upload_locked(
        cls,
        device_id: str,
        owner_user_no: int | None = None,
        *,
        use_cache: bool = True,
    ) -> bool:
        """
        특정 device_id 가 수동 업로드 잠금 상태인지 반환.

        사용 예:
        - /dashboard/board_devices 응답에 auto_managed 표시
        - /dashboard/upload/select 서버 차단
        """
        did = str(device_id or "").strip()
        if not did:
            return False

        locked = cls.list_locked_device_ids(
            owner_user_no=owner_user_no,
            use_cache=use_cache,
        )
        return did in locked

    @staticmethod
    def get_job(job_id: int) -> BulletinAutoJob | None:
        try:
            return BulletinAutoJob.query.filter(BulletinAutoJob.id == int(job_id)).first()
        except SQLAlchemyError:
            try:
                db.session.rollback()
            except Exception:
                pass
            return None

    @staticmethod
    def get_manage_jobs(owner_user_no: int | None = None) -> List[BulletinAutoJob]:
        try:
            q = BulletinAutoJob.query
            if owner_user_no:
                q = q.filter(
                    or_(
                        BulletinAutoJob.owner_user_no.is_(None),
                        BulletinAutoJob.owner_user_no == int(owner_user_no),
                    )
                )
            return q.order_by(BulletinAutoJob.priority.asc(), BulletinAutoJob.id.desc()).all()
        except SQLAlchemyError:
            return BulletinAutoJobRepository._safe_empty_jobs()

    @classmethod
    def get_due_jobs(cls, run_time: str) -> List[Tuple[BulletinAutoJob, BulletinAutoJobSchedule]]:
        hhmm = cls._normalize_run_time(run_time)
        try:
            rows = (
                db.session.query(BulletinAutoJob, BulletinAutoJobSchedule)
                .join(
                    BulletinAutoJobSchedule,
                    BulletinAutoJobSchedule.job_id == BulletinAutoJob.id,
                )
                .filter(
                    BulletinAutoJob.is_enabled.is_(True),
                    BulletinAutoJob.auto_post_enabled.is_(True),
                    BulletinAutoJobSchedule.is_enabled.is_(True),
                    BulletinAutoJobSchedule.run_time == hhmm,
                )
                .order_by(BulletinAutoJob.priority.asc(), BulletinAutoJob.id.asc())
                .all()
            )
            return rows
        except SQLAlchemyError:
            cls._safe_empty_jobs()
            return []

    @staticmethod
    def list_schedules(job_id: int) -> List[BulletinAutoJobSchedule]:
        try:
            return (
                BulletinAutoJobSchedule.query
                .filter(BulletinAutoJobSchedule.job_id == int(job_id))
                .order_by(BulletinAutoJobSchedule.sort_order.asc(), BulletinAutoJobSchedule.run_time.asc())
                .all()
            )
        except SQLAlchemyError:
            try:
                db.session.rollback()
            except Exception:
                pass
            return []

    @staticmethod
    def list_keywords(job_id: int, schedule_id: int | None = None) -> List[BulletinAutoJobKeyword]:
        try:
            base_q = (
                BulletinAutoJobKeyword.query
                .filter(
                    BulletinAutoJobKeyword.job_id == int(job_id),
                    BulletinAutoJobKeyword.is_enabled.is_(True),
                )
                .order_by(BulletinAutoJobKeyword.sort_order.asc(), BulletinAutoJobKeyword.id.asc())
            )

            if schedule_id is None:
                return base_q.filter(BulletinAutoJobKeyword.schedule_id.is_(None)).all()

            scoped = base_q.filter(BulletinAutoJobKeyword.schedule_id == int(schedule_id)).all()
            if scoped:
                return scoped
            return base_q.filter(BulletinAutoJobKeyword.schedule_id.is_(None)).all()
        except SQLAlchemyError:
            try:
                db.session.rollback()
            except Exception:
                pass
            return []

    @staticmethod
    def save_job(payload: Dict[str, Any], owner_user_no: int | None = None) -> BulletinAutoJob:
        job_id = payload.get("id")
        if job_id:
            job = BulletinAutoJob.query.filter(BulletinAutoJob.id == int(job_id)).first()
            if not job:
                raise ValueError("job not found")
        else:
            job = BulletinAutoJob()
            db.session.add(job)

        if owner_user_no and not job.owner_user_no:
            job.owner_user_no = int(owner_user_no)

        job_type = str(payload.get("job_type") or "groupware").strip().lower()
        if job_type not in ("groupware", "news"):
            raise ValueError("job_type must be groupware or news")

        job.job_name = str(payload.get("job_name") or "").strip() or "자동 게시 Job"
        job.job_type = job_type
        job.is_enabled = bool(payload.get("is_enabled", True))
        job.target_device_id = str(payload.get("target_device_id") or "").strip()
        job.template_code = str(payload.get("template_code") or "default").strip()
        job.article_count = max(1, int(payload.get("article_count") or 3))
        job.summary_length = min(500, max(50, int(payload.get("summary_length") or 200)))

        if job_type == "groupware":
            job.upcoming_start_date = BulletinAutoJobRepository._normalize_optional_date(
                payload.get("upcoming_start_date")
            )
            job.upcoming_end_date = BulletinAutoJobRepository._normalize_optional_date(
                payload.get("upcoming_end_date")
            )
            if job.upcoming_start_date and job.upcoming_end_date and job.upcoming_start_date > job.upcoming_end_date:
                raise ValueError("upcoming_start_date must be before or equal to upcoming_end_date")
        else:
            job.upcoming_start_date = None
            job.upcoming_end_date = None

        job.priority = int(payload.get("priority") or 10)
        job.auto_post_enabled = bool(payload.get("auto_post_enabled", True))
        job.lock_manual_upload = bool(payload.get("lock_manual_upload", True))
        job.updated_at = datetime.now().replace(microsecond=0)

        db.session.flush()

        # 활성 Job 관련 캐시 무효화
        BulletinJobCache.set_active_jobs([], ttl_seconds=1)
        return job

    @classmethod
    def replace_schedules(
        cls,
        job_id: int,
        rows: Iterable[Any],
        *,
        job_type: str = "groupware",
    ) -> List[BulletinAutoJobSchedule]:
        BulletinAutoJobSchedule.query.filter(BulletinAutoJobSchedule.job_id == int(job_id)).delete()

        created: List[BulletinAutoJobSchedule] = []
        normalized_type = str(job_type or "groupware").strip().lower()
        seen: set[str] = set()

        for idx, raw in enumerate(rows or []):
            if isinstance(raw, str):
                run_time = raw
                keyword_text = None
            elif isinstance(raw, dict):
                run_time = raw.get("run_time") or ""
                keyword_text = raw.get("keyword_text")
            else:
                continue

            hhmm = cls._normalize_run_time(str(run_time))
            if hhmm in seen:
                raise ValueError(f"duplicated run_time: {hhmm}")
            seen.add(hhmm)

            if normalized_type == "news":
                kw = str(keyword_text or "").strip()
                if not kw:
                    raise ValueError(f"keyword_text is required for run_time={hhmm}")
            else:
                kw = None

            row = BulletinAutoJobSchedule(
                job_id=int(job_id),
                run_time=hhmm,
                keyword_text=kw,
                sort_order=idx,
                is_enabled=True,
            )
            db.session.add(row)
            created.append(row)

        if len(created) == 0:
            raise ValueError("at least one schedule is required")
        if len(created) > 7:
            raise ValueError("maximum 7 schedules are allowed")

        db.session.flush()
        return created

    @staticmethod
    def replace_keywords(job_id: int, rows: Iterable[Dict[str, Any]]) -> List[BulletinAutoJobKeyword]:
        BulletinAutoJobKeyword.query.filter(BulletinAutoJobKeyword.job_id == int(job_id)).delete()
        created: List[BulletinAutoJobKeyword] = []
        for idx, row in enumerate(rows or []):
            keyword_text = str(row.get("keyword_text") or "").strip()
            if not keyword_text:
                continue
            schedule_id = row.get("schedule_id")
            keyword = BulletinAutoJobKeyword(
                job_id=int(job_id),
                schedule_id=(int(schedule_id) if schedule_id else None),
                keyword_group_name=(str(row.get("keyword_group_name") or "").strip() or None),
                keyword_text=keyword_text,
                sort_order=int(row.get("sort_order") or idx),
                is_enabled=bool(row.get("is_enabled", True)),
            )
            db.session.add(keyword)
            created.append(keyword)
        db.session.flush()
        return created

    @staticmethod
    def delete_job(job_id: int) -> bool:
        row = BulletinAutoJob.query.filter(BulletinAutoJob.id == int(job_id)).first()
        if not row:
            return False
        db.session.delete(row)

        # 활성 Job 관련 캐시 무효화
        BulletinJobCache.set_active_jobs([], ttl_seconds=1)
        return True

    @staticmethod
    def touch_run_result(job_id: int, success: bool) -> None:
        row = BulletinAutoJob.query.filter(BulletinAutoJob.id == int(job_id)).first()
        if not row:
            return

        now = datetime.now().replace(microsecond=0)
        row.last_run_at = now
        if success:
            row.last_success_at = now