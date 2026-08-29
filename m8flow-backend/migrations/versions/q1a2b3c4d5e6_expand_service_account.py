"""Expand service_account with name, hashed secret, and created-by.

Revision ID: q1a2b3c4d5e6
Revises: p9i0j1k2l3m4
Create Date: 2026-08-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "q1a2b3c4d5e6"
down_revision = "p9i0j1k2l3m4"
branch_labels = None
depends_on = None

TABLE = "service_account"


def _columns(table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table)}


def _unique_names(table: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    return {constraint["name"] for constraint in inspector.get_unique_constraints(table) if constraint["name"]}


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return
    columns = _columns(TABLE)
    if "client_id" not in columns:
        op.add_column(
            TABLE,
            sa.Column("client_id", sa.String(length=255), nullable=False, server_default=""),
        )
        op.alter_column(TABLE, "client_id", server_default=None)
    if "name" not in columns:
        op.add_column(
            TABLE,
            sa.Column("name", sa.String(length=255), nullable=False, server_default=""),
        )
        op.alter_column(TABLE, "name", server_default=None)
    if "secret_hash" not in columns:
        op.add_column(
            TABLE,
            sa.Column("secret_hash", sa.String(length=255), nullable=False, server_default=""),
        )
        op.alter_column(TABLE, "secret_hash", server_default=None)
    if "created_by_user_id" not in columns:
        op.add_column(
            TABLE,
            sa.Column("created_by_user_id", sa.Integer(), nullable=False, server_default="0"),
        )
        op.alter_column(TABLE, "created_by_user_id", server_default=None)

    uniques = _unique_names(TABLE)
    if "service_account_uniq" not in uniques:
        op.create_unique_constraint(
            "service_account_uniq",
            TABLE,
            ["m8f_tenant_id", "name", "created_by_user_id"],
        )
    if "uq_host_service_account_client_id" not in uniques:
        op.create_unique_constraint("uq_host_service_account_client_id", TABLE, ["client_id"])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return
    uniques = _unique_names(TABLE)
    if "uq_host_service_account_client_id" in uniques:
        op.drop_constraint("uq_host_service_account_client_id", TABLE, type_="unique")
    columns = _columns(TABLE)
    if "secret_hash" in columns:
        op.drop_column(TABLE, "secret_hash")
    # Leave name / created_by_user_id / service_account_uniq in place: they
    # predate this revision on overlay schemas, so dropping them here would
    # not restore that earlier shape.
