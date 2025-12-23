from sqlalchemy import asc
from ..models import EInkPosting
from pybo import db
from datetime import datetime, timedelta

def kst_now_naive() -> datetime:
        return datetime.now().replace(microsecond=0)

class PostingSchedulerService:

    @staticmethod
    def tick_device(*, user_id: int, device_id: str):
        now = kst_now_naive()

        # 1) 만료된 active → expired
        active = (EInkPosting.query
            .filter_by(user_id=user_id, device_id=device_id, status="active")
            .with_for_update()
            .first())

        if active and active.end_time and active.end_time <= now:
            active.status = "expired"
            active.end_time = now
            active.reason = (active.reason or "")[:200] + "|auto_expired"

        # 2) start_time <= now 인 wait 중 가장 빠른 1개 선택
        next_wait = (EInkPosting.query
            .filter_by(user_id=user_id, device_id=device_id, status="wait")
            .filter(EInkPosting.start_time.isnot(None))
            .filter(EInkPosting.start_time <= now)
            .order_by(EInkPosting.start_time.asc(), EInkPosting.id.asc())
            .with_for_update()
            .first())

        if not next_wait:
            db.session.commit()
            return {"ok": True, "device_id": device_id, "changed": False}

        # 3) active가 남아있으면(무기한 end_time=None 포함) 선행 종료 처리 후 승격
        if active and active.status == "active":
            # preempt
            active.status = "expired"
            active.end_time = now
            active.reason = (active.reason or "")[:200] + "|preempted"

        next_wait.status = "active"
        # start_time이 과거면 now로 보정(선택)
        if next_wait.start_time and next_wait.start_time < now:
            next_wait.start_time = now
        next_wait.reason = (next_wait.reason or "")[:200] + "|promoted"

        db.session.commit()
        return {"ok": True, "device_id": device_id, "changed": True, "active_posting_id": next_wait.id}

    @staticmethod
    def tick_all():
        # 운영 확장: (user_id, device_id) distinct로 돌리기
        rows = (db.session.query(EInkPosting.user_id, EInkPosting.device_id)
            .filter(EInkPosting.status.in_(["active","wait"]))
            .distinct()
            .all())

        changed = 0
        for uid, did in rows:
            try:
                r = PostingSchedulerService.tick_device(user_id=int(uid), device_id=str(did))
                if r.get("changed"): changed += 1
            except Exception:
                db.session.rollback()
        return {"ok": True, "devices": len(rows), "changed": changed}
