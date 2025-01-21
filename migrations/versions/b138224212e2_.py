"""empty message

Revision ID: b138224212e2
Revises: 7a3113c84e97
Create Date: 2025-01-21 10:00:45.706246

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b138224212e2'
down_revision = '7a3113c84e97'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('NaverData', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sizewidth', sa.String(length=100), nullable=False))
        batch_op.drop_column('sizeweight')

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('NaverData', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sizeweight', sa.VARCHAR(length=100), nullable=False))
        batch_op.drop_column('sizewidth')

    # ### end Alembic commands ###
