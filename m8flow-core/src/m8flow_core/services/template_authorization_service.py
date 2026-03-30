from __future__ import annotations

from typing import Any

from flask import g
from sqlalchemy import or_, and_

from m8flow_core.models.template import TemplateModel, TemplateVisibility
from m8flow_core.adapters import get_authz_adapter


class TemplateAuthorizationService:
    """Visibility and edit rules for templates."""

    @staticmethod
    def _tenant_id() -> str | None:
        return getattr(g, "m8flow_tenant_id", None)

    @classmethod
    def can_view(cls, template: TemplateModel, user: Any | None = None) -> bool:
        # PUBLIC: anyone with auth context
        if template.is_public():
            return True

        # TENANT: must match tenant
        if template.is_tenant_visible():
            return cls._tenant_id() is not None and cls._tenant_id() == template.m8f_tenant_id

        # PRIVATE: must be creator and same tenant
        if template.is_private():
            return (
                user is not None
                and template.created_by == user.username
                and cls._tenant_id() is not None
                and cls._tenant_id() == template.m8f_tenant_id
            )
        return False

    @classmethod
    def can_edit(cls, template: TemplateModel, user: Any | None = None) -> bool:
        if user is None:
            return False

        # Owner can always edit
        if template.created_by == user.username:
            return True

        # Delegate to the configured authz adapter (spiff-arena or standalone)
        authz = get_authz_adapter()
        if authz is not None:
            try:
                return authz.user_has_permission(user, "update", "/templates")
            except Exception:
                return False

        return False

    @classmethod
    def filter_query_by_visibility(cls, query, user: Any | None = None):
        """Apply visibility filters for the current tenant/user."""
        tenant_id = cls._tenant_id()
        if tenant_id is None:
            return query.filter(TemplateModel.visibility == TemplateVisibility.public.value)

        conditions = [
            TemplateModel.visibility == TemplateVisibility.public.value,
            and_(
                TemplateModel.visibility == TemplateVisibility.tenant.value,
                TemplateModel.m8f_tenant_id == tenant_id,
            ),
        ]
        if user is not None:
            conditions.append(
                and_(
                    TemplateModel.visibility == TemplateVisibility.private.value,
                    TemplateModel.m8f_tenant_id == tenant_id,
                    TemplateModel.created_by == user.username,
                )
            )
        return query.filter(or_(*conditions))
