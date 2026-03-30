from m8flow_core.models.tenant import M8flowTenantModel, TenantStatus
from m8flow_core.db.registry import get_db
from m8flow_core.adapters import get_error_factory


def _err(error_code: str, message: str, status_code: int) -> Exception:
    return get_error_factory()(error_code, message, status_code)


class TenantService:
    @staticmethod
    def _check_not_default_tenant(identifier: str):
        """Check that the given identifier is not 'default' to prevent operations on default tenant."""
        if identifier and identifier.lower() == "default":
            raise _err("forbidden_tenant", "Cannot perform operations on default tenant.", 403)

    @staticmethod
    def get_tenant_by_id(tenant_id: str):
        TenantService._check_not_default_tenant(tenant_id)
        tenant = M8flowTenantModel.query.filter_by(id=tenant_id).first()
        if not tenant:
            raise _err("tenant_not_found", f"Tenant with ID '{tenant_id}' not found.", 404)
        return tenant

    @staticmethod
    def check_tenant_exists(identifier: str) -> dict:
        """
        Check if an active tenant exists by slug or id. Unauthenticated; for pre-login tenant selection.
        Returns {"exists": True, "tenant_id": "..."} or {"exists": False}. Only considers ACTIVE tenants.
        """
        if not identifier or not identifier.strip():
            return {"exists": False}
        identifier = identifier.strip()
        db = get_db()
        tenant = (
            M8flowTenantModel.query.filter(
                M8flowTenantModel.status == TenantStatus.ACTIVE,
                db.or_(
                    M8flowTenantModel.slug == identifier,
                    M8flowTenantModel.id == identifier,
                ),
            )
            .first()
        )
        if tenant:
            return {"exists": True, "tenant_id": tenant.id}
        return {"exists": False}

    @staticmethod
    def get_tenant_by_slug(slug: str):
        TenantService._check_not_default_tenant(slug)
        tenant = M8flowTenantModel.query.filter_by(slug=slug).first()
        if not tenant:
            raise _err("tenant_not_found", f"Tenant with slug '{slug}' not found.", 404)
        return tenant

    @staticmethod
    def get_all_tenants():
        try:
            return M8flowTenantModel.query.filter(
                M8flowTenantModel.id != "default",
                M8flowTenantModel.slug != "default"
            ).all()
        except Exception as e:
            raise _err("database_error", f"Error fetching tenants: {str(e)}", 500)
