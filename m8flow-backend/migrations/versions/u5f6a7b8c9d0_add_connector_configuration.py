"""Add m8flow_connector_configuration and enable tenant RLS.

Revision ID: u5f6a7b8c9d0
Revises: t4e5f6a7b8c9
Create Date: 2026-08-30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "u5f6a7b8c9d0"
down_revision = "t4e5f6a7b8c9"
branch_labels = None
depends_on = None

TABLE = "m8flow_connector_configuration"
_TENANT_PREDICATE = "(m8f_tenant_id = current_setting('app.current_tenant', true))"
_BYPASS_PREDICATE = "(current_setting('app.bypass_rls', true) = 'on')"
_TENANT_POLICY = f"{TABLE}_tenant_isolation"
_BYPASS_POLICY = f"{TABLE}_super_admin_select"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("m8f_tenant_id", sa.String(length=255), nullable=False),
        sa.Column("connector_type", sa.String(length=50), nullable=False),
        sa.Column("profile_name", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("config_json", sa.JSON(), nullable=False),
        sa.Column("secret_refs", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_by_user_id", sa.Integer(), nullable=False),
        sa.Column("created_at_in_seconds", sa.Integer(), nullable=False),
        sa.Column("updated_at_in_seconds", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["m8f_tenant_id"], ["m8flow_tenant.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "m8f_tenant_id",
            "connector_type",
            "profile_name",
            name="uq_host_m8flow_connector_configuration_profile",
        ),
    )
    op.create_index(
        op.f("ix_host_m8flow_connector_configuration_m8f_tenant_id"),
        TABLE,
        ["m8f_tenant_id"],
        unique=False,
    )
    op.create_index(
        "ix_host_m8flow_connector_configuration_tenant_type",
        TABLE,
        ["m8f_tenant_id", "connector_type"],
        unique=False,
    )
    op.create_index(
        "ix_host_m8flow_connector_configuration_tenant_active",
        TABLE,
        ["m8f_tenant_id", "is_active"],
        unique=False,
    )

    if not _is_postgres():
        return
    op.execute(sa.text(f"ALTER TABLE {TABLE} ENABLE ROW LEVEL SECURITY"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS {_TENANT_POLICY} ON {TABLE}"))
    op.execute(
        sa.text(
            f"CREATE POLICY {_TENANT_POLICY} ON {TABLE} "
            f"FOR ALL USING {_TENANT_PREDICATE} WITH CHECK {_TENANT_PREDICATE}"
        )
    )
    op.execute(sa.text(f"DROP POLICY IF EXISTS {_BYPASS_POLICY} ON {TABLE}"))
    op.execute(
        sa.text(
            f"CREATE POLICY {_BYPASS_POLICY} ON {TABLE} "
            f"FOR SELECT USING {_BYPASS_PREDICATE}"
        )
    )


def downgrade() -> None:
    if _is_postgres():
        op.execute(sa.text(f"DROP POLICY IF EXISTS {_BYPASS_POLICY} ON {TABLE}"))
        op.execute(sa.text(f"DROP POLICY IF EXISTS {_TENANT_POLICY} ON {TABLE}"))
        op.execute(sa.text(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY"))
    op.drop_index("ix_host_m8flow_connector_configuration_tenant_active", table_name=TABLE)
    op.drop_index("ix_host_m8flow_connector_configuration_tenant_type", table_name=TABLE)
    op.drop_index(
        op.f("ix_host_m8flow_connector_configuration_m8f_tenant_id"), table_name=TABLE
    )
    op.drop_table(TABLE)
