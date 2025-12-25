# pybo/service/posing_scheduler.py
from datetime import datetime, timedelta
from sqlalchemy import or_, asc
from pybo import db
from ..models import EInkPosting

def kst_now_naive() -> datetime:
    # Windows가 KST면 OK. (서버 시간대가 UTC면 여기부터 바꿔야 함)
    return datetime.now().replace(microsecond=0)

class PostingSchedulerService:

    @staticmethod
    def _safe_reason_append(reason: str, token: str, limit: int = 200) -> str:
        base = (reason or "")[:limit]
        return base + token

    @staticmethod
    def tick_device(*, user_id: int, device_id: str, logger=None):
        now = kst_now_naive()

        if logger:
            logger.debug(f"[TICK] device={device_id} now={now}")

        changed = False
        promoted = False
        failed_count = 0

        # 1) 만료된 active → expired
        active = (EInkPosting.query
            .filter_by(user_id=user_id, device_id=device_id, status="active")
            .order_by(EInkPosting.start_time.desc(), EInkPosting.id.desc())
            .with_for_update()
            .first())

        if active and active.end_time and active.end_time <= now:
            # active 만료 처리
            active.status = "expired"

            # end_time을 now로 "늘리는" 건 안전(대개 start_time < now)
            # 혹시라도 start_time이 None/미래 등 이상치면 CHECK에 걸릴 수 있으니 가드
            if active.start_time and now <= active.start_time:
                active.end_time = active.start_time + timedelta(seconds=1)
                active.reason = PostingSchedulerService._safe_reason_append(active.reason, "|auto_expired_adjust")
            else:
                active.end_time = now
                active.reason = PostingSchedulerService._safe_reason_append(active.reason, "|auto_expired")

            changed = True
            if logger:
                logger.debug(f"[TICK] expired active id={active.id} (end_time<=now)")

        # 2) wait 후보 중 "지금 시작 가능(start_time<=now 또는 NULL)" 중에서 가장 빠른 것부터 처리
        #    단, end_time이 이미 과거인 경우는 서버 멈춤/지연으로 발생 가능 → failed 처리하고 다음 후보로 넘어감
        next_wait = None

        # 안전장치: 한 tick에서 최대 몇 개까지 failed 스캔/처리할지(무한루프 방지)
        MAX_STALE_SCAN = 20
        scan = 0

        while scan < MAX_STALE_SCAN:
            scan += 1
            cand = (EInkPosting.query
                .filter_by(user_id=user_id, device_id=device_id, status="wait")
                .filter(or_(EInkPosting.start_time.is_(None), EInkPosting.start_time <= now))
                .order_by(asc(EInkPosting.start_time), asc(EInkPosting.id))
                .with_for_update()
                .first())

            if not cand:
                next_wait = None
                break

            # ✅ 핵심: end_time이 이미 과거면 승격시키면 안 됨
            if cand.end_time and cand.end_time <= now:
                cand.status = "failed"
                cand.reason = PostingSchedulerService._safe_reason_append(
                    cand.reason,
                    f"|stale_wait(end_time<=now:{cand.end_time})"
                )
                failed_count += 1
                changed = True

                if logger:
                    logger.warning(
                        f"[TICK] stale wait -> failed id={cand.id} "
                        f"start={cand.start_time} end={cand.end_time} now={now}"
                    )

                # 다음 후보 찾기
                continue

            # end_time이 과거는 아니지만, 혹시 start/end 범위가 이미 깨진 데이터면(제약조건이 더 엄격할 수 있음)
            # 시간값을 건드리지 않고 status만 failed로 보내는게 안전
            if cand.start_time and cand.end_time and cand.end_time <= cand.start_time:
                cand.status = "failed"
                cand.reason = PostingSchedulerService._safe_reason_append(
                    cand.reason,
                    f"|bad_range(end<=start:{cand.end_time}<={cand.start_time})"
                )
                failed_count += 1
                changed = True
                if logger:
                    logger.warning(
                        f"[TICK] bad range wait -> failed id={cand.id} "
                        f"start={cand.start_time} end={cand.end_time} now={now}"
                    )
                continue

            next_wait = cand
            break

        # 후보가 없으면 여기서 종료(필요 시에만 commit)
        if not next_wait:
            if changed:
                db.session.commit()
            else:
                db.session.rollback()
            return {
                "ok": True,
                "device_id": device_id,
                "changed": changed,
                "promoted": False,
                "failed_count": failed_count,
            }

        # 3) active가 아직 살아있으면 선행 종료 처리 후 승격
        if active and active.status == "active":
            active.status = "expired"

            if active.start_time and now <= active.start_time:
                active.end_time = active.start_time + timedelta(seconds=1)
                active.reason = PostingSchedulerService._safe_reason_append(active.reason, "|preempted_adjust")
            else:
                active.end_time = now
                active.reason = PostingSchedulerService._safe_reason_append(active.reason, "|preempted")

            changed = True
            if logger:
                logger.debug(f"[TICK] preempt active id={active.id}")

        # 4) wait → active 승격 (이제 end_time 과거 케이스는 위에서 제거됨)
        next_wait.status = "active"

        # start_time 보정: None 또는 과거면 now로
        # (end_time이 존재할 때 now가 end_time보다 작다는 건 위에서 보장됨)
        if (next_wait.start_time is None) or (next_wait.start_time < now):
            next_wait.start_time = now

        next_wait.reason = PostingSchedulerService._safe_reason_append(next_wait.reason, "|promoted")
        changed = True
        promoted = True

        db.session.commit()

        if logger:
            logger.debug(f"[TICK] promoted wait->active id={next_wait.id} failed_count={failed_count}")

        return {
            "ok": True,
            "device_id": device_id,
            "changed": True,
            "promoted": True,
            "failed_count": failed_count,
            "active_posting_id": next_wait.id,
        }

    @staticmethod
    def tick_all(logger=None):
        rows = (db.session.query(EInkPosting.user_id, EInkPosting.device_id)
            .filter(EInkPosting.status.in_(["active", "wait"]))
            .distinct()
            .all())

        changed = 0
        promoted = 0
        failed_total = 0

        for uid, did in rows:
            try:
                r = PostingSchedulerService.tick_device(
                    user_id=int(uid),
                    device_id=str(did),
                    logger=logger
                )
                if r.get("changed"):
                    changed += 1
                if r.get("promoted"):
                    promoted += 1
                failed_total += int(r.get("failed_count") or 0)
            except Exception as e:
                db.session.rollback()
                if logger:
                    logger.exception(f"[TICK] device={did} crashed: {e}")
                else:
                    raise

        return {
            "ok": True,
            "devices": len(rows),
            "changed": changed,
            "promoted": promoted,
            "failed_total": failed_total,
        }
