"""document_info_refactor

Revision ID: 667442e620c8
Revises: 010666fea308
Create Date: 2025-12-10 13:32:31.952088

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '667442e620c8'
down_revision = '010666fea308'
branch_labels = None
depends_on = None


def upgrade():
    # uploads / upload_approval_steps 는 건드리지 않고,
    # sign_slots 만 uploads -> document_infos 참조로 교체한다.

    with op.batch_alter_table('sign_slots', schema=None) as batch_op:
        # 1) FK 먼저 제거 (이 FK가 uq_signslot_upload_slotkey 인덱스를 쓰고 있음)
        batch_op.drop_constraint(
            'fk_sign_slots_upload_id_uploads',
            type_='foreignkey',
        )

        # 2) 그 다음, 예전 유니크 인덱스 삭제
        batch_op.drop_index('uq_signslot_upload_slotkey')

        # 3) document_info 기반 인덱스/제약/FK 생성
        batch_op.create_index(
            'idx_signslot_doc',
            ['document_info_id', 'filled'],
            unique=False,
        )
        batch_op.create_index(
            'idx_signslot_doc_slot',
            ['document_info_id', 'slot_key'],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f('ix_sign_slots_document_info_id'),
            ['document_info_id'],
            unique=False,
        )

        batch_op.create_unique_constraint(
            'uq_signslot_doc_slotkey',
            ['document_info_id', 'slot_key'],
        )

        batch_op.create_foreign_key(
            batch_op.f('fk_sign_slots_document_info_id_document_infos'),
            'document_infos',
            ['document_info_id'],
            ['id'],
            ondelete='CASCADE',
        )

        # 4) 더 이상 필요없는 upload_id 컬럼 제거
        batch_op.drop_column('upload_id')


def downgrade():
    # 다시 uploads 를 참조하던 구조로 되돌리기
    with op.batch_alter_table('sign_slots', schema=None) as batch_op:
        # 1) upload_id 컬럼 복구
        batch_op.add_column(
            sa.Column('upload_id', mysql.BIGINT(), autoincrement=False, nullable=False)
        )

        # 2) document_infos FK 제거
        batch_op.drop_constraint(
            batch_op.f('fk_sign_slots_document_info_id_document_infos'),
            type_='foreignkey',
        )

        # 3) uploads FK 복구
        batch_op.create_foreign_key(
            'fk_sign_slots_upload_id_uploads',
            'uploads',
            ['upload_id'],
            ['id'],
            ondelete='CASCADE',
        )

        # 4) document_info 기반 유니크/인덱스 제거
        batch_op.drop_constraint('uq_signslot_doc_slotkey', type_='unique')
        batch_op.drop_index(batch_op.f('ix_sign_slots_document_info_id'))
        batch_op.drop_index('idx_signslot_doc_slot')
        batch_op.drop_index('idx_signslot_doc')

        # 5) 예전 유니크 인덱스 복구
        batch_op.create_index(
            'uq_signslot_upload_slotkey',
            ['upload_id', 'slot_key'],
            unique=True,
        )
