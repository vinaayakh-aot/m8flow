"""Drop duplicate and redundant secondary indexes.

Revision ID: v6g7h8i9j0k1
Revises: u5f6a7b8c9d0
Create Date: 2026-08-31

True duplicates (same columns as a PK or unique constraint) and secondary
indexes covered by a unique index's leftmost prefix. Does not drop PKs,
unique constraints that are the only uniqueness rule, or list/filter
indexes that are unused only because local tables are still small
(Postgres prefers a seq scan).
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "v6g7h8i9j0k1"
down_revision = "u5f6a7b8c9d0"
branch_labels = None
depends_on = None

# Secondary indexes: duplicates of a PK/unique, or covered by a unique prefix.
# Do not drop UNIQUE constraints that duplicate a PK — FKs may depend on them
# (task.guid is referenced by human_task / future_task).
_DROP_INDEXES = (
    ("ix_task_guid", "task"),
    ("ix_m8flow_tenant_slug", "m8flow_tenant"),
    ("ix_m8flow_tenant_invitation_token_hash", "m8flow_tenant_invitation"),
    ("ix_permission_target_uri", "permission_target"),
    ("ix_permission_target_command", "permission_target"),
    ("ix_permission_assignment_principal_id", "permission_assignment"),
    ("ix_user_service", "user"),
    ("ix_user_service_id", "user"),
    ("ix_user_email", "user"),
    ("ix_group_name", "group"),
    ("ix_group_source_is_open_id", "group"),
)

_RESTORE_INDEXES = (
    ("ix_task_guid", "task", ["guid"], True),
    ("ix_m8flow_tenant_slug", "m8flow_tenant", ["slug"], False),
    ("ix_m8flow_tenant_invitation_token_hash", "m8flow_tenant_invitation", ["token_hash"], False),
    ("ix_permission_target_uri", "permission_target", ["uri"], False),
    ("ix_permission_target_command", "permission_target", ["command"], False),
    ("ix_permission_assignment_principal_id", "permission_assignment", ["principal_id"], False),
    ("ix_user_service", "user", ["service"], False),
    ("ix_user_service_id", "user", ["service_id"], False),
    ("ix_user_email", "user", ["email"], False),
    ("ix_group_name", "group", ["name"], False),
    ("ix_group_source_is_open_id", "group", ["source_is_open_id"], False),
)


def _inspector():
    return sa.inspect(op.get_bind())


def _index_exists(table: str, index_name: str) -> bool:
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(table))


def upgrade() -> None:
    for index_name, table in _DROP_INDEXES:
        if _index_exists(table, index_name):
            op.drop_index(index_name, table_name=table)


def downgrade() -> None:
    for index_name, table, columns, unique in _RESTORE_INDEXES:
        if not _index_exists(table, index_name):
            op.create_index(index_name, table, columns, unique=unique)
