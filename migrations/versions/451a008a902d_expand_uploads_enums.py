"""Expand uploads enums

Revision ID: 451a008a902d
Revises: c07a2f31a2c8
Create Date: 2025-10-11 00:27:15.979077

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '451a008a902d'
down_revision = 'c07a2f31a2c8'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE uploads MODIFY target_dir "
        "ENUM('uploads','proceed','checked','updates') NOT NULL DEFAULT 'proceed'"
    )
    op.execute(
        "ALTER TABLE uploads MODIFY status "
        "ENUM('draft','in_review','checked','approved','rejected') NOT NULL DEFAULT 'draft'"
    )


def downgrade():
    op.execute(
        "ALTER TABLE uploads MODIFY target_dir "
        "ENUM('uploads','proceed') NOT NULL DEFAULT 'proceed'"
    )
    op.execute(
        "ALTER TABLE uploads MODIFY status "
        "ENUM('draft','in_review') NOT NULL DEFAULT 'draft'"
    )
