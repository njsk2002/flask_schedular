# pybo/scheduler.py
import os
import time
import shutil
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_SCHED = None


def cleanup_old_uploads(app):
    tmpdir_root = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "eink_uploads")
    now = time.time()
    if not os.path.isdir(tmpdir_root):
        return

    for d in os.listdir(tmpdir_root):
        full = os.path.join(tmpdir_root, d)
        try:
            if os.path.isdir(full):
                mtime = os.path.getmtime(full)
                if now - mtime > 3600:
                    shutil.rmtree(full, ignore_errors=True)
                    app.logger.info(f"[CLEANUP] Auto-deleted old temp dir {full}")
        except Exception as e:
            app.logger.warning(f"[CLEANUP] Failed {full}: {e}")


def init_scheduler(app):
    global _SCHED
    if _SCHED is not None:
        app.logger.info("[SCHEDULER] init_scheduler called again; returning existing scheduler")
        return _SCHED

    scheduler = BackgroundScheduler(
        daemon=True,
        timezone="Asia/Seoul",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 15,
        },
    )

    # 1) cleanup job
    def _job_cleanup():
        try:
            cleanup_old_uploads(app)
        except Exception:
            app.logger.exception("[SCHEDULER] cleanup job crashed")

    scheduler.add_job(
        _job_cleanup,
        trigger=IntervalTrigger(minutes=30),
        id="cleanup_old_uploads",
        replace_existing=True,
    )

    # 2) posting tick job
    from .service.posing_scheduler import PostingSchedulerService

    def _job_posting_tick():
        try:
            with app.app_context():
                result = PostingSchedulerService.tick_all(logger=app.logger)
            # ✅ 핵심: changed/rows를 반드시 로그로 남김
            # app.logger.debug(f"[SCHEDULER] tick_all result={result}")
        except Exception:
            app.logger.exception("[SCHEDULER] tick_all crashed")

    scheduler.add_job(
        _job_posting_tick,
        trigger=IntervalTrigger(seconds=2),
        id="eink_posting_tick",
        replace_existing=True,
    )

    scheduler.start()
    _SCHED = scheduler

    try:
        jobs = scheduler.get_jobs()
        app.logger.info("[SCHEDULER] jobs=" + ", ".join([f"{j.id}@{j.next_run_time}" for j in jobs]))
    except Exception:
        app.logger.exception("[SCHEDULER] failed to list jobs")

    return scheduler
