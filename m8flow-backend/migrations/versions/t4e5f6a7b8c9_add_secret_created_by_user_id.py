"""Add created_by_user_id to secret.

Revision ID: t4e5f6a7b8c9
Revises: s3d4e5f6a7b8
Create Date: 2026-08-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "t4e5f6a7b8c9"
down_revision = "s3d4e5f6a7b8"
branch_labels = None
depends_on = None

TABLE = "secret"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if "created_by_user_id" not in columns:
        op.add_column(
            TABLE,
            sa.Column("created_by_user_id", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column(TABLE, "created_by_user_id", server_default=None)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if "created_by_user_id" in columns:
        op.drop_column(TABLE, "created_by_user_id")
