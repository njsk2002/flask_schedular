import threading
from flask import Flask
from flask_cors import CORS
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import MetaData, text
import config, os
from flask_jwt_extended import JWTManager
from .schedular import init_scheduler

# ✅ 데이터베이스 설정
naming_convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
db = SQLAlchemy(metadata=MetaData(naming_convention=naming_convention))
migrate = Migrate()

def create_app():
    app = Flask(__name__)
    app.config.from_object(config)
    CORS(app)

    # ✅ 파일 업로드 폴더 설정
    UPLOAD_FILE_FOLDER = "C:/DavidProject/flask_project/uploads_files"
    app.config['UPLOAD_FILE_FOLDER'] = UPLOAD_FILE_FOLDER
    if not os.path.exists(UPLOAD_FILE_FOLDER):
        os.makedirs(UPLOAD_FILE_FOLDER, exist_ok=True)

    UPLOAD_BMP_FOLDER = "C:/DavidProject/flask_project/bmp_files"
    app.config['UPLOAD_BMP_FOLDER'] = UPLOAD_BMP_FOLDER
    if not os.path.exists(UPLOAD_BMP_FOLDER):
        os.makedirs(UPLOAD_BMP_FOLDER, exist_ok=True)

    # ✅ JWT 초기화
    jwt = JWTManager(app)

    # ✅ ORM 초기화
    db.init_app(app)

    with app.app_context():
        if db.engine.name == "sqlite":
            with db.engine.connect() as connection:
                connection.execute(text("PRAGMA foreign_keys=ON"))

    # ✅ 마이그레이션 설정
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith("sqlite"):
        migrate.init_app(app, db, render_as_batch=True)
    else:
        migrate.init_app(app, db)

    # ✅ 블루프린트 등록
    from .views import (
        cal_user_controller, main_views, question_views, answer_views, auth_views,
        comment_views, vote_views, co2_controller, cal_schedular_controller,
        openai_controller, ytube_voice_controller, naver_api_controller, 
        e_namecard_controller, e_device_controller, e_bulletin_controller, esp32_controller)


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

    # ✅ 필터 설정
    from .filter import format_datetime
    app.jinja_env.filters['datetime'] = format_datetime

    # ✅ ❗ import를 여기에서 실행하여 순환 참조 방지
    from .views.e_namecard_controller import cleanup_expired_qr_codes
    import threading
    cleanup_thread = threading.Thread(target=cleanup_expired_qr_codes, args=(app,), daemon=True)  # ✅ app 전달
    cleanup_thread.start()


    # APScheduler 초기화
    init_scheduler()
    app.logger.info("[SCHEDULER] Cleanup job initialized")

    return app
