"""empty message

Revision ID: 42d7452d27c4
Revises: e36e98e1b64e
Create Date: 2024-12-26 16:06:02.406677

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '42d7452d27c4'
down_revision = 'e36e98e1b64e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('_alembic_tmp_calendar_schedule')
    with op.batch_alter_table('calendar_schedule', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=False))
        batch_op.create_foreign_key(batch_op.f('fk_calendar_schedule_user_id_user_authorization'), 'user_authorization', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('refresh_token', schema=None) as batch_op:
        batch_op.drop_constraint('fk_refresh_token_user_id_user_authorization', type_='foreignkey')
        batch_op.create_foreign_key(batch_op.f('fk_refresh_token_user_id_user_authorization'), 'user_authorization', ['user_id'], ['id'], ondelete='CASCADE')

    with op.batch_alter_table('user_authorization', schema=None) as batch_op:
        batch_op.alter_column('password',
               existing_type=sa.VARCHAR(length=150),
               nullable=False)
        batch_op.create_unique_constraint(batch_op.f('uq_user_authorization_email'), ['email'])

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('user_authorization', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('uq_user_authorization_email'), type_='unique')
        batch_op.alter_column('password',
               existing_type=sa.VARCHAR(length=150),
               nullable=True)

    with op.batch_alter_table('refresh_token', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_refresh_token_user_id_user_authorization'), type_='foreignkey')
        batch_op.create_foreign_key('fk_refresh_token_user_id_user_authorization', 'user_authorization', ['user_id'], ['id'])

    with op.batch_alter_table('calendar_schedule', schema=None) as batch_op:
        batch_op.drop_constraint(batch_op.f('fk_calendar_schedule_user_id_user_authorization'), type_='foreignkey')
        batch_op.drop_column('user_id')

    op.create_table('_alembic_tmp_calendar_schedule',
    sa.Column('id', sa.INTEGER(), nullable=False),
    sa.Column('content', sa.VARCHAR(length=300), nullable=False),
    sa.Column('start_time', sa.VARCHAR(length=150), nullable=True),
    sa.Column('end_time', sa.VARCHAR(length=150), nullable=True),
    sa.Column('cal_date', sa.VARCHAR(length=150), nullable=True),
    sa.Column('create_date', sa.DATETIME(), nullable=False),
    sa.Column('modify_date', sa.DATETIME(), nullable=True),
    sa.Column('user_id', sa.INTEGER(), nullable=False),
    sa.ForeignKeyConstraint(['user_id'], ['user_authorization.id'], name='fk_calendar_schedule_user_id_user_authorization', ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id', name='pk_calendar_schedule')
    )
    # ### end Alembic commands ###
