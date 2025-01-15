from pybo import db


# class Question(db.Model):
#     id = db.Column(db.Integer, primary_key=True)
#     subject = db.Column(db.String(200), nullable=False)
#     content = db.Column(db.Text(), nullable=False)
#     create_date = db.Column(db.DateTime(), nullable=False)
#     #user_id = db.Column(db.String(150), db.ForeignKey('user.userid', ondelete='CASCADE', nullable=False))
#     user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=True, server_default ='1')
#     user = db.relationship('User', backref=db.backref('question_set'))

# question_voter = db.Table(
#         'question_voter',
#         db.Column('user_no', db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), primary_key=True),
#         db.Column('question_id', db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), primary_key=True)

#     )


# answer_voter = db.Table(
#         'answer_voter',
#         db.Column('user_no', db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), primary_key=True),
#         db.Column('answer_id', db.Integer, db.ForeignKey('answer.id', ondelete='CASCADE'), primary_key=True)

#     )

class QuestionVoter(db.Model):
    __tablename__ = 'question_voter'
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), primary_key=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), primary_key=True)

class AnswerVoter(db.Model):
    __tablename__ = 'answer_voter'
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), primary_key=False)
    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id', ondelete='CASCADE'), primary_key=True)



class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(201), nullable=False)
    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('question_set'))
    modify_date = db.Column(db.DateTime(), nullable=True)
    voter = db.relationship('User', secondary='question_voter', backref=db.backref('question_voter_set')) 
    

class Answer(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete ='CASCADE'))
    question = db.relationship('Question',backref=db.backref('answer_set',))
    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)    
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('answer_set'))
    modify_date = db.Column(db.DateTime(), nullable=True) 
    voter = db.relationship('User', secondary='answer_voter', backref=db.backref('answer_voter_set'))


class User(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    userid= db.Column(db.String(150), unique=True, nullable=False)
    password = db.Column(db.String(200),nullable=False)
    username= db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), nullable=False)
    phone = db.Column(db.String(150), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)  
    modify_date = db.Column(db.DateTime(), nullable=False)  


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('comment_set'))
    content = db.Column(db.Text(), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime())
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), nullable=True)
    question = db.relationship('Question', backref=db.backref('comment_set'))
    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id', ondelete='CASCADE'), nullable=True)
    answer = db.relationship('Answer', backref=db.backref('comment_set'))


class Co2Management(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    use_date = db.Column(db.String(150), nullable=False)
    use_elec = db.Column(db.String(150), nullable=True)
    co2_elec = db.Column(db.String(150), nullable=True)
    use_water = db.Column(db.String(150), nullable=True)
    co2_water = db.Column(db.String(150), nullable=True)
    use_waste = db.Column(db.String(150), nullable=True)
    co2_waste = db.Column(db.String(150), nullable=True)
    use_vehicle = db.Column(db.String(150), nullable=True)
    co2_vehicle = db.Column(db.String(150), nullable=True)
    use_gas = db.Column(db.String(150), nullable=True)
    co2_gas = db.Column(db.String(150), nullable=True)
    use_total = db.Column(db.String(150), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)
    

class ElecUsage(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    room_no = db.Column(db.String(150), nullable=False)
    use_year = db.Column(db.String(150), nullable=False)
    acum_ref = db.Column(db.String(150), nullable=False)
    acum_jan = db.Column(db.String(150), nullable=True)
    use_jan = db.Column(db.String(150), nullable=True)
    acum_feb = db.Column(db.String(150), nullable=True)
    use_feb = db.Column(db.String(150), nullable=True)
    acum_mar = db.Column(db.String(150), nullable=True)
    use_mar = db.Column(db.String(150), nullable=True)
    acum_apr = db.Column(db.String(150), nullable=True)
    use_apr = db.Column(db.String(150), nullable=True)
    acum_may = db.Column(db.String(150), nullable=True)
    use_may = db.Column(db.String(150), nullable=True)
    acum_jun = db.Column(db.String(150), nullable=True)
    use_jun = db.Column(db.String(150), nullable=True)
    acum_jul = db.Column(db.String(150), nullable=True)
    use_jul = db.Column(db.String(150), nullable=True)
    acum_aug = db.Column(db.String(150), nullable=True)
    use_aug = db.Column(db.String(150), nullable=True)
    acum_sep = db.Column(db.String(150), nullable=True)
    use_sep = db.Column(db.String(150), nullable=True)
    acum_oct = db.Column(db.String(150), nullable=True)
    use_oct = db.Column(db.String(150), nullable=True)
    acum_nov = db.Column(db.String(150), nullable=True)
    use_nov= db.Column(db.String(150), nullable=True)
    acum_dec = db.Column(db.String(150), nullable=True)
    use_dec = db.Column(db.String(150), nullable=True)
    total = db.Column(db.String(150), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)

class VehicleUsage(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    car_no = db.Column(db.String(150), nullable=False)
    car_name= db.Column(db.String(150), nullable=False)
    car_fuel= db.Column(db.String(150), nullable=False)
    use_year = db.Column(db.String(150), nullable=False)
    acum_ref = db.Column(db.String(150), nullable=False)
    acum_jan = db.Column(db.String(150), nullable=True)
    use_jan = db.Column(db.String(150), nullable=True)
    acum_feb = db.Column(db.String(150), nullable=True)
    use_feb = db.Column(db.String(150), nullable=True)
    acum_mar = db.Column(db.String(150), nullable=True)
    use_mar = db.Column(db.String(150), nullable=True)
    acum_apr = db.Column(db.String(150), nullable=True)
    use_apr = db.Column(db.String(150), nullable=True)
    acum_may = db.Column(db.String(150), nullable=True)
    use_may = db.Column(db.String(150), nullable=True)
    acum_jun = db.Column(db.String(150), nullable=True)
    use_jun = db.Column(db.String(150), nullable=True)
    acum_jul = db.Column(db.String(150), nullable=True)
    use_jul = db.Column(db.String(150), nullable=True)
    acum_aug = db.Column(db.String(150), nullable=True)
    use_aug = db.Column(db.String(150), nullable=True)
    acum_sep = db.Column(db.String(150), nullable=True)
    use_sep = db.Column(db.String(150), nullable=True)
    acum_oct = db.Column(db.String(150), nullable=True)
    use_oct = db.Column(db.String(150), nullable=True)
    acum_nov = db.Column(db.String(150), nullable=True)
    use_nov= db.Column(db.String(150), nullable=True)
    acum_dec = db.Column(db.String(150), nullable=True)
    use_dec = db.Column(db.String(150), nullable=True)
    total = db.Column(db.String(150), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)

class WaterUsage(db.Model):
    no = db.Column(db.Integer, primary_key=True)
    room_no = db.Column(db.String(150), nullable=False)
    use_year = db.Column(db.String(150), nullable=False)
    acum_ref = db.Column(db.String(150), nullable=False)
    acum_jan = db.Column(db.String(150), nullable=True)
    use_jan = db.Column(db.String(150), nullable=True)
    acum_feb = db.Column(db.String(150), nullable=True)
    use_feb = db.Column(db.String(150), nullable=True)
    acum_mar = db.Column(db.String(150), nullable=True)
    use_mar = db.Column(db.String(150), nullable=True)
    acum_apr = db.Column(db.String(150), nullable=True)
    use_apr = db.Column(db.String(150), nullable=True)
    acum_may = db.Column(db.String(150), nullable=True)
    use_may = db.Column(db.String(150), nullable=True)
    acum_jun = db.Column(db.String(150), nullable=True)
    use_jun = db.Column(db.String(150), nullable=True)
    acum_jul = db.Column(db.String(150), nullable=True)
    use_jul = db.Column(db.String(150), nullable=True)
    acum_aug = db.Column(db.String(150), nullable=True)
    use_aug = db.Column(db.String(150), nullable=True)
    acum_sep = db.Column(db.String(150), nullable=True)
    use_sep = db.Column(db.String(150), nullable=True)
    acum_oct = db.Column(db.String(150), nullable=True)
    use_oct = db.Column(db.String(150), nullable=True)
    acum_nov = db.Column(db.String(150), nullable=True)
    use_nov= db.Column(db.String(150), nullable=True)
    acum_dec = db.Column(db.String(150), nullable=True)
    use_dec = db.Column(db.String(150), nullable=True)
    total = db.Column(db.String(150), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)


class CalendarSchedule(db.Model):
    __tablename__ = 'calendar_schedule'  # 테이블 이름 명시
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 명시적으로 autoincrement 추가
    user_id = db.Column(db.Integer, db.ForeignKey('user_authorization.id', ondelete='CASCADE'), nullable=False)
    content = db.Column(db.String(300), nullable=False)
    start_time = db.Column(db.String(150), nullable=True)
    end_time = db.Column(db.String(150), nullable=True)
    cal_date = db.Column(db.String(150), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)

# 사용자와의 관계
    user = db.relationship('UserAuthorization', backref=db.backref('calendar_schedule', lazy=True, passive_deletes=True))

class UserAuthorization(db.Model):
    __tablename__ = 'user_authorization'  # 테이블 이름 명시
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 명시적으로 autoincrement 추가
    email = db.Column(db.String(300), nullable=False, unique=True)
    password = db.Column(db.String(150), nullable=False)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)

class RefreshToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_authorization.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(500), nullable=False, unique=True)
    expires_at = db.Column(db.DateTime, nullable=False)

    # 사용자와의 관계
    user = db.relationship('UserAuthorization', backref=db.backref('refresh_tokens', lazy=True, passive_deletes=True))

class YoutubeURL(db.Model):
    __tablename__ = 'YoutubeURL'  # 테이블 이름 명시
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 명시적으로 autoincrement 추가
    #user_id = db.Column(db.Integer, db.ForeignKey('user_authorization.id', ondelete='CASCADE'), nullable=False)
    star_name = db.Column(db.String(100), nullable=False)
    type_video = db.Column(db.String(100), nullable=False)
    title_video = db.Column(db.String(300), nullable=False)
    
    json_file = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    update_date = db.Column(db.String(150), nullable=False)

    view_count = db.Column(db.String(100), nullable=True)
    favorite_count = db.Column(db.String(100), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)


   

    
