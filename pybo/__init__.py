# __init__.py

import sys
import os
import threading
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, text
from flask_jwt_extended import JWTManager
import config

# 외부 스케줄러 초기화 함수
from .schedular import init_scheduler

# ─────────────────────────────────────────────────────────────
# DB 메타데이터 네이밍 컨벤션
#  - Alembic autogenerate 시 제약/인덱스 이름을 일관되게 생성
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

# ─────────────────────────────────────────────────────────────
# 스케줄러/백그라운드 작업 가드 유틸
#  - 마이그레이션/CLI 실행 시, 또는 리로더 자식 프로세스에서는
#    스케줄러/청소 스레드가 절대 켜지지 않도록 차단
#  - 환경변수 FLASK_SKIP_SCHEDULER=1 로도 강제 비활성 가능
# ─────────────────────────────────────────────────────────────
def _running_migration_cmd() -> bool:
    """flask db migrate/upgrade/... 등 마이그레이션/CLI 실행 여부 감지"""
    mig_words = {"db", "migrate", "upgrade", "downgrade", "stamp", "current", "heads", "show"}
    argv = {a.lower() for a in sys.argv}
    return len(mig_words & argv) > 0

def _in_reloader_child() -> bool:
    """Werkzeug 리로더의 자식 프로세스 여부 감지(중복 초기화 방지)"""
    # 리로더 활성 시 부모는 WERKZEUG_RUN_MAIN 미정의, 자식은 "true"
    return os.environ.get("WERKZEUG_RUN_MAIN") != "true"

def _should_skip_schedulers() -> bool:
    """스케줄러/청소 스레드 실행 여부 최종 판단"""
    return (
        os.environ.get("FLASK_SKIP_SCHEDULER") == "1"  # 환경변수로 강제 비활성
        or _running_migration_cmd()                    # 마이그레이션/CLI 중
        or _in_reloader_child()                        # 리로더 자식 프로세스
    )

# ─────────────────────────────────────────────────────────────
# 앱 팩토리
# ─────────────────────────────────────────────────────────────
def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    CORS(app)

    # ─────────────────────────────────────────────────────────
    # 업로드 폴더 준비
    #  - 존재하지 않으면 생성
    # ─────────────────────────────────────────────────────────
    upload_root = "C:/DavidProject/flask_project"
    upload_file_folder = os.path.join(upload_root, "uploads_files")
    upload_bmp_folder = os.path.join(upload_root, "bmp_files")

    app.config['UPLOAD_FILE_FOLDER'] = upload_file_folder
    app.config['UPLOAD_BMP_FOLDER'] = upload_bmp_folder
    app.config["SIGN_BASE_DIR"] = r"C:/DavidProject/flask_project/flask_schedular/uploads"

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
    # MySQL 버전 로깅(연결 확인)
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
    # 모델 모듈을 명시적으로 import
    #  - Alembic autogenerate가 모든 모델을 인식하도록 보장
    #  - circular import를 피하기 위해 여기서 import
    # ─────────────────────────────────────────────────────────
    from . import models  # 중요: 누락 시 autogenerate가 빈 리비전을 만들 수 있음

    # ─────────────────────────────────────────────────────────
    # 마이그레이션 초기화
    #  - SQLite를 병행 사용한다면 render_as_batch=True 선택 가능(주석 참고)
    # ─────────────────────────────────────────────────────────
    # if app.config.get('SQLALCHEMY_DATABASE_URI', '').startswith("sqlite"):
    #     migrate.init_app(app, db, render_as_batch=True)
    # else:
    migrate.init_app(app, db)

    # ─────────────────────────────────────────────────────────
    # 블루프린트 등록
    # ─────────────────────────────────────────────────────────
    from .views import (
        cal_user_controller, main_views, question_views, answer_views, auth_views,
        comment_views, vote_views, co2_controller, cal_schedular_controller,
        openai_controller, ytube_voice_controller, naver_api_controller,
        e_namecard_controller, e_device_controller, e_bulletin_controller,
        esp32_controller, e_worksheet_controller
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

    # ─────────────────────────────────────────────────────────
    # Jinja2 필터 등록
    # ─────────────────────────────────────────────────────────
    from .filter import format_datetime
    app.jinja_env.filters['datetime'] = format_datetime

    # ─────────────────────────────────────────────────────────
    # 백그라운드 작업(청소 스레드/스케줄러) - 강력 가드 적용
    #  - 마이그레이션/CLI/리로더 자식/환경변수 상황에서는 실행하지 않음
    # ─────────────────────────────────────────────────────────
    if not _should_skip_schedulers():
        # 청소 스레드 시작: app_context 필요 시 인자 전달
        from .views.e_namecard_controller import cleanup_expired_qr_codes

        cleanup_thread = threading.Thread(
            target=cleanup_expired_qr_codes,
            args=(app,),
            daemon=True
        )
        cleanup_thread.start()

        # APScheduler 초기화
        init_scheduler()
        app.logger.info("[SCHEDULER] Cleanup job initialized")
    else:
        app.logger.info("[SCHEDULER] Skipped (migration/CLI/reloader/env)")

    return app
