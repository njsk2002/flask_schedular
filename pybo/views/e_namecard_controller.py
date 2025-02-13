import os, functools, time, base64,vobject, urllib, io
from uuid import uuid4
from datetime import datetime, timedelta
from flask import Blueprint, url_for, render_template, flash, request, session, g , jsonify, current_app, send_from_directory,Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect, secure_filename
from sqlalchemy.exc import SQLAlchemyError
from PIL import Image  # ✅ WEBP 변환을 위해 추가
from pybo import db
from pybo.forms import UserCreateForm, UserLoginForm
from pybo.models import User, NameCard, FileUpload, ShareCard, QRCode, WelcomeData
from ..views.auth_views import login_required
from ..service.image_manageent import ImageManagement
from ..service.bmp_trans import BMPTrans

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
    namecard_id = data.get("namecard_id")

    user = g.user

    # ✅ 업로드 폴더 설정
    output_folder = current_app.config.get('UPLOAD_BMP_FOLDER')

    # ✅ QR URL 생성
    unique_id = str(uuid4())  # 매번 새로운 UUID 생성
    expiration_time = datetime.utcnow() + timedelta(minutes=30)  # 30분 후 만료

    # ✅ QR 정보 DB 저장
    qr_entry = QRCode(
        unique_id=unique_id,
        user_id=user.no,
        namecard_id=namecard_id,
        share_card_id=share_no,
        expires_at=expiration_time
    )
    db.session.add(qr_entry)
    db.session.commit()

    # ✅ QR 코드 URL 생성
    qr_url = f"http://192.168.0.136:5000/qr/{unique_id}"

    print("QR URL: ", qr_url)
    print("upload_folder: ", output_folder)

    # ✅ 명함 정보 가져오기
    e_namecard = NameCard.query.filter_by(id=namecard_id, user_id=user.no).first()
    bmp_name, bmp_path = BMPTrans.generate_bmp_namecard(e_namecard, output_folder, qr_url)

    # ✅ 웰컴페이지 데이터 저장
    welcome_data = WelcomeData(
        user_id=user.no,
        namecard_id=namecard_id,
        share_card_id=share_no,
        bmp_name=bmp_name,
        bmp_path=bmp_path,
        qr_code=qr_url,
        unique_id=unique_id,
        expires_at=expiration_time
    )

    db.session.add(welcome_data)
    db.session.commit()

    # ✅ JSON 응답으로 message & QR URL 반환
    return jsonify({
        "message": "선택한 웰컴페이지가 저장되었습니다.",
        "qr_code": qr_url,
        "unique_id": unique_id
    })

######## 웰컴페이지 접근 ################################33
@bp.route('/welcome_page/<unique_id>', methods=['GET'])
# @login_required
def welcome_page(unique_id):
    # ✅ WelcomeData에서 데이터 조회
    welcome_data = WelcomeData.query.filter_by(unique_id=unique_id).first()
    
    if not welcome_data:
        return "잘못된 요청입니다.", 404
    
     # ✅ namecard 데이터 가져오기
    name_card = NameCard.query.filter_by(id=welcome_data.namecard_id).first()

    # ✅ ShareCard 데이터 가져오기
    share_card = ShareCard.query.filter_by(no=welcome_data.share_card_id).first()

    return render_template(
        'namecard/e_welcome_page.html', 
        welcome_data=welcome_data, 
        namecard = name_card,
        share_card=share_card,
   
    )


# ########## VCF ##################################3
# @bp.route('/generate_vcard')
# def generate_vcard():
#     photo_base64 = encode_photo_to_base64("C:/DavidProject/flask_project/bmp_files/iu/202411111646288523_t.jpg")
#     vcard_data = f"""BEGIN:VCARD
# VERSION:3.0
# FN:아이유
# EMAIL:iu2@icetech.co.kr
# TEL:+1234567890
# NOTE:안녕하세요! 아이유에요! 만나 뵙게 되어 영광입니다. 2025-01-24일 아이스기술 본사
# PHOTO;ENCODING=b;TYPE=JPEG:{photo_base64}
# END:VCARD
# """
#     return Response(vcard_data, mimetype='text/vcard', headers={"Content-Disposition": "attachment;filename=contact.vcf"})


    
# def encode_photo_to_base64(photo_path):
#     with open(photo_path, "rb") as photo_file:
#         encoded_photo = base64.b64encode(photo_file.read()).decode("utf-8")
#     return encoded_photo

# ########## VCF ##################################3


@bp.route('/generate_vcard', methods=['POST'])
def generate_vcard():
    data = request.json
    namecard_id = data.get("namecard_id")
    unique_id = data.get("unique_id")
    welcome_data_no = data.get("welcome_data_no")

    namecard = NameCard.query.filter_by(id=namecard_id).first()
    if not namecard:
        return jsonify({"error": "명함 정보를 찾을 수 없습니다."}), 404

    welcome_data = WelcomeData.query.filter_by(no=welcome_data_no).first()
    if not welcome_data or welcome_data.unique_id != unique_id:
        return jsonify({"error": "잘못된 요청입니다."}), 400

    today_date = datetime.today().strftime('%Y-%m-%d')
    username = namecard.username.replace(" ", "_").strip() if namecard.username else ""
    company = namecard.company.replace(" ", "_").strip() if namecard.company else ""
    email = namecard.email.strip() if namecard.email else ""
    phone = namecard.phone.strip() if namecard.phone else ""
    position = namecard.position.strip() if namecard.position else ""
    com_address = namecard.com_address.strip() if namecard.com_address else ""
    tel_dir = namecard.tel_dir.strip() if namecard.tel_dir else ""
    fax = namecard.fax.strip() if namecard.fax else ""

    # ✅ 파일명을 UTF-8로 변환 후 URL 인코딩
    filename = f"{username}_{company}.vcf"
    encoded_filename = urllib.parse.quote(filename.encode('utf-8'))

    # ✅ 사진 Base64 인코딩
    photo_base64 = ""
    if namecard.selected_photo:
        split_file = namecard.selected_photo.split("uploads/")[1]
        photo_path = os.path.join("C:/DavidProject/flask_project/flask_schedular/uploads/", split_file)
        print("사진 경로:", photo_path)
        photo_base64 = encode_photo_to_base64(photo_path)

    if not photo_base64:
        print("⚠️ 사진 Base64 인코딩 실패!")
        photo_base64 = ""  # 사진이 없을 경우 빈 문자열 처리
    else:
        print("✅ 사진 Base64 인코딩 성공!")

    # ✅ Base64 데이터 75바이트마다 줄바꿈 추가 (vCard 표준에 맞게)
    formatted_photo_base64 = "\n ".join(photo_base64[i:i+75] for i in range(0, len(photo_base64), 75))

    # ✅ vCard 데이터 직접 생성
    vcard_data = f"""BEGIN:VCARD
VERSION:3.0
FN:{username}
EMAIL;TYPE=WORK:{email}
TEL;TYPE=CELL:{phone} 
TITLE:{position}
"""

    # ✅ 회사명과 부서를 ORG 필드에 추가
    if namecard.department:
        vcard_data += f"ORG:{company};{namecard.department}\n"  # 회사 + 부서
    else:
        vcard_data += f"ORG:{company}\n"  # 부서 정보가 없으면 회사명만 추가

    vcard_data += f"""ADR;TYPE=WORK:;;{com_address};;;;
NOTE:안녕하세요! {today_date}에 인사드렸던 {company} {username}입니다.
"""

    # ✅ 추가 전화번호, 팩스 추가 (옵션)
    if tel_dir:
        vcard_data += f"TEL;TYPE=WORK:{tel_dir}\n"  # 직장 전화번호
    if fax:
        vcard_data += f"TEL;TYPE=WORK,FAX:{fax}\n"  # 직장 팩스

    # ✅ 사진 추가 (Base64 직접 삽입)
    if photo_base64:
        vcard_data += f"PHOTO;ENCODING=b;TYPE=JPEG:\n {formatted_photo_base64}\n"

    vcard_data += "END:VCARD\n"

    return Response(
        vcard_data,
        mimetype='text/vcard',
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}"
        }
    )


# ✅ 사진을 Base64로 변환하는 함수
def encode_photo_to_base64(photo_path):
    try:
        with Image.open(photo_path) as img:
            img = img.convert("RGB")  # ✅ RGB 변환 (투명 PNG 대비)
            img = img.resize((300, 300))  # ✅ 300x300 크기 조절
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG")  # ✅ JPEG 포맷으로 저장
            return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except FileNotFoundError:
        print(f"⚠️ 파일을 찾을 수 없음: {photo_path}")
        return None





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


# def cleanup_expired_qr_codes(app):
#     while True:
#         with app.app_context():  # ✅ Flask 애플리케이션 컨텍스트 사용
#             expired_qrs = QRCode.query.filter(QRCode.expires_at < datetime.utcnow()).all()
#             for qr in expired_qrs:
#                 db.session.delete(qr)
#             db.session.commit()
#             print("✅ 만료된 QR 코드 삭제 완료")

#         time.sleep(60)  # 60초마다 실행

def cleanup_expired_qr_codes(app):
    while True:
        with app.app_context():
            try:
                expired_qrs = QRCode.query.filter(QRCode.expires_at < datetime.utcnow()).all()
                for qr in expired_qrs:
                    db.session.delete(qr)
                db.session.commit()
                print("✅ 만료된 QR 코드 삭제 완료")
            except Exception as e:
                db.session.rollback()
                print(f"❌ QR 코드 삭제 중 오류 발생: {e}")

        time.sleep(300)  # 60초마다 실행




