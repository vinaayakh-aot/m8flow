from m8flow_core.db.registry import db


class TenantScoped:
    """Abstract marker for tenant-scoped models."""
    __abstract__ = True


class M8fTenantScopedMixin:
    """Mixin that adds a foreign key to m8flow_tenant for multi-tenant data isolation."""
    m8f_tenant_id = db.Column(db.String(255), db.ForeignKey("m8flow_tenant.id"), nullable=False, index=True)
