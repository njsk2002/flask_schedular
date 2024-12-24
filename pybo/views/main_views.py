from flask import Blueprint, render_template, url_for, request, g , flash
from werkzeug.utils import redirect

from pybo.models import Question

bp = Blueprint('main',__name__,url_prefix='/')

@bp.route('/hello')
def hello_pybo():
    return 'Hello, Pybo!!!'

@bp.route('/')
def index():
    # page = request.args.get('page', type=int, default=1)  # 페이지 번호를 URL에서 가져옴
    # question_list = Question.query.order_by(Question.create_date.desc()).paginate(page=page, per_page=10)
    return redirect(url_for('co2.main_list'))


    #return redirect(url_for('kinvestor._list'))

@bp.route('/detail/<int:question_id>/')
def detail(question_id):
    question = Question.query.get_or_404(question_id)
    return render_template('question/question_detail.html', question = question)
