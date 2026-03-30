from __future__ import annotations
from dataclasses import dataclass

from m8flow_core.db.registry import db, get_base_model
from m8flow_core.models.audit_mixin import AuditDateTimeMixin
from m8flow_core.models.tenant_scoped import M8fTenantScopedMixin, TenantScoped


@dataclass
class NatsTokenModel(M8fTenantScopedMixin, TenantScoped, get_base_model(), AuditDateTimeMixin):  # type: ignore[misc]
    """SQLAlchemy model for NATS tokens."""
    __tablename__ = "m8flow_nats_tokens"

    m8f_tenant_id: str = db.Column(
        db.String(255),
        db.ForeignKey("m8flow_tenant.id"),
        primary_key=True
    )
    token: str = db.Column(db.String(255), nullable=False, unique=True)
    created_by: str = db.Column(db.String(255), nullable=False)
    modified_by: str = db.Column(db.String(255), nullable=False)

    def __repr__(self):
        return f"<NatsTokenModel(tenant_id={self.m8f_tenant_id}, token={self.token})>"
