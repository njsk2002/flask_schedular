from flask import Flask

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
# from flaskext.markdown import Markdown

import config
# from .views import question_views

# Import the StockVO module
from .vo.stock_code_vo import StockInfoVO

from flask_jwt_extended import JWTManager



# =========== SQLight에만 해당 다른 DB 상관없음 ===============================
from sqlalchemy import MetaData, text

naming_convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(column_0_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}
db = SQLAlchemy(metadata=MetaData(naming_convention=naming_convention))
migrate = Migrate()

# =========== SQLight에만 해당 다른 DB 상관없음 ===============================

# db = SQLAlchemy()
# migrate = Migrate()


def create_app():
    app = Flask(__name__)
    #app.config['DEBUG'] = True
    app.config.from_object(config)

    # Initialize JWT
    jwt = JWTManager(app)

    # @app.route('/')
    # def hello_pybo():
    #     return 'HELLO PYBO!'

    #ORM
    db.init_app(app)

    with app.app_context():
        if db.engine.name == "sqlite":
            with db.engine.connect() as connection:
                connection.execute(text("PRAGMA foreign_keys=ON"))

    # =========== SQLight에만 해당 다른 DB 상관없음 ===============================
    if app.config['SQLALCHEMY_DATABASE_URI'].startswith("sqlite"):
        migrate.init_app(app, db, render_as_batch=True)
    else:
        migrate.init_app(app, db)
    # =========== SQLight에만 해당 다른 DB 상관없음 ===============================

    #migrate.init_app(app, db)   
    from . import models

    #블루프린트
    from .views import cal_user_controller,main_views,question_views, answer_views, auth_views,comment_views,vote_views,co2_controller,cal_schedular_controller,openai_controller,ytube_voice_controller
    
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




    # 필터
    from .filter import format_datetime
    app.jinja_env.filters['datetime'] = format_datetime

    # 마크다운 (글자 정렬 및 ul처러 표시)
    # Markdown(app, extensions=['nl2br','fenced_code'])
    return app