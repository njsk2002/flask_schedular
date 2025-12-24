from apscheduler.schedulers.background import BackgroundScheduler
from ..service.posing_scheduler import PostingSchedulerService

def start_posting_scheduler(app):
    scheduler = BackgroundScheduler(timezone="Asia/Seoul")

    def _job():
        with app.app_context():
            PostingSchedulerService.tick_all()

    scheduler.add_job(
        _job,
        trigger="interval",
        seconds=2,          # 1~5초 권장(ESP32 polling 주기와 맞추기)
        id="eink_posting_tick",
        replace_existing=True,
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    return scheduler
