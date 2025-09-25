from pybo import db
from sqlalchemy.sql import func
from datetime import datetime, timezone, timedelta


# ✅ KST 타임존 설정 (UTC+9)
KST = timezone(timedelta(hours=9))



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
    __tablename__ = 'user'

    no = db.Column(db.Integer, primary_key=True)
    userid= db.Column(db.String(150), unique=True, nullable=False, default='')
    password = db.Column(db.String(200), nullable=False, default='')
    username= db.Column(db.String(150), nullable=False, default='')
    userimage = db.Column(db.String(300), nullable=True)
    email = db.Column(db.String(150), nullable=False, default='')
    phone = db.Column(db.String(150), nullable=False, default='')
    photo_1 = db.Column(db.String(500), nullable=True)
    photo_2 = db.Column(db.String(500), nullable=True)
    photo_3 = db.Column(db.String(500), nullable=True)
    company = db.Column(db.String(100), nullable=True)
    com_address = db.Column(db.String(500), nullable=True)
    tel_rep = db.Column(db.String(100), nullable=True)
    tel_dir = db.Column(db.String(100), nullable=True)
    fax = db.Column(db.String(100), nullable=True)
    homepage = db.Column(db.String(300), nullable=True)
    department = db.Column(db.String(150), nullable=True)
    position = db.Column(db.String(150), nullable=True)
    blood = db.Column(db.String(150), nullable=True)
    healthy = db.Column(db.String(150), nullable=True)
    age = db.Column(db.String(150), nullable=True)
    namecard = db.Column(db.String(150), nullable=False, default='0')
    address = db.Column(db.String(500), nullable=True)
    security = db.Column(db.String(100), nullable=False, default='0')

    create_date = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(KST))
    modify_date = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(KST), onupdate=lambda: datetime.now(KST))

    # ✅ 관계 설정 (User가 삭제될 때, 연결된 데이터 삭제)
    namecards = db.relationship('NameCard', backref='user', cascade="all, delete", lazy=True)
    files = db.relationship('FileUpload', backref='user', cascade="all, delete", lazy=True)
    sharecards = db.relationship('ShareCard', backref='user', cascade="all, delete", lazy=True)
    
class NameCard(db.Model):
    __tablename__ = 'namecard'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete="CASCADE"), nullable=False)
    selected_photo = db.Column(db.String(500), nullable=True)
    department = db.Column(db.String(150), nullable=True)
    position = db.Column(db.String(150), nullable=True)
    username = db.Column(db.String(150), nullable=True)
    phone = db.Column(db.String(150), nullable=True)
    email = db.Column(db.String(150), nullable=True)
    company = db.Column(db.String(100), nullable=True)
    com_address = db.Column(db.String(500), nullable=True)
    tel_rep = db.Column(db.String(100), nullable=True)
    tel_dir = db.Column(db.String(100), nullable=True)
    fax = db.Column(db.String(100), nullable=True)
    homepage = db.Column(db.String(300), nullable=True)


   # ✅ Python에서 KST로 변환 후 저장
    create_date = db.Column(db.DateTime(timezone=True),nullable=False,default=lambda: datetime.now(KST)) # ✅ KST 시간으로 저장
    modify_date = db.Column(db.DateTime(timezone=True),nullable=False,default=lambda: datetime.now(KST), onupdate=lambda: datetime.now(KST))  
    # ✅ KST 시간으로 저장# ✅ KST 시간으로 업데이트


    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "selected_photo": self.selected_photo or "",
            "department": self.department or "",
            "position": self.position or "",
            "username": self.username or "",
            "phone": self.phone or "",
            "email": self.email or "",
            "company": self.company or "",
            "com_address": self.com_address or "",
            "tel_rep": self.tel_rep or "",
            "tel_dir": self.tel_dir or "",
            "fax": self.fax or "",
            "homepage": self.homepage or "",
            "created_at": self.create_date.strftime('%Y-%m-%d %H:%M:%S') if self.create_date else None,
            "updated_at": self.modify_date.strftime('%Y-%m-%d %H:%M:%S') if self.modify_date else None
        }

class FileUpload(db.Model):
    """ 파일 업로드 테이블 (파일 최대 10개 저장 가능) """
    __tablename__ = 'fileuploads'
    
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.no'), nullable=False)  # 업로드한 사용자

    # 최대 10개의 파일 (파일명 저장)
    file_1 = db.Column(db.String(255), nullable=True)
    file_2 = db.Column(db.String(255), nullable=True)
    file_3 = db.Column(db.String(255), nullable=True)
    file_4 = db.Column(db.String(255), nullable=True)
    file_5 = db.Column(db.String(255), nullable=True)
    file_6 = db.Column(db.String(255), nullable=True)
    file_7 = db.Column(db.String(255), nullable=True)
    file_8 = db.Column(db.String(255), nullable=True)
    file_9 = db.Column(db.String(255), nullable=True)
    file_10 = db.Column(db.String(255), nullable=True)

    uploaded_at = db.Column(db.DateTime, default=db.func.now())

    def to_dict(self):
        """ JSON 응답을 위한 Dict 변환 """
        return {
            "id": self.id,
            "user_id": self.user_id,
            "files": [
                self.file_1, self.file_2, self.file_3, self.file_4, self.file_5,
                self.file_6, self.file_7, self.file_8, self.file_9, self.file_10
            ],
            "uploaded_at": self.uploaded_at.strftime("%Y-%m-%d %H:%M:%S")
        }

class ShareCard(db.Model):
    __tablename__ = 'sharecard'

    no = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete="CASCADE"), nullable=False)
    namecard_id = db.Column(db.Integer, db.ForeignKey('namecard.id', ondelete="CASCADE"), nullable=False)
    fileupload_id = db.Column(db.Integer, db.ForeignKey('fileuploads.id', ondelete="CASCADE"), nullable=False)
    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    introduce = db.Column(db.String(500), nullable=True)
    vcf = db.Column(db.String(150), nullable=True)
    qrcode = db.Column(db.String(150), nullable=True)
    s_ncard = db.Column(db.String(150), nullable=False)
    custom_email = db.Column(db.String(150), nullable=True)
    s_file1 = db.Column(db.String(300), nullable=True)
    s_file2 = db.Column(db.String(300), nullable=True)
    s_file3 = db.Column(db.String(300), nullable=True)
    s_file4 = db.Column(db.String(300), nullable=True)
    s_file5 = db.Column(db.String(300), nullable=True)
    count = db.Column(db.String(100), nullable=True)

    # ✅ Python에서 KST로 변환 후 저장
    create_date = db.Column(db.DateTime(timezone=True),nullable=False,default=lambda: datetime.now(KST)) # ✅ KST 시간으로 저장
    modify_date = db.Column(db.DateTime(timezone=True),nullable=False,default=lambda: datetime.now(KST), onupdate=lambda: datetime.now(KST))  
    # ✅ KST 시간으로 저장# ✅ KST 시간으로 업데이트

    def to_dict(self):
        return {
            "no": self.no,
            "user_id": self.user_id,
            "namecard_id": self.namecard_id,
            "fileupload_id": self.fileupload_id,
            "title": self.title,
            "content": self.content,
            "introduce": self.introduce or "",
            "vcf": self.vcf or "",
            "qrcode": self.qrcode or "",
            "s_ncard": self.s_ncard,
            "custom_email": self.custom_email or "",
            "s_file1": self.s_file1 or "",
            "s_file2": self.s_file2 or "",
            "s_file3": self.s_file3 or "",
            "s_file4": self.s_file4 or "",
            "s_file5": self.s_file5 or "",
            "count": self.count or "",
            "created_at": self.create_date.strftime('%Y-%m-%d %H:%M:%S') if self.create_date else None,
            "updated_at": self.modify_date.strftime('%Y-%m-%d %H:%M:%S') if self.modify_date else None
        }
## 웰컴 페이지 Welcome Page
class WelcomeData(db.Model):
    __tablename__ = 'welcomedata'

    no = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete="CASCADE"), nullable=False)
    namecard_id = db.Column(db.Integer, db.ForeignKey('namecard.id', ondelete="CASCADE"), nullable=False)
    share_card_id = db.Column(db.Integer, db.ForeignKey('sharecard.no', ondelete="CASCADE"), nullable=False)
    bmp_name = db.Column(db.String(200), nullable=False)
    bmp_path = db.Column(db.String(500), nullable=False)
    qr_code = db.Column(db.String(500), nullable=True)
    unique_id = db.Column(db.String(150), nullable=True)
    count = db.Column(db.String(150), nullable=True)

    # ✅ Python에서 KST로 변환 후 저장
    create_date = db.Column(db.DateTime(timezone=True),nullable=False,default=lambda: datetime.now(KST)) # ✅ KST 시간으로 저장
    expires_at = db.Column(db.DateTime, nullable=False)  # 만료 시간
    # ✅ KST 시간으로 저장# ✅ KST 시간으로 업데이트


    def to_dict(self):
        return {
            "no": self.no,
            "user_id": self.user_id,
            "namecard_id": self.namecard_id,
            "share_card_id": self.share_card_id,
            "bmp_name": self.bmp_name,
            "bmp_path": self.bmp_path,
            "qr_code": self.qr_code or "",
            "unique_id": self.unique_id or "",
            "count": self.count or "",
            "created_at": self.create_date.strftime('%Y-%m-%d %H:%M:%S') if self.create_date else None,
            "expires_at": self.expires_at.strftime('%Y-%m-%d %H:%M:%S') if self.expires_at else None
        }



# ✅ QR 코드 저장용 테이블 생성
class QRCode(db.Model):
    __tablename__ = 'qr_code'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, nullable=False)
    namecard_id = db.Column(db.Integer, nullable=False)
    share_card_id = db.Column(db.Integer, nullable=False)
    unique_id = db.Column(db.String(100), unique=True, nullable=False)  # 고유한 URL 값
    # ✅ Python에서 KST로 변환 후 저장
    create_date = db.Column(db.DateTime(timezone=True),nullable=False,default=lambda: datetime.now(KST)) # ✅ KST 시간으로 저장
    expires_at = db.Column(db.DateTime, nullable=False)  # 만료 시간


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

class ImageData(db.Model):
    __tablename__ = 'ImageData'  # 테이블 이름 명시
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 명시적으로 autoincrement 추가
    #user_id = db.Column(db.Integer, db.ForeignKey('user_authorization.id', ondelete='CASCADE'), nullable=False)
    key_word = db.Column(db.String(100), nullable=False)
    type_image = db.Column(db.String(100), nullable=False)
    title_image = db.Column(db.String(300), nullable=False)
    
    json_file = db.Column(db.String(200), nullable=False)
    thumbnail = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(500), nullable=False)

    bmp_42_mono = db.Column(db.String(200), nullable=True)
    bmp_42_3color = db.Column(db.String(200), nullable=True)
    bmp_37_4color = db.Column(db.String(200), nullable=True)
    bmp_29_mono = db.Column(db.String(200), nullable=True)
    bmp_29_3color = db.Column(db.String(200), nullable=True)
    bmp_29_4color = db.Column(db.String(200), nullable=True)
    bmp_file_1 = db.Column(db.String(200), nullable=True)
    bmp_file_2 = db.Column(db.String(200), nullable=True)

    sizewidth = db.Column(db.String(100), nullable=False)
    sizeheight = db.Column(db.String(100), nullable=False)
    update_date = db.Column(db.String(150), nullable=False)

    view_count = db.Column(db.String(100), nullable=True)
    favorite_count = db.Column(db.String(100), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)

class NewsData(db.Model):
    __tablename__ = 'NewsData'  # 테이블 이름 명시
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 명시적으로 autoincrement 추가
    #user_id = db.Column(db.Integer, db.ForeignKey('user_authorization.id', ondelete='CASCADE'), nullable=False)
    star_name = db.Column(db.String(100), nullable=False)
    type_news = db.Column(db.String(100), nullable=False)
    title_new = db.Column(db.String(300), nullable=False)
    
    json_file = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    origin_url = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    update_date = db.Column(db.String(150), nullable=False)

    view_count = db.Column(db.String(100), nullable=True)
    favorite_count = db.Column(db.String(100), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)

class BlogData(db.Model):
    __tablename__ = 'BlogData'  # 테이블 이름 명시
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 명시적으로 autoincrement 추가
    #user_id = db.Column(db.Integer, db.ForeignKey('user_authorization.id', ondelete='CASCADE'), nullable=False)
    star_name = db.Column(db.String(100), nullable=False)
    type_blog = db.Column(db.String(100), nullable=False)
    title_blog = db.Column(db.String(300), nullable=False)
    
    json_file = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    update_date = db.Column(db.String(150), nullable=False)

    view_count = db.Column(db.String(100), nullable=True)
    favorite_count = db.Column(db.String(100), nullable=True)
    create_date = db.Column(db.DateTime(), nullable=False)
    modify_date = db.Column(db.DateTime(), nullable=True)



   

    
