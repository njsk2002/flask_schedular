# pybo/scheduler/__init__.py
from __future__ import annotations

import importlib.util
import os
import shutil
import time
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_SCHED = None


def _register_eink_jobs(scheduler, app):
    """
    pybo.scheduler 패키지 내부의 job_scheduler.py 를 파일 경로로 직접 로드한다.
    현재 파일(__init__.py)은 이미 pybo/scheduler/ 디렉터리 안에 있으므로,
    추가로 /scheduler 를 한 번 더 붙이면 잘못된 경로가 된다.
    """
    try:
        mod_path = Path(__file__).resolve().parent / "job_scheduler.py"

        app.logger.warning(f"[AUTO-SCHED-BOOT] trying job module path: {mod_path}")

        if not mod_path.exists():
            app.logger.warning(f"[SCHEDULER] EINK job module not found: {mod_path}")
            return

        spec = importlib.util.spec_from_file_location(
            "pybo_scheduler_job_scheduler",
            str(mod_path)
        )
        if spec is None or spec.loader is None:
            app.logger.warning("[SCHEDULER] Failed to create spec for job_scheduler")
            return

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        app.logger.warning("[AUTO-SCHED-BOOT] job module loaded successfully")

        if hasattr(module, "register_jobs"):
            app.logger.warning("[AUTO-SCHED-BOOT] calling register_jobs(scheduler, app)")
            module.register_jobs(scheduler, app)
            app.logger.warning("[SCHEDULER] EINK generation jobs registered")
        else:
            app.logger.warning("[SCHEDULER] register_jobs not found in job_scheduler module")

    except Exception:
        app.logger.exception("[SCHEDULER] Failed to register EINK generation jobs")


def cleanup_old_uploads(app):
    tmpdir_root = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "eink_uploads")
    now = time.time()

    if not os.path.isdir(tmpdir_root):
        app.logger.warning(f"[CLEANUP] tmpdir_root not found: {tmpdir_root}")
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

    app.logger.warning("[SCHEDULER] init_scheduler ENTER")

    scheduler = BackgroundScheduler(
        daemon=True,
        timezone="Asia/Seoul",
        job_defaults={
            "coalesce": True,
            "max_instances": 1,
            "misfire_grace_time": 15,
        },
    )

    def _job_cleanup():
        try:
            app.logger.warning("[SCHEDULER] cleanup_old_uploads fired")
            cleanup_old_uploads(app)
        except Exception:
            app.logger.exception("[SCHEDULER] cleanup job crashed")

    scheduler.add_job(
        _job_cleanup,
        trigger=IntervalTrigger(minutes=30),
        id="cleanup_old_uploads",
        replace_existing=True,
    )
    app.logger.warning("[SCHEDULER] cleanup_old_uploads job added")

    from ..service.posing_scheduler import PostingSchedulerService

    def _job_posting_tick():
        try:
            app.logger.warning("[SCHEDULER] eink_posting_tick fired")
            with app.app_context():
                PostingSchedulerService.tick_all(logger=app.logger)
        except Exception:
            app.logger.exception("[SCHEDULER] tick_all crashed")

    scheduler.add_job(
        _job_posting_tick,
        trigger=IntervalTrigger(seconds=2),
        id="eink_posting_tick",
        replace_existing=True,
    )
    app.logger.warning("[SCHEDULER] eink_posting_tick job added")

    # 자동 게시 스케줄러 등록
    _register_eink_jobs(scheduler, app)

    scheduler.start()
    _SCHED = scheduler

    try:
        jobs = scheduler.get_jobs()
        app.logger.warning(
            "[SCHEDULER] jobs=" + ", ".join([f"{j.id}@{j.next_run_time}" for j in jobs])
        )
    except Exception:
        app.logger.exception("[SCHEDULER] failed to list jobs")

    return scheduler