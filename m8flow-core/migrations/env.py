"""Alembic env for m8flow-core — runs standalone (no spiff-arena required).

To run:
    cd m8flow-core
    M8FLOW_BACKEND_DATABASE_URI=postgresql://... alembic -c migrations/alembic.ini upgrade head
"""
import logging
import os
import sys
from pathlib import Path

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.orm import DeclarativeBase

# Ensure m8flow_core src is importable when running Alembic directly.
MIGRATIONS_DIR = Path(__file__).resolve().parent
CORE_SRC_DIR = MIGRATIONS_DIR.parent / "src"
if str(CORE_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(CORE_SRC_DIR))


class _StandaloneBase(DeclarativeBase):
    pass


import m8flow_core

m8flow_core.configure_db(None, _StandaloneBase)

# Import all m8flow_core models to populate _StandaloneBase metadata.
import m8flow_core.models.audit_mixin  # noqa: F401
import m8flow_core.models.tenant_scoped  # noqa: F401
import m8flow_core.models.tenant  # noqa: F401
import m8flow_core.models.template  # noqa: F401
import m8flow_core.models.process_model_template  # noqa: F401
import m8flow_core.models.nats_token  # noqa: F401

config = context.config

# Do not call fileConfig — let calling process control logging.
for name in ("alembic", "alembic.runtime.migration"):
    lg = logging.getLogger(name)
    lg.handlers = []
    lg.propagate = True

target_metadata = _StandaloneBase.metadata


def get_url() -> str:
    url = os.environ.get("M8FLOW_BACKEND_DATABASE_URI") or os.environ.get("M8FLOW_DATABASE_URI")
    if not url:
        raise RuntimeError("Set M8FLOW_BACKEND_DATABASE_URI or M8FLOW_DATABASE_URI for Alembic.")
    return url


def run_migrations_online() -> None:
    connectable = engine_from_config(
        {"sqlalchemy.url": get_url()},
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table="alembic_version_m8flow",
            compare_type=True,
        )

        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
