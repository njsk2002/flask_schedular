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



# ─────────────────────────────────────────────────────────────
# Upload: 새 워크플로우
#   - target_dir: in_review | checked | approved | upload
#   - status    : draft | in_review | checked | approved | rejected
#   - 즉시배포형은 처음부터 target_dir='upload', status='approved', need_approval=False
# ─────────────────────────────────────────────────────────────

class Upload(db.Model):
    __tablename__ = 'uploads'
    __table_args__ = (
        # 단계/상태 제약
        CheckConstraint(
                "target_dir IN ('in_review','checked','approved','uploads')",
                name='ck_upload_target_dir'
            ),
        CheckConstraint(
            "status IN ('draft','in_review','checked','approved','rejected','uploads')",
            name='ck_upload_status'
            ),

        # 업로드 큐/리스트 화면 최적화 인덱스
        db.Index('idx_upload_queue', 'user_id', 'target_dir', 'status', 'created_at'),
        TABLE_ARGS,
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    user_id   = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='SET NULL'))
    device_id = db.Column(db.String(64))   # (옵션) 특정 디바이스를 미리 지정 가능

    # 원본 파일명 / 저장 경로(상대 또는 절대)
    orig_filename = db.Column(db.String(255), nullable=False)
    stored_path   = db.Column(db.String(500), nullable=False)  # 예: "<userid>/in_review/..."

    # 단계 디렉토리(기본: in_review)
    target_dir = db.Column(db.String(16), nullable=False, default='in_review', index=True)

    need_approval = db.Column(db.Boolean, nullable=False, default=True)

    # 상태
    status = db.Column(db.String(16), nullable=False, default='in_review', index=True)

    # 렌더 파라미터(옵션)
    pages   = db.Column(db.Integer, default=1)
    width   = db.Column(db.Integer)
    height  = db.Column(db.Integer)
    mode    = db.Column(db.String(20))
    scale   = db.Column(db.String(20))
    percent = db.Column(db.Integer)
    rotate  = db.Column(db.Integer)

    # 결재선/레이아웃 스냅샷
    route_id       = db.Column(db.BigInteger, db.ForeignKey('approval_routes.id', ondelete='SET NULL'))
    sign_layout_id = db.Column(db.BigInteger, db.ForeignKey('sign_layouts.id', ondelete='SET NULL'))

    route_snapshot_json  = db.Column(db.JSON)
    layout_snapshot_json = db.Column(db.JSON)
    metadata_json        = db.Column(db.JSON)  # 업로드 단계 메타(경량)

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    updated_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    user        = db.relationship('User', backref=db.backref('uploads', lazy=True, passive_deletes=True))
    route       = db.relationship('ApprovalRoute', backref=db.backref('uploads', lazy=True, passive_deletes=True))
    sign_layout = db.relationship('SignLayout', backref=db.backref('uploads', lazy=True, passive_deletes=True))

    # Upload 클래스 하단 관계 추가(이미 backref로도 접근 가능하지만 명시)
    # approval_steps = db.relationship('UploadApprovalStep', backref='upload',
    #                                 cascade="all, delete", passive_deletes=True, lazy=True)
    # sign_slots     = db.relationship('SignSlot', backref='upload',
    #                                 cascade="all, delete", passive_deletes=True, lazy=True)
    # device_jobs    = db.relationship('DeviceJob', backref='upload',
    #                                 cascade="all, delete", passive_deletes=True, lazy=True)




# ─────────────────────────────────────────────────────────────
# 업로드 단위 결재 열(최대 5열)
# 템플릿(ApprovalRoute/ApprovalRouteStep)과 별개로, 해당 업로드에 귀속되는 인스턴스를 저장
# ─────────────────────────────────────────────────────────────

class UploadApprovalStep(db.Model):
    __tablename__ = 'upload_approval_steps'
    __table_args__ = (
        db.UniqueConstraint('upload_id', 'col_index', name='uq_uapproval_col'),
        db.Index('idx_uapproval_upload', 'upload_id', 'status'),
        TABLE_ARGS,
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    upload_id = db.Column(db.BigInteger, db.ForeignKey('uploads.id', ondelete='CASCADE'), nullable=False, index=True)

    # 1~5 열
    col_index = db.Column(db.Integer, nullable=False)  # 1..5

    # 단계(작성/검토/승인) — 화면 용어 그대로 Enum 구성
    step_type = db.Column(db.Enum('작성','검토','승인', name='approval_step_type'), nullable=False)

    # 스냅샷(그 시점의 부서/이름/사진 등)
    dept_snapshot      = db.Column(db.String(150))
    userid_snapshot    = db.Column(db.String(150))
    username_snapshot  = db.Column(db.String(150))
    photo_1_snapshot   = db.Column(db.String(500))

    # 진행 상태
    status = db.Column(db.Enum('pending','signed', name='approval_sign_status'), nullable=False, default='pending')
    signed_by_user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='SET NULL'))
    signed_at         = db.Column(MySQLDateTime(fsp=0))

    # (옵션) 합성된 사인 이미지/스탬프 저장 경로
    sign_asset_path = db.Column(db.String(500))

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    updated_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    upload = db.relationship('Upload', backref=db.backref('approval_steps', lazy=True, passive_deletes=True))
    signed_by = db.relationship('User', foreign_keys=[signed_by_user_id], lazy='joined')


# ─────────────────────────────────────────────────────────────
# 서명 슬롯(최대 30칸, 부분업데이트 좌표용)
# ─────────────────────────────────────────────────────────────

class SignSlot(db.Model):
    __tablename__ = 'sign_slots'
    __table_args__ = (
        db.UniqueConstraint('upload_id', 'slot_key', name='uq_signslot_upload_slotkey'),
        db.Index('idx_signslot_upload', 'upload_id', 'filled'),
        db.Index('idx_signslot_user', 'target_user_id', 'filled'),
        db.Index('idx_signslot_upload_slot', 'upload_id', 'slot_key'),
        TABLE_ARGS,
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    upload_id = db.Column(db.BigInteger, db.ForeignKey('uploads.id', ondelete='CASCADE'), nullable=False, index=True)

    # 프론트 레이어 id와 1:1 매핑(예: 'S001')
    slot_key = db.Column(db.String(64), nullable=False)

    mode = db.Column(db.Enum('check','photo', name='sign_slot_mode'), nullable=False)  # ✔ or photo
    target_user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='SET NULL'))

    label = db.Column(db.String(150))

    # BASE 좌표(1200x1600) 저장 — 부분업데이트 시 디바이스 픽셀로 변환
    x = db.Column(db.Integer, nullable=False)
    y = db.Column(db.Integer, nullable=False)
    w = db.Column(db.Integer, nullable=False)
    h = db.Column(db.Integer, nullable=False)

    # 채움 상태
    filled       = db.Column(db.Boolean, nullable=False, default=False)
    filled_by_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='SET NULL'))
    filled_at    = db.Column(MySQLDateTime(fsp=0))

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    updated_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    upload      = db.relationship('Upload', backref=db.backref('sign_slots', lazy=True, passive_deletes=True))
    target_user = db.relationship('User', foreign_keys=[target_user_id], lazy='joined')
    filled_by   = db.relationship('User', foreign_keys=[filled_by_id], lazy='joined')


# ─────────────────────────────────────────────────────────────
# E-INK: 디바이스 / 자산 / 게시(스케줄)
#   - upload 단계에서 확정된 장치용 산출물(.bin/.meta) 이력 관리
# ─────────────────────────────────────────────────────────────

class EInkDevice(db.Model):
    __tablename__ = 'eink_device'
    __table_args__ = (
        UniqueConstraint('user_no', 'device_id', name='uq_eink_device_user_device'),
        TABLE_ARGS,
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    # PK FK 한 가닥만 유지
    user_no = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'),
                        nullable=False, index=True)

    # (선택) 캐시용: 경로에 바로 쓰기 위해 userid 문자열 보관(UNIQUE FK 아님)
    user_userid = db.Column(db.String(64), nullable=True, index=True)

    device_id   = db.Column(db.String(64), nullable=False)
    device_name = db.Column(db.String(128))

    panel_res = db.Column(db.String(16), nullable=False)
    bpp       = db.Column(db.Integer, nullable=False, default=4)
    cap       = db.Column(db.String(16), nullable=False, default='BWR')

    supports_partial = db.Column(db.Boolean, nullable=False, default=True)
    supports_rle     = db.Column(db.Boolean, nullable=False, default=True)
    supports_zlib    = db.Column(db.Boolean, nullable=False, default=True)

    current_ver = db.Column(db.BigInteger, nullable=False, default=0)
    last_seen   = db.Column(MySQLDateTime(fsp=0))

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    updated_at = db.Column(MySQLDateTime(fsp=0), nullable=False,
                           default=kst_now_naive, onupdate=kst_now_naive)

    user = db.relationship('User', foreign_keys=[user_no],
                           backref=db.backref('eink_devices', lazy=True, passive_deletes=True))



# ─────────────────────────────────────────────────────────────
# 디바이스 전송 잡(전체/부분 공용 큐)
# 결재 완료 후 full 업데이트, 서명 수행 시 partial 업데이트를 하나의 큐로 관리
# ─────────────────────────────────────────────────────────────

class DeviceJob(db.Model):
    __tablename__ = 'device_jobs'
    __table_args__ = (
        db.Index('idx_djob_dev_status', 'device_id', 'status'),
        db.Index('idx_djob_type_status', 'job_type', 'status'),
        TABLE_ARGS,
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    user_id   = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False, index=True)
    device_id = db.Column(db.String(64), nullable=False, index=True)

    job_type = db.Column(db.Enum('full','partial', name='device_job_type'), nullable=False)
    status   = db.Column(db.Enum('queued','sending','done','error', name='device_job_status'), nullable=False, default='queued')

    # 소스 추적(옵션)
    src_upload_id = db.Column(db.BigInteger, db.ForeignKey('uploads.id', ondelete='SET NULL'))
    src_asset_id  = db.Column(db.BigInteger, db.ForeignKey('eink_asset.id', ondelete='SET NULL'))

    # 페이로드 경로(상대경로 권장)
    payload_relpath = db.Column(db.String(512))

    # 부분업데이트용 디바이스 픽셀 좌표(전체는 NULL)
    region_x = db.Column(db.Integer)
    region_y = db.Column(db.Integer)
    region_w = db.Column(db.Integer)
    region_h = db.Column(db.Integer)

    priority    = db.Column(db.Integer, nullable=False, default=10)
    error_msg   = db.Column(db.String(255))

    created_at  = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    started_at  = db.Column(MySQLDateTime(fsp=0))
    finished_at = db.Column(MySQLDateTime(fsp=0))

    user  = db.relationship('User', backref=db.backref('device_jobs', lazy=True, passive_deletes=True))
    upload= db.relationship('Upload', backref=db.backref('device_jobs', lazy=True, passive_deletes=True))
    asset = db.relationship('EInkAsset', backref=db.backref('device_jobs', lazy=True, passive_deletes=True))



class EInkAsset(db.Model):
    """
    upload 단계에서 확정된 장치용 산출물(.bin/.meta)을 이력으로 저장
    """
    __tablename__ = 'eink_asset'
    __table_args__ = (
        # 조회/스케줄 최적화
        db.Index('idx_easset_user_dev_ver', 'user_id', 'device_id', 'ver'),
        db.Index('idx_easset_sched', 'user_id', 'device_id', 'expect_post_time', 'expire_time'),
        # 동일 user-device 내 ver 유일 보장
        UniqueConstraint('user_id', 'device_id', 'ver', name='uq_easset_user_dev_ver'),
        # 값 제약
        CheckConstraint('width  > 0',   name='ck_easset_width_pos'),
        CheckConstraint('height > 0',   name='ck_easset_height_pos'),
        CheckConstraint('raw_len   > 0', name='ck_easset_rawlen_pos'),
        CheckConstraint('total_len > 0', name='ck_easset_totallen_pos'),
        TABLE_ARGS,
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    user_id   = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False, index=True)
    device_id = db.Column(db.String(64), nullable=False, index=True)  # 예: "E03"

    # (옵션) 어느 Upload에서 파생되었는지 추적
    upload_id = db.Column(db.BigInteger, db.ForeignKey('uploads.id', ondelete='SET NULL'))

    # 렌더 결과 스펙
    width  = db.Column(db.Integer, nullable=False)
    height = db.Column(db.Integer, nullable=False)
    mode   = db.Column(db.String(16), nullable=False)
    bpp    = db.Column(db.Integer, nullable=False, default=4)
    ver    = db.Column(db.BigInteger, nullable=False)
    uuid   = db.Column(db.String(36), nullable=False)

    # 파일 경로 (userid 루트 기준 상대경로)
    bin_relpath  = db.Column(db.String(512), nullable=False)    # "upload/E03/renders/....bin"
    meta_relpath = db.Column(db.String(512), nullable=False)    # "upload/E03/renders/....meta.json"

    # 무결성/용량
    raw_len   = db.Column(db.Integer, nullable=False)
    total_len = db.Column(db.Integer, nullable=False)
    crc32_le  = db.Column(db.String(8), nullable=False)         # 소문자 8-hex

    # 델타 가능 힌트
    asset_partial_ready = db.Column(db.Boolean, nullable=False, default=False)

    # (선택) 메타 JSON 전체 스냅샷
    meta_json = db.Column(db.JSON)

    # 스케줄
    expect_post_time   = db.Column(MySQLDateTime(fsp=0))
    posting_period_sec = db.Column(db.Integer)
    expire_time        = db.Column(MySQLDateTime(fsp=0))

    # 승인/결재 결과 스냅샷(최종본 기준)
    need_approval  = db.Column(db.Boolean, nullable=False, default=False)
    final_approval = db.Column(db.Boolean, nullable=False, default=True)
    route_id       = db.Column(db.BigInteger, db.ForeignKey('approval_routes.id', ondelete='SET NULL'))

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    updated_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    user   = db.relationship('User', backref=db.backref('eink_assets', lazy=True, passive_deletes=True))
    route  = db.relationship('ApprovalRoute', backref=db.backref('eink_assets', lazy=True, passive_deletes=True))
    upload = db.relationship('Upload', backref=db.backref('derived_assets', lazy=True, passive_deletes=True))


class EInkPosting(db.Model):
    """
    디바이스에 어떤 자산을 언제 보여줄지(현재/미래) 상태 관리
    """
    __tablename__ = 'eink_posting'
    __table_args__ = (
        db.Index('idx_eposting_window', 'user_id', 'device_id', 'start_time', 'end_time'),
        CheckConstraint(
            '(end_time IS NULL) OR (start_time IS NULL) OR (start_time < end_time)',
            name='ck_eposting_time_range'
        ),
        TABLE_ARGS,
    )

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)

    user_id   = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), nullable=False, index=True)
    device_id = db.Column(db.String(64), nullable=False, index=True)
    asset_id  = db.Column(db.BigInteger, db.ForeignKey('eink_asset.id', ondelete='CASCADE'), nullable=False, index=True)

    status = db.Column(
        db.Enum('scheduled','active','expired','canceled','failed', name='eink_posting_status'),
        nullable=False, default='scheduled'
    )
    start_time = db.Column(MySQLDateTime(fsp=0))
    end_time   = db.Column(MySQLDateTime(fsp=0))
    reason     = db.Column(db.String(255))

    created_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive)
    updated_at = db.Column(MySQLDateTime(fsp=0), nullable=False, default=kst_now_naive, onupdate=kst_now_naive)

    user  = db.relationship('User', backref=db.backref('eink_postings', lazy=True, passive_deletes=True))
    asset = db.relationship('EInkAsset', backref=db.backref('postings', lazy=True, passive_deletes=True))


# ─────────────────────────────────────────────────────────────
# 훅/헬퍼
# ─────────────────────────────────────────────────────────────

@event.listens_for(EInkAsset, 'before_insert')
def _fill_expire_time(mapper, connection, target: 'EInkAsset'):
    """
    posting_period_sec가 있으면 expire_time 자동 계산.
    (형의 기준: DB에도 KST 저장이므로 KST naive 그대로 계산)
    """
    if target.expect_post_time and target.posting_period_sec and not target.expire_time:
        target.expire_time = target.expect_post_time + timedelta(seconds=int(target.posting_period_sec))


def create_immediate_upload_record(
    *, user_id:int, device_id:str,
    orig_filename:str, stored_relpath:str,
    width:int, height:int, mode:str, bpp:int=4
) -> Upload:
    """
    즉시배포형: 곧바로 upload/ 에 저장하고 Upload 레코드를 upload 상태로 만든다.
    이어서 파일시스템에서 bin/meta 생성 → EInkAsset/EInkPosting 생성은 서비스 계층에서 수행.
    """
    rec = Upload(
        user_id=user_id,
        device_id=device_id,
        orig_filename=orig_filename,
        stored_path=stored_relpath,     # 예: "<userid>/upload/E03/assets/... 또는 renders/..."
        target_dir='uploads',
        status='approved',
        need_approval=False,
        width=width, height=height, mode=mode #bpp=bpp
    )
    db.session.add(rec)
    return rec




