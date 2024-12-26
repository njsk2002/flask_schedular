from datetime import datetime, timedelta
from flask import Flask, Blueprint, request, jsonify
from pybo import db
from ..models import UserAuthorization, RefreshToken

from flask_jwt_extended import (JWTManager, create_access_token, create_refresh_token,jwt_required, get_jwt_identity, get_jwt, decode_token)
from flask_bcrypt import Bcrypt
from flask_cors import CORS



#비밀번호 해시화
from werkzeug.security import generate_password_hash, check_password_hash
import base64

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
    
    # 이메일 중복 여부 확인
    if UserAuthorization.query.filter_by(email = user_email).first():
        print('이미 등록된 이메일입니다')
        return jsonify({'status' : 'error', 'message' : '이미 등록되어 있는 이메일입니다.'}), 400
    
    hashed_password = generate_password_hash(user_password)
   

   

    #토큰 생성
    access_token = create_access_token(identity=user_email)
    refresh_token = create_refresh_token(identity=user_email)

    # 새로운 일정 데이터 생성
    user = UserAuthorization(
        email = user_email,
        password = hashed_password,
        create_date=datetime.now(),  # 현재 시간으로 생성 날짜 설정
        modify_date=None  # 초기에는 None으로 설정
    )
    try:
        db.session.add(user)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")

    token_entry = RefreshToken(
        user_id = user.id,
        token = refresh_token,
        expires_at=datetime.utcnow() + timedelta(days=30)
    )

    try:
        db.session.add(token_entry)
        db.session.commit()
        return jsonify({
            'status': 'success', 
            'message': 'Data saved successfully',
            'accessToken' : access_token,
            'refreshToken' : refresh_token
            }), 201
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
        return jsonify({
            'status': 'error', 
            'message': 'An error occurred while saving data'
            }), 500
    
    
@bp.route('/login', methods=['GET', 'POST'])
def login():
    #Authorization 헤더에서 값 추출
    auth_header = request.headers.get('authorization')
    if not auth_header or not auth_header.startswith('Basic '):
        return jsonify({'status': 'error', 'message': 'Authorization header is missing or invalid'}), 401
    
    #Basic 인증값 디코딩
    try:
        encoded_credentials = auth_header.split(' ')[1]
        decoded_credentials = base64.b64decode(encoded_credentials).decode('utf-8')
        email, password = decoded_credentials.split(':')
    except Exception as e:
        print(f"Error decoding credentials: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid authorization credentials'}), 400
    

    print(email, password)
    
    #이메일로 사용자 확인
    user = UserAuthorization.query.filter_by(email=email).first()
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404

    # 비밀번호 검증
    if not check_password_hash(user.password, password):
        return jsonify({'status': 'error', 'message': 'Invalid password'}), 401 
    
    # Access Token 및 Refresh Token 생성
    access_token = create_access_token(identity=email)
    refresh_token = create_refresh_token(identity=email)

    # Refresh Token을 DB에 저장
    try:
        token_entry = RefreshToken.query.filter_by(user_id=user.id).first()
        if token_entry:
            # 기존 토큰 업데이트
            token_entry.token = refresh_token
            token_entry.expires_at = datetime.utcnow() + timedelta(days=30)
        else:
            # 새로운 토큰 저장
            token_entry = RefreshToken(
                user_id=user.id,
                token=refresh_token,
                expires_at=datetime.utcnow() + timedelta(days=30)
            )
            db.session.add(token_entry)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error saving refresh token: {e}")
        return jsonify({'status': 'error', 'message': 'An error occurred while saving refresh token'}), 500

    # 성공 응답 반환
    return jsonify({
        'status': 'success',
        'accessToken': access_token,
        'refreshToken': refresh_token
    }), 200    

# ######### Refresh Token -- 언제 사용할지 미정(로그인시 및 정보 요청 시 지속적으로 확인) -- ##############################3
@bp.route('/refresh', methods=['POST'])
def refresh_token():
    token = request.json.get('refresh_token')
    if not token:
            return jsonify({'status': 'error', 'message': 'Missing refresh token'}), 400

    token_entry = RefreshToken.query.filter_by(token=token).first()

    if not token_entry:
       return jsonify({'status': 'error', 'message': 'Invalid refresh token'}), 401

    if token_entry.expires_at < datetime.utcnow():
        db.session.delete(token_entry)
        db.session.commit()
        return jsonify({'status': 'error', 'message': 'Refresh token expired'}), 401

    # 갱신 로직 실행 # Create new access token
    new_access_token = create_access_token(identity=token_entry.user.email)
    
    return jsonify({'status': 'success', 'accessToken': new_access_token}), 200


# 요청 처리 전 검증
@bp.before_app_request
def validate_token():
    # 특정 엔드포인트에서 검증 건너뛰기
    if request.endpoint == 'cal_user.refresh_access_token':
        return  # Refresh 토큰 경로는 스킵

    # Authorization 헤더 확인
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'status': 'error', 'message': 'Authorization header missing or invalid'}), 401

    # 토큰 추출
    access_token = auth_header.split(' ')[1]
    try:
        # 토큰 디코딩
        decoded_token = decode_token(access_token)
        identity = decoded_token.get('sub')  # 'sub'은 기본적으로 사용자 ID를 의미

        if not identity:
            raise ValueError('Invalid token')

        # 데이터베이스에서 사용자 확인
        user = UserAuthorization.query.filter_by(email=identity).first()
        if not user:
            raise ValueError('User not found')

    except Exception as e:
        print(f"Access token validation error: {e}")
        return jsonify({'status': 'error', 'message': 'Invalid access token'}), 401