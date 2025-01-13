from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, PasswordField
from wtforms.fields import EmailField  #교재는 wtforms.fields.html5로 되어 있으나, 에러발생해서 수정
from wtforms.validators import DataRequired, Length, EqualTo, Email


class QuestionForm(FlaskForm):
    subject = StringField('제목', validators=[DataRequired('제목은 필수 입력 항목입니다.')])
    content = TextAreaField('내용', validators=[DataRequired('내용은 필수 입력 항목입니다.')])

class AnswerForm(FlaskForm):
    content = TextAreaField('내용', validators=[DataRequired('내용은 필수입력 항목입니다.')])

class UserCreateForm(FlaskForm):
    userid = StringField('ID', validators=[DataRequired(), Length(min=3, max=25)])
    password1 = PasswordField('비밀번호', validators=[DataRequired(), EqualTo('password2','비밀번호가 일치하지 않습니다')])
    password2 = PasswordField('비밀번호확인', validators=[DataRequired()])
    username = StringField('사용자이름', validators=[DataRequired(), Length(min=3, max=25)])
    email = EmailField('이메일', [DataRequired(), Email()])
    phone = StringField('휴대폰', validators=[DataRequired(), Length(min=3, max=25)])

class UserLoginForm(FlaskForm):
    userid = StringField('ID', validators=[DataRequired(), Length(min=3, max=25)])
    password = PasswordField('비밀번호',validators=[DataRequired()])

class CommentForm(FlaskForm):
    content = TextAreaField('내용',validators=[DataRequired()])