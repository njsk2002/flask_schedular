"""empty message

Revision ID: d0f109f6dfa4
Revises: 667442e620c8
Create Date: 2025-12-10 13:46:01.650000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = 'd0f109f6dfa4'
down_revision = '667442e620c8'
branch_labels = None
depends_on = None


def upgrade():
    # 업로드/승인 스텝 레거시 테이블 정리
    # 인덱스는 DROP TABLE 시 자동으로 같이 삭제되므로
    # 굳이 drop_index 를 할 필요가 없다.

    # 1) 자식 테이블 먼저 삭제 (uploads 를 참조할 수도 있으므로)
    op.drop_table('upload_approval_steps')

    # 2) 부모 테이블 삭제
    op.drop_table('uploads')


def downgrade():
    # 필요하다면 리버스 시 테이블을 재생성
    # (기존 667442e620c8 의 downgrade 부분에서 테이블 정의 복사)

    op.create_table(
        'uploads',
        sa.Column('id', mysql.BIGINT(), autoincrement=True, nullable=False),
        sa.Column('user_id', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('device_id', mysql.VARCHAR(length=64), nullable=True),
        sa.Column('orig_filename', mysql.VARCHAR(length=255), nullable=False),
        sa.Column('stored_path', mysql.VARCHAR(length=500), nullable=False),
        sa.Column('target_dir', mysql.VARCHAR(length=16), server_default=sa.text("'proceed'"), nullable=False),
        sa.Column('need_approval', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False),
        sa.Column('status', mysql.VARCHAR(length=16), server_default=sa.text("'draft'"), nullable=False),
        sa.Column('pages', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('width', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('height', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('mode', mysql.VARCHAR(length=20), nullable=True),
        sa.Column('scale', mysql.VARCHAR(length=20), nullable=True),
        sa.Column('percent', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('rotate', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('route_id', mysql.BIGINT(), autoincrement=False, nullable=True),
        sa.Column('sign_layout_id', mysql.BIGINT(), autoincrement=False, nullable=True),
        sa.Column('route_snapshot_json', mysql.JSON(), nullable=True),
        sa.Column('layout_snapshot_json', mysql.JSON(), nullable=True),
        sa.Column('metadata_json', mysql.JSON(), nullable=True),
        sa.Column('created_at', mysql.DATETIME(), nullable=False),
        sa.Column('updated_at', mysql.DATETIME(), nullable=False),
        sa.Column('doc_name', mysql.VARCHAR(length=200), nullable=True),
        sa.Column('need_stamp', mysql.TINYINT(display_width=1), autoincrement=False, nullable=False),
        sa.Column('expire_time', mysql.DATETIME(), nullable=True),
        sa.Column('final_doc_relpath', mysql.VARCHAR(length=500), nullable=True),
        sa.ForeignKeyConstraint(['route_id'], ['approval_routes.id'], name='fk_uploads_route_id_approval_routes', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['sign_layout_id'], ['sign_layouts.id'], name='fk_uploads_sign_layout_id_sign_layouts', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['user_id'], ['user.no'], name='fk_uploads_user_id_user', ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_default_charset='utf8mb4',
        mysql_engine='InnoDB'
    )
    with op.batch_alter_table('uploads', schema=None) as batch_op:
        batch_op.create_index('ix_uploads_target_dir', ['target_dir'], unique=False)
        batch_op.create_index('ix_uploads_status', ['status'], unique=False)
        batch_op.create_index('idx_upload_queue', ['user_id', 'target_dir', 'status', 'created_at'], unique=False)

    op.create_table(
        'upload_approval_steps',
        sa.Column('id', mysql.BIGINT(), autoincrement=True, nullable=False),
        sa.Column('upload_id', mysql.BIGINT(), autoincrement=False, nullable=False),
        sa.Column('col_index', mysql.INTEGER(), autoincrement=False, nullable=False),
        sa.Column('step_type', mysql.ENUM('작성', '검토', '승인'), nullable=False),
        sa.Column('dept_snapshot', mysql.VARCHAR(length=150), nullable=True),
        sa.Column('userid_snapshot', mysql.VARCHAR(length=150), nullable=True),
        sa.Column('username_snapshot', mysql.VARCHAR(length=150), nullable=True),
        sa.Column('photo_1_snapshot', mysql.VARCHAR(length=500), nullable=True),
        sa.Column('status', mysql.ENUM('pending', 'signed'), nullable=False),
        sa.Column('signed_by_user_id', mysql.INTEGER(), autoincrement=False, nullable=True),
        sa.Column('signed_at', mysql.DATETIME(), nullable=True),
        sa.Column('sign_asset_path', mysql.VARCHAR(length=500), nullable=True),
        sa.Column('created_at', mysql.DATETIME(), nullable=False),
        sa.Column('updated_at', mysql.DATETIME(), nullable=False),
        sa.ForeignKeyConstraint(['signed_by_user_id'], ['user.no'], name='fk_upload_approval_steps_signed_by_user_id_user', ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['upload_id'], ['uploads.id'], name='fk_upload_approval_steps_upload_id_uploads', ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        mysql_collate='utf8mb4_0900_ai_ci',
        mysql_default_charset='utf8mb4',
        mysql_engine='InnoDB'
    )
    with op.batch_alter_table('upload_approval_steps', schema=None) as batch_op:
        batch_op.create_index('uq_uapproval_col', ['upload_id', 'col_index'], unique=True)
        batch_op.create_index('ix_upload_approval_steps_upload_id', ['upload_id'], unique=False)
        batch_op.create_index('idx_uapproval_upload', ['upload_id', 'status'], unique=False)
