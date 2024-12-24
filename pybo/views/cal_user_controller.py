from datetime import datetime
from flask import Blueprint, request, jsonify
from pybo import db
from ..models import CalendarSchedule, UserAuthorization

bp = Blueprint('uauth', __name__, url_prefix='/uauth')


@bp.route('/register', methods=['GET', 'POST'])
def register():
    # 요청에서 JSON 데이터 가져오기
    data = request.json
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400

    # 필수 필드 확인
    required_fields = ['email', 'password']
    for field in required_fields:
        if field not in data:
            return jsonify({'status': 'error', 'message': f'Missing field: {field}'}), 400

    # JSON 데이터에서 값 추출
    user_email = data.get('email')
    user_password = data.get('password')
   

    print('데이터는:', data)

    # 새로운 일정 데이터 생성
    user_authorization = UserAuthorization(
        email = user_email,
        password = user_password,
        create_date=datetime.now(),  # 현재 시간으로 생성 날짜 설정
        modify_date=None  # 초기에는 None으로 설정
    )

    try:
        db.session.add(user_authorization)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Data saved successfully'}), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        return jsonify({'status': 'error', 'message': 'An error occurred while saving data'}), 500
    
@bp.route('/login', methods=['GET', 'POST'])
def login():
    data = request.json
    print(data)
