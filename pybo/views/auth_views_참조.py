from datetime import datetime
from flask import Blueprint, url_for, render_template, flash, request, session, g
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import redirect

from pybo import db
from pybo.forms import UserCreateForm, UserLoginForm
from pybo.models import User

bp =Blueprint('auth',__name__,url_prefix='/auth')

import functools

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
        

@bp.route('/signup/', methods=('GET', 'POST'))
def signup():
    form = UserCreateForm()
    if request.method == 'POST' and form.validate_on_submit():
        userid = User.query.filter_by(userid=form.userid.data).first()
        if not userid:
            user = User(userid=form.userid.data,
                          password= generate_password_hash(form.password1.data),
                          username= form.username.data,
                          email = form.email.data,
                          phone = form.phone.data,
                          create_date=datetime.now(),
                          modify_date=datetime.now()

                          )
            db.session.add(user)
            db.session.commit()
            return redirect(url_for('main.index'))
        else:
            flash('이미 존재하는 사용자입니다.')
    
    return render_template('auth/signup.html', form=form)

@bp.route('/login/', methods=('GET', 'POST'))
def login():
    form = UserLoginForm()
    if request.method == 'POST' and form.validate_on_submit():
        error = None
        user = User.query.filter_by(userid=form.userid.data).first()
        if not user:
            error = ' 존재하지 않는 사용자입니다.'
        elif not check_password_hash(user.password, form.password.data):
            error = ' 비밀번호가 올바르지 않습니다.'
        if error is None:
            session.clear()
            session['user_no'] = user.no
            return redirect(url_for('co2.admin'))
        flash(error)

    return render_template('auth/login.html', form=form)

@bp.route('/logout/')
def logout():
    session.clear()
    return redirect(url_for('main.index'))

