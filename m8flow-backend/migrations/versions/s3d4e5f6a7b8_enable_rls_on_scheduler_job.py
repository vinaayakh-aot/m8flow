"""Enable PostgreSQL RLS on scheduler_job.

The table was added after i2b3c4d5e6f7, so it never received the tenant
isolation + SELECT-only super-admin bypass policy pair every other
m8f_tenant_id table carries. Beat and workers already SET LOCAL
app.current_tenant; without these policies Postgres does not constrain
due-job rows.

Revision ID: s3d4e5f6a7b8
Revises: r2c3d4e5f6a7
Create Date: 2026-08-29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "s3d4e5f6a7b8"
down_revision = "r2c3d4e5f6a7"
branch_labels = None
depends_on = None

TABLE = "scheduler_job"
_TENANT_PREDICATE = "(m8f_tenant_id = current_setting('app.current_tenant', true))"
_BYPASS_PREDICATE = "(current_setting('app.bypass_rls', true) = 'on')"
_TENANT_POLICY = f"{TABLE}_tenant_isolation"
_BYPASS_POLICY = f"{TABLE}_super_admin_select"


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _table_ready() -> bool:
    inspector = sa.inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return False
    columns = {column["name"] for column in inspector.get_columns(TABLE)}
    return "m8f_tenant_id" in columns


def upgrade() -> None:
    if not _is_postgres() or not _table_ready():
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
    if not _is_postgres() or not _table_ready():
        return

    op.execute(sa.text(f"DROP POLICY IF EXISTS {_BYPASS_POLICY} ON {TABLE}"))
    op.execute(sa.text(f"DROP POLICY IF EXISTS {_TENANT_POLICY} ON {TABLE}"))
    op.execute(sa.text(f"ALTER TABLE {TABLE} DISABLE ROW LEVEL SECURITY"))
