"""
m8flow_backend template service — extends m8flow_core.TemplateService with
spiff-arena-specific operations (ProcessModelService, SpecFileService, git commit).
"""
from __future__ import annotations

import logging
from typing import Any

from flask import g

from spiffworkflow_backend.exceptions.api_error import ApiError
from spiffworkflow_backend.models.db import db
from spiffworkflow_backend.models.process_model import ProcessModelInfo
from spiffworkflow_backend.models.user import UserModel
from spiffworkflow_backend.routes.process_api_blueprint import _commit_and_push_to_git
from spiffworkflow_backend.services.process_model_service import ProcessModelService
from spiffworkflow_backend.services.spec_file_service import SpecFileService

from m8flow_core.services.template_service import TemplateService as _CoreTemplateService
from m8flow_core.models.process_model_template import ProcessModelTemplateModel

# Re-export core constants so existing imports continue to work
from m8flow_core.services.template_service import (  # noqa: F401
    MAX_ZIP_SIZE,
    MAX_EXTRACTED_SIZE,
    MAX_ZIP_ENTRIES,
    UNIQUE_TEMPLATE_CONSTRAINT,
    TENANT_REQUIRED_MESSAGE,
)

logger = logging.getLogger(__name__)


class TemplateService(_CoreTemplateService):
    """Extends the core TemplateService with spiff-arena-specific process model creation."""

    @classmethod
    def create_process_model_from_template(
        cls,
        template_id: int,
        process_group_id: str,
        process_model_id: str,
        display_name: str,
        description: str | None,
        user: UserModel | None,
        tenant_id: str | None = None,
    ) -> dict[str, Any]:
        """Create a process model from a template, copying all files."""
        if user is None:
            raise ApiError("unauthorized", "User must be authenticated", status_code=403)

        tenant = tenant_id or getattr(g, "m8flow_tenant_id", None)
        if tenant is None:
            raise ApiError("tenant_required", TENANT_REQUIRED_MESSAGE, status_code=400)

        template = cls.get_template_by_id(template_id, user=user)
        if template is None:
            raise ApiError("not_found", "Template not found", status_code=404)

        if not template.files:
            raise ApiError("invalid_template", "Template has no files", status_code=400)

        full_process_model_id = f"{process_group_id}/{process_model_id}"

        if not ProcessModelService.is_process_group_identifier(process_group_id):
            raise ApiError(
                "process_group_not_found",
                f"Process group '{process_group_id}' does not exist",
                status_code=404,
            )

        if ProcessModelService.is_process_model_identifier(full_process_model_id):
            raise ApiError(
                "process_model_exists",
                f"Process model '{full_process_model_id}' already exists",
                status_code=409,
            )

        if ProcessModelService.is_process_group_identifier(full_process_model_id):
            raise ApiError(
                "process_group_exists",
                f"A process group with ID '{full_process_model_id}' already exists",
                status_code=409,
            )

        process_model_info = ProcessModelInfo(
            id=full_process_model_id,
            display_name=display_name,
            description=description or "",
        )
        ProcessModelService.add_process_model(process_model_info)

        primary_file_name = None
        primary_process_id = None
        files_copied = 0
        decision_id_map: dict[str, str] = {}

        logger.info(
            "Copying %d files from template %d to process model %s",
            len(template.files), template_id, full_process_model_id,
        )

        dmn_entries = [e for e in template.files if e.get("file_type") == "dmn"]
        other_entries = [e for e in template.files if e.get("file_type") != "dmn"]

        for file_entry in dmn_entries + other_entries:
            file_name = file_entry.get("file_name")
            file_type = file_entry.get("file_type")
            if not file_name:
                continue

            try:
                content = cls.get_file_content(template, file_name)
            except ApiError as e:
                raise ApiError(
                    "file_copy_failed",
                    f"Failed to copy file '{file_name}' from template: {e.message}",
                    status_code=500,
                )
            except Exception as e:
                raise ApiError(
                    "file_copy_failed",
                    f"Failed to copy file '{file_name}' from template: {str(e)}",
                    status_code=500,
                )

            if file_type == "dmn":
                content, file_decision_map = cls._transform_dmn_content(content, process_model_id)
                decision_id_map.update(file_decision_map)
            elif file_type == "bpmn":
                content, new_process_id = cls._transform_bpmn_content(
                    content, process_model_id, decision_id_map=decision_id_map or None
                )
                if primary_file_name is None:
                    primary_file_name = file_name
                    primary_process_id = new_process_id

            try:
                SpecFileService.update_file(process_model_info, file_name, content)
                files_copied += 1
            except Exception as e:
                raise ApiError(
                    "file_write_failed",
                    f"Failed to write file '{file_name}' to process model: {str(e)}",
                    status_code=500,
                )

        if files_copied == 0:
            raise ApiError("no_files_copied", "No files could be copied from the template", status_code=500)

        if primary_file_name:
            process_model_info.primary_file_name = primary_file_name
        if primary_process_id:
            process_model_info.primary_process_id = primary_process_id
        ProcessModelService.save_process_model(process_model_info)

        username = user.username if hasattr(user, "username") else "unknown"
        provenance = ProcessModelTemplateModel(
            process_model_identifier=full_process_model_id,
            source_template_id=template.id,
            source_template_key=template.template_key,
            source_template_version=template.version,
            source_template_name=template.name,
            m8f_tenant_id=tenant,
            created_by=username,
        )
        db.session.add(provenance)
        ProcessModelTemplateModel.commit_with_rollback_on_exception()

        _commit_and_push_to_git(
            f"User: {username} created process model {full_process_model_id} "
            f"from template {template.template_key} v{template.version}"
        )

        return {
            "process_model": process_model_info.to_dict(),
            "template_info": provenance.serialized(),
        }
