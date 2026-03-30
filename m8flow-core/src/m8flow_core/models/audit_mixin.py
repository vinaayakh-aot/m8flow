from __future__ import annotations

from m8flow_core.db.registry import db


class AuditDateTimeMixin:  # pylint: disable=too-few-public-methods
    """Spiff-standard audit timestamps stored as epoch seconds.

    Any model inheriting this mixin and the configured base model will have these fields
    automatically set/updated by the SQLAlchemy listeners registered at startup.
    """

    created_at_in_seconds = db.Column(db.Integer, nullable=False)
    updated_at_in_seconds = db.Column(db.Integer, nullable=False)
