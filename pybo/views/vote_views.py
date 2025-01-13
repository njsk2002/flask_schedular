from datetime import datetime

from flask import Blueprint, url_for, request, render_template, g , flash
from werkzeug.utils import redirect


from .. import db


from ..models import Question, Answer, QuestionVoter,  AnswerVoter #table 이름

from .auth_views import login_required #login 확인

bp = Blueprint('vote',__name__, url_prefix='/vote')

@bp.route('/question/<int:question_id>/')
@login_required
def question(question_id):
    _question = Question.query.get_or_404(question_id)

    # _question 객체의 모든 속성과 값 출력
    question_values = {column.name: getattr(_question, column.name) for column in _question.__table__.columns}
    print(question_values)

    if g.user == _question.user:
        flash('본인이 작성한 글은 추천할 수 없습니다.')
   
    else:
        if QuestionVoter.query.get((question_id)):
            _voter = QuestionVoter.query.get((question_id))
            if _voter.user_no == g.user.no:       
                flash('추천은 한번만 가능합니다.')
          
            else:
                _question.voter.append(g.user)
                db.session.commit()
        else:
            _question.voter.append(g.user)
            db.session.commit()
    return redirect(url_for('question.detail',question_id = question_id))

@bp.route('/answer/<int:answer_id>/')
@login_required
def answer(answer_id):
    _answer = Answer.query.get_or_404(answer_id)
    if g.user == _answer.user:
        flash('본인이 작성한 글은 추천할 수 없습니다.')
    else:
        if AnswerVoter.query.get((answer_id)):
            _voter = AnswerVoter.query.get((answer_id))
            if _voter.user_no == g.user.no:       
                flash('추천은 한번만 가능합니다.')
          
            else:
                _answer.voter.append(g.user)
                db.session.commit()
        else:
            _answer.voter.append(g.user)
            db.session.commit()
    return redirect(url_for('question.detail',question_id = _answer.question.id))