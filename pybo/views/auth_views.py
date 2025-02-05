import os, functools
from uuid import uuid4
from datetime import datetime
from flask import Blueprint, url_for, render_template, flash, request, session, g , jsonify, current_app
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect, secure_filename

from pybo import db
from pybo.forms import UserCreateForm, UserLoginForm
from pybo.models import User

bp =Blueprint('auth',__name__,url_prefix='/auth')



#=== 로그인 되었는지 먼저 확인하는 함수 @login_required 어노테이션으로 사용 가능 ====
def login_required(view):
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if g.user is None:
            return redirect(url_for('auth.login'))
        return view(**kwargs)
    
    return wrapped_view

#=== 로그인 되었을때 session data를 g.user 데이터로 이동/ 다른 class에서 g.user로 login 유무 확인가능 ====
@bp.before_app_request
def load_logged_in_user():
    user_no = session.get('user_no')
    if user_no is None:
        g.user = None
    else:
        g.user = User.query.get(user_no)

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
            team_type = request.form.get('team_type', '').strip()
            role_type = request.form.get('role_type', '').strip()
            blood_type = request.form.get('blood_type', '').strip()
            health = request.form.get('health', '').strip()
            health_other = request.form.get('health_other', '').strip()
            age = request.form.get('age', '').strip()

            # 📌 아이디 중복 체크
            existing_user = User.query.filter_by(userid=userid).first()
            if existing_user:
                flash('이미 존재하는 사용자입니다.', 'error')
                return render_template('auth/signup.html')

            # 📌 파일 처리 (사진 업로드)
            photo = request.files.get('photo')
            photo_filename = None

            if photo and photo.filename != "":
                filename = secure_filename(photo.filename)  # 보안 처리를 위한 안전한 파일명 변환
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')

                # 📌 폴더가 없으면 생성
                if not os.path.exists(upload_folder):
                    os.makedirs(upload_folder)

                # 📌 파일명과 확장자 분리
                name, ext = os.path.splitext(filename)

                # 📌 10자 이상이면 앞 10자 + UUID4, 10자 이하면 전체 파일명 + UUID4
                short_name = name[:10] if len(name) >= 10 else name
                unique_filename = f"{short_name}_{uuid4().hex[:8]}{ext}"  # UUID 8자리 추가

                # 📌 파일 저장 경로
                photo_path = os.path.join(upload_folder, unique_filename)
                photo.save(photo_path)  # 사진 저장
                photo_filename = unique_filename  # DB 저장용 파일명

            print(f"✅ 저장된 파일명: {photo_filename}")  # 서버 로그 출력

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
                blood=blood_type,
                healthy=health,
                age=age,
                photo=photo_filename,  # 사진 파일명 저장
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
            else:
                flash('회원가입에 문제가 발생했습니다. 다시 시도해 주세요.', 'error')
                print("❌ [회원가입 실패] 데이터 저장 확인 불가")
                db.session.rollback()
                return render_template('auth/e_signup.html')

            #return redirect(url_for('main.index'))  # 회원가입 완료 후 메인 페이지로 이동
            return render_template('auth/e_signup.html')


        except Exception as e:
            db.session.rollback()  # 에러 발생 시 롤백
            flash('서버 오류가 발생했습니다. 다시 시도해 주세요.', 'error')
            print(f"❌ [회원가입 오류] {e}")  # 서버 로그에 오류 출력
            return render_template('auth/e_signup.html')

    return render_template('auth/e_signup.html')

################## 마이페이지 #########################################
@bp.route('/mypage', methods=['GET', 'POST'])
def mypage():
    # 로그인 체크
    if 'user_id' not in session:
        flash('로그인이 필요합니다.', 'error')
        return redirect(url_for('auth.login'))

    # 현재 로그인된 사용자 정보 가져오기
    user = User.query.filter_by(id=session['user_id']).first()

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

    return render_template('auth/mypage.html', user=user)

@bp.route('/login', methods=('GET', 'POST'))
def login():
    form = UserLoginForm()
    print("login 시도")
    if request.method == 'POST' and form.validate_on_submit():
        error = None
        print("login 시도2")
        user = User.query.filter_by(userid=form.userid.data).first()
        if not user:
            error = ' 존재하지 않는 사용자입니다.'
        elif not check_password_hash(user.password, form.password.data):
            error = ' 비밀번호가 올바르지 않습니다.'
        if error is None:
            session.clear()
            session['user_no'] = user.no
            return redirect(url_for('naverapi.admin_image'))
        flash(error)

    return render_template('auth/e_login.html', form=form)

@bp.route('/logout/')
def logout():
    session.clear()
    return redirect(url_for('main.index'))

