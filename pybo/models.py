# models.py
from pybo import db
from sqlalchemy import PrimaryKeyConstraint, UniqueConstraint
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import DATETIME as MySQLDateTime
from datetime import datetime, timezone, timedelta
from sqlalchemy import event
from sqlalchemy.ext.associationproxy import association_proxy  # ← 추가
from sqlalchemy import CheckConstraint

# ─────────────────────────────────────────────────────────────
# ✅ 기준: "DB에도 KST 저장", 화면에서도 KST 그대로 사용
#    - MySQL DATETIME 은 타임존 정보를 저장하지 않으므로
#      파이썬에서 KST 시각을 생성(naive)해 넣는다.
# ─────────────────────────────────────────────────────────────
KST_TZ = timezone(timedelta(hours=9))

def kst_now_naive():
    """KST 현재 시각을 naive datetime으로 반환."""
    # 변경: KST 기준으로 DB에 넣기 위해 tzinfo 제거
    return datetime.now(KST_TZ).replace(tzinfo=None)

# 공통 테이블 옵션 (엔진/문자셋)
TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4"
}

# ─────────────────────────────────────────────────────────────
# 투표(조인) 테이블: 컴포지트 PK로 정규화
# ─────────────────────────────────────────────────────────────
class QuestionVoter(db.Model):
    __tablename__ = 'question_voter'
    __table_args__ = (
        PrimaryKeyConstraint('user_no', 'question_id', name='pk_question_voter'),
        TABLE_ARGS,
    )
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'), nullable=False)

class AnswerVoter(db.Model):
    __tablename__ = 'answer_voter'
    __table_args__ = (
        PrimaryKeyConstraint('user_no', 'answer_id', name='pk_answer_voter'),
        TABLE_ARGS,
    )
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)  # ✅ 유지: 올바른 FK
    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id', ondelete='CASCADE'), nullable=False)

# ─────────────────────────────────────────────────────────────
# Q/A/댓글
# ─────────────────────────────────────────────────────────────
class Question(db.Model):
    __tablename__ = 'question'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    subject = db.Column(db.String(201), nullable=False)
    content = db.Column(db.Text(), nullable=False)

    # 변경: server_default=func.now() → default=kst_now_naive / onupdate=kst_now_naive
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('question_set', passive_deletes=True))

    voter = db.relationship(
        'User',
        secondary='question_voter',
        backref=db.backref('question_voter_set', lazy='dynamic'),
        passive_deletes=True
    )

class Answer(db.Model):
    __tablename__ = 'answer'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'))
    question = db.relationship('Question', backref=db.backref('answer_set', passive_deletes=True))

    content = db.Column(db.Text(), nullable=False)

    # 변경: server_default 제거, 파이썬 KST 기본값 사용
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('answer_set', passive_deletes=True))

    voter = db.relationship(
        'User',
        secondary='answer_voter',
        backref=db.backref('answer_voter_set', lazy='dynamic'),
        passive_deletes=True
    )

class Comment(db.Model):
    __tablename__ = 'comment'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)
    user = db.relationship('User', backref=db.backref('comment_set', passive_deletes=True))

    content = db.Column(db.Text(), nullable=False)

    # 변경: server_default 제거, 파이썬 KST 기본값 사용
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

    question_id = db.Column(db.Integer, db.ForeignKey('question.id', ondelete='CASCADE'))
    question = db.relationship('Question', backref=db.backref('comment_set', passive_deletes=True))
    answer_id = db.Column(db.Integer, db.ForeignKey('answer.id', ondelete='CASCADE'))
    answer = db.relationship('Answer', backref=db.backref('comment_set', passive_deletes=True))

# ─────────────────────────────────────────────────────────────
# 사용자
# ─────────────────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'user'
    __table_args__ = TABLE_ARGS  # ← 수정: UniqueConstraint 제거

    no = db.Column(db.Integer, primary_key=True, autoincrement=True)
    userid = db.Column(db.String(150), nullable=False, unique=True, default='')  # ← unique=True 유지

    password = db.Column(db.String(200), nullable=False, default='')
    username = db.Column(db.String(150), nullable=False, default='')

    userimage = db.Column(db.String(300))
    email = db.Column(db.String(150), nullable=False, default='')
    phone = db.Column(db.String(150), nullable=False, default='')

    photo_1 = db.Column(db.String(500))
    photo_2 = db.Column(db.String(500))
    photo_3 = db.Column(db.String(500))

    company = db.Column(db.String(100))
    com_address = db.Column(db.String(500))
    tel_rep = db.Column(db.String(100))
    tel_dir = db.Column(db.String(100))
    fax = db.Column(db.String(100))
    homepage = db.Column(db.String(300))
    department = db.Column(db.String(150))
    position = db.Column(db.String(150))
    blood = db.Column(db.String(150))
    healthy = db.Column(db.String(150))
    age = db.Column(db.String(150))
    namecard = db.Column(db.String(150), nullable=False, default='0')
    address = db.Column(db.String(500))
    security = db.Column(db.String(100), nullable=False, default='0')

    # 변경: server_default 제거, 파이썬 KST 기본값 사용
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    # 관계
    namecards = db.relationship('NameCard', backref='user', cascade="all, delete", passive_deletes=True, lazy=True)
    files = db.relationship('FileUpload', backref='user', cascade="all, delete", passive_deletes=True, lazy=True)
    sharecards = db.relationship('ShareCard', backref='user', cascade="all, delete", passive_deletes=True, lazy=True)

# ─────────────────────────────────────────────────────────────
# 명함/파일/공유카드
# ─────────────────────────────────────────────────────────────
class NameCard(db.Model):
    __tablename__ = 'namecard'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete="CASCADE"), nullable=False)

    selected_photo = db.Column(db.String(500))
    department = db.Column(db.String(150))
    position = db.Column(db.String(150))
    username = db.Column(db.String(150))
    phone = db.Column(db.String(150))
    email = db.Column(db.String(150))
    company = db.Column(db.String(100))
    com_address = db.Column(db.String(500))
    tel_rep = db.Column(db.String(100))
    tel_dir = db.Column(db.String(100))
    fax = db.Column(db.String(100))
    homepage = db.Column(db.String(300))

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    def to_dict(self):
        def fmt(dt): return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None  # 저장 자체가 KST이므로 tz 변환 불필요
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
            "created_at": fmt(self.create_date),
            "updated_at": fmt(self.modify_date),
        }

class FileUpload(db.Model):
    __tablename__ = 'fileuploads'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)

    file_1 = db.Column(db.String(255))
    file_2 = db.Column(db.String(255))
    file_3 = db.Column(db.String(255))
    file_4 = db.Column(db.String(255))
    file_5 = db.Column(db.String(255))
    file_6 = db.Column(db.String(255))
    file_7 = db.Column(db.String(255))
    file_8 = db.Column(db.String(255))
    file_9 = db.Column(db.String(255))
    file_10 = db.Column(db.String(255))

    # 변경: server_default 제거 → KST 기본값
    uploaded_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)

    def to_dict(self):
        def fmt(dt): return dt.strftime("%Y-%m-%d %H:%M:%S") if dt else None
        return {
            "id": self.id,
            "user_id": self.user_id,
            "files": [
                self.file_1, self.file_2, self.file_3, self.file_4, self.file_5,
                self.file_6, self.file_7, self.file_8, self.file_9, self.file_10
            ],
            "uploaded_at": fmt(self.uploaded_at)
        }

class ShareCard(db.Model):
    __tablename__ = 'sharecard'
    __table_args__ = TABLE_ARGS

    no = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete="CASCADE"), nullable=False)
    namecard_id = db.Column(db.Integer, db.ForeignKey('namecard.id', ondelete="CASCADE"), nullable=False)
    fileupload_id = db.Column(db.Integer, db.ForeignKey('fileuploads.id', ondelete="CASCADE"), nullable=False)

    title = db.Column(db.String(500), nullable=False)
    content = db.Column(db.String(500), nullable=False)
    introduce = db.Column(db.String(500))
    vcf = db.Column(db.String(150))
    qrcode = db.Column(db.String(150))
    s_ncard = db.Column(db.String(150), nullable=False)
    custom_email = db.Column(db.String(150))
    s_file1 = db.Column(db.String(300))
    s_file2 = db.Column(db.String(300))
    s_file3 = db.Column(db.String(300))
    s_file4 = db.Column(db.String(300))
    s_file5 = db.Column(db.String(300))
    count = db.Column(db.String(100))

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    def to_dict(self):
        def fmt(dt): return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None
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
            "created_at": fmt(self.create_date),
            "updated_at": fmt(self.modify_date)
        }

# ─────────────────────────────────────────────────────────────
# 웰컴/QR
# ─────────────────────────────────────────────────────────────
class WelcomeData(db.Model):
    __tablename__ = 'welcomedata'
    __table_args__ = TABLE_ARGS

    no = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete="CASCADE"), nullable=False)
    namecard_id = db.Column(db.Integer, db.ForeignKey('namecard.id', ondelete="CASCADE"), nullable=False)
    share_card_id = db.Column(db.Integer, db.ForeignKey('sharecard.no', ondelete="CASCADE"), nullable=False)

    bmp_name = db.Column(db.String(200), nullable=False)
    bmp_path = db.Column(db.String(500), nullable=False)
    qr_code = db.Column(db.String(500))
    unique_id = db.Column(db.String(150))
    count = db.Column(db.String(150))

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    expires_at = db.Column(MySQLDateTime(fsp=0), nullable=False)

    def to_dict(self):
        def fmt(dt): return dt.strftime('%Y-%m-%d %H:%M:%S') if dt else None
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
            "created_at": fmt(self.create_date),
            "expires_at": fmt(self.expires_at)
        }

class QRCode(db.Model):
    __tablename__ = 'qr_code'
    __table_args__ = (
        UniqueConstraint('unique_id', name='uq_qr_unique_id'),
        TABLE_ARGS,
    )
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # 변경(권장): 참조 무결성 강화 – FK 추가
    user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False)        # ← 변경
    namecard_id = db.Column(db.Integer, db.ForeignKey('namecard.id', ondelete='CASCADE'), nullable=False) # ← 변경
    share_card_id = db.Column(db.Integer, db.ForeignKey('sharecard.no', ondelete='CASCADE'), nullable=False)  # ← 변경

    unique_id = db.Column(db.String(100), nullable=False)  # unique 제약은 위에서 부여

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    expires_at = db.Column(MySQLDateTime(fsp=0), nullable=False)

# ─────────────────────────────────────────────────────────────
# ESG/사용량
# ─────────────────────────────────────────────────────────────
class Co2Management(db.Model):
    __tablename__ = 'co2_management'
    __table_args__ = TABLE_ARGS

    no = db.Column(db.Integer, primary_key=True, autoincrement=True)
    use_date = db.Column(db.String(150), nullable=False)

    use_elec = db.Column(db.String(150))
    co2_elec = db.Column(db.String(150))
    use_water = db.Column(db.String(150))
    co2_water = db.Column(db.String(150))
    use_waste = db.Column(db.String(150))
    co2_waste = db.Column(db.String(150))
    use_vehicle = db.Column(db.String(150))
    co2_vehicle = db.Column(db.String(150))
    use_gas = db.Column(db.String(150))
    co2_gas = db.Column(db.String(150))
    use_total = db.Column(db.String(150))

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

class ElecUsage(db.Model):
    __tablename__ = 'elec_usage'
    __table_args__ = TABLE_ARGS

    no = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_no = db.Column(db.String(150), nullable=False)
    use_year = db.Column(db.String(150), nullable=False)
    acum_ref = db.Column(db.String(150), nullable=False)

    acum_jan = db.Column(db.String(150))
    use_jan = db.Column(db.String(150))
    acum_feb = db.Column(db.String(150))
    use_feb = db.Column(db.String(150))
    acum_mar = db.Column(db.String(150))
    use_mar = db.Column(db.String(150))
    acum_apr = db.Column(db.String(150))
    use_apr = db.Column(db.String(150))
    acum_may = db.Column(db.String(150))
    use_may = db.Column(db.String(150))
    acum_jun = db.Column(db.String(150))
    use_jun = db.Column(db.String(150))
    acum_jul = db.Column(db.String(150))
    use_jul = db.Column(db.String(150))
    acum_aug = db.Column(db.String(150))
    use_aug = db.Column(db.String(150))
    acum_sep = db.Column(db.String(150))
    use_sep = db.Column(db.String(150))
    acum_oct = db.Column(db.String(150))
    use_oct = db.Column(db.String(150))
    acum_nov = db.Column(db.String(150))
    use_nov = db.Column(db.String(150))
    acum_dec = db.Column(db.String(150))
    use_dec = db.Column(db.String(150))
    total = db.Column(db.String(150), nullable=False)

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

class VehicleUsage(db.Model):
    __tablename__ = 'vehicle_usage'
    __table_args__ = TABLE_ARGS

    no = db.Column(db.Integer, primary_key=True, autoincrement=True)
    car_no = db.Column(db.String(150), nullable=False)
    car_name = db.Column(db.String(150), nullable=False)
    car_fuel = db.Column(db.String(150), nullable=False)
    use_year = db.Column(db.String(150), nullable=False)
    acum_ref = db.Column(db.String(150), nullable=False)

    acum_jan = db.Column(db.String(150))
    use_jan = db.Column(db.String(150))
    acum_feb = db.Column(db.String(150))
    use_feb = db.Column(db.String(150))
    acum_mar = db.Column(db.String(150))
    use_mar = db.Column(db.String(150))
    acum_apr = db.Column(db.String(150))
    use_apr = db.Column(db.String(150))
    acum_may = db.Column(db.String(150))
    use_may = db.Column(db.String(150))
    acum_jun = db.Column(db.String(150))
    use_jun = db.Column(db.String(150))
    acum_jul = db.Column(db.String(150))
    use_jul = db.Column(db.String(150))
    acum_aug = db.Column(db.String(150))
    use_aug = db.Column(db.String(150))
    acum_sep = db.Column(db.String(150))
    use_sep = db.Column(db.String(150))
    acum_oct = db.Column(db.String(150))
    use_oct = db.Column(db.String(150))
    acum_nov = db.Column(db.String(150))
    use_nov = db.Column(db.String(150))
    acum_dec = db.Column(db.String(150))
    use_dec = db.Column(db.String(150))
    total = db.Column(db.String(150))

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

class WaterUsage(db.Model):
    __tablename__ = 'water_usage'
    __table_args__ = TABLE_ARGS

    no = db.Column(db.Integer, primary_key=True, autoincrement=True)
    room_no = db.Column(db.String(150), nullable=False)
    use_year = db.Column(db.String(150), nullable=False)
    acum_ref = db.Column(db.String(150), nullable=False)

    acum_jan = db.Column(db.String(150))
    use_jan = db.Column(db.String(150))
    acum_feb = db.Column(db.String(150))
    use_feb = db.Column(db.String(150))
    acum_mar = db.Column(db.String(150))
    use_mar = db.Column(db.String(150))
    acum_apr = db.Column(db.String(150))
    use_apr = db.Column(db.String(150))
    acum_may = db.Column(db.String(150))
    use_may = db.Column(db.String(150))
    acum_jun = db.Column(db.String(150))
    use_jun = db.Column(db.String(150))
    acum_jul = db.Column(db.String(150))
    use_jul = db.Column(db.String(150))
    acum_aug = db.Column(db.String(150))
    use_aug = db.Column(db.String(150))
    acum_sep = db.Column(db.String(150))
    use_sep = db.Column(db.String(150))
    acum_oct = db.Column(db.String(150))
    use_oct = db.Column(db.String(150))
    acum_nov = db.Column(db.String(150))
    use_nov = db.Column(db.String(150))
    acum_dec = db.Column(db.String(150))
    use_dec = db.Column(db.String(150))
    total = db.Column(db.String(150), nullable=False)

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

# ─────────────────────────────────────────────────────────────
# 캘린더/인증/컨텐츠
# ─────────────────────────────────────────────────────────────
class UserAuthorization(db.Model):
    __tablename__ = 'user_authorization'
    __table_args__ = TABLE_ARGS  # ← 수정: UniqueConstraint 제거

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    email = db.Column(db.String(300), nullable=False, unique=True)  # ← unique=True 유지
    password = db.Column(db.String(150), nullable=False)

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

class CalendarSchedule(db.Model):
    __tablename__ = 'calendar_schedule'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_authorization.id', ondelete='CASCADE'), nullable=False)

    content = db.Column(db.String(300), nullable=False)
    start_time = db.Column(db.String(150))
    end_time = db.Column(db.String(150))
    cal_date = db.Column(db.String(150))

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

    user = db.relationship('UserAuthorization', backref=db.backref('calendar_schedule', lazy=True, passive_deletes=True))

class RefreshToken(db.Model):
    __tablename__ = 'refresh_token'
    __table_args__ = TABLE_ARGS  # ← 수정: UniqueConstraint 제거

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user_authorization.id', ondelete='CASCADE'), nullable=False)
    token = db.Column(db.String(500), nullable=False, unique=True)  # ← unique=True 유지
    expires_at = db.Column(MySQLDateTime(fsp=0), nullable=False)

    user = db.relationship('UserAuthorization', backref=db.backref('refresh_tokens', lazy=True, passive_deletes=True))

# 컨텐츠 계열: YouTube / Image / News / Blog
class YoutubeURL(db.Model):
    __tablename__ = 'youtube_url'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    star_name = db.Column(db.String(100), nullable=False)
    type_video = db.Column(db.String(100), nullable=False)
    title_video = db.Column(db.String(300), nullable=False)

    json_file = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    update_date = db.Column(db.String(150), nullable=False)

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

class ImageData(db.Model):
    __tablename__ = 'image_data'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    key_word = db.Column(db.String(100), nullable=False)
    type_image = db.Column(db.String(100), nullable=False)
    title_image = db.Column(db.String(300), nullable=False)

    json_file = db.Column(db.String(200), nullable=False)
    thumbnail = db.Column(db.String(500), nullable=False)
    url = db.Column(db.String(500), nullable=False)

    bmp_42_mono = db.Column(db.String(200))
    bmp_42_3color = db.Column(db.String(200))
    bmp_37_4color = db.Column(db.String(200))
    bmp_29_mono = db.Column(db.String(200))
    bmp_29_3color = db.Column(db.String(200))
    bmp_29_4color = db.Column(db.String(200))
    bmp_file_1 = db.Column(db.String(200))
    bmp_file_2 = db.Column(db.String(200))

    sizewidth = db.Column(db.String(100), nullable=False)
    sizeheight = db.Column(db.String(100), nullable=False)
    update_date = db.Column(db.String(150), nullable=False)

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

class NewsData(db.Model):
    __tablename__ = 'news_data'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    star_name = db.Column(db.String(100), nullable=False)
    type_news = db.Column(db.String(100), nullable=False)
    title_new = db.Column(db.String(300), nullable=False)

    json_file = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    origin_url = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    update_date = db.Column(db.String(150), nullable=False)

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)

class BlogData(db.Model):
    __tablename__ = 'blog_data'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    star_name = db.Column(db.String(100), nullable=False)
    type_blog = db.Column(db.String(100), nullable=False)
    title_blog = db.Column(db.String(300), nullable=False)

    json_file = db.Column(db.String(200), nullable=False)
    url = db.Column(db.String(200), nullable=False)
    summary = db.Column(db.String(500), nullable=False)
    update_date = db.Column(db.String(150), nullable=False)

    # 변경: server_default 제거 → KST 기본값
    create_date = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    modify_date = db.Column(MySQLDateTime(fsp=0), onupdate=kst_now_naive)



# ─────────────────────────────────────────────────────────────
# E-INK 업로드 / 결재 레이아웃 / 결재선
# ─────────────────────────────────────────────────────────────

class SignLayout(db.Model):
    __tablename__ = 'sign_layouts'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    name = db.Column(db.String(100), nullable=False)

    # BASE 좌표계(1200x1600 권장)
    canvas_w = db.Column(db.Integer, nullable=False, default=1200)
    canvas_h = db.Column(db.Integer, nullable=False, default=1600)

    # 결재란 부모 박스(절대 좌표, BASE 기준)
    parent_x = db.Column(db.Integer, nullable=False)
    parent_y = db.Column(db.Integer, nullable=False)
    parent_w = db.Column(db.Integer, nullable=False)
    parent_h = db.Column(db.Integer, nullable=False)

    # 템플릿/슬롯/레이어 정의(JSON)
    tpl_json    = db.Column(db.JSON, nullable=False)   # {label_ratio, line_pos_ratio, font_size_px, ...}
    slots_json  = db.Column(db.JSON, nullable=False)   # [{x_rel,y_rel,w_rel,h_rel,role,label}, ...]
    layers_json = db.Column(db.JSON)                   # (옵션) stamp/validity 포함 전체 구조

    version = db.Column(db.Integer, nullable=False, default=1)
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='SET NULL'))

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    updated_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    owner = db.relationship('User', backref=db.backref('own_sign_layouts', lazy=True, passive_deletes=True))


class ApprovalRoute(db.Model):
    __tablename__ = 'approval_routes'
    __table_args__ = TABLE_ARGS

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    # ✅ 결재선 이름(필수)
    name = db.Column(db.String(100), nullable=False)

    # 작성자
    created_by = db.Column(
        db.Integer,
        db.ForeignKey('user.no', ondelete='SET NULL'),
        index=True,
        nullable=True
    )

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)

    # 작성자 관계
    creator = db.relationship(
        'User',
        backref=db.backref('approval_routes', lazy=True, passive_deletes=True),
        foreign_keys=[created_by],
        lazy='joined'
    )

    # ✅ 프록시 필드명 충돌 방지: creator_username 등으로 변경
    creator_userid     = association_proxy('creator', 'userid')
    creator_username   = association_proxy('creator', 'username')
    creator_department = association_proxy('creator', 'department')
    creator_position   = association_proxy('creator', 'position')
    creator_photo_1    = association_proxy('creator', 'photo_1')

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,  # ← 실 컬럼
            "created_by": self.created_by,
            "created_at": self.created_at,
            "creator": {
                "userid": self.creator_userid,
                "username": self.creator_username,
                "department": self.creator_department,
                "position": self.creator_position,
                "photo_1": self.creator_photo_1,
            },
        }






class ApprovalRouteStep(db.Model):
    __tablename__ = 'approval_route_steps'
    __table_args__ = (
        UniqueConstraint('route_id', 'step_order', name='uq_route_steporder'),
        TABLE_ARGS,
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    route_id = db.Column(db.BigInteger, db.ForeignKey('approval_routes.id', ondelete='CASCADE'), nullable=False, index=True)
    step_order = db.Column(db.Integer, nullable=False)
    role = db.Column(db.Enum('author', 'review', 'approve', 'review2', 'approve2', name='approval_role'), nullable=False)

    assignee_user_id  = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='SET NULL'), index=True)
    assignee_group_id = db.Column(db.Integer)
    sign_required     = db.Column(db.Boolean, nullable=False, default=True)

    assignee = db.relationship('User', foreign_keys=[assignee_user_id], lazy='joined')

    # 최신 User 필드 접근용 프록시
    assignee_userid     = association_proxy('assignee', 'userid')
    assignee_username   = association_proxy('assignee', 'username')
    assignee_department = association_proxy('assignee', 'department')
    assignee_position   = association_proxy('assignee', 'position')
    assignee_photo_1    = association_proxy('assignee', 'photo_1')

    # 스냅샷 컬럼
    assignee_userid_snapshot      = db.Column(db.String(150))
    assignee_username_snapshot    = db.Column(db.String(150))
    assignee_department_snapshot  = db.Column(db.String(150))
    assignee_position_snapshot    = db.Column(db.String(150))
    assignee_photo_1_snapshot     = db.Column(db.String(500))

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    updated_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)
    

# ─────────────────────────────────────────────────────────────
# 👇 자동 업데이트 👇
# ─────────────────────────────────────────────────────────────
@event.listens_for(ApprovalRouteStep, 'before_insert')
def _fill_step_assignee_snapshot(mapper, connection, target: 'ApprovalRouteStep'):
    # 담당자가 지정되어 있으면 그 시점의 값을 스냅샷으로 저장
    if target.assignee is not None:
        u = target.assignee
        target.assignee_userid_snapshot     = getattr(u, 'userid', None)
        target.assignee_username_snapshot   = getattr(u, 'username', None)
        target.assignee_department_snapshot = getattr(u, 'department', None)
        target.assignee_position_snapshot   = getattr(u, 'position', None)
        target.assignee_photo_1_snapshot    = getattr(u, 'photo_1', None)



class Upload(db.Model):
    __tablename__ = 'uploads'
    __table_args__ = (
        # ✅ ENUM 대신 VARCHAR + CHECK 제약으로 전환
        CheckConstraint(
            "target_dir IN ('uploads','proceed','checked','updates')",
            name='ck_upload_target_dir'
        ),
        CheckConstraint(
            "status IN ('draft','in_review','checked','approved','rejected')",
            name='ck_upload_status'
        ),
        TABLE_ARGS,
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    user_id   = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='SET NULL'))
    device_id = db.Column(db.String(64))

    orig_filename = db.Column(db.String(255), nullable=False)
    stored_path   = db.Column(db.String(500), nullable=False)

    # ✅ ENUM → VARCHAR(16) + CHECK
    target_dir = db.Column(db.String(16), nullable=False, default='proceed', index=True)

    need_approval = db.Column(db.Boolean, nullable=False, default=True)

    # ✅ ENUM → VARCHAR(16) + CHECK
    status = db.Column(db.String(16), nullable=False, default='draft', index=True)

    pages   = db.Column(db.Integer, default=1)
    width   = db.Column(db.Integer)
    height  = db.Column(db.Integer)
    mode    = db.Column(db.String(20))
    scale   = db.Column(db.String(20))
    percent = db.Column(db.Integer)
    rotate  = db.Column(db.Integer)

    route_id       = db.Column(db.BigInteger, db.ForeignKey('approval_routes.id', ondelete='SET NULL'))
    sign_layout_id = db.Column(db.BigInteger, db.ForeignKey('sign_layouts.id', ondelete='SET NULL'))

    route_snapshot_json  = db.Column(db.JSON)
    layout_snapshot_json = db.Column(db.JSON)
    metadata_json        = db.Column(db.JSON)

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    updated_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    user        = db.relationship('User', backref=db.backref('uploads', lazy=True, passive_deletes=True))
    route       = db.relationship('ApprovalRoute', backref=db.backref('uploads', lazy=True, passive_deletes=True))
    sign_layout = db.relationship('SignLayout', backref=db.backref('uploads', lazy=True, passive_deletes=True))



