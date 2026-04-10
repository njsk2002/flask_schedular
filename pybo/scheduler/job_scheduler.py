from __future__ import annotations

import threading
from datetime import datetime
from typing import Any, Dict, List

from apscheduler.triggers.interval import IntervalTrigger

from pybo.cache.bulletin_job_cache import BulletinJobCache
from pybo.repository.bulletin_auto_job_repository import BulletinAutoJobRepository
from pybo.repository.bulletin_device_lock_repository import BulletinDeviceLockRepository
from pybo.repository.repository_scheduler_cache import RepositorySchedulerCache
from pybo.service.groupware_service import GroupwareService
from pybo.service.news_service import NewsService


_RUN_LOCK = threading.Lock()


def _safe_log(app, level: str, msg: str, **kw: Any) -> None:
    line = msg if not kw else f"{msg} | {kw}"
    logger = app.logger
    getattr(logger, level, logger.info)(line)


def _serialize_due_items(due_items) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for auto_job, schedule in due_items:
        try:
            rows.append(
                {
                    "job_id": int(getattr(auto_job, "id", 0) or 0),
                    "job_name": str(getattr(auto_job, "job_name", "") or ""),
                    "job_type": str(getattr(auto_job, "job_type", "") or ""),
                    "device_id": str(getattr(auto_job, "target_device_id", "") or ""),
                    "job_enabled": bool(getattr(auto_job, "is_enabled", False)),
                    "schedule_id": int(getattr(schedule, "id", 0) or 0),
                    "run_time": str(getattr(schedule, "run_time", "") or ""),
                    "schedule_enabled": bool(getattr(schedule, "is_enabled", False)),
                    "sort_order": int(getattr(schedule, "sort_order", 0) or 0),
                }
            )
        except Exception as e:
            rows.append(
                {
                    "error": "serialize_failed",
                    "detail": str(e),
                }
            )
    return rows


def _run_single_job(app, *, now: datetime, auto_job, schedule) -> Dict[str, Any]:
    job_type = str(auto_job.job_type or "").strip().lower()

    _safe_log(
        app,
        "warning",
        "[AUTO-SCHED] run_single_job:start",
        now=now.strftime("%Y-%m-%d %H:%M:%S"),
        job_id=int(getattr(auto_job, "id", 0) or 0),
        job_name=str(getattr(auto_job, "job_name", "") or ""),
        job_type=job_type,
        device_id=str(getattr(auto_job, "target_device_id", "") or ""),
        schedule_id=int(getattr(schedule, "id", 0) or 0),
        schedule_run_time=str(getattr(schedule, "run_time", "") or ""),
    )

    if job_type == "groupware":
        res = GroupwareService(device_id=str(auto_job.target_device_id)).run(
            force=False,
            run_at=now,
            auto_job=auto_job,
            schedule_item=schedule,
        )
        _safe_log(app, "warning", "[AUTO-SCHED] run_single_job:end", result=res)
        return res

    if job_type == "news":
        res = NewsService(device_id=str(auto_job.target_device_id)).run(
            force=False,
            run_at=now,
            auto_job=auto_job,
            schedule_item=schedule,
            slot_label=str(schedule.run_time),
        )
        _safe_log(app, "warning", "[AUTO-SCHED] run_single_job:end", result=res)
        return res

    res = {
        "ok": False,
        "job": "unknown",
        "job_id": int(getattr(auto_job, "id", 0) or 0),
        "error": f"unsupported job_type: {job_type}",
    }
    _safe_log(app, "warning", "[AUTO-SCHED] run_single_job:unsupported", result=res)
    return res


def polling_tick(app) -> Dict[str, Any]:
    # 1) 이 로그가 안 뜨면 polling_tick 자체가 호출 안 된 것
    _safe_log(app, "warning", "[AUTO-SCHED] polling_tick ENTER")

    if not _RUN_LOCK.acquire(blocking=False):
        _safe_log(app, "warning", "[AUTO-SCHED] tick skipped", reason="already_running")
        return {"ok": True, "skipped": True, "reason": "already_running"}

    try:
        with app.app_context():
            raw_now = datetime.now()
            now = raw_now.replace(second=0, microsecond=0)
            hhmm = now.strftime("%H:%M")

            # 2) 현재 실제 tick 시각과 HH:MM 정규화 값 확인
            _safe_log(
                app,
                "warning",
                "[AUTO-SCHED] tick start",
                raw_now=raw_now.strftime("%Y-%m-%d %H:%M:%S"),
                normalized_now=now.strftime("%Y-%m-%d %H:%M:%S"),
                hhmm=hhmm,
            )

            all_active_jobs = BulletinAutoJobRepository.list_active_jobs()
            _safe_log(
                app,
                "warning",
                "[AUTO-SCHED] active jobs loaded",
                count=len(all_active_jobs),
            )

            BulletinDeviceLockRepository.sync_from_jobs(all_active_jobs)
            _safe_log(app, "warning", "[AUTO-SCHED] device lock sync done")

            due = BulletinAutoJobRepository.get_due_jobs(hhmm)
            due_rows = _serialize_due_items(due)

            # 3) 여기서 due_count=0 이면 15:26 잡이 조회 자체가 안 된 것
            _safe_log(
                app,
                "warning",
                "[AUTO-SCHED] due jobs loaded",
                hhmm=hhmm,
                due_count=len(due),
                due_items=due_rows,
            )

            results = []
            skipped = []

            for auto_job, schedule in due:
                dedupe_key = f"{int(auto_job.id)}:{hhmm}"
                should_skip = BulletinJobCache.should_skip_minutely(
                    dedupe_key,
                    hold_seconds=55,
                )

                if should_skip:
                    skip_row = {
                        "job_id": int(auto_job.id),
                        "job_name": str(auto_job.job_name or ""),
                        "schedule_id": int(schedule.id),
                        "run_time": str(schedule.run_time),
                        "reason": "dedupe_skip",
                        "dedupe_key": dedupe_key,
                    }
                    skipped.append(skip_row)
                    _safe_log(app, "warning", "[AUTO-SCHED] due job skipped", **skip_row)
                    continue

                try:
                    res = _run_single_job(app, now=now, auto_job=auto_job, schedule=schedule)
                except Exception as e:
                    app.logger.exception("[AUTO-SCHED] job failed", exc_info=True)
                    res = {
                        "ok": False,
                        "job": str(auto_job.job_type),
                        "job_id": int(auto_job.id),
                        "device_id": str(auto_job.target_device_id),
                        "error": str(e),
                    }

                RepositorySchedulerCache.set_run(
                    key=f"job_{int(auto_job.id)}",
                    status=("success" if res.get("ok") else "failed"),
                    detail={
                        "tick_time": raw_now.strftime("%Y-%m-%d %H:%M:%S"),
                        "run_time": hhmm,
                        "job_name": str(auto_job.job_name),
                        "job_type": str(auto_job.job_type),
                        "schedule_id": int(schedule.id),
                        "schedule_run_time": str(schedule.run_time),
                        "result": res,
                    },
                )
                results.append(res)

            summary = {
                "ok": True,
                "time": hhmm,
                "raw_now": raw_now.strftime("%Y-%m-%d %H:%M:%S"),
                "due_count": len(due),
                "run_count": len(results),
                "skip_count": len(skipped),
                "skipped": skipped,
                "results": results,
            }

            RepositorySchedulerCache.set_run("auto_scheduler_tick", "success", summary)
            _safe_log(app, "warning", "[AUTO-SCHED] tick end", summary=summary)
            return summary

    except Exception as e:
        with app.app_context():
            RepositorySchedulerCache.set_run("auto_scheduler_tick", "failed", {"error": str(e)})
        _safe_log(app, "exception", "[AUTO-SCHED] polling tick failed", err=str(e))
        return {"ok": False, "error": str(e)}

    finally:
        _RUN_LOCK.release()


def register_jobs(scheduler, app) -> None:
    # 4) register_jobs 함수가 실제 호출됐는지 확인용
    _safe_log(app, "warning", "[AUTO-SCHED] register_jobs ENTER")

    def _tick_job():
        try:
            # 5) APScheduler가 실제 발사했는지 확인용
            _safe_log(app, "warning", "[AUTO-SCHED] APScheduler fired")
            res = polling_tick(app)
            _safe_log(app, "warning", "[AUTO-SCHED] tick", result=res)
        except Exception:
            app.logger.exception("[AUTO-SCHED] tick crashed")

    interval_sec = 60
    try:
        interval_sec = max(60, int(app.config.get("EINK_AUTOJOB_POLLING_SECONDS", 60)))
    except Exception:
        interval_sec = 60

    scheduler.add_job(
        _tick_job,
        trigger=IntervalTrigger(seconds=interval_sec, timezone="Asia/Seoul"),
        id="eink_auto_bulletin_polling",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=40,
    )

    try:
        job = scheduler.get_job("eink_auto_bulletin_polling")
        _safe_log(
            app,
            "warning",
            "[AUTO-SCHED] register_jobs done",
            interval_sec=interval_sec,
            job_id=(job.id if job else None),
            next_run_time=(str(job.next_run_time) if job and getattr(job, "next_run_time", None) else None),
        )

        # 6) 현재 scheduler에 등록된 전체 job도 같이 출력
        all_jobs = scheduler.get_jobs()
        _safe_log(
            app,
            "warning",
            "[AUTO-SCHED] scheduler jobs snapshot",
            jobs=[
                {
                    "id": j.id,
                    "next_run_time": str(getattr(j, "next_run_time", None)),
                    "trigger": str(getattr(j, "trigger", None)),
                }
                for j in all_jobs
            ],
        )

    except Exception as e:
        _safe_log(app, "warning", "[AUTO-SCHED] register_jobs inspect failed", err=str(e))


# manual trigger helpers (controller compatibility)
def run_groupware_now(force: bool = True) -> Dict[str, Any]:
    return GroupwareService(device_id="E06").run(force=force, run_at=datetime.now())


def run_news_now(force: bool = True, slot_label: str | None = None) -> Dict[str, Any]:
    return NewsService(device_id="E07").run(force=force, run_at=datetime.now(), slot_label=slot_label)