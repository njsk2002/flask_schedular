# pybo/scheduler.py
import os, time, shutil
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

# ✅ 전역 싱글톤 (create_app 여러 번 호출/리로더/워커에서 중복 start 방지)
_SCHED = None

def cleanup_old_uploads(app):
    """
    임시 업로드 폴더 정리 (30분마다)
    - Flask app을 인자로 받아 app.logger 사용 (current_app 의존 제거)
    """
    tmpdir_root = os.path.join(os.path.expanduser("~"), "AppData", "Local", "Temp", "eink_uploads")
    now = time.time()
    if not os.path.isdir(tmpdir_root):
        return

    for d in os.listdir(tmpdir_root):
        full = os.path.join(tmpdir_root, d)
        try:
            if os.path.isdir(full):
                mtime = os.path.getmtime(full)
                if now - mtime > 3600:  # 1시간 지난 폴더
                    shutil.rmtree(full, ignore_errors=True)
                    app.logger.info(f"[CLEANUP] Auto-deleted old temp dir {full}")
        except Exception as e:
            app.logger.warning(f"[CLEANUP] Failed {full}: {e}")

def init_scheduler(app):
    """
    ✅ create_app()에서 init_scheduler(app) 1회 호출
    - cleanup job
    - posting scheduler tick job
    """
    global _SCHED
    if _SCHED is not None:
        return _SCHED

    scheduler = BackgroundScheduler(daemon=True, timezone="Asia/Seoul")

    # ---------------------------------------------------------
    # 1) Cleanup job
    # ---------------------------------------------------------
    def _job_cleanup():
        # cleanup은 DB 안 쓰지만 logger 안전하게
        cleanup_old_uploads(app)

    scheduler.add_job(
        _job_cleanup,
        trigger=IntervalTrigger(minutes=30),
        id="cleanup_old_uploads",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=60,
    )

    # ---------------------------------------------------------
    # 2) ✅ Posting queue tick job (wait -> active / active -> expired)
    # ---------------------------------------------------------
    from .service.posing_scheduler import PostingSchedulerService

    def _job_posting_tick():
        # APScheduler는 요청 컨텍스트가 없으니 app_context 필수
        with app.app_context():
            PostingSchedulerService.tick_all()

    scheduler.add_job(
        _job_posting_tick,
        trigger=IntervalTrigger(seconds=2),   # 필요하면 1~5로 조정
        id="eink_posting_tick",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
        misfire_grace_time=10,
    )

    scheduler.start()
    _SCHED = scheduler
    return scheduler
