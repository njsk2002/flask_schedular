"""empty message

Revision ID: 5edbb8d06335
Revises: 8984abddf618
Create Date: 2025-02-13 09:55:15.303282

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5edbb8d06335'
down_revision = '8984abddf618'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('welcomedata',
    sa.Column('no', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('namecard_id', sa.Integer(), nullable=False),
    sa.Column('share_card_id', sa.Integer(), nullable=False),
    sa.Column('bmp_name', sa.String(length=200), nullable=False),
    sa.Column('bmp_path', sa.String(length=500), nullable=False),
    sa.Column('qr_code', sa.String(length=500), nullable=True),
    sa.Column('unique_id', sa.String(length=150), nullable=True),
    sa.Column('qrcode', sa.String(length=150), nullable=True),
    sa.Column('count', sa.String(length=150), nullable=True),
    sa.Column('create_date', sa.DateTime(timezone=True), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.ForeignKeyConstraint(['namecard_id'], ['namecard.id'], name=op.f('fk_welcomedata_namecard_id_namecard'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['share_card_id'], ['sharecard.no'], name=op.f('fk_welcomedata_share_card_id_sharecard'), ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['user.no'], name=op.f('fk_welcomedata_user_id_user'), ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('no', name=op.f('pk_welcomedata'))
    )
    with op.batch_alter_table('qr_code', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column('namecard_id', sa.Integer(), nullable=False))
        batch_op.add_column(sa.Column('share_card_id', sa.Integer(), nullable=False))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('qr_code', schema=None) as batch_op:
        batch_op.drop_column('share_card_id')
        batch_op.drop_column('namecard_id')
        batch_op.drop_column('user_id')

    op.drop_table('welcomedata')
    # ### end Alembic commands ###
