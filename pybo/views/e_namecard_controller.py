import os, functools
from uuid import uuid4
from datetime import datetime
from flask import Blueprint, url_for, render_template, flash, request, session, g , jsonify, current_app, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect, secure_filename
from sqlalchemy.exc import SQLAlchemyError

from pybo import db
from pybo.forms import UserCreateForm, UserLoginForm
from pybo.models import User, NameCard, FileUpload, ShareCard
from ..views.auth_views import login_required
from ..service.image_manageent import ImageManagement

bp =Blueprint('enamecard',__name__,url_prefix='/enamecard')

# 업로드된 파일을 정적 경로로 서빙
UPLOAD_FOLDER = "C:/DavidProject/flask_project/flask_schedular/uploads"
bp.upload_folder = UPLOAD_FOLDER

@bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(bp.upload_folder, filename)

# #=== 로그인 되었는지 먼저 확인하는 함수 @login_required 어노테이션으로 사용 가능 ====
# def login_required(view):
#     @functools.wraps(view)
#     def wrapped_view(**kwargs):
#         if g.user is None:
#             return redirect(url_for('auth.login'))
#         return view(**kwargs)
    
#     return wrapped_view

# #=== 로그인 되었을때 session data를 g.user 데이터로 이동/ 다른 class에서 g.user로 login 유무 확인가능 ====
# @bp.before_app_request
# def load_logged_in_user():
#     user_id = session.get('user_id')
#     if user_id is None:
#         g.user = None
#     else:
#         g.user = db.session.query(User).filter_by(userid=user_id).first()
#         print(f"조회된 사용자: {g.user}")  # user 값이 None인지 확인
        
#         if g.user is None:
#             session.pop('user_id', None)  # 세션에 유효하지 않은 ID 제거

########## E-namecard 등록 ###################
@bp.route('/gen_namecard', methods=['POST'])
@login_required
def gen_namecard():
    user = g.user
    data = request.json

    if not user:
            return jsonify({"error": "로그인이 필요합니다."}), 401

    data = request.json
    print("E-NAMECARD 요청 데이터:", data)  # 디버깅 로그

    # 선택된 정보만 저장
    namecard = NameCard(
        user_id=user.no, # 🚀 user_id 대신 user.no 사용 (User 모델의 기본키 확인 필요)
        selected_photo=data.get("selected_photo"),
        department=data.get("department") if data.get("department_check") else None,
        position=data.get("position") if data.get("position_check") else None,
        username=data.get("username") if data.get("username_check") else None,
        phone=data.get("phone") if data.get("phone_check") else None,
        email=data.get("email") if data.get("email_check") else None,
        company=data.get("company") if data.get("company_check") else None,
        com_address=data.get("com_address") if data.get("com_address_check") else None,
        tel_rep=data.get("tel_rep") if data.get("tel_rep_check") else None,
        tel_dir=data.get("tel_dir") if data.get("tel_dir_check") else None,
        fax=data.get("fax") if data.get("fax_check") else None,
        homepage=data.get("homepage") if data.get("homepage_check") else None
    )

    db.session.add(namecard)
    db.session.commit()

    namecards = NameCard.query.filter_by(user_id=user.no).all()

    # if namecards is not None:


    return jsonify({"message": "명함이 저장되었습니다.", "namecard": namecard.to_dict()}), 201

@bp.route('/get_namecards', methods=['GET'])
@login_required
def get_namecards():
    user = g.user
    namecards = NameCard.query.filter_by(user_id=user.no).all()
    
    data = [card.to_dict() for card in namecards]  # JSON 객체 대신 리스트 전달

    return render_template('namecard/e_namecard.html', namecards=data)


@bp.route('/gen_sharecards', methods=['GET'])
@login_required
def gen_sharecards():
    user = g.user
    namecards = NameCard.query.filter_by(user_id=user.no).all()
    fileuploads = FileUpload.query.filter_by(user_id=user.no).all()
    
    return render_template(
        'namecard/e_gen_share.html', 
        namecards=[card.to_dict() for card in namecards],
        fileuploads=[file.to_dict() for file in fileuploads]
    )

@bp.route('/save_sharecards', methods=['POST'])
@login_required
def save_sharecard():
    user = g.user
    try:
        # 클라이언트에서 데이터 받기
        data = request.json

        print("데이터는? ", data)

        title = data.get("title")
        introduce = data.get("introduce")
        content = data.get("content")
        namecard_id = data.get("selected_card")
        selected_files = data.get("selected_files", [])  # 체크된 파일 목록

        # 필수 필드 확인
        if not title or not content or not namecard_id:
            return jsonify({"success": False, "message": "필수 필드가 누락되었습니다."}), 400

        # 파일 저장 처리 (최대 5개)
        file_fields = ["s_file1", "s_file2", "s_file3", "s_file4", "s_file5"]
        file_data = {file_fields[i]: selected_files[i] for i in range(min(len(selected_files), 5))}

        # ShareCard 객체 생성 및 DB 저장
        new_sharecard = ShareCard(
            user_id= user.no,
            namecard_id=namecard_id,
            fileupload_id='1',  # 파일 업로드 관련 추가 구현 필요
            title=title,
            introduce=introduce,
            content=content,
            s_ncard=str(namecard_id),
            **file_data,
            create_date=datetime.utcnow(),
            modify_date=datetime.utcnow()
        )

        db.session.add(new_sharecard)
        db.session.commit()

        return jsonify({"success": True, "message": "공유 명함이 성공적으로 저장되었습니다."})

    except SQLAlchemyError as e:
        db.session.rollback()
        return jsonify({"success": False, "message": f"DB 오류 발생: {str(e)}"}), 500
    except Exception as e:
        return jsonify({"success": False, "message": f"서버 오류 발생: {str(e)}"}), 500

@bp.route('/view_sharecards', methods=['GET'])
@login_required
def view_sharecards():
    try:
        # 현재 로그인한 사용자 정보 가져오기
        user = g.user

        # 현재 사용자의 공유 명함 데이터 조회
        share_data = ShareCard.query.filter_by(user_id=user.no).all()

        # 공유 명함 리스트 변환
        sharecards = []
        for share in share_data:
            # 명함 데이터 조회
            namecard = NameCard.query.filter_by(id=share.namecard_id).first()
            
            # 공유된 파일 리스트 생성
            shared_files = [share.s_file1, share.s_file2, share.s_file3, share.s_file4, share.s_file5]
            shared_files = [f for f in shared_files if f]  # None 값 제거

            sharecards.append({
                "no": share.no,
                "namecard_id" : share.namecard_id,
                "title": share.title,
                "introduce": share.introduce,
                "content": share.content,
                "namecard": {
                    "username": namecard.username if namecard else "명함 없음",
                    "company": namecard.company if namecard else "회사 정보 없음",
                    "position": namecard.position if namecard else "직급 정보 없음",
                    "email": namecard.email if namecard else "이메일 없음",
                    "phone": namecard.phone if namecard else "전화번호 없음",
                    "tel_rep": namecard.tel_rep if namecard else "공용전화 없음",
                    "tel_dir": namecard.tel_dir if namecard else "직통전화 없음",
                    "fax": namecard.fax if namecard else "팩스 없음",
                    "com_address": namecard.com_address if namecard else "팩스 없음",
                    "homepage": namecard.homepage if namecard else "팩스 없음",
                    "selected_photo": namecard.selected_photo if namecard else "/static/default_profile.jpg"
                },
                "shared_files": shared_files,
                "created_at": share.create_date.strftime('%Y-%m-%d %H:%M:%S') if share.create_date else None
            })

            print(sharecards)

        # 공유 명함 데이터를 e_sharecard.html로 전달
        return render_template('namecard/e_sharecard.html', namecards=sharecards)

    except Exception as e:
        return render_template('namecard/e_sharecard.html', error_message=f"서버 오류 발생: {str(e)}")

@bp.route('/gen_welcome', methods=['POST'])
@login_required
def gen_welcome():
    data = request.json
    share_no = data.get("share_no")
    namecard_id = data.get("share_no")

    user = g.user



    return jsonify({"message": "선택한 명함이 저장되었습니다."})

@bp.route('/save_namecard', methods=['POST'])
@login_required
def save_namecard():
    data = request.json
    selected_card_id = data.get("namecard_id")

    if not selected_card_id:
        return jsonify({"message": "명함이 선택되지 않았습니다."}), 400

    user = g.user
    selected_card = NameCard.query.filter_by(id=selected_card_id, user_id=user.no).first()

    if not selected_card:
        return jsonify({"message": "해당 명함을 찾을 수 없습니다."}), 404

    # 사용자 기본 명함으로 설정 (예: is_selected 필드 업데이트)
    selected_card.is_selected = True
    db.session.commit()

    return jsonify({"message": "선택한 명함이 저장되었습니다."})


