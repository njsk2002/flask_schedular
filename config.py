import os

BASE_DIR = os.path.dirname(__file__)

SQLALCHEMY_DATABASE_URI = 'sqlite:///{}'.format(os.path.join(BASE_DIR, 'pybo.db'))
SQLALCHEMY_TRACK_MODIFICATIONS = False

SECRET_KEY = "dev"

# JWT 설정
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "default-secret-key")  # 환경 변수에서 로드, 기본값 설정
JWT_ACCESS_TOKEN_EXPIRES = 3600  # Access Token 만료 시간 (1시간, 초 단위)
JWT_REFRESH_TOKEN_EXPIRES = 86400  # Refresh Token 만료 시간 (1일, 초 단위)


PDF_DPI = 200
POPPLER_PATH = os.getenv("POPPLER_PATH")  # httpd.conf SetEnv 또는 시스템 PATH 사용

