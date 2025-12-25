import sys
import os

# 프로젝트 디렉토리와 pybo 디렉토리를 sys.path에 추가
sys.path.insert(0, 'C:/DavidProject/flask_project/flask_scheduler')
sys.path.insert(0, 'C:/DavidProject/flask_project/flask_scheduler/pybo')

from pybo import create_app
application = create_app()

#from pybo import app as application
