"""empty message

Revision ID: bdceb7a19120
Revises: 0338dc092ac5
Create Date: 2025-10-13 14:57:50.592660

"""
# migrations/versions/bdceb7a19120_.py
# migrations/versions/bdceb7a19120_.py
from alembic import op
import sqlalchemy as sa

revision = "bdceb7a19120"
down_revision = "0338dc092ac5"
branch_labels = None
depends_on = None


def _exec(sql, **params):
    bind = op.get_bind()
    print(f"[alembic] SQL> {sql}  {params if params else ''}")
    return bind.execute(sa.text(sql), params)


def _exists_col(table, col):
    r = _exec("""
        SELECT COUNT(*) AS cnt
        FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :t
          AND COLUMN_NAME = :c
    """, t=table, c=col).scalar()
    return bool(r)


def _fk_names_on_cols(table, cols):
    rows = _exec("""
        SELECT CONSTRAINT_NAME
        FROM information_schema.KEY_COLUMN_USAGE
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :t
          AND COLUMN_NAME IN :cols
          AND REFERENCED_TABLE_NAME IS NOT NULL
    """, t=table, cols=tuple(cols)).fetchall()
    return [r[0] for r in rows]


def _unique_exists(table, uq_name, colset):
    # 1) 같은 이름의 UNIQUE 가 있는지
    r = _exec("""
        SELECT COUNT(*) FROM information_schema.TABLE_CONSTRAINTS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME = :t
          AND CONSTRAINT_NAME = :n
          AND CONSTRAINT_TYPE = 'UNIQUE'
    """, t=table, n=uq_name).scalar()
    if r:
        return True
    # 2) 동일 컬럼셋 UNIQUE 가 있는지
    want = ",".join(colset)
    for name, cols in _exec("""
        SELECT k.CONSTRAINT_NAME,
               GROUP_CONCAT(k.COLUMN_NAME ORDER BY k.ORDINAL_POSITION) AS cols
        FROM information_schema.TABLE_CONSTRAINTS tc
        JOIN information_schema.KEY_COLUMN_USAGE k
          ON k.TABLE_SCHEMA = tc.TABLE_SCHEMA
         AND k.TABLE_NAME = tc.TABLE_NAME
         AND k.CONSTRAINT_NAME = tc.CONSTRAINT_NAME
        WHERE tc.TABLE_SCHEMA = DATABASE()
          AND tc.TABLE_NAME = :t
          AND tc.CONSTRAINT_TYPE = 'UNIQUE'
        GROUP BY k.CONSTRAINT_NAME
    """, t=table).fetchall():
        if cols == want:
            return True
    return False


def upgrade():
    print("[alembic] === START upgrade bdceb7a19120 ===")

    # 0) 레거시 FK(user_id) 제거(있으면)
    for fk_name in _fk_names_on_cols("eink_device", ["user_id"]):
        _exec(f"ALTER TABLE eink_device DROP FOREIGN KEY `{fk_name}`")

    # 1) user_no 컬럼 보장: 없으면 추가, 있으면 NOT NULL로 보정
    if not _exists_col("eink_device", "user_no"):
        print("[alembic] add column eink_device.user_no (INT NOT NULL)")
        op.add_column("eink_device", sa.Column("user_no", sa.Integer(), nullable=False))
    else:
        print("[alembic] column user_no already exists → ensure NOT NULL")
        _exec("ALTER TABLE eink_device MODIFY COLUMN user_no INT NOT NULL")

    # 2) user_userid 캐시 컬럼: 없을 때만 추가 (VARCHAR(64) NULL)
    if not _exists_col("eink_device", "user_userid"):
        print("[alembic] add column eink_device.user_userid (VARCHAR(64) NULL)")
        op.add_column("eink_device", sa.Column("user_userid", sa.String(64), nullable=True))
    else:
        print("[alembic] column user_userid already exists (skip)")

    # 3) FK(user_no -> user.no) 없으면 생성
    if not _fk_names_on_cols("eink_device", ["user_no"]):
        print("[alembic] create FK fk_eink_device_user (user_no -> user.no)")
        _exec("""
            ALTER TABLE eink_device
            ADD CONSTRAINT fk_eink_device_user
            FOREIGN KEY (user_no) REFERENCES user(no)
            ON DELETE CASCADE
        """)
    else:
        print("[alembic] FK on user_no already exists (skip)")

    # 4) UNIQUE(user_no, device_id) 없으면 생성
    if not _unique_exists("eink_device", "uq_eink_device_user_device", ["user_no", "device_id"]):
        print("[alembic] create UNIQUE uq_eink_device_user_device (user_no, device_id)")
        _exec("""
            ALTER TABLE eink_device
            ADD CONSTRAINT uq_eink_device_user_device
            UNIQUE KEY (user_no, device_id)
        """)
    else:
        print("[alembic] UNIQUE (user_no, device_id) already exists (skip)")

    # 5) 레거시 user_id 컬럼 제거(있으면)
    if _exists_col("eink_device", "user_id"):
        print("[alembic] drop legacy column eink_device.user_id")
        _exec("ALTER TABLE eink_device DROP COLUMN user_id")

    print("[alembic] ✅ upgrade finished.")


def downgrade():
    # UNIQUE 제거
    if _unique_exists("eink_device", "uq_eink_device_user_device", ["user_no", "device_id"]):
        _exec("ALTER TABLE eink_device DROP INDEX uq_eink_device_user_device")
    # FK 제거
    for fk_name in _fk_names_on_cols("eink_device", ["user_no"]):
        _exec(f"ALTER TABLE eink_device DROP FOREIGN KEY `{fk_name}`")
    # 보조 컬럼 제거
    if _exists_col("eink_device", "user_userid"):
        _exec("ALTER TABLE eink_device DROP COLUMN user_userid")
    # user_no 는 남겨도 되지만, 롤백이라면 제거
    if _exists_col("eink_device", "user_no"):
        _exec("ALTER TABLE eink_device DROP COLUMN user_no")
    print("[alembic] ✅ downgrade finished.")
