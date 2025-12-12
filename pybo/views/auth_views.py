import os, functools, unicodedata, re
from uuid import uuid4
from datetime import datetime
from flask import Blueprint, url_for, render_template, flash, request, session, g , jsonify, current_app, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect, secure_filename
from flask_login import login_user, logout_user, login_required, current_user
from pybo import db
from pybo.forms import UserCreateForm, UserLoginForm
from pybo.models import User,FileUpload
from ..service.image_manageent import ImageManagement

bp =Blueprint('auth',__name__,url_prefix='/auth')


from flask_wtf.csrf import generate_csrf

@bp.route('/get-csrf-token', methods=['GET'])
def get_csrf_token():
    token = generate_csrf()
    return jsonify({'csrf_token': token})


###########################################################################
###########################  로그인 유무 ####################################
###########################################################################
#=== 로그인 되었는지 먼저 확인하는 함수 @login_required 어노테이션으로 사용 가능 ====
# import functools
# from flask import redirect, url_for, session, g
# from pybo.models import User
# from pybo import db

# def login_required(view):
#     @functools.wraps(view)
#     def wrapped_view(**kwargs):
#         if g.user is None:
#             print("[DEBUG] @login_required: g.user is None, redirecting to login")
#             return redirect(url_for('auth.login'))
#         print(f"[DEBUG] @login_required: g.user is present: {g.user}")
#         return view(**kwargs)
#     return wrapped_view

# @bp.before_app_request
# def load_logged_in_user():
#     user_id = session.get('user_id')
#     if user_id is None:
#         g.user = None
#         print("[DEBUG] load_logged_in_user: No user_id found in session")
#     else:
#         g.user = db.session.query(User).filter_by(userid=user_id).first()
#         print(f"[DEBUG] load_logged_in_user: Retrieved user: {g.user}")
#         if g.user is None:
#             session.pop('user_id', None)
#             print("[DEBUG] load_logged_in_user: Invalid user_id removed from session")

# 🔥 기존 login_required, load_logged_in_user 삭제하고 이걸로 교체

@bp.before_app_request
def load_logged_in_user():
    """
    Flask-Login의 current_user를 g.user에 그대로 매핑.
    기존 코드(g.user)를 최대한 안 깨고 가져가기 위한 브리지.
    """
    if current_user.is_authenticated:
        g.user = current_user
    else:
        g.user = None



###########################################################################
########################### 이미지 및 파일 업로드 ############################
###########################################################################
# 업로드된 파일을 정적 경로로 서빙
UPLOAD_IMAGE_FOLDER = "C:/DavidProject/flask_project/flask_schedular/uploads"
# UPLOAD_FILE_FOLDER = 'C:/DavidProject/flask_project/flask_schedular/uploadfiles'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx', 'txt', 'xls', 'xlsx', 'ppt', 'pptx'}

bp.upload_image_folder = UPLOAD_IMAGE_FOLDER
# bp.config['UPLOAD_FILE_FOLDER'] = UPLOAD_FILE_FOLDER

@bp.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(bp.upload_image_folder, filename)


def allowed_file(filename):
    """ 허용된 파일 확장자 체크 """
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


### terms 열기 
@bp.route('/terms')
def terms():
    return render_template('auth/e_terms.html')  # e_terms.html을 렌더링

##################  아이디 중복 체트 ##########################
@bp.route('/idcheck', methods=['POST'])
def idcheck():
    data = request.get_json()
    userid = data.get('userid', '').strip()
    print(f"사용자 아이디는 {userid} 입니다.")
    if not userid:
        return jsonify({'available': False, 'message': '아이디를 입력해 주세요.'})
    
    # 중복 여부 확인
    user = User.query.filter_by(userid=userid).first()
    if user:
        return jsonify({'available': False, 'message': '이미 존재하는 사용자입니다.'})
    else:
        return jsonify({'available': True, 'message': '사용 가능한 아이디입니다.'})


################## 등록 #########################################
@bp.route('/signup', methods=('GET', 'POST'))
def signup():
    if request.method == 'POST':
        try:
            # 📌 클라이언트에서 전달된 데이터 가져오기 (name 속성에 맞춰 수정)
            userid = request.form.get('userid', '').strip()
            password = request.form.get('password', '').strip()
            username = request.form.get('name', '').strip()
            email = request.form.get('email', '').strip()
            phone = request.form.get('phone', '').strip()
            company = request.form.get('company', '').strip()
            address = request.form.get('address', '').strip()
            tel_rep = request.form.get('tel_rep', '').strip()
            tel = request.form.get('tel', '').strip()
            fax = request.form.get('fax', '').strip()
            homepage = request.form.get('homepage', '').strip()

            team_type = request.form.get('team_type', '').strip()
            role_type = request.form.get('role_type', '').strip()
            # blood_type = request.form.get('blood_type', '').strip()
            # health = request.form.get('health', '').strip()
            # health_other = request.form.get('health_other', '').strip()
            # age = request.form.get('age', '').strip()

            print("전화번호: ", tel_rep)

            # 📌 아이디 중복 체크
            existing_user = User.query.filter_by(userid=userid).first()
            if existing_user:
                flash('이미 존재하는 사용자입니다.', 'error')
                return render_template('auth/e_signup.html')

            # 📌 파일 처리 (사진 업로드)

            # 📌 메인 파일 처리 로직
            upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')

            photo1_filename = ImageManagement.save_uploaded_photo(request.files.get('photo1'), upload_folder)
            photo2_filename = ImageManagement.save_uploaded_photo(request.files.get('photo2'), upload_folder)
            photo3_filename = ImageManagement.save_uploaded_photo(request.files.get('photo3'), upload_folder)

            # 📌 저장된 파일 로그 출력
            print(f"✅ 저장된 파일명 - photo1: {photo1_filename}, photo2: {photo2_filename}, photo3: {photo3_filename}")

            # if photo and photo.filename != "":
            #     filename = secure_filename(photo.filename)  # 보안 처리를 위한 안전한 파일명 변환
            #     upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')

            #     # 📌 폴더가 없으면 생성
            #     if not os.path.exists(upload_folder):
            #         os.makedirs(upload_folder)

            #     # 📌 파일명과 확장자 분리
            #     name, ext = os.path.splitext(filename)

            #     # 📌 10자 이상이면 앞 10자 + UUID4, 10자 이하면 전체 파일명 + UUID4
            #     short_name = name[:10] if len(name) >= 10 else name
            #     unique_filename = f"{short_name}_{uuid4().hex[:8]}{ext}"  # UUID 8자리 추가

            #     # 📌 파일 저장 경로
            #     photo_path = os.path.join(upload_folder, unique_filename)
            #     photo.save(photo_path)  # 사진 저장
            #     photo_filename = unique_filename  # DB 저장용 파일명

            # print(f"✅ 저장된 파일명: {photo_filename}")  # 서버 로그 출력

            # 📌 새 사용자 객체 생성
            user = User(
                userid=userid,
                password=generate_password_hash(password),  # 비밀번호 해싱
                username=username,
                email=email,
                phone=phone,
                company=company,
                department=team_type,
                position=role_type,
                com_address = address,
                tel_rep = tel_rep,
                tel_dir = tel,
                fax = fax,
                homepage = homepage,
                # blood=blood_type,
                # healthy=health,
                # age=age,
                photo_1=photo1_filename,  # 사진 파일명 저장
                photo_2=photo2_filename,  # 사진 파일명 저장
                photo_3=photo3_filename,  # 사진 파일명 저장

                create_date=datetime.now(),
                modify_date=datetime.now()
            )

            # 📌 데이터베이스 저장
            db.session.add(user)
            db.session.commit()

            # ✅ 저장 확인 (DB에서 다시 조회)
            saved_user = User.query.filter_by(userid=userid).first()
            if saved_user:
                flash('회원가입이 완료되었습니다!', 'success')
                print("✅ [회원가입 성공] 저장된 사용자 정보:")
                print(f"아이디: {saved_user.userid}, 이메일: {saved_user.email}, 회사: {saved_user.company}, 등록일: {saved_user.create_date}")

                # 회원가입 완료 후 회원가입 성공 플래그 전달
                return render_template('auth/e_signup.html', signup_success=True)

            else:
                flash('회원가입에 문제가 발생했습니다. 다시 시도해 주세요.', 'error')
                print("❌ [회원가입 실패] 데이터 저장 확인 불가")
                db.session.rollback()
                return render_template('auth/e_signup.html', signup_success=False)


        except Exception as e:
            db.session.rollback()  # 에러 발생 시 롤백
            flash('서버 오류가 발생했습니다. 다시 시도해 주세요.', 'error')
            print(f"❌ [회원가입 오류] {e}")  # 서버 로그에 오류 출력
            return render_template('auth/e_signup.html')

    return render_template('auth/e_signup.html', signup_success=False)

################## 마이페이지 #########################################
@bp.route('/mypage', methods=['GET', 'POST'])
@login_required
def mypage():
    # user = g.user  # 이미 @login_required 적용됨
    user = current_user  # 또는 g.user (둘 다 동일)

    print("login한 사용자:", user)  # 디버깅 확인

    if user:
        user_data = {
            "no": user.no,
            "userid": user.userid,
            "username": user.username,
            # "userimage": url_for('uploaded_file', filename=user.userimage) if user.userimage else "",
            "userimage": url_for('auth.uploaded_file', filename=user.userimage) if user.userimage else "",

            "email": user.email,
            "phone": user.phone,
            "photos": [
                {"name": "photo_1", "url": url_for('auth.uploaded_file', filename=user.photo_1) if user.photo_1 not in [None, ""] else ""},
                {"name": "photo_2", "url": url_for('auth.uploaded_file', filename=user.photo_2) if user.photo_2 not in [None, ""] else ""},
                {"name": "photo_3", "url": url_for('auth.uploaded_file', filename=user.photo_3) if user.photo_3 not in [None, ""] else ""}
            ],
            "company": user.company,
            "com_address": user.com_address,
            "tel_rep": user.tel_rep,
            "tel_dir": user.tel_dir,
            "fax": user.fax,
            "homepage": user.homepage,
            "department": user.department,
            "position": user.position,
            "blood": user.blood,
            "healthy": user.healthy,
            "age": user.age,
            "namecard": user.namecard,
            "address": user.address,
            "security": user.security,
            "create_date": user.create_date.strftime('%Y-%m-%d %H:%M:%S') if user.create_date else None,
            "modify_date": user.modify_date.strftime('%Y-%m-%d %H:%M:%S') if user.modify_date else None,
        }
        
        return render_template('auth/e_mypage.html', user=user_data)

    return redirect(url_for('auth.login'))  # 로그인되지 않은 경우 로그인 페이지로 이동

################## 파일 업로 -- 최대 10개 까지  #########################################

@bp.route('/file_upload', methods=['POST'])
@login_required
def file_upload():
    """ 📂 파일 업로드 API (최대 10개만 저장 후 초과 파일 반환) """

    # user = g.user  # 로그인한 사용자 정보
    user = current_user
    if not user:
        return jsonify({"success": False, "message": "로그인이 필요합니다."}), 401

    # ✅ 업로드 폴더 설정
    upload_folder = current_app.config.get('UPLOAD_FILE_FOLDER')

    # ✅ 기존 업로드된 파일 조회
    file_upload = FileUpload.query.filter_by(user_id=user.no).first()
    
    # 기존 업로드된 파일 목록 가져오기 (file_1 ~ file_10)
    existing_files = {}
    if file_upload:
        for i in range(1, 11):
            file_name = getattr(file_upload, f"file_{i}", None)
            if file_name:
                existing_files[file_name] = f"file_{i}"  # 파일명 -> 테이블 칼럼명 매핑

    new_files = {}  # 새로 업로드할 파일 저장
    duplicate_files = []  # 중복된 파일 리스트
    exceeded_files = []  # 10개 초과로 업로드할 수 없는 파일

    for i in range(1, 11):  
        file_key = f'file_{i}'
        if file_key in request.files:
            file = request.files[file_key]

            if file and allowed_file(file.filename):
                original_filename = file.filename

                # ✅ `secure_filename()` 적용 후 한글 파일명 복구
                safe_filename = safe_filename_korean(original_filename)

                # ✅ 중복 여부 확인
                if safe_filename in existing_files:
                    duplicate_files.append(safe_filename)  # 중복된 파일 저장
                else:
                    new_files[file_key] = safe_filename  # 새로운 파일만 저장

    # ✅ 기존 파일 개수 + 새로운 파일 개수가 10개를 초과하는 경우 처리
    available_slots = [f"file_{i}" for i in range(1, 11) if not getattr(file_upload, f"file_{i}", None)]
    
    # 10개 초과 시 초과된 파일을 따로 저장
    if len(existing_files) + len(new_files) > 10:
        excess_count = (len(existing_files) + len(new_files)) - 10
        exceeded_files = list(new_files.values())[-excess_count:]  # 초과된 파일 저장
        new_files = dict(list(new_files.items())[:-excess_count])  # 10개까지만 유지

    # ✅ 새로운 파일 저장 (10개 이내만 저장)
    for key, filename in new_files.items():
        file_path = os.path.join(upload_folder, filename)
        request.files[key].save(file_path)

    # ✅ FileUpload 테이블 업데이트 (비어있는 칼럼에 저장)
    if not file_upload:
        file_upload = FileUpload(user_id=user.no)

    for key, filename in new_files.items():
        if available_slots:
            slot = available_slots.pop(0)  # 비어있는 칼럼 가져오기
            setattr(file_upload, slot, filename)  # 해당 칼럼에 저장

    db.session.add(file_upload)
    db.session.commit()

    return jsonify({
        "success": True,
        "message": "파일 업로드 완료. 초과된 파일은 제외되었습니다.",
        "uploaded_files": list(new_files.values()),  # 저장된 파일
        "duplicate_files": duplicate_files,  # 중복 파일 목록
        "exceeded_files": exceeded_files  # 초과된 파일 목록
    })


def safe_filename_korean(filename):
    """ 한글이 깨지지 않도록 secure_filename 적용 후 복구 """
    safe_name = secure_filename(filename)

    # 확장자를 포함한 경우
    name, ext = os.path.splitext(filename)

    # secure_filename() 이후 이름이 비었거나 확장자만 남는 경우, 원본 파일명 유지
    if not safe_name or safe_name == ext:
        return filename  # 원본 파일명 사용

    # 파일명에 불필요한 공백 및 특수문자 정리 (한글 유지)
    cleaned_name = re.sub(r'[^\w가-힣.-]', '_', name)
    
    # 정규화 (NFC 형태로 변환하여 파일 시스템 호환성 유지)
    cleaned_name = unicodedata.normalize('NFC', cleaned_name)
    
    return f"{cleaned_name}{ext}"

################## 업데이트 #########################################
@bp.route('/update', methods=['GET', 'POST'])
@login_required
def update():
    # 로그인 체크
    # if 'user_id' not in session:
    #     flash('로그인이 필요합니다.', 'error')
    #     return redirect(url_for('auth.login'))

    # # 현재 로그인된 사용자 정보 가져오기
    # user = User.query.filter_by(id=session['user_id']).first()

    user = current_user  # 또는 g.user

    if request.method == 'POST':
        try:
            # 회원 정보 업데이트
            user.email = request.form.get('email', '').strip()
            user.phone = request.form.get('phone', '').strip()
            user.company = request.form.get('company', '').strip()
            user.department = request.form.get('team_type', '').strip()
            user.position = request.form.get('role_type', '').strip()
            user.age = request.form.get('age', '').strip()

            # 프로필 사진 변경 처리
            photo = request.files.get('photo')
            if photo and photo.filename != "":
                filename = secure_filename(photo.filename)
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')

                # 폴더가 없으면 생성
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)

                # 파일명 처리
                name, ext = os.path.splitext(filename)
                short_name = name[:10] if len(name) >= 10 else name
                unique_filename = f"{short_name}_{uuid4().hex[:8]}{ext}"
                photo_path = os.path.join(upload_folder, unique_filename)
                photo.save(photo_path)

                # 기존 사진 삭제
                if user.photo:
                    old_photo_path = os.path.join(upload_folder, user.photo)
                    if os.path.exists(old_photo_path):
                        os.remove(old_photo_path)

                user.photo = unique_filename

            user.modify_date = datetime.now()
            db.session.commit()
            flash("회원 정보가 업데이트되었습니다.", "success")
            return redirect(url_for('auth.mypage'))

        except Exception as e:
            db.session.rollback()
            flash("업데이트 중 오류가 발생했습니다.", "error")
            print(f"❌ [업데이트 오류] {e}")

    return render_template('auth/e_mypage.html', user=user)

############  LOGIN  로그인 #######################3
@bp.route('/login', methods=('GET', 'POST'))
def login():
    form = UserLoginForm()
    print("login 시도")

    if request.method == 'POST':
        if not form.validate_on_submit():
            print("유효성 검사 실패:", form.errors)
        error = None
        print("login 시도2")
        user = User.query.filter_by(userid=form.userid.data).first()

        if not user:
            error = '존재하지 않는 사용자입니다.'
        elif not check_password_hash(user.password, form.password.data):
            error = '비밀번호가 올바르지 않습니다.'
        if error is None:
            # 1) 예전 세션 비우고
            session.clear()

            # 2) Flask-Login 세션 생성
            login_user(user)

            # 3) 추가로 쓰고 싶은 값만 세션에 넣기
            session['user_no']   = user.no
            session['user_id']   = user.userid
            session['user_name'] = getattr(user, 'username', None)
            # session['dept']      = getattr(user, 'dept', None)
            session['dept'] = getattr(user, 'department', None)

            session['position']  = getattr(user, 'position', None)

            return jsonify({
                'success': True,
                'user': {
                    'no':        user.no,
                    'userid':    user.userid,
                    'username':  user.username,
                    'email':     getattr(user, 'email', None),
                    # 'dept':      getattr(user, 'dept', None),
                    'dept':      getattr(user, 'department', None),
                    'position':  getattr(user, 'position', None),
                }
            })

        return jsonify({'success': False, 'error': error})

    return render_template('auth/e_login.html', form=form)


@bp.route('/logout/')
@login_required
def logout():
    logout_user()      # 🔹 Flask-Login 세션 종료
    session.clear()    # 🔹 기존 커스텀 세션도 같이 정리
    return redirect(url_for('main.index'))

