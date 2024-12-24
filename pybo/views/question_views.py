from datetime import datetime
from flask import Blueprint, render_template, request, url_for, g , flash
from werkzeug.utils import redirect
from pybo import db  # .. import db로 되어있는데, pybo로 변경
from ..forms import QuestionForm, AnswerForm
from sqlalchemy import func
from ..models import Question, Answer, User, QuestionVoter

from pybo.views.auth_views import login_required

bp = Blueprint('question',__name__,url_prefix='/question')


# @bp.route('/list/')
# def _list():
#     page = request.args.get('page', type=int, default=1) #페이지
#     question_list =  Question.query.order_by(Question.create_date.desc()) 
#     question_list = question_list.paginate(page=page, per_page=10)
#     return render_template('question/question_list.html',question_list =question_list)

@bp.route('/list/')
def _list():
    #입력파라메터
    page = request.args.get('page', type=int, default=1) #페이지
    kw = request.args.get('kw',type=str, default='')
    so = request.args.get('so', type=str, default='recent')
    
    #정렬
    if so == 'recommend':
        sub_query = db.session.query(QuestionVoter.question_id, func.count('*').label('num_voter'))\
                                     .group_by(QuestionVoter.question_id).subquery()

        question_list = Question.query.outerjoin(sub_query, Question.id == sub_query.c.question_id)\
        .order_by(sub_query.c.num_voter.desc(), Question.create_date.desc())
    elif so == 'popular':
        sub_query = db.session.query(Answer.question_id, func.count('*').label('num_answer'))\
                                     .group_by(Answer.question_id).subquery()

        question_list = Question.query.outerjoin(sub_query, Question.id == sub_query.c.question_id)\
        .order_by(sub_query.c.num_answer.desc(), Question.create_date.desc())
    else:
        question_list = Question.query.order_by(Question.create_date.desc())

    # #조회
    # question_list =  Question.query.order_by(Question.create_date.desc()) 
    # 조회
    if kw:
        search = '%%{}%%'.format(kw)
        sub_query = db.session.query(Answer.question_id, Answer.content, User.username) \
            .join(User, Answer.user_no == User.no).subquery()
        question_list = question_list \
            .join(User) \
            .outerjoin(sub_query, sub_query.c.question_id == Question.id) \
            .filter(Question.subject.ilike(search) |  # 질문제목
                    Question.content.ilike(search) |  # 질문내용
                    User.username.ilike(search) |  # 질문작성자
                    sub_query.c.content.ilike(search) |  # 답변내용
                    sub_query.c.username.ilike(search)  # 답변작성자
                    ) \
            .distinct()

    # 페이징
    question_list = question_list.paginate(page=page, per_page=10)
    return render_template('question/question_list.html', question_list=question_list, page=page, kw=kw)

@bp.route('/detail/<int:question_id>/')
def detail(question_id):   
    form = AnswerForm() 
    question = Question.query.get_or_404(question_id)
    return render_template('question/question_detail.html', question=question, form=form)

@bp.route('/create/', methods=('GET', 'POST'))
@login_required
def create():
    form = QuestionForm()
    print(request.method)
    print(form.validate_on_submit())

    if request.method == 'POST' and form.validate_on_submit():
        print('POST 방식')
        question = Question(subject=form.subject.data, content=form.content.data, create_date=datetime.now(), user=g.user)
       #  question = Question(subject="fdfdf", content="fdfd", create_date=datetime.now())
        db.session.add(question)
        db.session.commit()
        return redirect(url_for('main.index'))
    return render_template('question/question_form.html', form=form)

@bp.route('/modify/<int:question_id>',methods=('GET','POST'))
@login_required
def modify(question_id):
    question = Question.query.get_or_404(question_id)

    if g.user != question.user:
        flash('수정 권한이 없습니다.')
        return redirect(url_for('question.detail', question_id = question_id))
    if request.method == 'POST':
        form = QuestionForm
        if form.validate_on_submit():
            form.populate_obj(question)
            question.modify_date = datetime.now()
            db.session.commit()
            return redirect(url_for('question.detail', question_id = question_id))
    else:
        form = QuestionForm(obj=question)
    return render_template('question/question_form.html',form=form)

@bp.route('/delete/<int:question_id>')
@login_required
def delete(question_id):
    question = Question.query.get_or_404(question_id)

    if g.user != question.user:
        flash('삭제권한이 없습니다.')
        return redirect(url_for('question.detail', question_id=question_id))
    db.session.delete(question_id)
    db.session.commit()

    return redirect(url_for('question._list'))