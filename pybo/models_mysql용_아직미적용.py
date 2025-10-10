# models.py (MySQL 기준)
from pybo import db
from sqlalchemy import UniqueConstraint, Index, text
from datetime import datetime, timezone, timedelta

# =========================================================
# KST 설정 (DB에는 tz정보 없는 naive DATETIME으로 KST 시각 저장)
# =========================================================
KST = timezone(timedelta(hours=9))
def now_kst():
    # MySQL DATETIME은 tz 정보를 저장하지 않으므로 KST naive로 저장
    return datetime.now(KST).replace(tzinfo=None)

# =========================================================
# 공통 테이블 옵션 (MySQL 전용)
# =========================================================
MYSQL_TABLE_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_general_ci",
}

# ─────────────────────────────────────────────────────────
# (기존) 예시: 기존 모델의 DateTime를 MySQL/KST 방식으로 교체
#   - timezone=True 제거
#   - default=now_kst / onupdate=now_kst 로 변경
#   - __table_args__ = MYSQL_TABLE_ARGS 추가(모든 테이블에 권장)
#   아래 User/NameCard/ShareCard 등으로 패턴 예시만 보여줌.
#   나머지 기존 테이블도 동일 패턴으로 바꾸면 됨.
# ─────────────────────────────────────────────────────────

class User(db.Model):
    __tablename__ = 'user'
    __table_args__ = (MYSQL_TABLE_ARGS,)

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

    # ✅ MySQL KST naive DATETIME
    create_date = db.Column(db.DateTime, nullable=False, default=now_kst)
    modify_date = db.Column(db.DateTime, nullable=False, default=now_kst, onupdate=now_kst)

    # 관계
    namecards = db.relationship('NameCard', backref='user', cascade="all, delete", lazy=True)
    files = db.relationship('FileUpload', backref='user', cascade="all, delete", lazy=True)
    sharecards = db.relationship('ShareCard', backref='user', cascade="all, delete", lazy=True)


class NameCard(db.Model):
    __tablename__ = 'namecard'
    __table_args__ = (MYSQL_TABLE_ARGS,)

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

    create_date = db.Column(db.DateTime, nullable=False, default=now_kst)
    modify_date = db.Column(db.DateTime, nullable=False, default=now_kst, onupdate=now_kst)

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


class ShareCard(db.Model):
    __tablename__ = 'sharecard'
    __table_args__ = (MYSQL_TABLE_ARGS,)

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

    create_date = db.Column(db.DateTime, nullable=False, default=now_kst)
    modify_date = db.Column(db.DateTime, nullable=False, default=now_kst, onupdate=now_kst)

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

# ─────────────────────────────────────────────────────────
# (기존 다른 모델들)
#  - Question/Answer/Comment/FileUpload/WelcomeData/QRCode/Co2Management/...
#  - DateTime 필드를 모두 아래 패턴처럼 바꿔주세요:
#      db.Column(db.DateTime, nullable=False, default=now_kst)
#      db.Column(db.DateTime, nullable=True, onupdate=now_kst)
#  - 각 클래스에 __table_args__ = (MYSQL_TABLE_ARGS,) 추가 권장
# ─────────────────────────────────────────────────────────


# ======================================================================
#                      ▼▼▼  E-Ink 폼/배포/권한 (신규) ▼▼▼
# ======================================================================

# ENUM 정의 (MySQL ENUM으로 생성)
from sqlalchemy.dialects.mysql import ENUM as MySQLEnum

DeviceRoleEnum = MySQLEnum('board', 'checklist', 'other', name='device_role')
BindingStatusEnum = MySQLEnum('DRAFT','QUEUED','SENT','APPLIED','FAILED','ARCHIVED', name='binding_status')
ACLSubjectEnum = MySQLEnum('user','group', name='acl_subject')
ACLRoleEnum = MySQLEnum('view','check','approve', name='acl_role')


class Form(db.Model):
    __tablename__ = 'forms'
    __table_args__ = (
        UniqueConstraint('sheet_no', name='uq_forms_sheet_no'),
        MYSQL_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sheet_no = db.Column(db.String(64), nullable=False)  # 사내 배포용 번호
    owner_user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='SET NULL'), nullable=True)
    title = db.Column(db.String(200), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=now_kst)

    # 최신 버전 바로 접근하고 싶다면 (선택)
    current_version_id = db.Column(db.Integer, db.ForeignKey('form_versions.id', ondelete='SET NULL'), nullable=True)


class FormVersion(db.Model):
    __tablename__ = 'form_versions'
    __table_args__ = (
        UniqueConstraint('form_id', 'version_no', name='uq_form_versions_form_version'),
        Index('ix_form_versions_form_created', 'form_id', 'created_at'),
        MYSQL_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    form_id = db.Column(db.Integer, db.ForeignKey('forms.id', ondelete='CASCADE'), nullable=False)
    version_no = db.Column(db.Integer, nullable=False)  # 1,2,3…
    json_file_path = db.Column(db.String(500), nullable=False)
    json_sha256 = db.Column(db.String(64), nullable=False)
    # (옵션) 조회 최적화를 위해 본문도 함께 저장 가능
    json_body = db.Column(db.JSON, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=now_kst)

    # 역참조 편의
    form = db.relationship('Form', backref=db.backref('versions', cascade='all, delete-orphan', lazy=True))


class Device(db.Model):
    __tablename__ = 'devices'
    __table_args__ = (
        UniqueConstraint('device_name', name='uq_devices_name'),
        MYSQL_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    device_name = db.Column(db.String(100), nullable=False)  # 예: "A20"
    install_location = db.Column(db.String(200), nullable=True)
    role = db.Column(DeviceRoleEnum, nullable=False, server_default='checklist')
    is_active = db.Column(db.Boolean, nullable=False, server_default=text('0'))
    capabilities = db.Column(db.JSON, nullable=True)  # {"panel":"1200x1600","palette":"6c_4bpp"}
    last_seen_at = db.Column(db.DateTime, nullable=True)

    created_at = db.Column(db.DateTime, nullable=False, default=now_kst)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=now_kst)


class DeviceBinding(db.Model):
    """
    장치에 특정 폼 버전을 배포한 기록(인스턴스).
    예: 장치 A20에 form X의 v3을 2025-09-25에 배포.
    """
    __tablename__ = 'device_bindings'
    __table_args__ = (
        Index('ix_device_bindings_device_published', 'device_id', 'published_at'),
        MYSQL_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)

    form_id = db.Column(db.Integer, db.ForeignKey('forms.id', ondelete='CASCADE'), nullable=False)
    form_version_id = db.Column(db.Integer, db.ForeignKey('form_versions.id', ondelete='CASCADE'), nullable=False)
    device_id = db.Column(db.Integer, db.ForeignKey('devices.id', ondelete='CASCADE'), nullable=False)

    # 스냅샷(선택): 배포시점 파일/해시/위치
    json_file_path = db.Column(db.String(500), nullable=True)
    json_sha256 = db.Column(db.String(64), nullable=True)
    location = db.Column(db.String(200), nullable=True)

    status = db.Column(BindingStatusEnum, nullable=False, server_default='DRAFT')
    created_at = db.Column(db.DateTime, nullable=False, default=now_kst)
    published_at = db.Column(db.DateTime, nullable=True)
    applied_at = db.Column(db.DateTime, nullable=True)

    # 관계
    form = db.relationship('Form', lazy=True)
    version = db.relationship('FormVersion', lazy=True)
    device = db.relationship('Device', lazy=True)


class FormACL(db.Model):
    """
    폼 접근 권한(사용자/그룹 단위)
    """
    __tablename__ = 'form_acl'
    __table_args__ = (
        UniqueConstraint('form_id', 'subject_type', 'subject_id', 'role', name='uq_form_acl'),
        MYSQL_TABLE_ARGS,
    )

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    form_id = db.Column(db.Integer, db.ForeignKey('forms.id', ondelete='CASCADE'), nullable=False)

    subject_type = db.Column(ACLSubjectEnum, nullable=False)  # user | group
    subject_id = db.Column(db.String(128), nullable=False)    # user.no 또는 그룹 식별자
    role = db.Column(ACLRoleEnum, nullable=False)             # view | check | approve

    created_at = db.Column(db.DateTime, nullable=False, default=now_kst)


class DeviceACL(db.Model):
    """
    디바이스 단위 사용자 권한 (최대 20명 제한은 트리거/애플리케이션에서 강제)
    """
    __tablename__ = 'device_acl'
    __table_args__ = (
        MYSQL_TABLE_ARGS,
    )

    device_id = db.Column(db.Integer, db.ForeignKey('devices.id', ondelete='CASCADE'), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.no', ondelete='CASCADE'), primary_key=True)
    created_at = db.Column(db.DateTime, nullable=False, default=now_kst)

    device = db.relationship('Device', lazy=True)
    user = db.relationship('User', lazy=True)


# ─────────────────────────────────────────────────────────
# (선택) 운영 편의를 위한 View 정의 (ORM이 아닌 순수 SQL로 생성)
#   work_sheet_list: 장치/위치/상태/파일/해시 등 한 번에 보이기
#   Alembic migration이나 초기 스크립트에서 아래 SQL 실행 권장
# ─────────────────────────────────────────────────────────
# MySQL:
# CREATE OR REPLACE VIEW work_sheet_list AS
# SELECT
#   b.id                 AS binding_id,
#   f.id                 AS form_id,
#   f.sheet_no,
#   v.id                 AS form_version_id,
#   v.version_no,
#   v.json_file_path,
#   v.json_sha256,
#   d.device_name,
#   COALESCE(b.location, d.install_location) AS location,
#   b.status,
#   v.created_at         AS version_created_at,
#   b.published_at,
#   b.applied_at
# FROM device_bindings b
# JOIN form_versions v ON b.form_version_id = v.id
# JOIN forms f         ON v.form_id = f.id
# JOIN devices d       ON b.device_id = d.id;


# ─────────────────────────────────────────────────────────
# (중요) 디바이스 ACL 20명 제한 트리거 (MySQL 8)
#   Alembic migration이나 초기 스크립트에서 실행
# ─────────────────────────────────────────────────────────
# DELIMITER $$
# CREATE TRIGGER trg_device_acl_limit
# BEFORE INSERT ON device_acl
# FOR EACH ROW
# BEGIN
#   IF (SELECT COUNT(*) FROM device_acl WHERE device_id = NEW.device_id) >= 20 THEN
#     SIGNAL SQLSTATE '45000'
#       SET MESSAGE_TEXT = 'This device already has 20 users';
#   END IF;
# END$$
# DELIMITER ;

