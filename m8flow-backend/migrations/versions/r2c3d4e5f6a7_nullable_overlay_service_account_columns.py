"""Allow rewrite service-account inserts without overlay user_id/api_key_hash.

Revision ID: r2c3d4e5f6a7
Revises: q1a2b3c4d5e6
Create Date: 2026-08-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "r2c3d4e5f6a7"
down_revision = "q1a2b3c4d5e6"
branch_labels = None
depends_on = None

TABLE = "service_account"


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return
    columns = {column["name"]: column for column in inspector.get_columns(TABLE)}
    if columns.get("user_id") is not None and not columns["user_id"].get("nullable", True):
        op.alter_column(TABLE, "user_id", existing_type=sa.Integer(), nullable=True)
    if columns.get("api_key_hash") is not None and not columns["api_key_hash"].get("nullable", True):
        op.alter_column(TABLE, "api_key_hash", existing_type=sa.String(length=255), nullable=True)


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    if "api_key_hash" in columns:
        op.alter_column(TABLE, "api_key_hash", existing_type=sa.String(length=255), nullable=False)
    if "user_id" in columns:
        op.alter_column(TABLE, "user_id", existing_type=sa.Integer(), nullable=False)
