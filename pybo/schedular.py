import os, time, shutil
from apscheduler.schedulers.background import BackgroundScheduler
from flask import current_app

def cleanup_old_uploads():
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
                    shutil.rmtree(full)
                    current_app.logger.info(f"[CLEANUP] Auto-deleted old temp dir {full}")
        except Exception as e:
            current_app.logger.warning(f"[CLEANUP] Failed {full}: {e}")

def init_scheduler():
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(cleanup_old_uploads, "interval", minutes=30)
    scheduler.start()
    return scheduler
