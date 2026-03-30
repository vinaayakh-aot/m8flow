from __future__ import annotations

import enum
from dataclasses import dataclass

from m8flow_core.db.registry import db, get_base_model
from m8flow_core.models.audit_mixin import AuditDateTimeMixin


class TenantStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    DELETED = "DELETED"


@dataclass
class M8flowTenantModel(get_base_model(), AuditDateTimeMixin):  # type: ignore[misc]
    """SQLAlchemy model for M8flowTenantModel."""
    __tablename__ = "m8flow_tenant"

    id: str = db.Column(db.String(255), primary_key=True)
    name: str = db.Column(db.String(255), nullable=False)
    slug: str = db.Column(db.String(255), unique=True, index=True, nullable=False)
    status: TenantStatus = db.Column(
        db.Enum(TenantStatus), default=TenantStatus.ACTIVE, nullable=False
    )
    created_by: str | None = db.Column(db.String(255), nullable=False)
    modified_by: str | None = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<M8flowTenantModel(name={self.name}, slug={self.slug}, status={self.status})>"
