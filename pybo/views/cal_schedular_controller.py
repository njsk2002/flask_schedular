from datetime import datetime
from flask import Blueprint, request, jsonify
from pybo import db
from ..models import CalendarSchedule, UserAuthorization
from flask_jwt_extended import (
    jwt_required, get_jwt_identity
)

bp = Blueprint('schedule', __name__, url_prefix='/schedule')


@bp.route('/calendar_data', methods=['GET', 'POST'])
@jwt_required(optional=True)
def calendar_data():
    identity = get_jwt_identity() #email
    if not identity:
        return jsonify({'status': 'error', 'message': 'Invalid or missing access token'}), 401

    # 요청에서 JSON 데이터 가져오기
    data = request.json

    print(data)
    if not data:
        return jsonify({'status': 'error', 'message': 'No data provided'}), 400

    # 필수 필드 확인
    required_fields = ['content', 'date', 'startTime', 'endTime']
    for field in required_fields:
        if field not in data:
            return jsonify({'status': 'error', 'message': f'Missing field: {field}'}), 400

    # JSON 데이터에서 값 추출
    cal_content = data.get('content')
    cal_date = data.get('date')
    start_time = data.get('startTime')
    end_time = data.get('endTime')

    print('데이터는:', data)

      # 사용자 확인
    user = UserAuthorization.query.filter_by(email=identity).first()
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404
    
    print('데이터는:', data, user.id)
    # 새로운 일정 데이터 생성
    calendar_schedular = CalendarSchedule(
        user_id = user.id,
        content=cal_content,
        start_time=start_time,
        end_time=end_time,
        cal_date=cal_date,
        create_date=datetime.now(),  # 현재 시간으로 생성 날짜 설정
        modify_date=None  # 초기에는 None으로 설정
    )

    try:
        db.session.add(calendar_schedular)
        db.session.commit()
        
        # 방금 추가된 데이터를 가져오기
        cal_data = CalendarSchedule.query.filter_by(user_id=user.id).order_by(CalendarSchedule.id.desc()).first()
        
        if not cal_data:
            return jsonify({
                'status': 'error',
                'message': 'No data found for the user'
            }), 404
        
        # 성공 응답 반환
        return jsonify({
            'status': 'success', 
            'message': 'Data saved successfully',
            'id': cal_data.id,
            'userId': cal_data.user_id,
            'content': cal_data.content,
            'startTime': cal_data.start_time,
            'endTime': cal_data.end_time,
            'calDate': cal_data.cal_date
        }), 201

    except Exception as e:
        # 에러 발생 시 처리
        db.session.rollback()
        print(f"Error: {e}")
        return jsonify({
            'status': 'error', 
            'message': 'An error occurred while saving data'
        }), 500
    
