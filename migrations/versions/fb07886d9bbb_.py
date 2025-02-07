"""empty message

Revision ID: fb07886d9bbb
Revises: fe5547c381c2
Create Date: 2024-12-26 15:39:10.656385

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fb07886d9bbb'
down_revision = 'fe5547c381c2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('calendar_schedule', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(batch_op.f('fk_calendar_schedule_user_id_user_authorization'), 'user_authorization', ['user_id'], ['id'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('calendar_schedule', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_calendar_schedule_user_id_user_authorization'), type_='foreignkey')
        batch_op.drop_column('user_id')

    # ### end Alembic commands ###
