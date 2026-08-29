from __future__ import annotations

import logging
import os

from alembic import context
from sqlalchemy import engine_from_config, pool

from m8flow_backend.db import alembic_target_metadata

config = context.config
target_metadata = alembic_target_metadata()

for name in ("alembic", "alembic.runtime.migration"):
    lg = logging.getLogger(name)
    lg.handlers = []
    lg.propagate = True


def get_url():
    url = os.environ.get("M8FLOW_BACKEND_DATABASE_URI") or os.environ.get("M8FLOW_DATABASE_URI")
    if not url:
        raise RuntimeError("Set M8FLOW_BACKEND_DATABASE_URI or M8FLOW_DATABASE_URI for Alembic.")
    return url


def run_migrations_online():
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
