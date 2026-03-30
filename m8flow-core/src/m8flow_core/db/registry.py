"""
m8flow_core.db.registry — lazy db proxy and configuration.

Call configure_db() once during startup (before any model module is imported):

    from m8flow_core.db.registry import configure_db
    configure_db(real_db_instance, BaseModelClass)

All m8flow_core model files then import:

    from m8flow_core.db.registry import db
    from m8flow_core.db.registry import get_base_model

The _DbProxy resolves attribute access against the real db at mapper-init time,
matching the pattern used by Flask-SQLAlchemy itself.
"""
from __future__ import annotations

from typing import Any

from m8flow_core.exceptions import M8flowConfigurationError

_db: Any = None
_BaseModel: Any = None


class _DbProxy:
    """Lazy proxy to the configured SQLAlchemy db instance.

    Attribute access is forwarded to the real db after configure_db() is called.
    Safe to import at module level; resolution is deferred to mapper-init time.
    """

    def __getattr__(self, name: str) -> Any:
        if _db is None:
            # Standalone fallback (e.g. Alembic without Flask-SQLAlchemy): delegate to
            # sqlalchemy / sqlalchemy.orm so models can be imported for metadata discovery.
            import sqlalchemy as _sa
            import sqlalchemy.orm as _sa_orm
            for _mod in (_sa, _sa_orm):
                if hasattr(_mod, name):
                    return getattr(_mod, name)
            raise M8flowConfigurationError(
                f"m8flow_core db is not configured and {name!r} is not available from sqlalchemy. "
                "Call m8flow_core.configure_db(db, base_model) before importing models."
            )
        return getattr(_db, name)

    def __repr__(self) -> str:
        return f"<_DbProxy configured={_db is not None}>"


# Module-level singleton — safe to import early
db = _DbProxy()


def configure_db(real_db: Any, base_model: Any) -> None:
    """Configure the db instance and base model used by all m8flow_core models.

    Must be called before any m8flow_core model module is imported.

    Args:
        real_db: The SQLAlchemy db instance (Flask-SQLAlchemy or plain SQLAlchemy).
        base_model: The declarative base class models should inherit from.
                    For spiff-arena: SpiffworkflowBaseDBModel.
                    For standalone use: a plain DeclarativeBase subclass.
    """
    global _db, _BaseModel
    _db = real_db
    _BaseModel = base_model


def get_db() -> Any:
    """Return the configured db instance. Raises M8flowConfigurationError if not yet configured."""
    if _db is None:
        raise M8flowConfigurationError(
            "m8flow_core db is not configured. "
            "Call m8flow_core.configure_db(db, base_model) before importing models."
        )
    return _db


def get_base_model() -> Any:
    """Return the configured SQLAlchemy base model. Raises M8flowConfigurationError if not yet configured."""
    if _BaseModel is None:
        raise M8flowConfigurationError(
            "m8flow_core base model is not configured. "
            "Call m8flow_core.configure_db(db, base_model) before importing models."
        )
    return _BaseModel
