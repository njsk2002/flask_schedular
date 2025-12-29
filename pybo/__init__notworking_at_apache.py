# pybo/__init__.py
import sys
import os
import threading
import time
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, text
from flask_jwt_extended import JWTManager
from flask_login import LoginManager
import config

from .scheduler import init_scheduler  # ✅ 스케줄러

# ─────────────────────────────────────────────────────────────
# DB 메타데이터 네이밍 컨벤션
# ─────────────────────────────────────────────────────────────
naming_convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

db = SQLAlchemy(metadata=MetaData(naming_convention=naming_convention))
migrate = Migrate()
login_manager = LoginManager()

# ─────────────────────────────────────────────────────────────
# 스케줄러 가드
# ─────────────────────────────────────────────────────────────
def _running_migration_cmd() -> bool:
    mig_words = {"db", "migrate", "upgrade", "downgrade", "stamp", "current", "heads", "show"}
    argv = {a.lower() for a in sys.argv}
    return len(mig_words & argv) > 0

def _should_skip_schedulers(app) -> bool:
    # 1) 강제 스킵
    if os.environ.get("FLASK_SKIP_SCHEDULER") == "1":
        return True

    # 2) 마이그레이션/CLI 실행 시 스킵
    if _running_migration_cmd():
        return True

    # 3) dev/test에서만 reloader parent 방지
    if (app.debug or app.testing):
        if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
            return True

    return False


def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    CORS(app)

    # ─────────────────────────────────────────────────────────
    # 업로드 폴더
    # ─────────────────────────────────────────────────────────
    upload_root = "C:/DavidProject/flask_project"
    upload_file_folder = os.path.join(upload_root, "uploads_files")
    upload_bmp_folder = os.path.join(upload_root, "bmp_files")

    app.config['UPLOAD_FILE_FOLDER'] = upload_file_folder
    app.config['UPLOAD_BMP_FOLDER'] = upload_bmp_folder
    app.config["SIGN_BASE_DIR"] = r"C:/DavidProject/flask_project/flask_scheduler/uploads"

    os.makedirs(upload_file_folder, exist_ok=True)
    os.makedirs(upload_bmp_folder, exist_ok=True)

    # ─────────────────────────────────────────────────────────
    # JWT
    # ─────────────────────────────────────────────────────────
    JWTManager(app)

    # ─────────────────────────────────────────────────────────
    # ORM 초기화
    # ─────────────────────────────────────────────────────────
    db.init_app(app)

    # ─────────────────────────────────────────────────────────
    # MySQL 버전 로깅
    # ─────────────────────────────────────────────────────────
    with app.app_context():
        try:
            if db.engine.name == "mysql":
                with db.engine.connect() as connection:
                    version = connection.execute(text("SELECT VERSION();")).scalar()
                    app.logger.info(f"✅ MySQL 서버 버전: {version}")
        except Exception as e:
            app.logger.warning("MySQL 서버에 연결할 수 없습니다. 설정을 확인하세요.")
            app.logger.exception(e)

    # ─────────────────────────────────────────────────────────
    # 모델 import
    # ─────────────────────────────────────────────────────────
    from . import models
    from .models import User

    # ─────────────────────────────────────────────────────────
    # Flask-Login
    # ─────────────────────────────────────────────────────────
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "로그인이 필요한 페이지입니다."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id: str):
        try:
            return User.query.get(int(user_id))
        except Exception:
            return None

    # ─────────────────────────────────────────────────────────
    # 마이그레이션
    # ─────────────────────────────────────────────────────────
    migrate.init_app(app, db)

    # ─────────────────────────────────────────────────────────
    # 블루프린트 등록
    # ─────────────────────────────────────────────────────────
    from .views import (
        cal_user_controller, main_views, question_views, answer_views, auth_views,
        comment_views, vote_views, co2_controller, cal_schedular_controller,
        openai_controller, ytube_voice_controller, naver_api_controller,
        e_namecard_controller, e_device_controller, e_bulletin_controller,
        esp32_controller, e_worksheet_controller, e_dashboard_controller, assign_controller
    )

    app.register_blueprint(main_views.bp)
    app.register_blueprint(question_views.bp)
    app.register_blueprint(answer_views.bp)
    app.register_blueprint(auth_views.bp)
    app.register_blueprint(comment_views.bp)
    app.register_blueprint(vote_views.bp)
    app.register_blueprint(co2_controller.bp)
    app.register_blueprint(cal_schedular_controller.bp)
    app.register_blueprint(cal_user_controller.bp)
    app.register_blueprint(openai_controller.bp)
    app.register_blueprint(ytube_voice_controller.bp)
    app.register_blueprint(naver_api_controller.bp)
    app.register_blueprint(e_namecard_controller.bp)
    app.register_blueprint(e_device_controller.bp)
    app.register_blueprint(e_bulletin_controller.bp)
    app.register_blueprint(esp32_controller.bp)
    app.register_blueprint(e_worksheet_controller.bp)
    app.register_blueprint(e_dashboard_controller.bp)
    app.register_blueprint(assign_controller.bp)

    # ─────────────────────────────────────────────────────────
    # Jinja2 필터
    # ─────────────────────────────────────────────────────────
    from .filter import format_datetime
    app.jinja_env.filters['datetime'] = format_datetime

    # ─────────────────────────────────────────────────────────
    # ✅ 스케줄러/백그라운드 작업
    #  - Apache 환경에서도 "시작/실행/예외"가 무조건 로그에 남게 함
    # ─────────────────────────────────────────────────────────
    # 1) 현재 프로세스/환경 로그 (원인 확정용)
    app.logger.info(
        f"[SCHEDDBG] pid={os.getpid()} ppid={os.getppid() if hasattr(os, 'getppid') else -1} "
        f"debug={app.debug} testing={app.testing} "
        f"WERKZEUG_RUN_MAIN={os.environ.get('WERKZEUG_RUN_MAIN')} "
        f"FLASK_SKIP_SCHEDULER={os.environ.get('FLASK_SKIP_SCHEDULER')} "
        f"argv={' '.join(sys.argv)}"
    )

    if _should_skip_schedulers(app):
        app.logger.info("[SCHEDULER] Skipped (migration/CLI/reloader/env)")
        return app

    # 2) cleanup thread도 시작 로그를 남김
    from .views.e_namecard_controller import cleanup_expired_qr_codes

    def _start_cleanup():
        app.logger.info("[CLEANUP] cleanup thread starting")
        try:
            cleanup_expired_qr_codes(app)
        except Exception:
            app.logger.exception("[CLEANUP] cleanup thread crashed")

    threading.Thread(target=_start_cleanup, daemon=True).start()

    # 3) APScheduler init + 시작 여부 로그
    try:
        sched = init_scheduler(app)
        app.logger.info(f"[SCHEDULER] Scheduler initialized. running={getattr(sched, 'running', None)}")
    except Exception:
        app.logger.exception("[SCHEDULER] Scheduler init failed")

    return app
