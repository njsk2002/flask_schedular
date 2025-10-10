# import os

# BASE_DIR = os.path.dirname(__file__)

# SQLALCHEMY_DATABASE_URI = 'sqlite:///{}'.format(os.path.join(BASE_DIR, 'pybo.db'))
# SQLALCHEMY_TRACK_MODIFICATIONS = False

# SECRET_KEY = "dev"

# # JWT 설정
# JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default-secret-key")  # 환경 변수에서 로드, 기본값 설정
# JWT_ACCESS_TOKEN_EXPIRES = 3600  # Access Token 만료 시간 (1시간, 초 단위)
# JWT_REFRESH_TOKEN_EXPIRES = 86400  # Refresh Token 만료 시간 (1일, 초 단위)


import os
import configparser
from urllib.parse import quote_plus

# 현재 디렉토리 기준으로 settingvalue.ini 로드
BASE_DIR = os.path.dirname(__file__)
config_path = os.path.join(BASE_DIR, 'settingvalue.ini')

cfg = configparser.ConfigParser()
cfg.read(config_path)

PDF_DPI = 200
POPPLER_PATH = os.getenv("POPPLER_PATH")  # httpd.conf SetEnv 또는 시스템 PATH 사용

# -------------------- 기본 설정 --------------------
DEBUG = cfg.getboolean('DEFAULT', 'DEBUG', fallback=True)
# 우선 환경 변수에서 SECRET_KEY를 읽고, 없으면 [SECURITY] 섹션의 SECRET_KEY를 사용
SECRET_KEY = os.getenv('SECRET_KEY', cfg.get('SECURITY', 'SECRET_KEY', fallback='dev'))

# -------------------- DATABASE 설정 --------------------
# ; [DATABASE]
# ; DB_USER = root
# ; DB_PASSWORD = icetech0701
# ; DB_HOST = localhost
# ; DB_PORT = 3307
# ; DB_NAME = jntserver

DB_USER = os.getenv('DB_USER', cfg.get('DATABASE', 'DB_USER', fallback='icense'))
RAW_PWD = os.getenv('DB_PASSWORD', cfg.get('DATABASE', 'DB_PASSWORD', fallback='Icetech0701@'))
DB_PASSWORD = quote_plus(RAW_PWD)  # ★★★ 비밀번호 URL 인코딩 필수 ★★★

DB_HOST = os.getenv('DB_HOST', cfg.get('DATABASE', 'DB_HOST', fallback='127.0.0.1')).strip()
DB_PORT = os.getenv('DB_PORT', cfg.get('DATABASE', 'DB_PORT', fallback='3307')).strip()
DB_NAME = os.getenv('DB_NAME', cfg.get('DATABASE', 'DB_NAME', fallback='icense')).strip()

SQLALCHEMY_DATABASE_URI = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    f"?charset=utf8mb4"
)
SQLALCHEMY_TRACK_MODIFICATIONS = False

# -------------------- 백업 디렉토리 설정 --------------------
LOCAL_BACKUP_DIR = os.getenv('LOCAL_BACKUP_DIR', cfg.get('BACKUP', 'LOCAL_BACKUP_DIR', fallback='D:/mysql_backups/'))
CLIENT_BACKUP_DIR = os.getenv('CLIENT_BACKUP_DIR', cfg.get('BACKUP', 'CLIENT_BACKUP_DIR', fallback='\\\\CLIENT-PC\\BackupD'))


# -------------------- JWT 설정 --------------------
JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', cfg.get('JWT', 'JWT_SECRET_KEY', fallback='default-secret-key'))
JWT_ACCESS_TOKEN_EXPIRES = int(cfg.get('JWT', 'JWT_ACCESS_TOKEN_EXPIRES', fallback=3600))
JWT_REFRESH_TOKEN_EXPIRES = int(cfg.get('JWT', 'JWT_REFRESH_TOKEN_EXPIRES', fallback=86400))